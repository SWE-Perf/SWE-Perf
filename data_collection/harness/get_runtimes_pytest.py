# inspired by run_validation.py
from __future__ import annotations

import docker
import json
import resource
import traceback
from typing import Any

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tqdm import tqdm
from copy import copy
import os

from harness.constants import (
    INSTANCE_IMAGE_BUILD_DIR,
    KEY_INSTANCE_ID,
    RUN_EVALUATION_LOG_DIR,
    MAP_REPO_VERSION_TO_SPECS
)
from harness.docker_utils import (
    remove_image,
    copy_to_container,
    exec_run_with_timeout,
    cleanup_container,
    list_images,
    should_remove,
    clean_images,
)
from harness.docker_build import (
    BuildImageError,
    build_container,
    build_env_images,
    close_logger,
    setup_logger,
)
from harness.test_spec import make_test_spec, TestSpec
from harness.utils import load_sweperf_dataset, str2bool
from harness.grading import get_logs_eval


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

def get_validation_report(
    test_spec: TestSpec,
    log_path: str,
    include_tests_status: bool,
) -> dict[str, Any]:
    """
    Generate a report of model evaluation results from a prediction, task instance,
    and evaluation log.

    Args:
        test_spec (dict): test spec containing keys "instance_id", "FAIL_TO_PASS", and "PASS_TO_PASS"
        log_path (str): path to evaluation log
        include_tests_status (bool): whether to include the status of each test in the returned report
    Returns:
        report (dict): report of metrics
    """
    report_map = {}

    commit_id = test_spec.base_commit

    report_map[commit_id] = {
            # "patch_is_None": False,
            # "patch_exists": False,
            # "patch_successfully_applied": False,
            "resolved": False,
        }

    # Check if the model patch exists
    # if prediction["model_patch"] is None:
    #     report_map[instance_id]["none"] = True
    #     return report_map
    # report_map[instance_id]["patch_exists"] = True

    # Get evaluation logs
    eval_sm, found = get_logs_eval(log_path, test_spec.repo)

    if not found:
        return report_map
    # report_map[instance_id]["patch_successfully_applied"] = True

    from harness.constants import TestStatus
    report = {
        "PASS": [k for k, v in eval_sm.items() if v == TestStatus.PASSED.value],
        "FAIL": [k for k, v in eval_sm.items() if v == TestStatus.FAILED.value],
    }
    if len(report["FAIL"]) == 0 and len(report["PASS"]) > 0:
        report_map[commit_id]["resolved"] = True

    if include_tests_status:
        report_map[commit_id]["tests_status"] = report  # type: ignore
    
    return report_map


def run_instance(
        test_spec: TestSpec,
        rm_image: bool,
        force_rebuild: bool,
        client: docker.DockerClient,
        run_id: str,
        timeout: int | None = None,
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
    log_dir = RUN_EVALUATION_LOG_DIR / run_id / test_spec.repo.replace("/", "__") / test_spec.base_commit
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

        # # Copy model prediction as patch file to container
        # patch_file = Path(log_dir / "patch.diff")
        # patch_file.write_text(pred["model_patch"] or "")
        # logger.info(
        #     f"Intermediate patch for {instance_id} written to {patch_file}, now applying to container..."
        # )
        # copy_to_container(container, patch_file, Path("/tmp/patch.diff"))

        # # Attempt to apply patch to container
        # val = container.exec_run(
        #     "git apply --allow-empty -v /tmp/patch.diff",
        #     workdir="/testbed",
        #     user="root",
        # )
        # if val.exit_code != 0:
        #     logger.info(f"Failed to apply patch to container, trying again...")
            
        #     # try "patch --batch --fuzz=5 -p1 -i {patch_path}" to try again
        #     val = container.exec_run(
        #         "patch --batch --fuzz=5 -p1 -i /tmp/patch.diff",
        #         workdir="/testbed",
        #         user="root",
        #     )
        #     if val.exit_code != 0:
        #         logger.info(f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}")
        #         raise EvaluationError(
        #             instance_id,
        #             f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}",
        #             logger,
        #         )
        #     else:
        #         logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")
        # else:
        #     logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")

        # # Get git diff before running eval script
        # git_diff_output_before = (
        #     container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()
        # )
        # logger.info(f"Git diff before:\n{git_diff_output_before}")

        eval_file = Path(log_dir / "eval.sh")
        eval_file.write_text(test_spec.eval_script_alltests)
        # eval_file.write_text(test_spec.eval_script)
        logger.info(
            f"Eval script for {commit_id} written to {eval_file}; copying to container..."
        )
        copy_to_container(container, eval_file, Path("/eval.sh"))

        # Run eval script, write output to logs
        test_output_path = log_dir / "test_output.txt"
        logger.info(f"Test output for {commit_id} written to {test_output_path}")
        test_output, timed_out, total_runtime = exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout, test_output_path)
        logger.info(f'Test runtime: {total_runtime:_.2f} seconds')
        if timed_out:
            raise EvaluationError(
                commit_id,
                f"Test timed out after {timeout} seconds.",
                logger,
            )

        # Get git diff after running eval script
        # git_diff_output_after = (
        #     container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()
        # )

        # Check if git diff changed after running eval script
        # logger.info(f"Git diff after:\n{git_diff_output_after}")
        # if git_diff_output_after != git_diff_output_before:
        #     logger.info(f"Git diff changed after running eval script")

        # Get report from test output
        logger.info(f"Grading answer for {commit_id}...")
        report = get_validation_report(
            test_spec=test_spec,
            log_path=test_output_path,
            include_tests_status=True,
        )
        logger.info(
            f"report: {report}\n"
            f"Result for {commit_id}: resolved: {report[commit_id]['resolved']}"
        )

        # Write report to report.json
        with open(report_path, "w") as f:
            f.write(json.dumps(report, indent=4))
        return commit_id, report
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
    test_specs = list(map(make_test_spec, instances))

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


def get_dataset_from_commit(
        dataset_name: str,
        split: str,
        instance_ids: list,
        run_id: str,
        exclude_completed: bool = True,
        previous_run_id: str = None
    ):
    """
    Return only instances with unique commit and are in the dataset.
    If instance_ids is provided, only return instances with those IDs.
    If exclude_completed is True, only return instances that have not been run yet.
    Note: in this version, we will still keep the data point even if the patch is empty.
    """
    # load dataset
    dataset = load_sweperf_dataset(dataset_name, split)
    # construct fake dataset for unique base and head commit
    dataset_fake = []
    commit_id = set()
    for data in dataset:
        if data["base_commit"] not in commit_id:
            dataset_fake.append(data)
            commit_id.add(data["base_commit"])
        if data["head_commit"] not in commit_id:
            data_new = copy(data)
            data_new['base_commit'] = data["head_commit"]
            data_new['version'] = data["version_head"]
            dataset_fake.append(data_new)
            commit_id.add(data_new['head_commit'])
    print(f"There are {len(dataset_fake)} unique commit for dataset ({len(dataset)} samples).")
    dataset = []
    new_versions = []
    for data in dataset_fake:
        if data["version"] in MAP_REPO_VERSION_TO_SPECS[data["repo"]]:
            dataset.append(data)
        else:
            new_versions.append(data["version"])
    print(f"There are {len(dataset)} commits with version, and the undefined versions are {set(new_versions)}")

    dataset_commit_ids = {i["base_commit"] for i in dataset_fake}

    if instance_ids:
        # check that all instance IDs are in the dataset
        instance_ids = set(instance_ids)
        if instance_ids - dataset_commit_ids:
            raise ValueError(
                (
                    "Some instance IDs not found in dataset!"
                    f"\nMissing IDs:\n{' '.join(instance_ids - dataset_commit_ids)}"
                )
            )

    if instance_ids:
        # filter dataset to just the instance IDs
        dataset = [i for i in dataset if i[KEY_INSTANCE_ID] in instance_ids]

    # check which instance IDs have already been run
    completed_ids = set()
    for instance in dataset:
        report_file = (
            RUN_EVALUATION_LOG_DIR
            / run_id
            / instance["repo"].replace("/", "__")
            / instance["base_commit"]
            / "report.json"
        )
        if report_file.exists():
            completed_ids.add(instance["base_commit"])

    if completed_ids and exclude_completed:
        # filter dataset to only instances that have not been run
        print(f"{len(completed_ids)} instances already run, skipping...")
        dataset = [i for i in dataset if i['base_commit'] not in completed_ids]

    # check previous complete IDs
    previous_success_ids = set()
    if previous_run_id != None:
        print(f"Checking previous run {previous_run_id} for completed instances...")
        for instance in dataset:
            report_file = (
                RUN_EVALUATION_LOG_DIR
                / previous_run_id
                / instance["repo"].replace("/", "__")
                / instance["base_commit"]
                / "report.json"
            )
            if os.path.exists(report_file):
                previous_success_ids.add(instance["base_commit"])

        # filter dataset to only instances that have not been run
        print(f"{len(previous_success_ids)} instances success run in {previous_run_id}, skipping...")
        dataset = [i for i in dataset if i['base_commit'] in previous_success_ids]
    return dataset


def get_gold_predictions(dataset_name: str, split: str):
    """
    Get gold predictions for the given dataset and split.
    """
    dataset = load_sweperf_dataset(dataset_name, split)
    return [
        {
            KEY_INSTANCE_ID: datum[KEY_INSTANCE_ID],
            "model_patch": datum["patch"],
            "model_name_or_path": "gold",
        } for datum in dataset
    ]

def get_empty_predictions(dataset_name: str, split: str):
    """
    Get empty predictions for the given dataset and split.
    """
    dataset = load_sweperf_dataset(dataset_name, split)
    return [
        {
            KEY_INSTANCE_ID: datum[KEY_INSTANCE_ID],
            "model_patch": "",
            "model_name_or_path": "empty",
        } for datum in dataset
    ]

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

    # load predictions as map of instance_id to prediction
    # print("Using gold predictions - ignoring predictions_path")
    # predictions = get_gold_predictions(dataset_name, split)
    # predictions = {pred[KEY_INSTANCE_ID]: pred for pred in predictions}

    # get dataset from predictions
    dataset = get_dataset_from_commit(dataset_name, split, instance_ids, run_id, previous_run_id = previous_run_id)
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

    # # --- run empty predictions ---
    # print("Using empty predictions")
    # empty_predictions = get_empty_predictions(dataset_name, split)
    # empty_predictions = {pred[KEY_INSTANCE_ID]: pred for pred in empty_predictions}
    # empty_dataset = get_dataset_from_preds(dataset_name, split, instance_ids, empty_predictions, run_id)

    # this will remove the container in the gloden run
    # delete_instance_container(client, empty_dataset)
    # run_instances(empty_predictions, empty_dataset, cache_level, clean, force_rebuild, max_workers, run_id, timeout)

    # clean images + make final report
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
