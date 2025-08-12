#!/usr/bin/env python3

"""
Create a dataset for text-to-text training from the raw task instance outputs.
"""

import json
import logging
import os
from argparse import ArgumentParser
from pathlib import Path
from datasets import Dataset, DatasetDict, load_dataset, load_from_disk
from tqdm.auto import tqdm
import pandas as pd
from copy import deepcopy

from harness.make_datasets.create_instance import add_text_inputs, PROMPT_FUNCTIONS
from harness.make_datasets.tokenize_dataset import TOKENIZER_FUNCS
from harness.make_datasets.utils import string_to_bool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_jsonl_file(filename):
    if type(filename) == str:
        filename = Path(filename)
    if filename.name.endswith(".jsonl") or filename.name.endswith(".jsonl.all"):
        with open(filename) as f:
            return [json.loads(line) for line in f]
    elif filename.name.endswith(".json"):
        with open(filename) as f:
            return json.load(f)
    else:
        raise ValueError(f"Unknown file type {filename}")


def instances_generator(files):
    all_data = list()
    for file in tqdm(files, desc="Loading instance files"):
        all_data.extend(load_jsonl_file(file))
    return all_data


def get_training_and_eval_instances(raw_files, test_dataset):
    logger.info("Loading instances")
    raw_instances = list(instances_generator(raw_files))
    final_instances = list(test_dataset["test"])
    eval_repos = {x["repo"] for x in final_instances}
    train_instances = [x for x in raw_instances if x["repo"] not in eval_repos]
    train_instances = list(sorted(train_instances, key=lambda x: x["instance_id"]))
    eval_instances = list(sorted(final_instances, key=lambda x: x["instance_id"]))
    logger.info(f"Found {len(train_instances)} training ids")
    logger.info(f"Found {len(eval_instances)} eval ids")
    return train_instances, eval_instances


def extract_fields(instance):
    instance_id = instance["instance_id"]
    if instance["text_inputs"] is None or instance["patch"] is None:
        print(f"No text for {instance_id}")
        return None
    text_inputs = instance["text_inputs"].strip() + "\n\n"
    if text_inputs is None or instance["patch"] is None:
        print(f"No inputs for {instance_id}")
        return None
    patch = "\n".join([f"<patch>", instance["patch"], "</patch>"])
    return {**instance, "text": text_inputs, "patch": patch}


def main(
    dataset_name_or_path,
    splits,
    validation_ratio,
    output_dir,
    retrieval_file,
    prompt_style,
    file_source,
    k,
    max_context_len,
    tokenizer_name,
    push_to_hub_user,
):
    if push_to_hub_user is not None:
        hub_token = os.environ.get("HUGGING_FACE_HUB_TOKEN", None)
        assert hub_token is not None, "Must provide HUGGING_FACE_HUB_TOKEN to push to the Hub"
        assert output_dir is None, "Cannot provide output_dir if pushing to the Hub"
    if max_context_len is not None:
        assert tokenizer_name is not None
    if push_to_hub_user is None and not Path(output_dir).exists():
        Path(output_dir).mkdir(parents=True)
    output_file = f"{dataset_name_or_path.strip('/').split('/')[-1]}__{prompt_style}__fs-{file_source}"
    if k is not None:
        assert file_source not in {
            "all",
            "oracle",
        }, "Cannot use max_context_len with oracle or all file sources"
        output_file += f"__k-{k}"
    if max_context_len is not None:
        assert file_source not in {
            "all",
            "oracle",
        }, "Cannot use max_context_len with oracle or all file sources"
        assert (
            tokenizer_name is not None
        ), "Must provide tokenizer_name if max_context_len is not None"
        output_file += f"__mcc-{max_context_len}-{tokenizer_name}"
    if push_to_hub_user is None:
        output_file = Path(output_dir, output_file)
        if output_file.exists():
            logger.info(f"{output_file.absolute().as_posix()} already exists. Aborting")
            return
    if Path(dataset_name_or_path).exists():
        dataset = load_from_disk(dataset_name_or_path)
        dataset = dataset.to_list()
        # def load_jsonl(file_path):  
        #     """Load JSONL file into a list of dictionaries."""  
        #     data = []  
        #     with open(file_path, 'r') as f:  
        #         for line in f:  
        #             data.append(json.loads(line))  
        #     return data 
        # with open(dataset_name_or_path, "r") as f:
        #     dataset = load_jsonl(dataset_name_or_path)
        for i in range(len(dataset)):
            dataset[i]['duration_changes'] = str(dataset[i]['duration_changes'])
            dataset[i]['efficiency_test'] = str(dataset[i]['efficiency_test'])
        dataset = Dataset.from_list(dataset)
        print(dataset)
        dataset={"test": dataset}
    else:
        dataset = load_dataset(dataset_name_or_path)

    split_instances = dict()
    logger.info(f'Found {set(dataset.keys())} splits')
    if set(splits) - set(dataset.keys()) != set():
        raise ValueError(f"Unknown splits {set(splits) - set(dataset.keys())}")
    for split in splits:
        instance_dict = {}
        for x in tqdm(dataset[split]):
            instance_dict[x["instance_id"]] = x
        split_instances[split] = instance_dict
        add_text_inputs(
            split_instances[split],
            retrieval_file,
            k,
            prompt_style,
            file_source,
            max_context_len=max_context_len,
            tokenizer_name=tokenizer_name)
        if prompt_style == "statistics":
            for key in list(split_instances[split].values())[0]["statistics"]:
                stastistics = [x["statistics"][key] for x in split_instances[split].values()]
                if type(stastistics[0]) != list:
                    print(f"key: {key}, Mean: {sum(stastistics)/len(stastistics)}, Max: {max(stastistics)}, Min: {min(stastistics)}")
                else:
                    stastistics = [sta for sta in stastistics if sta != []]
                    print(f"key: {key}, Mean: {sum([sum(x)/len(x) for x in stastistics])/len(stastistics)}, Max: {max([max(x) for x in stastistics])}, Min: {min([min(x) for x in stastistics])}")
            return
        if prompt_style == "get_function_from_test":
            function_list = []
            for instance in split_instances[split].values():
                instance_id = instance["instance_id"]
                function_info = instance["function"]
                for test in eval(instance["efficiency_test"]):
                    function_list.append({
                        "instance_id": instance_id,
                        "test": test,
                        "test_content": function_info[test]["test_content"].replace('\\n', '\n'),
                        "called_funcs": json.dumps(list(function_info[test]["called_funcs"])),
                        "import_map": json.dumps(function_info[test]["import_map"]),
                        "resolved": json.dumps(function_info[test]["resolved"])
                    })
            pd.DataFrame(function_list).to_csv(
                Path(output_file).with_suffix(".csv"),
                index=False,
            )
            return
        if prompt_style == "get_function_from_patch":
            function_list = []
            for instance in split_instances[split].values():
                instance_id = instance["instance_id"]
                patch = instance["patch"]
                if "functions" not in instance:
                    instance["functions"] = {}
                    print(f"There is non funciton in {instance_id}")
                function_list.append({
                    "instance_id": instance_id,
                    "patch": patch.replace('\\n', '\n'),
                    "functions": instance["functions"]
                })
            pd.DataFrame(function_list).to_csv(
                Path(output_file).with_suffix(".csv"),
                index=False,
            )
            dataset = load_from_disk(dataset_name_or_path)
            dataset_new = []
            for idx, data in enumerate(dataset):
                sample_new = deepcopy(data)
                sample_new["patch_functions"] = json.dumps(split_instances[split][data["instance_id"]]["functions"])
                sample_new["problem_statement_oracle"] = '\n'.join([
"Please enhance the computational efficiency and execution speed across the entire repository. The optimization efforts may target one or more objective functions, including but not limited to:",
str(split_instances[split][data["instance_id"]]["functions"]),
"The following conditions apply:",
"1. Acceleration of at least one objective function is sufficient for success, as performance evaluations will be conducted collectively on all targeted functions.",
"2. Optimization may be achieved either directly through modifications to the objective functions or indirectly by improving computationally intensive subroutines upon which they depend.",
"3. Optimization efforts should prioritize maximal efficiency gains where feasible.",
"4. All existing unit tests must remain unaltered to preserve functional correctness."
        ])
                dataset_new.append(sample_new)
            dataset_new = Dataset.from_list(dataset_new)
            dataset_new.save_to_disk(dataset_name_or_path+".with_patch_functions")
            return
    columns = [
        "instance_id",
        "text",
        "repo",
        "base_commit",
        "problem_statement",
        "hints_text",
        "created_at",
        "patch",
        "test_patch",
        "file_contents"
        # "version",
        # "FAIL_TO_PASS",
        # "PASS_TO_PASS",
        # "environment_setup_commit",
        # "duration_changes", "efficiency_test"
    ]
    split_data = dict()
    for split in split_instances:
        split_data[split] = {key: list() for key in columns}
        for instance in tqdm(
            split_instances[split].values(), total=len(split_instances[split]), desc=f'Processing {split} instances',
        ):
            datum = extract_fields(instance)
            if datum is None:
                continue
            for key in columns:
                split_data[split][key].append(datum[key] if key in datum else "")
        logger.info(f"Found {len(split_data[split]['instance_id'])} {split} ids")
        split_data[split] = Dataset.from_dict(split_data[split])
    dataset = DatasetDict(split_data)
    if validation_ratio > 0 and "train" in dataset:
        train_val = dataset["train"].train_test_split(
            test_size=validation_ratio,
            seed=42,
        )
        dataset["train"] = train_val["train"]
        dataset["validation"] = train_val["test"]
    for split in dataset:
        logger.info(f"Found {len(dataset[split])} {split} instances")
    if push_to_hub_user is not None:
        dataset.push_to_hub(f'{push_to_hub_user}/{output_file}', use_auth_token=hub_token)
    else:
        dataset.save_to_disk(output_file)
    logger.info(f"Finsihed saving to {output_file}")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset_name_or_path",
        type=str,
        default="princeton-nlp/SWE-bench",
        help="Dataset to use for test set from HuggingFace Datasets or path to a save_to_disk directory.",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "test"],
        help="Splits to use from the dataset.",
    )
    parser.add_argument(
        "--validation_ratio",
        type=float,
        default=0.01,
        help="Ratio of the training set to use for validation.",
    )
    parser.add_argument(
        "--output_dir", type=str, help="Path to the output directory."
    )
    parser.add_argument(
        "--retrieval_file",
        type=str,
        help="Path to the file where the retrieval results are stored.",
    )
    parser.add_argument(
        "--prompt_style",
        type=str,
        default="style-3",
        choices=list(PROMPT_FUNCTIONS.keys())+["statistics", "get_function_from_test", "get_function_from_patch"],
        help="Prompt style to use. See create_instance.PROMPT_FUNCTIONS for details.",
    )
    parser.add_argument(
        "--file_source",
        type=str,
        default="oracle",
        choices=["oracle", "bm25", "all"],
        help="How to select the files to use in context.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="Maximum number of files to use for retrieval.",
    )
    parser.add_argument(
        "--max_context_len",
        type=int,
        default=None,
        help="Maximum number of tokens to use for context.",
    )
    parser.add_argument(
        "--tokenizer_name",
        type=str,
        default=None,
        choices=TOKENIZER_FUNCS.keys(),
        help="Tokenizer to use for max_context_len. Only needed if max_context_len is specified.",
    )
    parser.add_argument(
        "--push_to_hub_user",
        type=str,
        help="Username to use for pushing to the Hub. If not provided, will save to disk.",
    )
    main(**vars(parser.parse_args()))
