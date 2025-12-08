"""
Tests for ExternalToolDiscovery - External tool integration for work discovery

Tests cover:
- Initialization with various configurations
- Discovery with no tools configured
- Tool execution and result processing
- Work item creation from tool output
- Handling of tool not found scenarios
- Handling of tool timeout scenarios
- Health check functionality
- Claude interpretation mode (when enabled)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from dataclasses import dataclass
from typing import Optional


@dataclass
class MockToolResult:
    """Mock ToolResult for testing."""

    name: str
    command: str
    output_path: Optional[Path]
    stderr: str
    exit_code: int
    success: bool
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    timed_out: bool = False
    tool_not_found: bool = False
    _stdout: str = ""

    @property
    def stdout(self) -> str:
        return self._stdout

    @property
    def has_output(self) -> bool:
        return bool(self._stdout.strip() or self.stderr.strip())


class TestExternalToolDiscoveryInitialization:
    """Test ExternalToolDiscovery initialization and configuration."""

    def test_initialization_with_empty_config(self):
        """Discovery should initialize with empty config."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {}
        discovery = ExternalToolDiscovery(config)

        assert discovery.external_tools == []
        assert discovery.max_tasks_per_tool == 50
        assert discovery.default_timeout == 120

    def test_initialization_with_disabled_config(self):
        """Discovery should have no tools when disabled."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {
            "enabled": False,
            "tools": [{"name": "ruff", "command": "ruff check"}],
        }
        discovery = ExternalToolDiscovery(config)

        assert discovery.external_tools == []

    def test_initialization_with_tools_configured(self):
        """Discovery should parse tool configurations."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {
            "enabled": True,
            "tools": [
                {"name": "ruff", "command": "ruff check ."},
                {"name": "mypy", "command": "mypy ."},
            ],
        }
        discovery = ExternalToolDiscovery(config)

        assert len(discovery.external_tools) == 2
        tool_names = [t.name for t in discovery.external_tools]
        assert "ruff" in tool_names
        assert "mypy" in tool_names

    def test_initialization_with_custom_options(self):
        """Discovery should accept custom configuration options."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {
            "enabled": True,
            "tools": [],
            "max_tasks_per_tool": 25,
            "default_timeout": 60,
            "use_claude_interpretation": True,
        }
        discovery = ExternalToolDiscovery(config)

        assert discovery.max_tasks_per_tool == 25
        assert discovery.default_timeout == 60
        assert discovery.use_claude_interpretation is True


class TestExternalToolDiscoveryDiscover:
    """Test the discover() method."""

    @pytest.mark.asyncio
    async def test_discover_returns_empty_when_no_tools(self):
        """Discover should return empty list when no tools configured."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": True, "tools": []}
        discovery = ExternalToolDiscovery(config)

        work_items = await discovery.discover()

        assert work_items == []

    @pytest.mark.asyncio
    async def test_discover_processes_tool_with_issues(self):
        """Discover should create work items from tool with non-zero exit code."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {
            "enabled": True,
            "tools": [{"name": "ruff", "command": "ruff check ."}],
        }
        discovery = ExternalToolDiscovery(config)

        mock_result = MockToolResult(
            name="ruff",
            command="ruff check .",
            output_path=None,
            stderr="",
            exit_code=1,
            success=False,
            duration_seconds=1.5,
            _stdout="src/main.py:10:5: E501 line too long\nsrc/utils.py:20:1: F401 unused import",
        )

        with patch.object(
            discovery, "_process_tool_result", new_callable=AsyncMock
        ) as mock_process:
            mock_process.return_value = [
                {
                    "id": "test-id",
                    "type": "refactor",
                    "title": "Fix issues found by ruff",
                    "priority": 3,
                }
            ]

            # Patch the ToolOrchestrator
            with patch(
                "sugar.discovery.external_tool_discovery.ToolOrchestrator"
            ) as MockOrchestrator:
                mock_orch = MockOrchestrator.return_value
                mock_orch.execute_all.return_value = [mock_result]

                work_items = await discovery.discover()

                assert len(work_items) == 1
                mock_process.assert_called_once_with(mock_result)

    @pytest.mark.asyncio
    async def test_discover_skips_tool_not_found(self):
        """Discover should skip tools that are not found."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {
            "enabled": True,
            "tools": [{"name": "nonexistent", "command": "nonexistent_tool check"}],
        }
        discovery = ExternalToolDiscovery(config)

        mock_result = MockToolResult(
            name="nonexistent",
            command="nonexistent_tool check",
            output_path=None,
            stderr="",
            exit_code=127,
            success=False,
            tool_not_found=True,
        )

        with patch(
            "sugar.discovery.external_tool_discovery.ToolOrchestrator"
        ) as MockOrchestrator:
            mock_orch = MockOrchestrator.return_value
            mock_orch.execute_all.return_value = [mock_result]

            work_items = await discovery.discover()

            assert work_items == []

    @pytest.mark.asyncio
    async def test_discover_skips_timed_out_tools(self):
        """Discover should skip tools that timed out."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {
            "enabled": True,
            "tools": [{"name": "slow_tool", "command": "slow_tool check"}],
        }
        discovery = ExternalToolDiscovery(config)

        mock_result = MockToolResult(
            name="slow_tool",
            command="slow_tool check",
            output_path=None,
            stderr="",
            exit_code=-1,
            success=False,
            timed_out=True,
            duration_seconds=120.0,
        )

        with patch(
            "sugar.discovery.external_tool_discovery.ToolOrchestrator"
        ) as MockOrchestrator:
            mock_orch = MockOrchestrator.return_value
            mock_orch.execute_all.return_value = [mock_result]

            work_items = await discovery.discover()

            assert work_items == []

    @pytest.mark.asyncio
    async def test_discover_skips_exit_code_zero(self):
        """Discover should not create work items for successful tools (exit code 0)."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {
            "enabled": True,
            "tools": [{"name": "ruff", "command": "ruff check ."}],
        }
        discovery = ExternalToolDiscovery(config)

        mock_result = MockToolResult(
            name="ruff",
            command="ruff check .",
            output_path=None,
            stderr="",
            exit_code=0,
            success=True,
            duration_seconds=0.5,
        )

        with patch(
            "sugar.discovery.external_tool_discovery.ToolOrchestrator"
        ) as MockOrchestrator:
            mock_orch = MockOrchestrator.return_value
            mock_orch.execute_all.return_value = [mock_result]

            work_items = await discovery.discover()

            assert work_items == []


class TestWorkItemCreation:
    """Test work item creation from tool results."""

    @pytest.mark.asyncio
    async def test_parse_tool_output_creates_work_item(self):
        """Parse should create work item with correct structure."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": True, "tools": []}
        discovery = ExternalToolDiscovery(config)

        mock_result = MockToolResult(
            name="ruff",
            command="ruff check .",
            output_path=None,
            stderr="",
            exit_code=1,
            success=False,
            duration_seconds=1.5,
            _stdout="src/main.py:10:5: E501 line too long",
        )

        work_items = await discovery._parse_tool_output(mock_result)

        assert len(work_items) == 1
        item = work_items[0]
        assert item["type"] == "refactor"
        assert "ruff" in item["title"]
        assert item["priority"] == 3
        assert item["status"] == "pending"
        assert item["source"] == "external_tools"
        assert item["context"]["tool_name"] == "ruff"
        assert item["context"]["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_parse_tool_output_skips_duplicates(self):
        """Parse should skip duplicate work items."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": True, "tools": []}
        discovery = ExternalToolDiscovery(config)

        mock_result = MockToolResult(
            name="ruff",
            command="ruff check .",
            output_path=None,
            stderr="",
            exit_code=1,
            success=False,
            _stdout="same output",
        )

        # First call should create work item
        work_items_1 = await discovery._parse_tool_output(mock_result)
        assert len(work_items_1) == 1

        # Second call with same output should be skipped
        work_items_2 = await discovery._parse_tool_output(mock_result)
        assert len(work_items_2) == 0

    @pytest.mark.asyncio
    async def test_process_tool_result_limits_work_items(self):
        """Process should limit work items per tool."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": True, "tools": [], "max_tasks_per_tool": 2}
        discovery = ExternalToolDiscovery(config)

        # Mock _parse_tool_output to return many items
        with patch.object(
            discovery, "_parse_tool_output", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = [
                {"id": f"id-{i}", "title": f"Item {i}"} for i in range(10)
            ]

            mock_result = MockToolResult(
                name="ruff",
                command="ruff check .",
                output_path=None,
                stderr="",
                exit_code=1,
                success=False,
                _stdout="lots of output",
            )

            work_items = await discovery._process_tool_result(mock_result)

            assert len(work_items) == 2


class TestDescriptionGeneration:
    """Test description generation for work items."""

    def test_generate_description_includes_command(self):
        """Description should include the tool command."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": True, "tools": []}
        discovery = ExternalToolDiscovery(config)

        mock_result = MockToolResult(
            name="ruff",
            command="ruff check . --format json",
            output_path=None,
            stderr="",
            exit_code=1,
            success=False,
            duration_seconds=1.5,
            _stdout="error output",
        )

        description = discovery._generate_description(mock_result)

        assert "ruff check . --format json" in description
        assert "Exit Code:** 1" in description
        assert "1.50s" in description

    def test_generate_description_includes_output_preview(self):
        """Description should include output preview."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": True, "tools": []}
        discovery = ExternalToolDiscovery(config)

        mock_result = MockToolResult(
            name="ruff",
            command="ruff check .",
            output_path=None,
            stderr="",
            exit_code=1,
            success=False,
            _stdout="line 1\nline 2\nline 3",
        )

        description = discovery._generate_description(mock_result)

        assert "line 1" in description
        assert "line 2" in description


class TestSugarAddCommandParsing:
    """Test parsing of sugar add commands from Claude output."""

    def test_parse_sugar_add_basic_command(self):
        """Should parse basic sugar add command."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": True, "tools": []}
        discovery = ExternalToolDiscovery(config)

        claude_output = 'sugar add "Fix linting errors in main.py"'

        work_items = discovery._parse_sugar_add_commands(claude_output, "ruff")

        assert len(work_items) == 1
        assert work_items[0]["title"] == "Fix linting errors in main.py"
        assert work_items[0]["type"] == "refactor"

    def test_parse_sugar_add_with_type_and_priority(self):
        """Should parse sugar add command with type and priority."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": True, "tools": []}
        discovery = ExternalToolDiscovery(config)

        claude_output = 'sugar add "Fix type errors" --type=bugfix --priority=4'

        work_items = discovery._parse_sugar_add_commands(claude_output, "mypy")

        assert len(work_items) == 1
        assert work_items[0]["title"] == "Fix type errors"
        assert work_items[0]["type"] == "bugfix"
        assert work_items[0]["priority"] == 4

    def test_parse_multiple_sugar_add_commands(self):
        """Should parse multiple sugar add commands."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": True, "tools": []}
        discovery = ExternalToolDiscovery(config)

        claude_output = """
        Based on the ruff output, I recommend:
        sugar add "Fix unused imports in utils.py" --type=refactor --priority=2
        sugar add "Fix line length issues in main.py" --type=refactor --priority=1
        """

        work_items = discovery._parse_sugar_add_commands(claude_output, "ruff")

        assert len(work_items) == 2
        assert work_items[0]["title"] == "Fix unused imports in utils.py"
        assert work_items[1]["title"] == "Fix line length issues in main.py"


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_returns_status(self):
        """Health check should return component status."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {
            "enabled": True,
            "tools": [{"name": "ruff", "command": "ruff check ."}],
            "max_tasks_per_tool": 25,
            "default_timeout": 60,
        }
        discovery = ExternalToolDiscovery(config)

        health = await discovery.health_check()

        assert health["enabled"] is True
        assert health["configured_tools"] == 1
        assert "ruff" in health["tool_names"]
        assert health["max_tasks_per_tool"] == 25
        assert health["default_timeout"] == 60

    @pytest.mark.asyncio
    async def test_health_check_when_disabled(self):
        """Health check should indicate disabled state."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config = {"enabled": False}
        discovery = ExternalToolDiscovery(config)

        health = await discovery.health_check()

        assert health["enabled"] is False
        assert health["configured_tools"] == 0


class TestSugarLoopIntegration:
    """Test integration with SugarLoop."""

    def test_external_tool_discovery_added_to_modules(self, tmp_path):
        """ExternalToolDiscovery should be added to discovery modules when enabled."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        # Create a minimal config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
sugar:
  dry_run: true
  discovery:
    error_logs:
      enabled: false
    github:
      enabled: false
    code_quality:
      enabled: false
    test_coverage:
      enabled: false
    external_tools:
      enabled: true
      tools:
        - name: ruff
          command: ruff check .
  storage:
    database: ":memory:"
  claude:
    model: claude-3-5-sonnet-20241022
"""
        )

        # Patch dependencies to avoid actual initialization
        with patch("sugar.core.loop.WorkQueue"):
            with patch("sugar.core.loop.ClaudeWrapper"):
                with patch("sugar.core.loop.FeedbackProcessor"):
                    with patch("sugar.core.loop.AdaptiveScheduler"):
                        with patch("sugar.core.loop.GitOperations"):
                            with patch("sugar.core.loop.WorkflowOrchestrator"):
                                from sugar.core.loop import SugarLoop

                                loop = SugarLoop(str(config_file))

                                # Check that ExternalToolDiscovery was added
                                external_tool_modules = [
                                    m
                                    for m in loop.discovery_modules
                                    if isinstance(m, ExternalToolDiscovery)
                                ]
                                assert len(external_tool_modules) == 1

    def test_external_tool_discovery_not_added_when_disabled(self, tmp_path):
        """ExternalToolDiscovery should not be added when disabled."""
        from sugar.discovery.external_tool_discovery import ExternalToolDiscovery

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
sugar:
  dry_run: true
  discovery:
    error_logs:
      enabled: false
    github:
      enabled: false
    code_quality:
      enabled: false
    test_coverage:
      enabled: false
    external_tools:
      enabled: false
  storage:
    database: ":memory:"
  claude:
    model: claude-3-5-sonnet-20241022
"""
        )

        with patch("sugar.core.loop.WorkQueue"):
            with patch("sugar.core.loop.ClaudeWrapper"):
                with patch("sugar.core.loop.FeedbackProcessor"):
                    with patch("sugar.core.loop.AdaptiveScheduler"):
                        with patch("sugar.core.loop.GitOperations"):
                            with patch("sugar.core.loop.WorkflowOrchestrator"):
                                from sugar.core.loop import SugarLoop

                                loop = SugarLoop(str(config_file))

                                external_tool_modules = [
                                    m
                                    for m in loop.discovery_modules
                                    if isinstance(m, ExternalToolDiscovery)
                                ]
                                assert len(external_tool_modules) == 0
