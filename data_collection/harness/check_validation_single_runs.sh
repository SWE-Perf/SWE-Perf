python -m harness.check_validation_single_runs_ \
    --dataset_name  ../datasets/efficiency_dataset/efficiency-instances_swebench.efficiency_coverage_0627 \
    --run_id single_runs_0627 \
    --cache_level instance \
    --max_workers 20

python -m harness.check_validation_single_runs2

python -m harness.check_validation_single_runs_ \
    --dataset_name  ../datasets/efficiency_dataset/efficiency-instances_swebench.efficiency_coverage_0627.single_runs_p1 \
    --run_id single_runs_0627_2 \
    --cache_level instance \
    --max_workers 20

python -m harness.check_validation_single_runs3
