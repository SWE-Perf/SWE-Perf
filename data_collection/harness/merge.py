from harness.check_validation import load_dataset_, save_dataset
import re
from copy import deepcopy
import os

def single_function(patch):
    # More than 1 file
    if patch.count("diff --git ") > 1:
        return False
    
    flag_name = None # e.g. @@ -203,9 +203,7 @@ def is_clean(self) -> bool:
    function_name = None
    function_has_been_changed = False
    first_line = False
    function_name_changed = []
    func_pattern = re.compile(r'def\s+([\w_]+)\s*\(')
    for line in patch.split("\n"):
        if line.startswith("diff --git "): 
            continue

        func_match = re.search(func_pattern, line)
        if line.startswith("+++") or line.startswith("---"):
            if func_match:
                return False
        if first_line and func_match: # The first line of chunk
            flag_name = None
            function_name = func_match.group(1)
            first_line = False
        elif first_line: # The first line of chunk
            function_name = flag_name
            first_line = False
        elif func_match and not line.startswith("@@"): # match function and not in @@ line
            # Deal with the last chunk
            if function_name != None and function_has_been_changed:
                function_name_changed.append(function_name)
            function_has_been_changed = False
            function_name = func_match.group(1)
        elif line.startswith("@@"): # @@ line
            first_line = True
            flag_name = func_match.group(1) if func_match else None

            # Deal with the last chunk
            if function_name != None and function_has_been_changed:
                function_name_changed.append(function_name)
            function_name = None
            function_has_been_changed = False
            
        if line.startswith("+") or line.startswith("-"):
            function_has_been_changed = True

    if function_name != None and function_has_been_changed:
        function_name_changed.append(function_name)

    # if len(set(function_name_changed)) == 1: # v1, the same function name may be from the different class
    if len(function_name_changed) == 1: # v2 
        return True
    else:
        return False

        

if __name__ == "__main__":


    repos = ["astropy", "matplotlib", "seaborn", "requests", "xarray", "pylint", "scikit-learn", "sphinx", "sympy"]
    efficiency_paths = [f"../datasets/efficiency_dataset/{repo}-task-instances_versions.non-empty.json.efficiency_0627.efficiency_coverage" for repo in repos]
    efficiency_path = "../datasets/efficiency_dataset/efficiency-instances_swebench.efficiency_coverage_0627"
    single_function_path = "../datasets/efficiency_dataset/function_efficiency_dataset_swebench_20250627/"

    # repos = ["pandas", "moto", "mypy", "dvc", "dask", "conan", "pydantic", "bokeh", "hydra"]
    # efficiency_paths = [f"../datasets/efficiency_dataset/{repo}-task-instances_versions.non-empty.json.efficiency_0627.efficiency_coverage" for repo in repos]
    # efficiency_path = "../datasets/efficiency_dataset/efficiency-instances_swegym.efficiency_coverage_0627"
    # single_function_path = "../datasets/efficiency_dataset/function_efficiency_dataset_swegym_20250627/"

    merge_single_dataset = []
    merge_dataset = []
    total = 0
    for dataset_path in efficiency_paths:
        if not os.path.exists(dataset_path):
            print(f'There is no {dataset_path}!!!')
            continue
        dataset = load_dataset_(dataset_path)
        print(f"There are {len(dataset)} samples in {dataset_path}")
        total+=len(dataset)
        for sample in dataset:
            sample = deepcopy(sample)
            sample["problem_statement"] = '\n'.join([
        'I need you to improve its efficiency and execution speed for the test cases:',
        str(sample["efficiency_test"])
    ])
            merge_dataset.append(sample)
            if single_function(sample["patch"]):
                merge_single_dataset.append(sample)
    print(f"There are {len(merge_dataset)} samples from {total} effi samples.")
    print(f"There are {len(merge_single_dataset)} functional samples from {total} effi samples.")
    save_dataset(merge_single_dataset, single_function_path)
    save_dataset(merge_dataset, efficiency_path)