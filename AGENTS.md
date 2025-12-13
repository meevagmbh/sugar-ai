# Sugar - AGENTS.md

This file provides context and instructions to help AI coding agents work effectively with the Sugar project.

## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Auto-syncs to JSONL for version control
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**
```bash
bd ready --json
```

**Create new issues:**
```bash
bd create "Issue title" -t bug|feature|task -p 0-4 --json
bd create "Issue title" -p 1 --deps discovered-from:bd-123 --json
bd create "Subtask" --parent <epic-id> --json  # Hierarchical subtask (gets ID like epic-id.1)
```

**Claim and update:**
```bash
bd update bd-42 --status in_progress --json
bd update bd-42 --priority 1 --json
```

**Complete work:**
```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task**: `bd update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`
6. **Commit together**: Always commit the `.beads/issues.jsonl` file together with the code changes so issue state stays in sync with code state

### Auto-Sync

bd automatically syncs with git:
- Exports to `.beads/issues.jsonl` after changes (5s debounce)
- Imports from JSONL when newer (e.g., after `git pull`)
- No manual export/import needed!

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ✅ Store AI planning docs in `history/` directory
- ✅ Run `bd <cmd> --help` to discover available flags
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems
- ❌ Do NOT clutter repo root with planning documents

## Dev Environment Tips

### Project Structure Navigation
```bash
# Core project structure
sugar/                    # Main source code
├── core/                # Core loop and orchestration
├── discovery/           # Work discovery modules
├── executor/            # Claude Code CLI wrapper
├── learning/            # Adaptive learning system
├── storage/             # Database and work queue
├── utils/               # Utility functions
└── workflow/            # Workflow orchestration

tests/                   # Test suite
docs/                    # Documentation
config/                  # Configuration templates
```

### Development Setup
```bash
# Install in development mode
pip install -e .

# Install with optional dependencies
pip install -e ".[dev,test,github]"

# Verify installation
sugar --help
```

### Python Environment
- **Required Python**: 3.11+ (supports 3.11, 3.12, 3.13)
- **Dependencies**: See `pyproject.toml` for complete list
- **Key libraries**: Click, PyYAML, SQLAlchemy, aiosqlite

## Testing Instructions

### Test Commands
```bash
# Run full test suite
pytest

# Run with coverage
pytest --cov=sugar --cov-report=term-missing

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m slow          # Slow tests only

# Run specific test files
pytest tests/test_cli.py
pytest tests/test_core_loop.py
```

### CI Configuration Location
- **GitHub Actions**: `.github/workflows/ci.yml`
- **Test matrix**: Ubuntu, Windows, macOS with Python 3.11-3.13
- **Coverage**: Uploads to Codecov

### Code Quality Checks
```bash
# Linting
flake8 sugar --max-line-length=88

# Code formatting
black sugar tests

# Type checking (currently relaxed due to extensive work needed)
mypy sugar  # May have many warnings - type annotations in progress

# Security scanning
bandit -r sugar/
safety check
```

### Error Handling During Testing
- Tests use relaxed failure handling in CI to unblock pipeline
- Focus on core functionality tests first
- Integration tests mock Claude CLI with `/tmp/mock-claude/claude`

## PR Instructions

### PR Title Format
Follow conventional commit style:
- `feat: description` - New features
- `fix: description` - Bug fixes  
- `refactor: description` - Code refactoring
- `test: description` - Test additions/modifications
- `docs: description` - Documentation updates
- `ci: description` - CI/CD changes

### Pre-commit Requirements
1. **Code formatting**: `black sugar tests`
2. **Linting**: `flake8 sugar --max-line-length=88`
3. **Basic tests**: `pytest tests/` (relaxed failures acceptable)
4. **Security check**: `bandit -r sugar/` (review results)

### Testing Requirements
- All new features must include basic tests
- Integration tests should mock external dependencies
- Focus on core functionality over edge cases initially
- Coverage reports help identify untested areas

## Key Project Context

### Sugar's Purpose
Sugar is an autonomous development system that integrates with Claude Code CLI to:
- Continuously discover work from GitHub issues, error logs, code analysis
- Execute development tasks using Claude agents
- Learn and adapt from execution results
- Provide 24/7 autonomous development capabilities

### Architecture Patterns
- **Modular design**: Each component in separate modules
- **Async/await**: Heavy use of asyncio for concurrent operations
- **Database-backed**: SQLite with SQLAlchemy for work persistence
- **CLI-first**: Click-based command interface
- **Configuration-driven**: YAML configuration in `.sugar/config.yaml`

### Integration Points
- **Claude Code CLI**: External process execution via subprocess
- **GitHub API**: Optional GitHub integration for issue discovery
- **File system**: Error log monitoring and code analysis
- **Git operations**: Branch creation, commits, PR management

### Common Patterns
- Use `click.echo()` for user output, not `print()`
- Async functions for I/O operations (database, file system)
- Configuration validation with meaningful error messages
- Graceful error handling with user-friendly messages
- Path operations using `pathlib.Path`

### Testing Conventions
- Test files: `test_*.py` pattern
- Use `pytest` fixtures from `conftest.py`
- Mock external dependencies (Claude CLI, GitHub API)
- Prefer integration tests that test actual workflows
- Use temporary directories for file system tests