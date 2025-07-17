import json
from collections import defaultdict
import os
import pandas as pd
from tqdm import tqdm
from sweperf.harness.log_parsers import MAP_REPO_TO_PARSER
import re
from collections import Counter
import matplotlib.pyplot as plt 
from tqdm import tqdm
from sweperf.harness.check_validation import load_dataset_, save_dataset
from argparse import ArgumentParser
import numpy as np
from sweperf.harness.utils import filter_outliers, find_max_significant_improvement
from sweperf.harness.test_spec import REPEAT_TIME


def get_runtimes_and_results(repo: str, log_path):
    if not os.path.exists(log_path):
        print(f"{log_path} not exist!")
        return None, None
    with open(log_path, "r") as file:
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

def calculate_performance_result(sweperf_data, log_root):
    without_prediction = 0
    without_run = 0
    run_failed = 0
    run_time = 0
    human_improved = []
    model_improved = []
    human_total = []
    for _, data in sweperf_data.iterrows():
        id = data['instance_id']
        duration_changes = data["duration_changes"]
        efficiency_test = data["efficiency_test"]
        # calculate human total
        ht = []
        for test in efficiency_test:
            duration_change_base = filter_outliers([duration_change[test]["base"] for duration_change in duration_changes])
            duration_change_head = filter_outliers([duration_change[test]["head"] for duration_change in duration_changes])
            avg_base = np.mean(duration_change_base)
            avg_head = np.mean(duration_change_head)
            ht.append(find_max_significant_improvement(duration_change_head, duration_change_base))
        human_total.append(sum(ht)/len(ht))

        # calculate model total
        if not os.path.exists(os.path.join(log_root, id, "run_instance.log")):
            without_prediction += 1
            continue
        if not os.path.exists(os.path.join(log_root, id, "report.json")):
            without_run += 1
            continue

        with open(os.path.join(log_root, id, "report.json"), "r") as file:
            report = json.load(file)
        
        durations = {}
        resutls = {}
        durations_base = {}
        results_base = {}
        for test in report.keys():
            if "base" in report[test]:
                durations_base_ = [rep["duration"] for rep in report[test]["base"].values()]
                durations_base_ = filter_outliers(durations_base_)
                # if len(durations_base_) != 10:
                #     print(len(durations_base_))
                durations_base[test] = durations_base_

                results_base_ = [rep["outcome"] for rep in report[test]["base"].values()]
                results_base[test] = set(results_base_) == {"passed"}
            if "human" in report[test]:
                durations_head_ = [rep["duration"] for rep in report[test]["human"].values()]
                durations_head_ = filter_outliers(durations_head_)
                # if len(durations_base_) != 10:
                #     print(len(durations_base_))
                durations[test] = durations_head_
                resutls[test] = set([rep["outcome"] for rep in report[test]["human"].values()]) == {"passed"}        
        # log_path = os.path.join(log_root, id, "test_output.txt")
        # results, durations = get_runtimes_and_results(data['repo'], log_path)
        # log_path = os.path.join(log_root, id, "test_output_base.txt")
        # results_base, durations_base = get_runtimes_and_results(data['repo'], log_path)
        if durations==None:
            # print(f"{log_root} {id} durations is None")
            run_failed+=1
            continue

        hi = []
        mi = []
        for test in efficiency_test:
            if test not in durations or test not in durations_base:
                # print(f"{log_root} {id} {test} not in durations or durations_base")
                run_failed += 1
                break
            if not results_base[test] or not resutls[test]:
                # print(f"{log_root} {id} {test} not in results or results_base")
                run_failed += 1
                break
            duration_change_base = filter_outliers([duration_change[test]["base"] for duration_change in duration_changes])
            duration_change_head = filter_outliers([duration_change[test]["head"] for duration_change in duration_changes])
            avg_base = np.mean(duration_change_base)
            avg_head = np.mean(duration_change_head)
            hi_sig = find_max_significant_improvement(duration_change_head, duration_change_base)
            # hi.append((avg_base - avg_head)/avg_base)
            hi.append(hi_sig)
            mi_sig = find_max_significant_improvement(durations[test], durations_base[test])
            mi.append(mi_sig)
            # mi.append((durations_base[test] - durations[test])/durations_base[test] if durations[test] < durations_base[test] else 0)
            # mi.append((avg_base - durations[test])/avg_base)
            # print(f"----------{id}--{test}--{len(efficiency_test)}---------")
            # print(f"hi: {(avg_base - avg_head)/avg_base}, {avg_base}, {avg_head}")
            # print(f"mi: {(durations_base[test] - durations[test])/durations_base[test]}, {durations_base[test]}, {durations[test]}")
            # print(f"hi: {hi_sig}, {avg_base}, {avg_head}")
            # print(f"mi: {mi_sig}, {np.mean(durations_base[test])}, {np.mean(durations[test])}")

        else:
            # print(f"Id {id}, Test {test} mi: {sum(mi)/len(mi)}")
            human_improved.append(sum(hi)/len(hi))
            model_improved.append(sum(mi)/len(mi))

    with_prediction = len(sweperf_data) - without_prediction
    total = len(sweperf_data)
    print(f"There are {len(sweperf_data)} data, {without_prediction} without prediction and {with_prediction} with prediction. ")
    print(f"There are {without_run/total} ({without_run}/{total}) failed patch, {(with_prediction - without_run)/total} ({with_prediction - without_run}/{total}) success patch")
    print(f"There are {run_failed/total} ({run_failed}/{total}) failed run, {(with_prediction - without_run - run_failed)/total} ({with_prediction - without_run - run_failed}/{total}) success run")
    print(f"Claude efficiency improved: {sum(model_improved)/total}")
    print(f"Human efficiency improved: {sum(human_improved)/total}")
    print(f"Human total efficiency improved: {sum(human_total)/total}")
    return {
        "model": log_root,
        "total": total,
        "with_prediction": with_prediction,
        "with_run": with_prediction - without_run,
        "success": with_prediction - without_run - run_failed,
        "model_improved": sum(model_improved),
        "human_improved": sum(human_improved),
        "human_total_improved": sum(human_total),
        "apply": (with_prediction - without_run)/total,
        "correctness": (with_prediction - without_run - run_failed)/total,
        "performance": sum(model_improved)/total,
        "human_performance": sum(human_improved)/total,
        "human_total_performance": sum(human_total)/total,
    }


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("--dataset_dir", default="sweperf_dataset", required=True, type=str, help="Name of dataset or path to JSON file.")
    parser.add_argument("--log_root", required=True, type=str, help="log path")
    parser.add_argument("--output_path", required=True, type=str, help="performence output path")
    args = parser.parse_args()

    output_path = args.output_path

    log_root = args.log_root
    sweperf_data = load_dataset_(args.dataset_dir)
    sweperf_data = pd.DataFrame(sweperf_data)
    results = []
    # performence_paths = []
    # for log_root in log_roots:
    print("================================")
    print(log_root)
    print("[total]")
    result = calculate_performance_result(sweperf_data, log_root)
    result["repo"] = "total"
    results.append(result)
    for repo, group in sweperf_data.groupby('repo'):
        print("================================")
        print(log_root)
        print(f"[{repo}]")
        result = calculate_performance_result(group, log_root)
        if result:
            result["repo"] = repo
            results.append(result)
    # save results to csv
    df = pd.DataFrame(results)
    log_instance = log_root.split('/')[-1]

    df.to_csv(output_path, index=False)

