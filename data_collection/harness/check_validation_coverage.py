from pathlib import Path
from typing import List, Tuple
from datasets import load_from_disk

import docker
import json
import resource
import traceback
from typing import Any

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tqdm import tqdm

from harness.constants import (
    INSTANCE_IMAGE_BUILD_DIR,
    RUN_EVALUATION_LOG_DIR,
)
from harness.docker_utils import (
    remove_image,
    copy_to_container,
    exec_run_with_timeout,
    cleanup_container,
    list_images,
    should_remove,
    clean_images,
    copy_from_container
)
from harness.docker_build import (
    BuildImageError,
    build_container,
    build_env_images,
    close_logger,
    setup_logger,
)
from harness.test_spec import make_test_spec, TestSpec
from harness.utils import str2bool

from functools import partial
from xml.etree import ElementTree as ET



def extract_changed_lines_from_patch(patch_text: str) -> List[Tuple[str, List[int]]]:
    """
    Extract modified files and their changed line numbers from a unified diff patch.

    Args:
        patch_text (str): The text of the patch.

    Returns:
        List of tuples: [(filename, [line numbers])]
    """
    changed = []
    current_file = None
    current_lines = []

    for line in patch_text.splitlines():
        if line.startswith('+++ b/'):
            # Save the previous file if applicable
            if current_file and current_lines:
                changed.append((current_file, current_lines))
            current_file = line[6:]  # Extract file path after '+++ b/'
            current_lines = []
        elif line.startswith('@@'):
            # Example: @@ -23,6 +23,8 @@
            plus_section = line.split(' ')[1]  # Get "+23,8"
            start_line = int(plus_section.split(',')[0][1:])
            line_count = int(plus_section.split(',')[1]) if ',' in plus_section else 1
            current_lines.extend(range(start_line, start_line + line_count))

    # Add the last file
    if current_file and current_lines:
        changed.append((current_file, current_lines))

    return changed

def get_executed_lines(xml_path: str) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    base_path = root.findtext("./sources/source", default="").strip()
    base_path = base_path.strip("/").split("/")
    if len(base_path) > 1:
        base_path = "/".join(base_path[1:]) + "/"
    else:
        base_path = ""

    executed_lines = {}
    for class_tag in root.findall(".//class"):
        filename = class_tag.attrib['filename']
        lines = class_tag.findall(".//line")
        covered_lines = {int(line.attrib['number']) for line in lines if int(line.attrib['hits']) > 0}
        executed_lines[base_path+filename] = covered_lines
    return executed_lines


class EvaluationError(Exception):
    def __init__(self, instance_id, message, logger):
        super().__init__(message)
        self.super_str = super().__str__()
        self.instance_id = instance_id
        self.log_file = logger.log_file
        self.logger = logger

    def __str__(self):
        return (
            f"Evaluation error for {self.instance_id}: {self.super_str}\n"
            f"Check ({self.log_file}) for more information."
        )


def run_instance(
        test_spec: TestSpec,
        rm_image: bool,
        force_rebuild: bool,
        client: docker.DockerClient,
        run_id: str,
        timeout: int = None,
    ):
    """
    Run a single instance

    Args:
        test_spec (TestSpec): TestSpec instance
        rm_image (bool): Whether to remove the image after running
        force_rebuild (bool): Whether to force rebuild the image
        client (docker.DockerClient): Docker client
        run_id (str): Run ID
        timeout (int): Timeout for running tests
    """
    # Set up logging directory
    instance_id = test_spec.instance_id
    commit_id = test_spec.base_commit
    log_dir = RUN_EVALUATION_LOG_DIR / run_id / test_spec.repo.replace("/", "__") / test_spec.instance_id
    log_dir.mkdir(parents=True, exist_ok=True)

    # Link the image build dir in the log dir
    build_dir = INSTANCE_IMAGE_BUILD_DIR / test_spec.instance_image_key.replace(":", "__")
    image_build_link = log_dir / "image_build_dir"
    if not image_build_link.exists():
        try:
            # link the image build dir in the log dir
            image_build_link.symlink_to(build_dir.absolute(), target_is_directory=True)
        except:
            # some error, idk why
            pass
    log_file = log_dir / "run_instance.log"

    # Set up report file + logger
    report_path = log_dir / "report.json"
    if report_path.exists():
        return commit_id, json.loads(report_path.read_text())
    logger = setup_logger(commit_id, log_file)

    # Run the instance
    container = None
    try:
        # Build + start instance container (instance image should already be built)
        container = build_container(test_spec, client, run_id, logger, rm_image, force_rebuild)
        container.start()
        logger.info(f"Container for {commit_id} started: {container.id}")

        eval_file = Path(log_dir / "eval.sh")
        logger.info(f"Eval script coverage {test_spec.eval_script_coverage}")
        eval_file.write_text(test_spec.eval_script_coverage)
        logger.info(
            f"Eval script for {commit_id} written to {eval_file}; copying to container..."
        )
        copy_to_container(container, eval_file, Path("/eval.sh"))

        # Run eval script, write output to logs
        test_output_path = log_dir / "test_output.txt"
        logger.info(f"Test output for {commit_id} written to {test_output_path}")
        test_output, timed_out, total_runtime = exec_run_with_timeout(container, f"/bin/bash -c 'set +e; source /eval.sh || true'", timeout, test_output_path)
        # Copy coverage report from container to host
        for idx, _ in enumerate(test_spec.efficiency_test):
            local_path = log_dir / f"coverage_test{idx}.xml"
            container_path = f"/tmp/coverage_test{idx}.xml"
            try:
                copy_from_container(container, container_path, local_path)
            except:
                continue

        logger.info(f'Test runtime: {total_runtime:_.2f} seconds')
        if timed_out:
            print(
                commit_id,
                f"Test timed out after {timeout} seconds.",
                logger,
            )

        # Get report for coverage
        logger.info(f"Grading answer for {commit_id}...")
        patch = test_spec.patch
        logger.info(f"[patch]:\n{patch}\n")
        test_patch = test_spec.test_patch
        logger.info(f"[test_patch]:\n{test_patch}\n")
        changed = extract_changed_lines_from_patch(patch)
        logger.info(f"Changed files and lines: {changed}")
        test_changed = extract_changed_lines_from_patch(test_patch)
        logger.info(f"Changed test files and lines: {test_changed}")
        coverage = {}
        for idx, test in enumerate(test_spec.efficiency_test):
            coverage_path = log_dir / f"coverage_test{idx}.xml"
            if not coverage_path.exists():
                coverage[test] = False
                continue
            executed = get_executed_lines(coverage_path)
            logger.info(f"Executed lines for {test}: {executed}")
            for file, lines in test_changed: # test can't be changed
                covered = executed.get(file, set())
                logger.info(f"Checking coverage for {test} in {file} with test lines {lines} and covered lines {covered}")
                overlap = set(lines) & covered
                if overlap:
                    coverage[test] = False
                    break
            else:
                for file, lines in changed: # patch must be changed
                    covered = executed.get(file, set())
                    logger.info(f"Checking coverage for {test} in {file} with lines {lines} and covered lines {covered}")
                    overlap = set(lines) & covered
                    if overlap:
                        coverage[test] = True
                        break
                else:
                    coverage[test] = False
        logger.info(
            f"report: {coverage}\n"
            f"Result for {len(coverage)}: cover: {sum(coverage.values())}, "
            f"miss: {len(coverage) - sum(coverage.values())}"
        )

        # Write report to report.json
        with open(report_path, "w") as f:
            f.write(json.dumps(coverage, indent=4))
        return commit_id, coverage
    except EvaluationError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except BuildImageError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except Exception as e:
        error_msg = (f"Error in evaluating model for {commit_id}: {e}\n"
                     f"{traceback.format_exc()}\n"
                     f"Check ({logger.log_file}) for more information.")
        logger.error(error_msg)
    finally:
        # Remove instance container + image, close logger
        cleanup_container(client, container, logger)
        if rm_image:
            remove_image(client, test_spec.instance_image_key, logger)
        close_logger(logger)
    return


def run_instances(
        instances: list,
        cache_level: str,
        clean: bool,
        force_rebuild: bool,
        max_workers: int,
        run_id: str,
        timeout: int,
    ):
    """
    Run all instances for the given predictions in parallel.

    Args:
        instances (list): List of instances
        cache_level (str): Cache level
        clean (bool): Clean images above cache level
        force_rebuild (bool): Force rebuild images
        max_workers (int): Maximum number of workers
        run_id (str): Run ID
        timeout (int): Timeout for running tests
    """
    client = docker.from_env()
    func = partial(make_test_spec, is_eval=True)
    test_specs = list(map(func, instances))

    # print number of existing instance images
    instance_image_ids = {x.instance_image_key for x in test_specs}
    existing_images = {
        tag for i in client.images.list(all=True)
        for tag in i.tags if tag in instance_image_ids
    }
    if not force_rebuild and len(existing_images):
        print(f"Found {len(existing_images)} existing instance images. Will reuse them.")

    # run instances in parallel
    print(f"Running {len(instances)} instances...")
    with tqdm(total=len(instances), smoothing=0) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create a future for running each instance
            futures = {
                executor.submit(
                    run_instance,
                    test_spec,
                    should_remove(
                        test_spec.instance_image_key,
                        cache_level,
                        clean,
                        existing_images,
                    ),
                    force_rebuild,
                    client,
                    run_id,
                    timeout,
                ): None
                for test_spec in test_specs
            }
            # Wait for each future to complete
            for future in as_completed(futures):
                pbar.update(1)
                try:
                    # Update progress bar, check if instance ran successfully
                    future.result()
                except Exception as e:
                    traceback.print_exc()
                    continue
    print("All instances run.")

def delete_instance_container(client, dataset):
    instance_ids = [dp['instance_id'] for dp in dataset]
    container_names = set([f"sweb.eval.{instance_id}.test" for instance_id in instance_ids])
    container_list = client.containers.list(all=True)
    for container in container_list:
        if container.name in container_names:
            container.remove(force=True)


def main(
        dataset_name: str,
        split: str,
        instance_ids: list,
        max_workers: int,
        force_rebuild: bool,
        cache_level: str,
        clean: bool,
        open_file_limit: int,
        run_id: str,
        timeout: int,
        previous_run_id: str,
    ):
    """
    Run evaluation harness for the given dataset and predictions.
    """
    # set open file limit
    assert len(run_id) > 0, "Run ID must be provided"
    resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))
    client = docker.from_env()

    # get dataset from predictions
    dataset = load_from_disk(dataset_name)
    # check which instance IDs have already been run
    completed_ids = set()
    for instance in dataset:
        report_file = (
            RUN_EVALUATION_LOG_DIR
            / run_id
            / instance["repo"].replace("/", "__")
            / instance["instance_id"]
            / "report.json"
        )
        if report_file.exists():
            completed_ids.add(instance["base_commit"])

    if completed_ids:
        # filter dataset to only instances that have not been run
        print(f"{len(completed_ids)} instances already run, skipping...")
        dataset = [i for i in dataset if i['base_commit'] not in completed_ids]
    existing_images = list_images(client)
    delete_instance_container(client, dataset)
    print(f"Running {len(dataset)} unevaluated instances...")
    if not dataset:
        print("No instances to run.")
    else:
        # build environment images + run instances
        build_env_images(client, dataset, force_rebuild, max_workers)
        # this time w/ golden predictions (patch)
        run_instances(dataset, cache_level, clean, force_rebuild, max_workers, run_id, timeout)

    clean_images(client, existing_images, cache_level, clean)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--dataset_name", type=str, help="Name of dataset or path to JSON file.")
    parser.add_argument("--split", type=str, default="test", help="Split of the dataset")
    parser.add_argument("--instance_ids", nargs="+", type=str, help="Instance IDs to run (space separated)")
    parser.add_argument("--max_workers", type=int, default=4, help="Maximum number of workers (should be <= 75%% of CPU cores)")
    parser.add_argument("--open_file_limit", type=int, default=4096, help="Open file limit")
    parser.add_argument(
        "--timeout", type=int, default=7_200, help="Timeout (in seconds) for running tests for each instance"
        )
    parser.add_argument(
        "--force_rebuild", type=str2bool, default=False, help="Force rebuild of all images"
    )
    parser.add_argument(
        "--cache_level",
        type=str,
        choices=["none", "base", "env", "instance"],
        help="Cache level - remove images above this level",
        default="env",
    )
    # if clean is true then we remove all images that are above the cache level
    # if clean is false, we only remove images above the cache level if they don't already exist
    parser.add_argument(
        "--clean", type=str2bool, default=False, help="Clean images above cache level"
    )
    parser.add_argument("--run_id", type=str, required=True, help="Run ID - identifies the run")
    parser.add_argument("--previous_run_id", type=str, default=None, help = "This run follow the previous run.")
    args = parser.parse_args()
    main(**vars(args))

