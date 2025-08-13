# SWE-bench Data Point Validator

A comprehensive validation system for SWE-bench datapoints using the official Docker-based evaluation harness. This tool ensures data quality and provides automated CI/CD validation for pull requests.

## 🏗️ Project Structure

```
├── data_points/                    # SWE-bench data points (JSON files)
│   ├── astropy__astropy-11693.json      # Valid example
│   └── astropy__astropy-11693-fail.json # Invalid example  
├── swe_bench_validator/            # Main validator implementation
│   ├── __init__.py
│   ├── __main__.py
│   └── cli.py                      # CLI interface and validation logic
├── swe_bench_downloader/           # Data point downloader utility
├── .github/workflows/              # GitHub Actions CI/CD
│   └── validate-datapoints.yml    # Automated validation workflow
├── validator-config.yml            # Configuration file for validation rules
├── swe-bench-docker-architecture.md # Docker architecture documentation
└── README.md                       # This file
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **Docker** (for SWE-bench harness execution)
- **UV package manager** (recommended) or pip
- **120GB+ free disk space** (for Docker images and build artifacts)
- **x86_64 architecture preferred** (ARM/Mac M-series supported with `--namespace ''`)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd swe-bench-validator
   ```

2. **Install UV package manager:**
   ```bash
   pip install uv
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```

4. **Install SWE-bench harness:**
   ```bash
   pip install swebench
   ```

### Basic Usage

#### 1. Dry-run validation (structure only)
```bash
uv run python -m swe_bench_validator --dry-run --files data_points/astropy__astropy-11693.json
```

#### 2. Full validation with Docker harness
```bash
uv run python -m swe_bench_validator --files data_points/astropy__astropy-11693.json --max-workers 1 --timeout-seconds 1800
```

#### 3. ARM/Mac M-series users
```bash
uv run python -m swe_bench_validator --files data_points/astropy__astropy-11693.json --max-workers 1 --timeout-seconds 1800 --namespace ''
```

#### 4. Validate all data points
```bash
uv run python -m swe_bench_validator --max-workers 1 --timeout-seconds 1800
```

## 📋 Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--max-workers` | 1 | Maximum parallel workers for evaluation harness |
| `--timeout-seconds` | 1800 | Timeout per instance (seconds) for the harness process |
| `--namespace` | None | Docker namespace override (set to `''` on ARM to force local image builds) |
| `--verbose` | False | Verbose output |
| `--dry-run` | False | Validate structure only; skip harness execution |

## 🔧 Configuration

The validator uses [`validator-config.yml`](validator-config.yml) for configuration. Key settings:

- **Validation rules**: Required fields, format validation
- **Harness settings**: Workers, timeouts, Docker namespace
- **Output settings**: Log structure, artifact paths
- **Docker settings**: Resource limits, ARM support

## 📁 Output Structure

After validation, the following directories are created:

```
logs/
├── build_images/           # Docker image build logs
│   ├── base/              # Base image logs
│   ├── env/               # Environment image logs  
│   └── instances/         # Instance image logs
└── run_evaluation/        # Test execution logs
    └── validation_*/      # Per-validation run logs
        └── golden/        # Golden patch results
            └── instance_id/
                ├── eval.sh
                ├── patch.diff
                ├── report.json
                ├── run_instance.log
                └── test_output.txt

evaluation_results/        # Final evaluation results
```

## 🤖 GitHub Actions Integration

The project includes automated validation via GitHub Actions:

- **Triggers**: Changes to `data_points/**` files
- **Workflow**: [`.github/workflows/validate-datapoints.yml`](.github/workflows/validate-datapoints.yml)
- **Artifacts**: Automatically uploads logs and evaluation results
- **Status checks**: Provides green/red status for pull requests

### Example Workflow Usage

1. **Add/modify data point**: Edit files in `data_points/`
2. **Create pull request**: GitHub Actions automatically validates changes
3. **Review results**: Check status and download artifacts if needed

## 📖 Data Point Format

Valid SWE-bench data points must include:

```json
{
  "repo": "owner/repository",
  "instance_id": "unique_identifier", 
  "base_commit": "git_sha_hash",
  "patch": "diff --git a/file.py b/file.py\n...",
  "FAIL_TO_PASS": ["test1", "test2"],
  "PASS_TO_PASS": ["test3", "test4"]
}
```

See [`data_points/astropy__astropy-11693.json`](data_points/astropy__astropy-11693.json) for a complete valid example.

## 🐛 Troubleshooting

### Common Issues

1. **Docker permission errors**:
   ```bash
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

2. **ARM/Mac M-series build failures**:
   ```bash
   # Force local builds
   uv run python -m swe_bench_validator --namespace '' --files <file>
   ```

3. **Disk space issues**:
   ```bash
   # Clean Docker images
   docker system prune -a
   ```

4. **Memory/timeout issues**:
   ```bash
   # Reduce workers and increase timeout
   uv run python -m swe_bench_validator --max-workers 1 --timeout-seconds 3600
   ```

### Exit Codes

- **0**: Success (all datapoints valid)
- **1**: Structural/schema error(s)
- **2**: Execution/evaluation failure(s)

## 📚 Documentation

- **Docker Architecture**: [`swe-bench-docker-architecture.md`](swe-bench-docker-architecture.md)
- **SWE-bench Reference**: https://pypi.org/project/swebench/
- **Configuration**: [`validator-config.yml`](validator-config.yml)

## 🔗 Related Tools

- **Downloader**: Use `swe_bench_downloader/` to fetch data points from SWE-bench datasets
- **SWE-bench Harness**: Official evaluation harness for running tests in Docker containers

## 📄 License

This project follows the same license as the SWE-bench project.
