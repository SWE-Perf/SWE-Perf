
# SWE-Perf Data Collection

This repository contains the pipeline and scripts used to construct **SWE-Perf**. The pipeline comprises five distinct phases.

## 🔄 Overview of the Collection Pipeline

The data collection process is designed to systematically identify and verify pull requests (PRs) that introduce measurable and stable performance improvements. Each PR is evaluated through multiple stages:

```
Phase 1: Collect PRs
Phase 2: Measure Codebase Performance
Phase 3: Identify Performance PRs
Phase 4: Verify Stability
Phase 5: Extract Optimization Targets
```


## 1️⃣ Phase 1: Collect Pull Requests (PRs)

We first collect PRs from 12 popular GitHub repositories (as used in SWE-bench), with the following key steps, inspired by prior work such as [SWE-bench](https://github.com/SWE-bench/SWE-bench) and [SWE-GYM dataset collections scripts](https://github.com/SWE-Gym/SWE-Bench-Fork):

* Crawl PRs and associated tasks:

  ```bash
  sh collect/run_get_tasks_pipeline.sh
  ```

* Determine repository versions:

  ```bash
  sh versioning/run_get_versions.sh
  ```

Unlike SWE-bench, we retain PRs regardless of whether they contribute tests. This is because our focus is on **performance**, not test correctness.


## 2️⃣ Phase 2: Measure Codebase Performance

Each PR produces an original and modified codebase. We run all unit tests on both versions to obtain runtime performance data:

* Execute unit tests inside Docker containers:

  ```bash
  sh harness/get_runtimes_pytest.sh
  ```

## 3️⃣ Phase 3: Identify Performance-Optimizing PRs

This phase identifies PRs that lead to statistically meaningful performance improvements through three steps.

### Step 1: Filter PRs with Performance Gains

We summarize runtime data and identify PRs with improved unit test runtimes:

```bash
sh harness/check_validation_all_runs.sh
```

Script Components:
- Runtime Information Aggregation: Consolidate runtime data from Phase 2.
- Performance Optimizing PR Extraction: Apply filtering criteria.

### Step 2: Identify Tests Exercising Human Patches

We run coverage analysis to select unit tests that actually exercise modified code:

```bash
sh harness/check_validation_coverage.sh
```
Script Components:
- Coverage Testing: Identify unit tests that execute modified code segments.
- Coverage Aggregation: Consolidate coverage data to ensure performance improvements are attributable to PR changes.

### Step 3: Merge Data Across Repositories

We combine PRs from multiple repositories into one dataset:

```bash
python -m harness.merge
```

## 4️⃣ Phase 4: Verify Stable Performance Improvements

We verify that observed performance gains are statistically stable and reproducible.
```bash
sh harness/check_validation_single_runs.sh
```
Script Components (4 main steps):
- Stable Performance Testing: Execute comprehensive performance validation.
- Unit Test Aggregation: Consolidate unit tests meeting stability criteria.
- Stable Performance Re-testing: Perform additional validation rounds.
- Instance Aggregation: Compile final instances meeting all stability requirements.

## 5️⃣ Phase 5: Extract Optimization Targets

We extract optimization target functions for two downstream evaluation settings:

### Oracle (File-Level)

Extract target functions directly modified in human patches:

```bash
python -m harness.make_datasets.create_text_dataset \
    --dataset_name_or_path <input_dataset> \
    --output_dir <output_dir> \
    --prompt_style get_function_from_patch \
    --file_source oracle \
    --split test
```

### Realistic (Repo-Level)

Identify functions dynamically executed during performance-relevant unit tests:

  ```bash
  sh harness/check_validation_function.sh
  ```

## 📦 Uploading the Dataset

### 1. Push Docker Images

Prepare and push Docker images used to run each codebase:

```bash
python -m harness.prepare_images --dataset_name <dataset_name> --max_workers <num>
bash push_all_images.sh
```

### 2. Upload to HuggingFace

Upload full dataset to the HuggingFace Hub:

```bash
python -m harness.upload_to_huggingface
```