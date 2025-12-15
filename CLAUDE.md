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

## Test Style

Tests follow the **GIVEN/WHEN/THEN** pattern for clarity and readability:

```python
def test_order_book_returns_none_for_empty_book():
    """Empty order book returns None for mid price."""
    # GIVEN an empty order book
    book = OrderBook(depth=3)

    # WHEN we get the snapshot
    snapshot = book.get_snapshot()

    # THEN mid_price is None
    assert snapshot.mid_price is None
```

**Guidelines:**
- **WHEN should be one line** - test one behavior per test
- **Test names describe the scenario** - `test_<what>_<condition>_<expected>`
- **Docstring states the expected behavior** in plain English
- **Use helper functions** to reduce setup boilerplate (e.g., `_make_snapshot()`)
- **Avoid testing implementation details** - test behavior, not internals