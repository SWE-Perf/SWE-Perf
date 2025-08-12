
python -m run_evaluation \
    --dataset_name  SWE-Perf/SWE-Perf \
    --split test \
    --predictions_path "../datasets/outputs/outputs.jsonl" \
    --run_id evaluation \
    --cache_level instance \
    --max_workers 20


python -m check_evaluation \
    --dataset_dir  SWE-Perf/SWE-Perf \
    --split test \
    --log_root "../datasets/logs/run_evaluation/evaluation/model/" \
    --output_path "../datasets/outputs/model_result.csv"