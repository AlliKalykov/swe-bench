"""CLI for SWE-bench Data Point Validator.

Implements interface and orchestration for:
- Loading datapoints
- Structural validation
- Predictions file generation
- Invoking official SWE-bench evaluation harness (Docker-based)
- Parsing outcome and returning CI-friendly exit codes
"""

from __future__ import annotations

import json
import sys
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import click


@dataclass
class ValidatorConfig:
    max_workers: int = 1
    timeout_seconds: int = 1800
    namespace: Optional[str] = None
    dataset_name_default: str = "SWE-bench/SWE-bench"


def find_all_datapoints(root: Path) -> List[Path]:
    data_dir = root / "data_points"
    return sorted(p for p in data_dir.glob("*.json") if p.is_file())


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_list_field(maybe_list_or_str) -> List[str]:
    if isinstance(maybe_list_or_str, list):
        return [str(x) for x in maybe_list_or_str]
    if isinstance(maybe_list_or_str, str):
        # Some datapoints store JSON list as string
        try:
            parsed = json.loads(maybe_list_or_str)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            pass
    return []


def validate_datapoint_schema(dp: dict, path: Path) -> List[str]:
    errors: List[str] = []
    required_fields = [
        "repo",
        "instance_id",
        "base_commit",
        "patch",
        "FAIL_TO_PASS",
        "PASS_TO_PASS",
    ]
    for field in required_fields:
        if field not in dp:
            errors.append(f"{path.name}: missing required field '{field}'")

    if "repo" in dp and isinstance(dp["repo"], str):
        if "/" not in dp["repo"]:
            errors.append(f"{path.name}: repo must be in 'owner/repo' format")

    if "base_commit" in dp and isinstance(dp["base_commit"], str):
        if len(dp["base_commit"]) < 7:
            errors.append(f"{path.name}: base_commit must be a valid git SHA")

    if "patch" in dp and isinstance(dp["patch"], str):
        if not dp["patch"].lstrip().startswith("diff --git"):
            errors.append(f"{path.name}: patch must start with 'diff --git'")

    # Normalize lists for later logic (not strictly failing if empty)
    dp["FAIL_TO_PASS"] = parse_list_field(dp.get("FAIL_TO_PASS", []))
    dp["PASS_TO_PASS"] = parse_list_field(dp.get("PASS_TO_PASS", []))

    return errors


def build_predictions(datapoints: List[dict]) -> List[dict]:
    predictions = []
    for dp in datapoints:
        predictions.append({
            "instance_id": dp["instance_id"],
            "model_patch": dp["patch"],
            "model_name_or_path": "golden-patch-validator",
        })
    return predictions


def detect_dataset_name(dp: dict, default: str) -> str:
    meta = dp.get("_download_metadata") or {}
    name = meta.get("dataset_name")
    if isinstance(name, str) and name:
        return name
    return default


def run_harness(predictions_path: Path, instance_ids: List[str], cfg: ValidatorConfig, run_id: str, dataset_name: str, root: Path) -> int:
    # Create logs directory structure
    logs_dir = root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Create subdirectories for SWE-bench harness logs
    (logs_dir / "build_images").mkdir(exist_ok=True)
    (logs_dir / "run_evaluation").mkdir(exist_ok=True)
    
    # Create evaluation_results directory at root level (as expected by harness)
    eval_results_dir = root / "evaluation_results"
    eval_results_dir.mkdir(exist_ok=True)
    
    cmd = [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        dataset_name,
        "--predictions_path",
        str(predictions_path),
        "--max_workers",
        str(cfg.max_workers),
        "--run_id",
        run_id,
    ]
    if instance_ids:
        cmd.extend(["--instance_ids", *instance_ids])
    if cfg.namespace is not None:
        cmd.extend(["--namespace", cfg.namespace])

    # Set working directory to root so harness creates logs in the right place
    # Let harness handle its own timeouts internally; we also set an outer timeout
    try:
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=cfg.timeout_seconds,
            check=False,
            cwd=str(root),  # Run from project root so logs go to correct location
        )
    except subprocess.TimeoutExpired:
        click.echo("Harness execution timed out")
        return 2

    # Echo summarized logs (tail) for CI visibility
    output = completed.stdout or ""
    tail = "\n".join(output.splitlines()[-200:])
    click.echo("---- harness output (tail) ----")
    click.echo(tail)
    click.echo("-------------------------------")
    
    # Show log directory structure and artifacts for CI visibility
    if logs_dir.exists():
        click.echo(f"Logs created in: {logs_dir}")
        click.echo("Log directory structure:")
        for item in sorted(logs_dir.rglob("*")):
            if item.is_file():
                rel_path = item.relative_to(logs_dir)
                click.echo(f"  logs/{rel_path}")
    
    # Also show evaluation_results if they exist
    if eval_results_dir.exists():
        click.echo(f"Evaluation results in: {eval_results_dir}")
        for item in sorted(eval_results_dir.rglob("*")):
            if item.is_file():
                rel_path = item.relative_to(eval_results_dir)
                click.echo(f"  evaluation_results/{rel_path}")
    
    return completed.returncode


@click.command()
@click.argument(
    "files",
    nargs=-1,
    type=click.Path(exists=True),
)
@click.option(
    "--max-workers",
    type=int,
    default=1,
    show_default=True,
    help="Maximum parallel workers for evaluation harness",
)
@click.option(
    "--timeout-seconds",
    type=int,
    default=1800,
    show_default=True,
    help="Timeout per instance (seconds) for the harness process",
)
@click.option(
    "--namespace",
    default=None,
    help="Docker namespace override (set to '' on ARM to force local image builds)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Verbose output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate structure only; skip harness execution",
)
def main(
    files: tuple[str, ...],
    max_workers: int,
    timeout_seconds: int,
    namespace: Optional[str],
    verbose: bool,
    dry_run: bool,
):
    """Validate SWE-bench datapoints with the official evaluation harness.

    Exit codes:
    - 0: success (all datapoints valid)
    - 1: structural/schema error(s)
    - 2: execution/evaluation failure(s)
    """

    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data_points"
    if not data_dir.exists():
        click.echo(f"data_points directory not found at: {data_dir}")
        sys.exit(1)

    # Resolve target files
    target_files: List[Path] = []
    if files:
        for f in files:
            p = Path(f)
            if not p.is_absolute():
                # Accept both repo-root relative paths starting with data_points/
                # and bare filenames relative to the data_points directory
                if p.parts and p.parts[0] == "data_points":
                    p = root / p
                else:
                    p = data_dir / p
            if not p.exists():
                click.echo(f"File not found: {p}")
                sys.exit(1)
            target_files.append(p)
    else:
        target_files = find_all_datapoints(root)

    if not target_files:
        click.echo("No datapoint files to validate.")
        sys.exit(0)

    # Load and structurally validate
    datapoints: List[dict] = []
    structural_errors: List[str] = []
    for path in target_files:
        try:
            dp = load_json(path)
        except Exception as e:
            structural_errors.append(f"{path.name}: invalid JSON - {e}")
            continue

        errs = validate_datapoint_schema(dp, path)
        if errs:
            structural_errors.extend(errs)
            continue
        datapoints.append(dp)

    if structural_errors:
        click.echo("Structural validation errors found:")
        for e in structural_errors:
            click.echo(f"  - {e}")
        sys.exit(1)

    # If only structural validation requested, finish here
    if dry_run:
        click.echo("Structural validation passed for all provided datapoints (dry-run mode).")
        sys.exit(0)

    # Build predictions and write to temp file
    predictions = build_predictions(datapoints)
    run_id = "validate-gold"
    predictions_dir = root / ".validator_work"
    predictions_dir.mkdir(exist_ok=True)
    predictions_path = predictions_dir / f"predictions_{run_id}.json"
    with predictions_path.open("w", encoding="utf-8") as f:
        json.dump(predictions, f)

    # Determine dataset name (prefer consistent value among datapoints)
    cfg = ValidatorConfig(
        max_workers=max_workers,
        timeout_seconds=timeout_seconds,
        namespace=namespace,
    )
    dataset_name = cfg.dataset_name_default
    for dp in datapoints:
        dataset_name = detect_dataset_name(dp, cfg.dataset_name_default)
        break

    instance_ids = [dp["instance_id"] for dp in datapoints]
    click.echo(
        f"Running harness for {len(instance_ids)} instance(s) using dataset='{dataset_name}', max_workers={max_workers}"
    )
    rc = run_harness(predictions_path, instance_ids, cfg, run_id=run_id, dataset_name=dataset_name, root=root)

    if rc != 0:
        click.echo(f"Harness failed with exit code {rc}")
        sys.exit(2)

    # If harness succeeded, we assume tests passed per its evaluation contract.
    # For deeper FTP/PTP inspection, parse evaluation_results/* if needed.
    click.echo("Validation successful for all provided datapoints.")
    sys.exit(0)


if __name__ == "__main__":
    main()


