# SWE-Perf Oracle Inference Guide

This guide describes how to run inference for **SWE-Perf** in the *Oracle* setting.

## 1. Generate Prompts

In this step, you will collect the oracle-related source files and assemble them into prompts for the large language model.

Command:

```bash
python -m make_datasets.create_text_dataset \
    --dataset_name_or_path SWE-Perf/SWE-Perf \
    --output_dir ../../datasets/base_datasets/ \
    --prompt_style efficiency \
    --file_source oracle \
    --split test
```

## 2. Run Inference with an LLM

This step follows the same procedure as in [SWE-Bench’s inference guide](https://github.com/SWE-bench/SWE-bench/blob/main/docs/reference/inference.md).
The prompts generated in step 1 will be fed into the large language model to produce outputs.

Example with Anthropic Claude:

```bash
export ANTHROPIC_API_KEY=<your key>

python -m run_api \
    --dataset_name_or_path ../../datasets/base_datasets/SWE-Perf__efficiency__fs-oracle \
    --model_name_or_path claude-3 \
    --output_dir ../../datasets/outputs
```

## 3. Convert Outputs to the Required Format

Our evaluation code accepts input in unified diff format.
This step converts the model output into the format required for evaluation.

```bash
python -m transfer_repair.transfer_repair \
    --model_output_path ../datasets/outputs/output.jsonl \
    --dataset_path ../../datasets/base_datasets/SWE-Perf__efficiency__fs-oracle
```

The converted file will be saved as `../../datasets/outputs/output_repair.jsonl` .

You can then run the evaluation scripts located in the [evaluation](/evaluation/) directory to further assess performance.