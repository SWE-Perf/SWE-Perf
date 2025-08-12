python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/astropy-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/matplotlib-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/seaborn-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/flask-task-instances_versions.non-empty.json.efficiency \
    --run_id coverage \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/requests-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/xarray-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/pylint-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/pytest-task-instances_versions.non-empty.json.efficiency \
    --run_id coverage \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/scikit-learn-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/sphinx-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/sympy-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100

python -m harness.check_validation_coverage2 --dataset_name astropy
# python -m harness.check_validation_all_runs --dataset_name django
python -m harness.check_validation_coverage2 --dataset_name matplotlib
python -m harness.check_validation_coverage2 --dataset_name seaborn
python -m harness.check_validation_coverage2 --dataset_name flask
python -m harness.check_validation_coverage2 --dataset_name requests
python -m harness.check_validation_coverage2 --dataset_name xarray
python -m harness.check_validation_coverage2 --dataset_name pylint
python -m harness.check_validation_coverage2 --dataset_name pytest
python -m harness.check_validation_coverage2 --dataset_name scikit-learn
python -m harness.check_validation_coverage2 --dataset_name sphinx
python -m harness.check_validation_coverage2 --dataset_name sympy

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/pandas-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name pandas

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/moto-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name moto

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/mypy-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name mypy

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/dvc-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name dvc

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/dask-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name dask

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/conan-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name conan

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/pydantic-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name pydantic

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/bokeh-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name bokeh

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/modin-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name modin

python -m harness.check_validation_coverage \
    --dataset_name ../datasets/efficiency_dataset/hydra-task-instances_versions.non-empty.json.efficiency_0627 \
    --run_id coverage_0627 \
    --cache_level instance \
    --max_workers 100
python -m harness.check_validation_coverage2 --dataset_name hydra
