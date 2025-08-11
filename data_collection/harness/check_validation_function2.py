import json
from collections import defaultdict
import os
from tqdm import tqdm
from harness.log_parsers import MAP_REPO_TO_PARSER
from tqdm import tqdm
from harness.check_validation import  save_dataset,load_dataset_
from numpy import std, mean, sqrt
from copy import deepcopy

sweperf_data_path = "../datasets/efficiency_dataset/efficiency-instances_swebench.efficiency_coverage_0627.single_runs_p1_2.with_patch_functions"
print(sweperf_data_path)
log_root = "../datasets/logs/run_evaluation/function/"
efficiency_path = f'../datasets/efficiency_dataset/{".".join(sweperf_data_path.split("/")[-1].split("."))+".with_test_functions"}'
## Load dataset
sweperf_data = load_dataset_(sweperf_data_path)

function_num_list = []
without_function = 0
function_total_num_list = []
without_funciton_total = 0
dataset_with_efficiency_test = []
for data in tqdm(sweperf_data):
    instance_id = data["instance_id"]
    repo = data["repo"].replace("/", "__")
    function_path = os.path.join(log_root, repo, instance_id, f"report.json")
    if not os.path.exists(function_path):
        print(f"{function_path} not exist!")
        function_total = {}
    else:
        with open(function_path, "r") as file:
            function_report = json.load(file)

        for idx, func_list in enumerate(function_report["functions"]):
            function_num_list.append(len(func_list))
            if len(func_list) == 0:
                without_function+=1
                print(f"warning: {instance_id} - {idx} has no function!")
        
        if len(function_report["function_total"]) == 0:
            without_funciton_total+=1
            print(f"warning: {instance_id} has no function!")
        function_total_num_list.append(len(function_report["function_total"]))

        function_total = defaultdict(list)
        for func in function_report["function_total"]:
            function_total[func["mod"]].append(func['func_name'])
    data = deepcopy(data)
    # data["test_functions"] = function_total
    data["problem_statement_end2end"] = '\n'.join([
"Please enhance the computational efficiency and execution speed across the entire repository. The optimization efforts may target one or more objective functions, including but not limited to:",
str(function_total),
"The following conditions apply:",
"1. Acceleration of at least one objective function is sufficient for success, as performance evaluations will be conducted collectively on all targeted functions.",
"2. Optimization may be achieved either directly through modifications to the objective functions or indirectly by improving computationally intensive subroutines upon which they depend.",
"3. Optimization efforts should prioritize maximal efficiency gains where feasible.",
"4. All existing unit tests must remain unaltered to preserve functional correctness."
        ])
    # print(data["robtest_functions"])
    # print(data["plem_statement_end2end"])

    dataset_with_efficiency_test.append(data)

print(f"There are {mean(function_num_list)} function in each test, and {without_function} without function.")
print(f"There are {mean(function_total_num_list)} function in each sample, and {without_funciton_total} without function.")
save_dataset(dataset_with_efficiency_test, efficiency_path)