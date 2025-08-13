SWE-bench Docker Architecture (Overview and Integration)

1. Layers
- Base Image: OS + system toolchain + Python. Rarely rebuilt.
- Environment Image: Python deps for target repo; caches wheels/layers. Rebuilt when lock/requirements change.
- Instance Image: Checkout repo at base_commit, apply test_patch (dataset), then apply model patch (golden). Built per instance/patch.

2. Build/Cache
- Base pinned by Dockerfile digest.
- Environment keyed by requirements/lockfiles; wheel cache speeds installs.
- Instance keyed by (repo, base_commit, test_patch, model patch).

3. Execution Flow
- Clone/checkout base_commit.
- Build Environment (pip/uv install, possibly editable install).
- Apply test_patch (enables FAIL_TO_PASS checks), then golden patch.
- Run tests with timeouts; stream logs; collect results.
- Store logs in logs/build_images and logs/run_evaluation; results in evaluation_results.

4. Validator Integration
- Validator produces predictions (instance_id, model_patch).
- Invokes: `python -m swebench.harness.run_evaluation --dataset_name <name> --predictions_path <file> --max_workers <N> --run_id <id> [--instance_ids ...] [--namespace '']`.
- On ARM (e.g., Mac M-series) pass `--namespace ''` to force local builds (per swebench docs on PyPI).
- Validator reads tail logs for CI, checks harness RC, can further inspect evaluation_results for FTP/PTP.

5. Requirements Placement
- System deps in Base.
- Python deps in Environment; reused across instances for same repo/env commit.
- Repo-specific setup executed during Environment/Instance build as needed.

6. Timeouts/Resources
- Harness parallelism via --max_workers (recommendation: < 0.75*cores, capped at 24).
- Outer process timeout per instance from validator configuration.
- Disk: ~120GB free recommended; x86_64 preferred; ARM experimental (PyPI swebench page).

7. Failure Modes
- Build failures (Base/Environment/Instance): capture build logs and stderr tail.
- Patch apply failures: report conflicts/hunks; stop with actionable message.
- Test timeouts/OOM: mark as execution failure; suggest lowering parallelism.
- Network restrictions: note pull/build failures; advise runner network policy check.

8. Artifacts
- Persist Docker build logs, run logs, evaluation results directory.
- Optional: JUnit/Markdown summaries for CI checks/comments.


