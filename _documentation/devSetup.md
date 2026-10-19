# Developer Setup Guide

This document provides complete setup instructions for this repository, including managing dependencies with `uv` and linking the [Unitree Robotics Python SDK (`unitree_sdk2_python`)](https://github.com/unitreerobotics/unitree_sdk2_python) as a local editable package.

---

## Project Directory Structure Requirement

> **Directory Requirement:** The Unitree Robotics Python SDK (`unitree_sdk2_python`) **MUST** be installed in the parent directory (`..`), exactly one directory level above this project repository. This parent directory location is required so `uv` can resolve the local editable dependency source cleanly across development environments.

Expected layout:

```text
repos/                          # Parent workspace folder
├── unitree_sdk2_python/        # Cloned Unitree Python SDK repository
└── unitree-robotics-scripts/    # Project repository (containing pyproject.toml)
```

## 1. Install `uv`

Install `uv` on your machine using your system package manager or installer:

* **macOS**: `brew install uv`
* **Linux**: [Install via your Linux distribution package manager or Astral installer](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer).
* **Windows**: `winget install astral-sh.uv` or other options [here](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer)

Verify installation:
`uv --version`


## 2. Clone the Repositories

Navigate to your workspace directory, clone the SDK into the parent directory, and enter your project folder:

1. Navigate to your workspace root directory (e.g. `cd ..`)
2. Clone the Unitree Robotics Python SDK repository into the parent directory:
   `git clone https://github.com/unitreerobotics/unitree_sdk2_python.git`
3. Navigate into this project repository:
   `cd unitree-robotics-scripts`


## 3. Install Dependencies

Install packages with:

```text
uv sync --all-groups
```

### Dependency Configuration Details

`uv` records the local SDK path in `pyproject.toml` under `tool.uv.sources`:
* `unitree-sdk2py = { path = "../unitree_sdk2_python", editable = true }`

Top-level dependency groups (`robot-preinstalled` and `dev`) are declared under `dependency-groups` at the bottom of `pyproject.toml`.


## 4. Working with `uv` and Python

### Running Scripts
`uv run` automatically uses the virtual environment inside `.venv` without requiring manual shell activation:

* Run a Python script:
  `uv run python devops/verify_sdk-v5.py`
* Run on a specific robot network interface:
  `uv run python devops/verify_sdk-v5.py eth0`

### Quality Tools
* **Ruff (Linter & Formatter)**: `uv run ruff check`
* **Mypy (Static Type Checking)**: `uv run mypy .`
* **Pytest**: `uv run pytest`


## 5. Verification & Diagnostics

Run the diagnostic verification script to validate that dependencies, local SDK package links, IDL telemetry structures, and DDS channels are functional:

`uv run python devops/verify_sdk-v5.py`

The script performs a 3-step diagnostic check:
1. **Dependency Validation**: Checks availability of `numpy`, `cyclonedds`, and `opencv-python`.
2. **SDK Package Import**: Confirms `unitree_sdk2py` import from `../unitree_sdk2_python` and resolves IDL telemetry structures (`LowState_`).
3. **DDS Channel Initialization**: Tests binding on the platform loopback interface (`lo0` on macOS, `lo` on Linux, `127.0.0.1` on Windows).