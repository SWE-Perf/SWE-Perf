import json
import os
from tqdm import tqdm
from harness.log_parsers import MAP_REPO_TO_PARSER
from collections import Counter
from tqdm import tqdm
from harness.check_validation import save_dataset, load_dataset_
from numpy import std, mean, sqrt
from copy import deepcopy
from harness.check_validation_all_runs import caculate_cohen_d, coefficient_of_variation, plot_histogram
from scipy.stats import mannwhitneyu
from harness.utils import filter_outliers, find_max_significant_improvement
from harness.test_spec import REPEAT_TIME

sweperf_data_path = "../datasets/efficiency_dataset/efficiency-instances_swebench.efficiency_coverage_0627"
print(sweperf_data_path)
log_root = [
"../datasets/logs/run_evaluation/single_runs_0627/gold/"]
efficiency_path = f'{sweperf_data_path}.single_runs_p1'
## Load dataset
sweperf_data = load_dataset_(sweperf_data_path)

efficiency_num_ori = [len(data["efficiency_test"]) for data in sweperf_data]
print(f"There are {len(sweperf_data)} samples in {sweperf_data_path} with {sum(efficiency_num_ori)/len(sweperf_data)} efficiency tests ({sum(efficiency_num_ori)} / {len(sweperf_data)})")

for log in log_root:
    cv_ori = []
    cv_new = []
    performance_ori = []
    performance_new = []
    base_duration_ori = []
    base_duration_new = []
    base_duration_filter = []
    head_duration_filter = []
    samples_without_efficiency_test = 0
    samples_without_correct_test = 0
    efficiency_test_num = []
    dataset_with_efficiency_test = []
    repeat_num = REPEAT_TIME
    for data in tqdm(sweperf_data):
        instance_id = data["instance_id"]
        repo = data["repo"].replace("/", "__")

        duration_changes = [{} for _ in range(repeat_num)]  # Create a list of empty dictionaries for each log root
        # changes_ = {}
        log_path = os.path.join(log, instance_id, "report.json")
        if not os.path.exists(log_path):
            print(f"{log_path} not exist!")
            continue
        with open(log_path, "r") as file:
            report = json.load(file)
        for test in report.keys():
            if "base" in report[test] and "human" in report[test]:
                for re_idx in range(repeat_num):
                    if str(re_idx) in report[test]["base"] and str(re_idx) in report[test]["human"]:
                        base_duration = report[test]["base"][str(re_idx)]["duration"]
                        head_duration = report[test]["human"][str(re_idx)]["duration"]
                        change = head_duration - base_duration
                        duration_changes[re_idx][test] = {"base": base_duration, "head": head_duration, "change": change, "change_percent": change / base_duration if base_duration != 0 else 0,
                                        "base_outcome": report[test]["base"][str(re_idx)]["outcome"], "head_outcome": report[test]["human"][str(re_idx)]["outcome"]}  
            # duration_changes.append(changes_)

        # Find common keys present in all three dictionaries
        duration_changes = [dc for dc in duration_changes if len(dc) > 0]  # Filter out empty dictionaries
        if len(duration_changes) < repeat_num:
            samples_without_correct_test += 1
            print(f"Not enough logs for {instance_id} in {repo}. Skipping...")
            continue
        common_keys = set(duration_changes[0].keys())
        for d in duration_changes[1:]:
            common_keys &= set(d.keys())
        common_keys = sorted(common_keys)  # Sort for consistent ordering
        if len(common_keys) == 0:
            samples_without_correct_test += 1
            print(f"No common tests found for {instance_id} in {repo}. Skipping...")
            continue
        
        # Extract inner dictionary keys (e.g., 'base', 'head')
        sample_key = next(iter(duration_changes[0].values()))  # Get first inner dict as sample
        inner_keys = list(sample_key.keys())
        
        # Create one table per inner key
        tables = {}
        for inner_key in inner_keys:
            # Build list of lists containing only values
            table_data = {key:
                [
                    duration_changes[re_idx][key][inner_key]  # Dict1 value
                    for re_idx in range(repeat_num)
                ]
                for key in common_keys
            }
            
            tables[inner_key] = table_data

        efficiency_test = []
        correct_flag = False
        for key in common_keys:
            base_runtimes = tables["base"][key]
            base_runtimes = filter_outliers(base_runtimes)
            cv_base = coefficient_of_variation(base_runtimes)
            head_runtimes = tables["head"][key]
            head_runtimes = filter_outliers(head_runtimes)
            if len(head_runtimes) == 0 or len(base_runtimes) == 0:
                continue
            cv_head = coefficient_of_variation(head_runtimes)
            cv_ori.append(cv_base)
            cv_new.append(cv_head)
            base_duration_ori.append(mean(base_runtimes))

            avg_A = sum(base_runtimes) / len(base_runtimes)
            avg_B = sum(head_runtimes) / len(head_runtimes)
            ratio_ = (avg_B - avg_A) / avg_A
            ratio = find_max_significant_improvement(head_runtimes, base_runtimes)
            # print(f"[{ratio_}, {ratio}]")
            performance_ori.append(ratio)


            EFFICIENCY_BAR = {
            }
            efficiency_bar = EFFICIENCY_BAR.get(repo, -0.05)
            # correct
            flag = True
            for d in duration_changes:
                if d[key]['base_outcome'] != "passed" or d[key]['head_outcome'] != "passed":
                    flag = False
                    break
            if not flag:
                print("0")
                continue
            else:
                correct_flag = True
            
            cohen_d_ = caculate_cohen_d(base_runtimes, head_runtimes)

            stat, p = mannwhitneyu(base_runtimes, head_runtimes, alternative='greater')

            if ratio >= -efficiency_bar:
                efficiency_test.append(key)
                cv_new.append(cv_head)
                cv_new.append(cv_base)
                performance_new.append(ratio)
                base_duration_new.append(mean(base_runtimes))
                base_duration_filter.append(mean(base_runtimes))
                head_duration_filter.append(mean(head_runtimes))
            else:
                continue
        if len(efficiency_test)>0:
            new_data = deepcopy(data)
            new_data["duration_changes"] = duration_changes
            new_data["efficiency_test"] = efficiency_test
            dataset_with_efficiency_test.append(new_data)
            efficiency_test_num.append(len(efficiency_test))
        else:
            if correct_flag:
                samples_without_efficiency_test += 1
            else:
                samples_without_correct_test += 1

    print(f"There are {samples_without_correct_test} samples without correct test.")
    print(f"There are {samples_without_efficiency_test} samples without efficiency test.")
    print(f"We get {len(dataset_with_efficiency_test)} samples with {sum(efficiency_test_num)/len(dataset_with_efficiency_test)} ({sum(efficiency_test_num)}/{len(dataset_with_efficiency_test)}) efficiency test.")
    # count repo
    repo_count = Counter([data["repo"] for data in dataset_with_efficiency_test])
    print("Repo count in dataset with efficiency test:")
    for repo, count in repo_count.items():
        print(f"{repo}: {count}")

    # Plot histograms
    plot_histogram(cv_ori, filename='cv_ori_histogram.png', title='Coefficient of Variation (Original)', xlabel='CV', ylabel='Frequency')
    plot_histogram(cv_new, filename='cv_new_histogram.png', title='Coefficient of Variation (New)', xlabel='CV', ylabel='Frequency')
    plot_histogram(performance_ori, filename='performance_ori_histogram.png', title='Performance Ratio (Original)', xlabel='Performance Ratio', ylabel='Frequency', bins=50)
    plot_histogram(performance_new, filename='performance_new_histogram.png', title='Performance Ratio (New)', xlabel='Performance Ratio', ylabel='Frequency')
    base_duration_ori = [d for d in base_duration_ori if d < 10]
    base_duration_new = [d for d in base_duration_new if d < 10]
    base_duration_filter = [d for d in base_duration_filter if d < 5]
    head_duration_filter = [d for d in head_duration_filter if d < 5]
    plot_histogram(base_duration_ori, filename='base_duration_ori_histogram.png', title='Base Duration (Original)', xlabel='Duration', ylabel='Frequency', bins=50)
    plot_histogram(base_duration_new, filename='base_duration_new_histogram.png', title='Base Duration (New)', xlabel='Duration', ylabel='Frequency', bins=50)
    plot_histogram(base_duration_filter, filename='base_duration_filter_histogram.png', title='Base Duration Filtered', xlabel='Duration', ylabel='Frequency', bins=50)
    plot_histogram(head_duration_filter, filename='head_duration_filter_histogram.png', title='Head Duration Filtered', xlabel='Duration', ylabel='Frequency', bins=50)
    sweperf_data = dataset_with_efficiency_test
save_dataset(dataset_with_efficiency_test, efficiency_path)