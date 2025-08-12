python -m harness.check_validation_function \
    --dataset_name ../datasets/efficiency_dataset/efficiency-instances_swebench.efficiency_coverage_0627.single_runs_p1_2.with_patch_functions \
    --run_id function \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_function2
