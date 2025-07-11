<div align="center">
  <img src="misc/sweperf_logo.png" alt="SWE-Perf Logo" width="800"/>
</div>

<p align="center">
  <a href="https://swe-perf.github.io/">
    <img src="https://img.shields.io/badge/project-Home-b31b1b.svg" alt="arXiv Paper">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Data-blue" alt="Data">
  </a>
</p>

---

## What is SWE-Perf?

Optimizing code performance is paramount in software engineering, yet it remains a largely unexplored frontier for Large Language Models (LLMs). While models excel at fixing bugs, their ability to make code faster at a repository-scale is not well understood.

To address this, we introduce **SWE-Perf**, the first benchmark meticulously designed to evaluate LLMs on performance optimization tasks within genuine, complex **repository contexts**. Unlike benchmarks that focus on isolated code snippets, SWE-Perf challenges models to understand and modify **entire codebases**. The benchmark comprises **140 instances**, each derived from a real performance-improving pull request on a popular GitHub repository. For each instance, a model is provided with the full source code, a specific performance-related test, and the human expert's solution for reference. The core task is to generate a code patch that reduces the test's execution time without introducing bugs.

## How to Evaluate

Evaluate patch predictions on SWE-Perf with the following command:

```shell
python -m sweperf.harness.run_evaluation \
    --dataset_name SWE-Perf/SWE-Perf \
    --predictions_path <path_to_predictions> \
    --max_workers <num_workers> \
    --run_id <run_id> \

python -m sweperf.harness.check_evaluation \
        --dataset_dir  SWE-Perf/SWE-Perf \
        --log_root <path_to_log> \
        --output_path <csv_output_path>
```

## BibTeX

If you find our work useful, please consider citing our paper:
```bibtex
@article{he2025sweperf,
    title={SWE-Perf: Can Language Models Optimize Code Performance on Real-World Repositories?},
    author={He, Xinyi and Liu, Qian and Du, Mingzhe and Yan, Lin and Fan, Zhijie and Huang, Yiming and Yuan, Zejian and Ma, Zejun},
    journal={arXiv preprint arXiv:XXXX.XXXXX},
    year={2025}
}
```

## Contact & Acknowledgements

Please reach out to `qian.liu@tiktok.com` for questions or feedback on SWE-Perf. We welcome collaborations and suggestions for improving the benchmark. This work was conducted during Xinyi and Yiming's internship at TikTok.
