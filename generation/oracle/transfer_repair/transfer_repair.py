# Inspired by the original Agentless codebase
from datasets import load_from_disk
from argparse import ArgumentParser
import jsonlines
import json
from difflib import unified_diff
import os
import logging

from transfer_repair.postprocess_data import (
    check_code_differ_by_just_empty_lines,
    check_syntax,
    extract_python_blocks,
    fake_git_repo,
    lint_code,
    parse_diff_edit_commands,
    parse_edit_commands,
    parse_str_replace_edit_commands,
    split_edit_multifile_commands,
)


def _post_process_multifile_repair(
    raw_output: str,
    file_contents: dict[str, str],
    logger,
    diff_format=False,
    str_replace_format=False,
) -> tuple[list[str], list[str]]:
    if not str_replace_format:
        edit_multifile_commands = extract_python_blocks(raw_output)
    else:
        edit_multifile_commands = raw_output
    edited_files = []
    new_contents = []
    # try:
    file_to_commands = split_edit_multifile_commands(
        edit_multifile_commands,
        diff_format=diff_format,
        str_replace_format=str_replace_format,
    )
    # except Exception as e:
    #     logger.error(e)
    #     return edited_files, new_contents

    logger.info("=== file_to_commands: ===")
    logger.info(json.dumps(file_to_commands, indent=2))

    for edited_file_key in file_to_commands:
        edited_file = ""
        new_content = ""
        # try:
        logger.info(f"=== edited_file: {edited_file_key} ===")
        edit_commands = file_to_commands[edited_file_key]
        logger.info("=== edit_commands: ===")
        for c in edit_commands:
            logger.info(c)
            logger.info("\n" + "-" * 40)
        if edited_file_key == None:
            continue
        else:
            try:
                edited_file = eval(edited_file_key)  # convert '"file.py"' to 'file.py'
            except:
                logger.error(f"File {edited_file_key} is not a file name.")
                continue
        if edited_file not in file_contents:
            logger.error(f"File {edited_file} not found in file_contents.")
            continue
        content = file_contents[edited_file]
        if diff_format:
            new_content = parse_diff_edit_commands(
                edit_commands, content, [] # file_loc_intervals[edited_file]
            )
        elif str_replace_format:
            new_content = parse_str_replace_edit_commands(
                edit_commands, content, [] # file_loc_intervals[edited_file]
            )
        else:
            new_content = parse_edit_commands(edit_commands, content)
        # except Exception as e:
        #     logger.error(e)
        #     edited_file = ""
        #     new_content = ""

        if edited_file == "" or new_content == "":
            continue
        edited_files.append(edited_file)
        new_contents.append(new_content)
        diff = list(
            unified_diff(
                content.split("\n"),
                new_content.split("\n"),
                fromfile=edited_file,
                tofile=edited_file,
                lineterm="",
            )
        )

        logger.info(f"extracted patch:")
        logger.info("\n".join(diff))
        # print("\n".join(diff))

    return edited_files, new_contents


def post_process_raw_output(
    raw_output_text, file_contents, logger
):
    git_diffs = ""
    raw_git_diffs = ""
    edited_files, new_contents, contents = [], [], []
    # try:
    edited_files, new_contents = _post_process_multifile_repair(
        raw_output_text,
        file_contents,
        logger,
        diff_format=True,
        str_replace_format=False,
    )

    contents = [file_contents[edited_file] for edited_file in edited_files]

    git_diff = fake_git_repo("playground", edited_files, contents, new_contents)

    raw_git_diffs += "\n" + git_diff.replace("\ No newline at end of file\n", "")

    syntax_success = check_syntax(new_contents)

    differ_by_empty_lines = check_code_differ_by_just_empty_lines(
        new_contents, contents
    )

    logger.info(f"{differ_by_empty_lines = }")
    if syntax_success and not differ_by_empty_lines:
        git_diffs = raw_git_diffs
    else:
        git_diffs = ""  # no need to evaluate
    # except Exception as e:
    #     print(raw_output_text)
    #     print(e)

    return git_diffs, raw_git_diffs, contents, edited_files, new_contents


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model_output_path",
        type=str,
        default="../datasets/outputs/output.jsonl",
    )
    parser.add_argument(
        "--dataset_path",
        type=str,
        default="SWE-Perf/SWE-Perf",
    )
    args = parser.parse_args()

    swebperf_text_data = load_from_disk(args.dataset_path)["test"]
    swebperf_text_data = {
        data["instance_id"]: data for data in swebperf_text_data
    }
    # load raw output from the output jsonl file
    raw_outputs = []
    with jsonlines.open(args.model_output_path, "r") as reader:
        for obj in reader:
            raw_outputs.append(obj)
    output_folder = os.path.dirname(args.model_output_path)
    output_name = os.path.basename(args.model_output_path)[:-6] + "_repair"
    
    for idx, raw_output in enumerate(raw_outputs):
        instance_id = raw_output["instance_id"]
        os.makedirs(os.path.join(output_folder, output_name), exist_ok=True)
        log_file = os.path.join(output_folder, output_name, f"{instance_id}.log")
        logger = logging.getLogger(log_file)
        logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)

        logger.addHandler(fh)

        data = swebperf_text_data[instance_id]
        print(list(data.keys()))
        file_contents = json.loads(data["file_contents"])
        raw_output_text = raw_output["full_output"]
        (
                git_diffs,
                raw_git_diffs,
                content,
                edited_files,
                new_contents,
            ) = post_process_raw_output(
                raw_output_text, file_contents, logger
            )
        raw_outputs[idx]["model_patch"]= git_diffs.lstrip()

    with jsonlines.open(
        os.path.join(output_folder, output_name + ".jsonl"), "w"
    ) as writer:
        for raw_output in raw_outputs:
            writer.write(raw_output)
        
