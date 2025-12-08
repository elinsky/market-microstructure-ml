# Contributing

## Development Setup

```bash
# Python 3.11+
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Code Style

```bash
# Format
black .

# Lint
ruff check .

# Type check
mypy src/
```

## Testing

```bash
pytest -v
```

## Commit Style

Use [conventional commits](https://www.conventionalcommits.org/):

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code refactoring
- `test:` adding tests
- `chore:` maintenance

Examples:
```
feat: add ETH-USD support
fix: handle WS reconnection edge case
docs: update architecture diagrams
```

## Pull Requests

1. Create a feature branch from `main`
2. Make changes with clear commits
3. Ensure tests pass
4. Open PR with description of changes
