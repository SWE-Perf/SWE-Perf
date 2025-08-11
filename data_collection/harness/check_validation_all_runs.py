import json
from collections import defaultdict
import os
import pandas as pd
from tqdm import tqdm
from collections import Counter
import matplotlib.pyplot as plt 
from tqdm import tqdm
from harness.check_validation import load_jsonl, save_dataset, check_validation
from argparse import ArgumentParser
from numpy import std, mean, sqrt
from copy import deepcopy
from harness.constants import TestStatus

def plot_histogram(data, bins=10, title='Histogram', xlabel='Value', ylabel='Frequency', filename='histogram.png'):  
    """  
    Plot a histogram for the given data.  
    
    Parameters:  
    - data: list of numerical values to plot  
    - bins: int or sequence, optional, default: 10. Number of bins or bin edges.  
    - title: str, title of the histogram  
    - xlabel: str, label for the x-axis  
    - ylabel: str, label for the y-axis  
    """  
    plt.figure(figsize=(8, 6))  
    plt.hist(data, bins=bins, color='blue', edgecolor='black', alpha=0.7)  
    plt.title(title)  
    plt.xlabel(xlabel)  
    plt.ylabel(ylabel)  
    plt.grid(axis='y', alpha=0.75)  
    # Save the figure to a file  
    plt.savefig(filename, format=filename.split('.')[-1], dpi=300)

def coefficient_of_variation(data):
    mean = sum(data) / len(data)
    squared_diff = [(x - mean)**2 for x in data]
    std_dev = (sum(squared_diff) / len(data))**0.5
    cv = (std_dev / mean) * 100 if mean != 0 else 99  # Avoid division by zero
    return cv

def caculate_cohen_d(x,y):
    nx = len(x)
    ny = len(y)
    dof = nx + ny - 2
    return (mean(x) - mean(y)) / sqrt(((nx-1)*std(x, ddof=1) ** 2 + (ny-1)*std(y, ddof=1) ** 2) / dof)

if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset_name",
        type=str,
        default="pandas",
    )
    args = parser.parse_args()
    sweperf_data_path = f"../datasets/{args.dataset_name}/versions/{args.dataset_name}-task-instances_versions.non-empty.jsonl"
    print(sweperf_data_path)
    log_root = ["../datasets/logs/run_evaluation/all_dataset/","../datasets/logs/run_evaluation/all_dataset_run2/","../datasets/logs/run_evaluation/all_dataset_run3/"]
    output_path = ["../datasets/efficiency_dataset/all_dataset/","../datasets/efficiency_dataset/all_dataset_run2/","../datasets/efficiency_dataset/all_dataset_run3/"]
    success_run_path = [os.path.join(output, ".".join(sweperf_data_path.split("/")[-1].split("."))[:-1]+".success_run") for output in output_path]
    efficiency_path = f'../datasets/efficiency_dataset/{".".join(sweperf_data_path.split("/")[-1].split("."))[:-1]+".efficiency_0627"}'



    ## Load dataset
    sweperf_data = load_jsonl(sweperf_data_path)

    dataset = []
    for idx, s_path in tqdm(enumerate(success_run_path)):
        d = check_validation(sweperf_data, s_path, log_root[idx])
        d = {d_['instance_id']:d_ for d_ in d}
        dataset.append(deepcopy(d))
    del sweperf_data

    samples_without_efficiency_test = 0
    efficiency_test_num = []
    dataset_with_efficiency_test = []
    tables_all = defaultdict(list)
    for instance_id in tqdm(dataset[0].keys()):
        if instance_id not in dataset[1] or instance_id not in dataset[2]:
            continue
        repo = dataset[0][instance_id]["repo"].split("/")[-1]
        duration_changes = [d[instance_id]["duration_changes"] for d in dataset]

        # Find common keys present in all three dictionaries
        common_keys = set(duration_changes[0].keys())
        for d in duration_changes[1:]:
            common_keys &= set(d.keys())
        common_keys = sorted(common_keys)  # Sort for consistent ordering
        
        # Extract inner dictionary keys (e.g., 'base', 'head')
        sample_key = next(iter(duration_changes[0].values()))  # Get first inner dict as sample
        inner_keys = list(sample_key.keys())
        
        # Create one table per inner key
        tables = {}
        for inner_key in inner_keys:
            # Build list of lists containing only values
            table_data = {key:
                [
                    duration_changes[0][key][inner_key],  # Dict1 value
                    duration_changes[1][key][inner_key],  # Dict2 value
                    duration_changes[2][key][inner_key]   # Dict3 value
                ]
                for key in common_keys
            }
            
            tables[inner_key] = table_data
            tables_all[inner_key].append(table_data)        

        efficiency_test = []
        for key in common_keys:
            base_runtimes = tables["base"][key]
            cv_base = coefficient_of_variation(base_runtimes)
            head_runtimes = tables["head"][key]
            cv_head = coefficient_of_variation(head_runtimes)
            EFFICIENCY_BAR = {
                # "pandas": -0.5,
                # "mypy": -0.7,
                # "moto": -0.95,
                # "dvc": -0.4,
                # "dask": -0.4,
                # "conan": -0.4,
                # "pydantic": -0.7,
                # "hydra": -0.4,
                # "bokeh": -0.4,
            }
            efficiency_bar = EFFICIENCY_BAR.get(repo, -0.3)
            # print(f"Efficiency bar for {repo} is {efficiency_bar}")
            # correct
            flag = True
            for d in dataset:
                if key not in d[instance_id]['base_results'] or key not in d[instance_id]['head_results']:
                    flag = False
                    break
                if d[instance_id]['base_results'][key] != TestStatus.PASSED.value:
                    flag = False
                    break
                if d[instance_id]['head_results'][key] != TestStatus.PASSED.value:
                    flag = False
                    break
            if not flag:
                continue

            # check efficiency
            # if not all(a < (1+efficiency_bar) * b for a, b in zip(head_runtimes, base_runtimes)):
            #     continue

            # if cv_base > 15 or cv_head > 15:
            #     continue
            
            # cohen_d_ = caculate_cohen_d(base_runtimes, head_runtimes)
            # if cohen_d_ <= 2:
            #     continue

            avg_A = sum(base_runtimes) / len(base_runtimes)
            avg_B = sum(head_runtimes) / len(head_runtimes)
            ratio = (avg_B - avg_A) / avg_A

            if ratio < efficiency_bar:
                efficiency_test.append(key)
        if len(efficiency_test)>0:
            data = dataset[0][instance_id]
            data["duration_changes"] = [dataset[0][instance_id]["duration_changes"], dataset[1][instance_id]["duration_changes"], dataset[2][instance_id]["duration_changes"]]
            data["efficiency_test"] = efficiency_test
            dataset_with_efficiency_test.append(data)
            efficiency_test_num.append(len(efficiency_test))
        else:
            samples_without_efficiency_test += 1


    print(f"There are {samples_without_efficiency_test} samples without efficiency test.")
    print(f"We get {len(dataset_with_efficiency_test)} samples with {sum(efficiency_test_num)/len(dataset_with_efficiency_test)} ({sum(efficiency_test_num)}/{len(dataset_with_efficiency_test)}) efficiency test.")

    save_dataset(dataset_with_efficiency_test, efficiency_path)

    # base
    # Coefficient of Variation，CV
    base_runtimes_cv = [[coefficient_of_variation(values) for values in list(tables.values())] for tables in tables_all["base"]]
    plot_histogram([element for sublist in base_runtimes_cv for element in sublist], bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='base_cv_all.png')
    plot_histogram([min(cv) for cv in base_runtimes_cv], bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='base_cv_min.png')
    plot_histogram([max(cv) for cv in base_runtimes_cv], bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='base_cv_max.png')
    plot_histogram([sum(cv)/len(cv) for cv in base_runtimes_cv], bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='base_cv_avg.png')
