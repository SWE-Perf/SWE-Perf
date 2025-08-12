# # Example call for getting versions by building the repo locally
python -m versioning.get_versions \
    --instances_path "../datasets/pandas/tasks/pandas-task-instances.jsonl" \
    --retrieval_method execution \
    --conda_env "pandas-dev" \
    --num_workers 2 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/pandas/versions/"
python scripts/filter_empty_version.py  ../datasets/pandas/versions/pandas-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/MONAI/tasks/MONAI-task-instances.jsonl" \
    --retrieval_method execution \
    --conda_env "MONAI" \
    --num_workers 2 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/MONAI/versions/"
python scripts/filter_empty_version.py  ../datasets/MONAI/versions/MONAI-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/moto/tasks/moto-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "moto" \
    --num_workers 2 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/moto/versions/"
python scripts/filter_empty_version.py  ../datasets/moto/versions/moto-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/mypy/tasks/mypy-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "mypy" \
    --num_workers 2 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/mypy/versions/"
python scripts/filter_empty_version.py  ../datasets/mypy/versions/mypy-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/dvc/tasks/dvc-task-instances.jsonl" \
    --retrieval_method execution \
    --conda_env "dvc" \
    --num_workers 2 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/dvc/versions/"
python scripts/filter_empty_version.py  ../datasets/dvc/versions/dvc-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/dask/tasks/dask-task-instances.jsonl" \
    --retrieval_method execution \
    --conda_env "test-environment-310" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/dask/versions/"
python scripts/filter_empty_version.py  ../datasets/dask/versions/dask-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/conan/tasks/conan-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "conan" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/conan/versions/"
python scripts/filter_empty_version.py  ../datasets/conan/versions/conan-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/pydantic/tasks/pydantic-task-instances.jsonl" \
    --retrieval_method execution \
    --conda_env "pydantic" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/pydantic/versions/"
python scripts/filter_empty_version.py  ../datasets/pydantic/versions/pydantic-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/bokeh/tasks/bokeh-task-instances.jsonl" \
    --retrieval_method execution \
    --conda_env "bk-test" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/bokeh/versions/"
python scripts/filter_empty_version.py  ../datasets/bokeh/versions/bokeh-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/modin/tasks/modin-task-instances.jsonl" \
    --retrieval_method execution \
    --conda_env "modin" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/modin/versions/"
python scripts/filter_empty_version.py  ../datasets/modin/versions/modin-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/hydra/tasks/hydra-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "hydra" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/hydra/versions/"
python scripts/filter_empty_version.py  ../datasets/hydra/versions/hydra-task-instances_versions.json


cd versioning
python -m extract_web.get_versions_astropy
python scripts/filter_empty_version.py  ../datasets/astropy/versions/astropy-task-instances_versions.json


cd versioning
python -m extract_web.get_versions_xarray
python scripts/filter_empty_version.py  ../datasets/xarray/versions/xarray-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/django/tasks/django-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "django" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/django/versions/"
python scripts/filter_empty_version.py  ../datasets/django/versions/django-task-instances_versions.json


cd versioning
python -m extract_web.get_versions_matplotlib
python scripts/filter_empty_version.py  ../datasets/matplotlib/versions/matplotlib-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/scikit-learn/tasks/scikit-learn-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "scikit-learn" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/scikit-learn/versions/"
python scripts/filter_empty_version.py  ../datasets/scikit-learn/versions/scikit-learn-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/sympy/tasks/sympy-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "sympy" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/sympy/versions/"
python scripts/filter_empty_version.py  ../datasets/sympy/versions/sympy-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/sphinx/tasks/sphinx-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "sphinx" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/sphinx/versions/"
python scripts/filter_empty_version.py  ../datasets/sphinx/versions/sphinx-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/pytest/tasks/pytest-task-instances.jsonl" \
    --retrieval_method build \
    --conda_env "pytest" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/pytest/versions/"
python scripts/filter_empty_version.py  ../datasets/pytest/versions/pytest-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/pylint/tasks/pylint-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "pylint" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/pylint/versions/"
python scripts/filter_empty_version.py  ../datasets/pylint/versions/pylint-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/seaborn/tasks/seaborn-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "seaborn" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/seaborn/versions/"
python scripts/filter_empty_version.py  ../datasets/seaborn/versions/seaborn-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/flask/tasks/flask-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "flask" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/flask/versions/"
python scripts/filter_empty_version.py  ../datasets/flask/versions/flask-task-instances_versions.json


python -m versioning.get_versions \
    --instances_path "../datasets/requests/tasks/requests-task-instances.jsonl" \
    --retrieval_method github \
    --conda_env "requests" \
    --num_workers 4 \
    --path_conda "<path_to_conda>" \
    --testbed "../testbed" \
    --output_dir "../datasets/requests/versions/"
python scripts/filter_empty_version.py  ../datasets/requests/versions/requests-task-instances_versions.json
