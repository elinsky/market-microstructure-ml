# CLAUDE.md

This file provides guidance to Claude Code when working on this repository.

## Development Environment

- **Python version**: 3.11
- **Virtual environment**: pyenv virtualenv named `quotewatch`
- **Activate**: `pyenv activate quotewatch`

## Common Commands

```bash
# Install dependencies (including dev)
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Linting
black .
ruff check .
mypy src

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

## Conventions

- **TDD**: Write tests first for each component
- **Formatting**: black (88 char line length)
- **Linting**: ruff
- **Type checking**: mypy
- **Test coverage target**: 90%+