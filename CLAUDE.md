# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Lint/Test Commands
- Environment setup: `uv venv`
- Install dependencies: `uv pip install -e ".[dev]"`
- Run calibration: `uv run -m led_strip_calibrator process path/to/images`
- Run with options: `uv run -m led_strip_calibrator process path/to/images --method threshold --threshold 180 --visualize`
- Lint: `ruff check .`
- Format: `ruff format .`
- Type check: `mypy led_strip_calibrator`
- Tests: `pytest`
- Single test: `pytest tests/test_file.py::test_function`

Note: This project uses `uv run` to execute Python scripts within the virtual environment.

## Code Style Guidelines
- **Python**: Version 3.14+ with type hints throughout
- **MicroPython**: Use WLED library for LED control on ESP32
- **Formatting**: Follow ruff defaults (4 spaces, 88 char line length)
- **Imports**: Group standard library, third-party, then local imports
- **Naming**: snake_case for variables/functions, CamelCase for classes
- **Docstrings**: Use Google-style docstrings for all functions/classes
- **Error Handling**: Use explicit try/except with specific exceptions
- **Comments**: Document complex algorithms (especially centroid detection)
- **Constants**: Use UPPER_CASE for constants, especially pin assignments