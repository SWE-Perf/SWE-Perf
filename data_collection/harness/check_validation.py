import json
import os
import pandas as pd
from tqdm import tqdm
from harness.log_parsers import MAP_REPO_TO_PARSER
import re
import matplotlib.pyplot as plt 
from tqdm import tqdm
from datasets import Dataset, load_from_disk
from copy import deepcopy


def load_jsonl(file_path):  
    """Load JSONL file into a list of dictionaries."""  
    data = []  
    with open(file_path, 'r') as f:  
        for line in f:  
            data.append(json.loads(line))  
    return data 

def save_dataset(data, file_path):
    """Save a list of dictionaries to a JSONL file."""
    # with open(file_path, 'w') as f:
    #     for item in data:
    #         json_line = json.dumps(item)
    #         f.write(json_line + '\n')
    data_save = deepcopy(data)
    # dumps the dict
    for idx in range(len(data)):
        if "base_results" in data[idx]:
            data_save[idx]["base_results"] = json.dumps(data[idx]["base_results"])
        if "base_durations" in data[idx]:
            data_save[idx]["base_durations"] = json.dumps(data[idx]["base_durations"])
        if "head_results" in data[idx]:
            data_save[idx]["head_results"] = json.dumps(data[idx]["head_results"])
        if "head_durations" in data[idx]:
            data_save[idx]["head_durations"] = json.dumps(data[idx]["head_durations"])
        if "duration_changes" in data[idx]:
            data_save[idx]["duration_changes"] = json.dumps(data[idx]["duration_changes"])
        if "test_functions" in data[idx]:
            data_save[idx]["test_functions"] = json.dumps(data[idx]["test_functions"])
    dataset = Dataset.from_list(data_save)
    dataset.save_to_disk(file_path)
    del data_save

def load_dataset_(file_path):
    data = load_from_disk(file_path)
    data = data.to_list()
    if "base_results" in data[0]:
        for idx in range(len(data)):
            data[idx]["base_results"] = json.loads(data[idx]["base_results"])
            data[idx]["base_durations"] = json.loads(data[idx]["base_durations"])
            data[idx]["head_results"] = json.loads(data[idx]["head_results"])
            data[idx]["head_durations"] = json.loads(data[idx]["head_durations"])
            data[idx]["duration_changes"] = json.loads(data[idx]["duration_changes"])
            if "test_functions" in data[idx]:
                data[idx]["test_functions"] = json.loads(data[idx]["test_functions"])
            if "patch_functions" in data[idx]:
                data[idx]["patch_functions"] = json.loads(data[idx]["patch_functions"])
    else:
        for idx in range(len(data)):
            data[idx]["duration_changes"] = json.loads(data[idx]["duration_changes"])
    return data

def get_runtimes_and_results(repo: str, log_name: str, log_root):
    repo_name = repo.replace("/", "__").lower()
    if not os.path.exists(os.path.join(log_root, repo_name, log_name, "report.json")):
        print(f"repo:{repo}, commit: {log_name} don't have logs.")
        return None, None
    log_path = os.path.join(log_root, repo_name, log_name, "test_output.txt")
    if not os.path.exists(log_path):
        print(f"{log_path} not exist!")
        return None, None
    with open(os.path.join(log_root, repo_name, log_name, "test_output.txt"), "r") as file:
        content = file.read()
    
    # Get result for each test
    log_parser = MAP_REPO_TO_PARSER[repo]
    results = log_parser(content)

    # Get runtime for each test
    text = content.split("============================== slowest durations ===============================")[-1]
    text = content.split("=========================== short test summary info ============================")[0]
    pattern = r"(\d+\.\d+)s\s+call\s+(.*)"
    pattern_results = re.findall(pattern, text)
    durations = {}
    for time, test_name in pattern_results:
        durations[test_name]=float(time)
    return results, durations

def compare_durations(base_durations, head_durations):  
    """Compare base and head durations and find differences."""  
    changes = {}  
    for test_name, base_duration in base_durations.items():  
        head_duration = head_durations.get(test_name, None)  
        if head_duration is not None:  
            change = head_duration - base_duration  
            changes[test_name] = {"base": base_duration, "head": head_duration, "change": change, "change_percent": change / base_duration if base_duration != 0 else 0}  
    return changes  

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

def check_validation(sweperf_data, success_run_path, log_root):
    if not os.path.exists(success_run_path):
        ## parse runtime 
        samples_without_logs = 0
        dataset_with_success_logs = []

        change_percent = []
        change_percent_task = []
        change_total_percent_task = []
        change_percent_max_task = []
        change_percent_min_task = []
        unit_tests = []

        test_number_base = []
        test_number_head = []
        test_number_change = []
        test_names = []

        for data in tqdm(sweperf_data):
            # parse base commit
            base_results, base_durations = get_runtimes_and_results(data["repo"], data["base_commit"], log_root)
            if base_results==None and base_durations==None:
                samples_without_logs += 1
                continue

            # parse head commit
            head_results, head_durations = get_runtimes_and_results(data["repo"], data["head_commit"], log_root)
            if head_results==None and head_durations==None:
                samples_without_logs += 1
                continue

            # compare base & head duration
            duration_changes = compare_durations(base_durations, head_durations)
            if len(duration_changes) == 0:
                samples_without_logs += 1
                print(f"There are 0 duration_changes, while {len(base_results)} in base ({data['base_commit']}), {len(head_results)} in head ({data['head_commit']})")
                continue
            for test_name, change in duration_changes.items():  
                # print(f"{test_name}: {change['change']:.2f} minutes, {change['change_percent']:.2f}% change")  
                change_percent.append(change['change_percent'])
                unit_tests.append(test_name)
            test_number_base.append(len(base_durations))
            test_number_head.append(len(head_durations))
            test_number_change.append(len(duration_changes))
            test_names.extend(list(duration_changes.keys()))

            all_change_percent = [change['change_percent'] for _,change in duration_changes.items()]
            all_duration_base = [change['base'] for _,change in duration_changes.items()]
            all_duration_head = [change['head'] for _,change in duration_changes.items()]
            change_percent_task.append(sum(all_change_percent)/len(all_change_percent))
            change_total_percent_task.append((sum(all_duration_head)-sum(all_duration_base))/sum(all_duration_base)*100)
            change_percent_max_task.append(max(all_change_percent))
            change_percent_min_task.append(min(all_change_percent))

            data["base_results"] = base_results
            data["base_durations"] = base_durations
            data["head_results"] = head_results
            data["head_durations"] = head_durations
            data["duration_changes"] = duration_changes
            dataset_with_success_logs.append(data)


        # statistics
        plot_histogram(change_percent, bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='change_percent_histogram.png') 
        plot_histogram(change_percent_task, bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='change_percent_task_histogram.png')
        plot_histogram(change_total_percent_task, bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='change_total_percent_task.png')
        plot_histogram(change_percent_max_task, bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='change_percent_max_task.png')
        plot_histogram(change_percent_min_task, bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='change_percent_min_task.png')
        plot_histogram(test_number_base+test_number_head, bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='test_number.png')
        plot_histogram(test_number_change, bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='test_number_change.png')

        print(f"There are total {len(sweperf_data)} samples, and {samples_without_logs} samples without success logs.")
        print(f"We get {len(dataset_with_success_logs)} samples with success logs.")

        save_dataset(dataset_with_success_logs, success_run_path)
        return dataset_with_success_logs
    else:
        # dataset_with_success_logs = load_jsonl(success_run_path)
        dataset_with_success_logs = load_dataset_(success_run_path)
        return dataset_with_success_logs


if __name__ == "__main__":
    sweperf_data_path = "../datasets/pandas/versions/pandas-task-instances_versions.non-empty.jsonl"
    log_root = "../datasets/logs/run_evaluation/all_dataset/"
    output_path = "../datasets/efficiency_dataset/all_dataset/"
    os.makedirs(output_path, exist_ok=True)
    success_run_path = os.path.join(output_path, ".".join(sweperf_data_path.split("/")[-1].split("."))[:-1]+".success_run.jsonl")
    efficiency_path = os.path.join(output_path, ".".join(sweperf_data_path.split("/")[-1].split("."))[:-1]+".efficiency.jsonl")

    ## Load dataset
    sweperf_data = load_jsonl(sweperf_data_path)
    dataset_with_success_logs = check_validation(sweperf_data, success_run_path, log_root)

    del sweperf_data

    samples_without_efficiency_test = 0
    efficiency_test_num = []
    dataset_with_efficiency_test = []
    for data in dataset_with_success_logs:
        all_change_percent = [change['change_percent'] for _,change in data["duration_changes"].items()]
        efficiency_test = []
        for key in data["duration_changes"].keys():
            if data["duration_changes"][key]['change_percent'] < -0.5:
                efficiency_test.append(key)
        if len(efficiency_test)>0:
            data["efficiency_test"] = efficiency_test
            dataset_with_efficiency_test.append(data)
            efficiency_test_num.append(len(efficiency_test))
        else:
            samples_without_efficiency_test += 1

    print(f"There are {samples_without_efficiency_test} samples without efficiency test.")
    print(f"We get {len(dataset_with_success_logs)} samples with {sum(efficiency_test_num)/len(dataset_with_success_logs)} ({sum(efficiency_test_num)}/{len(dataset_with_success_logs)}) efficiency test.")
    plot_histogram(efficiency_test_num, bins=20, title='Sample Histogram', xlabel='Value', ylabel='Frequency', filename='test_number_efficiency.png')


    save_dataset(dataset_with_efficiency_test, efficiency_path)