# # Example call
python -m harness.get_runtimes_pytest \
    --dataset_name ../datasets/pandas/versions/pandas-task-instances_versions.non-empty.jsonl \
    --run_id all_dataset \
    --cache_level instance \
    --max_workers 100

python -m harness.get_runtimes_pytest \
    --dataset_name ../datasets/pandas/versions/pandas-task-instances_versions.non-empty.jsonl \
    --run_id all_dataset_run2 \
    --cache_level instance \
    --max_workers 100

python -m harness.get_runtimes_pytest \
    --dataset_name ../datasets/pandas/versions/pandas-task-instances_versions.non-empty.jsonl \
    --run_id all_dataset_run3 \
    --cache_level instance \
    --max_workers 100