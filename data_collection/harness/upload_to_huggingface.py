from datasets import load_from_disk, DatasetDict
import json
from harness.utils import filter_outliers, find_max_significant_improvement
import numpy as np

dataset = load_from_disk("../datasets/efficiency_dataset/efficiency-instances_swebench.efficiency_coverage_0627.single_runs_p1_2.with_patch_functions.with_test_functions")
print(dataset)

keys_to_keep = ["repo", "instance_id", "patch", "test_patch", "base_commit", "head_commit", "created_at", "version", "duration_changes", "efficiency_test", 'patch_functions', 'problem_statement_oracle', 'test_functions', 'problem_statement_end2end']

filtered_dataset = dataset.select_columns(keys_to_keep)
filtered_dataset = filtered_dataset.rename_columns({'problem_statement_end2end': 'problem_statement_realistic'})
human_performance = []
for idx, data in enumerate(filtered_dataset):
    efficiency_test = data['efficiency_test']
    duration_changes = json.loads(data['duration_changes'])
    ht = []
    for test in efficiency_test:
        duration_change_base = filter_outliers([duration_change[test]["base"] for duration_change in duration_changes])
        duration_change_head = filter_outliers([duration_change[test]["head"] for duration_change in duration_changes])
        avg_base = np.mean(duration_change_base)
        avg_head = np.mean(duration_change_head)
        ht.append(find_max_significant_improvement(duration_change_head, duration_change_base))
    human_performance.append(sum(ht)/len(ht))

filtered_dataset = filtered_dataset.add_column("human_performance", human_performance)
print(filtered_dataset)
print(filtered_dataset[0])
upload_dataset = DatasetDict({"test": filtered_dataset})
upload_dataset.push_to_hub("SWE-Perf/SWE-perf")
