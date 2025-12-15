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

## Git Workflow

**Always work in branches and use PRs** - never push directly to main.

```bash
# 1. Create a feature branch
git checkout -b feature-x

# 2. Make changes and commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: add feature x"

# 3. Push branch and open PR
git push -u origin feature-x
gh pr create --fill

# 4. CI runs on the PR - if it fails, fix and push again

# 5. Before merging, rebase onto main for fast-forward merge
git fetch origin
git rebase origin/main
git push --force-with-lease

# 6. Merge with fast-forward (use "Rebase and merge" in GitHub UI)
```

Branch protection blocks merging until `lint` and `test` jobs pass.

**Use fast-forward merges** (rebase and merge) for a clean linear history - no merge commits.

## Documentation & Tracking

**Everything gets tracked, everything gets documented.**

### GitHub Issues
- **Create issues before coding** - all work should be tracked in an issue
- **Groom issues before starting** - add requirements, tasks, acceptance criteria
- **Capture ideas as issues** - create backlog issues for "someday" work
- Update issue checkboxes as tasks are completed
- Link PRs to issues with "Closes #XX" in PR description
- Update epic checkboxes when child issues are completed
- Add implementation notes to issues when decisions are made

### Documentation Updates
Each PR should include relevant doc updates:
- `docs/architecture.md` - Component diagrams, data flow changes
- `docs/design/data-layer.md` - Implementation progress section
- `CHANGELOG.md` - User-facing changes under [Unreleased]
- Code docstrings - Keep in sync with implementation

### Commit Discipline
- Atomic commits - one logical change per commit
- Update docs in the same commit as code changes (not separate)
- PR description summarizes what changed and why

## Project Structure

```
src/
├── ingest/          # WebSocket client, order book
├── features/        # Feature extraction, labeling
├── model/           # ML classifiers
├── dashboard/       # Dash app
└── run_live.py      # Main entry point

tests/               # Unit tests
docs/                # Documentation
  ├── prd.md         # Product requirements
  ├── architecture.md
  ├── mldesign.md
  └── design/        # Design docs for epics
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