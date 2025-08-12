import json
import os
from tqdm import tqdm
from harness.log_parsers import MAP_REPO_TO_PARSER
from tqdm import tqdm
from harness.check_validation import  save_dataset, load_dataset_
from argparse import ArgumentParser
from numpy import std, mean, sqrt
from copy import deepcopy

parser = ArgumentParser(description=__doc__)
parser.add_argument(
    "--dataset_name",
    type=str,
    default="pandas",
)
args = parser.parse_args()
sweperf_data_path = f"../datasets/efficiency_dataset/{args.dataset_name}-task-instances_versions.non-empty.json.efficiency_0627"
print(sweperf_data_path)
log_root = "../datasets/logs/run_evaluation/coverage_0627/"
efficiency_path = f'../datasets/efficiency_dataset/{".".join(sweperf_data_path.split("/")[-1].split("."))+".efficiency_coverage"}'
## Load dataset
sweperf_data = load_dataset_(sweperf_data_path)

samples_without_efficiency_test = 0
efficiency_test_num = []
dataset_with_efficiency_test = []
for data in tqdm(sweperf_data):
    instance_id = data["instance_id"]
    repo = data["repo"].replace("/", "__")
    coverage_path = os.path.join(log_root, repo, instance_id, f"report.json")
    if not os.path.exists(coverage_path):
        print(f"{coverage_path} not exist!")
        continue
    with open(coverage_path, "r") as file:
        coverage = json.load(file)

    efficiency_test = []
    for test in coverage.keys():
        if coverage[test]:
            efficiency_test.append(test)
    if len(efficiency_test)>0:
        data = deepcopy(data)
        data["efficiency_test"] = efficiency_test
        dataset_with_efficiency_test.append(data)
        efficiency_test_num.append(len(efficiency_test))
    else:
        samples_without_efficiency_test += 1


print(f"There are {samples_without_efficiency_test} samples without efficiency test.")
print(f"We get {len(dataset_with_efficiency_test)} samples with {sum(efficiency_test_num)/len(dataset_with_efficiency_test)} ({sum(efficiency_test_num)}/{len(dataset_with_efficiency_test)}) efficiency test.")

save_dataset(dataset_with_efficiency_test, efficiency_path)