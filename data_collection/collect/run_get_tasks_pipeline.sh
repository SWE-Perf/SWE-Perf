#!/usr/bin/env bash

export GITHUB_TOKENS=<github_tokon>

python -m collect.get_tasks_pipeline \
    --repos 'Project-MONAI/MONAI' \
    --path_prs '../datasets/MONAI/prs/' \
    --path_tasks '../datasets/MONAI/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'getmoto/moto' \
    --path_prs '../datasets/moto/prs/' \
    --path_tasks '../datasets/moto/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'python/mypy' \
    --path_prs '../datasets/mypy/prs/' \
    --path_tasks '../datasets/mypy/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'iterative/dvc' \
    --path_prs '../datasets/dvc/prs/' \
    --path_tasks '../datasets/dvc/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'dask/dask' \
    --path_prs '../datasets/dask/prs/' \
    --path_tasks '../datasets/dask/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'conan-io/conan' \
    --path_prs '../datasets/conan/prs/' \
    --path_tasks '../datasets/conan/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'pydantic/pydantic' \
    --path_prs '../datasets/pydantic/prs/' \
    --path_tasks '../datasets/pydantic/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'facebookresearch/hydra' \
    --path_prs '../datasets/hydra/prs/' \
    --path_tasks '../datasets/hydra/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'bokeh/bokeh' \
    --path_prs '../datasets/bokeh/prs/' \
    --path_tasks '../datasets/bokeh/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'modin-project/modin' \
    --path_prs '../datasets/modin/prs/' \
    --path_tasks '../datasets/modin/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'astropy/astropy' \
    --path_prs '../datasets/astropy/prs/' \
    --path_tasks '../datasets/astropy/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'django/django' \
    --path_prs '../datasets/django/prs/' \
    --path_tasks '../datasets/django/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'matplotlib/matplotlib' \
    --path_prs '../datasets/matplotlib/prs/' \
    --path_tasks '../datasets/matplotlib/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'mwaskom/seaborn' \
    --path_prs '../datasets/seaborn/prs/' \
    --path_tasks '../datasets/seaborn/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'pallets/flask' \
    --path_prs '../datasets/flask/prs/' \
    --path_tasks '../datasets/flask/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'psf/requests' \
    --path_prs '../datasets/requests/prs/' \
    --path_tasks '../datasets/requests/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'pydata/xarray' \
    --path_prs '../datasets/xarray/prs/' \
    --path_tasks '../datasets/xarray/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'pylint-dev/pylint' \
    --path_prs '../datasets/pylint/prs/' \
    --path_tasks '../datasets/pylint/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'pytest-dev/pytest' \
    --path_prs '../datasets/pytest/prs/' \
    --path_tasks '../datasets/pytest/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'scikit-learn/scikit-learn' \
    --path_prs '../datasets/scikit-learn/prs/' \
    --path_tasks '../datasets/scikit-learn/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'sphinx-doc/sphinx' \
    --path_prs '../datasets/sphinx/prs/' \
    --path_tasks '../datasets/sphinx/tasks/'

python -m collect.get_tasks_pipeline \
    --repos 'sympy/sympy' \
    --path_prs '../datasets/sympy/prs/' \
    --path_tasks '../datasets/sympy/tasks/'