"""
External Tool Discovery - Run external linting/quality tools and discover work items

This module integrates the ToolOrchestrator with the SugarLoop discovery system,
allowing external tools like eslint, ruff, mypy, etc. to automatically discover
work items during the sugar run loop cycles.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sugar.discovery.external_tool_config import (
    ExternalToolConfig,
    parse_external_tools_from_discovery_config,
)
from sugar.discovery.orchestrator import ToolOrchestrator, ToolResult

logger = logging.getLogger(__name__)


class ExternalToolDiscovery:
    """
    Discovery module that runs external tools and creates work items from their output.

    This class adapts the ToolOrchestrator to work as a discovery module in the
    SugarLoop, enabling automatic discovery of issues from external tools like
    eslint, ruff, mypy, bandit, etc.
    """

    # Source identifier for work items created by this discovery module
    SOURCE_EXTERNAL_TOOLS = "external_tools"

    def __init__(
        self,
        config: Dict[str, Any],
        working_dir: Optional[Path] = None,
        claude_wrapper=None,
    ):
        """
        Initialize the ExternalToolDiscovery module.

        Args:
            config: The external_tools section from discovery config, containing:
                   - enabled: bool
                   - tools: List of tool configurations
                   - max_tasks_per_tool: int (optional)
                   - default_timeout: int (optional)
            working_dir: Working directory for tool execution (default: current dir)
            claude_wrapper: Optional ClaudeWrapper for interpreting tool output
        """
        self.config = config
        self.working_dir = working_dir or Path.cwd()
        self.claude_wrapper = claude_wrapper

        # Parse and validate tool configurations
        self.external_tools: List[ExternalToolConfig] = []
        if config.get("enabled", True):
            # Pass the full discovery config structure that includes external_tools
            discovery_config = {"external_tools": config}
            self.external_tools = parse_external_tools_from_discovery_config(
                discovery_config
            )

        # Configuration options
        self.max_tasks_per_tool = config.get("max_tasks_per_tool", 50)
        self.default_timeout = config.get("default_timeout", 120)
        self.use_claude_interpretation = config.get("use_claude_interpretation", False)

        # Track processed results to avoid duplicate work items
        self._processed_hashes: set = set()

        logger.debug(
            f"🔧 ExternalToolDiscovery initialized with {len(self.external_tools)} tools"
        )

    async def discover(self) -> List[Dict[str, Any]]:
        """
        Discover work items by running all configured external tools.

        Returns:
            List of work item dictionaries ready to be added to the work queue.
        """
        work_items = []

        if not self.external_tools:
            logger.debug("No external tools configured, skipping discovery")
            return work_items

        logger.debug(
            f"🔍 ExternalToolDiscovery running {len(self.external_tools)} tools"
        )

        # Create orchestrator with all configured tools
        orchestrator = ToolOrchestrator(
            external_tools=self.external_tools,
            working_dir=self.working_dir,
            default_timeout=self.default_timeout,
        )

        try:
            # Execute all tools
            results = orchestrator.execute_all(timeout_per_tool=self.default_timeout)

            # Process results and create work items
            for result in results:
                tool_work_items = await self._process_tool_result(result)
                work_items.extend(tool_work_items)

        except Exception as e:
            logger.error(f"Error executing external tools: {e}")
        finally:
            # Clean up temp files
            orchestrator.cleanup()

        logger.debug(
            f"🔍 ExternalToolDiscovery discovered {len(work_items)} work items"
        )
        return work_items

    async def _process_tool_result(self, result: ToolResult) -> List[Dict[str, Any]]:
        """
        Process a single tool result and create work items.

        Args:
            result: ToolResult from the orchestrator

        Returns:
            List of work item dictionaries
        """
        work_items = []

        # Skip if tool wasn't found or timed out
        if result.tool_not_found:
            logger.warning(f"Tool '{result.name}' not found, skipping")
            return work_items

        if result.timed_out:
            logger.warning(
                f"Tool '{result.name}' timed out after {result.duration_seconds}s"
            )
            return work_items

        # Exit code 0 typically means no issues found
        if result.exit_code == 0:
            logger.debug(f"Tool '{result.name}' found no issues (exit code 0)")
            return work_items

        # Check if there's output to process
        if not result.has_output:
            logger.debug(f"Tool '{result.name}' produced no output")
            return work_items

        # Parse tool output and create work items
        if self.use_claude_interpretation and self.claude_wrapper:
            work_items = await self._interpret_with_claude(result)
        else:
            work_items = await self._parse_tool_output(result)

        # Limit work items per tool
        if len(work_items) > self.max_tasks_per_tool:
            logger.info(
                f"Limiting {result.name} work items from {len(work_items)} "
                f"to {self.max_tasks_per_tool}"
            )
            work_items = work_items[: self.max_tasks_per_tool]

        return work_items

    async def _parse_tool_output(self, result: ToolResult) -> List[Dict[str, Any]]:
        """
        Parse tool output without Claude interpretation.

        Creates a single work item per tool run that references the issues found.
        For more granular parsing, Claude interpretation should be enabled.

        Args:
            result: ToolResult from the orchestrator

        Returns:
            List of work item dictionaries
        """
        work_items = []

        # Generate a hash to avoid duplicate work items
        output_hash = hash(f"{result.name}:{result.stdout[:1000]}")
        if output_hash in self._processed_hashes:
            logger.debug(f"Skipping duplicate work item for {result.name}")
            return work_items
        self._processed_hashes.add(output_hash)

        # Create a summary work item for this tool's findings
        stdout_preview = result.stdout[:500] if result.stdout else ""
        if len(result.stdout) > 500:
            stdout_preview += "..."

        work_item = {
            "id": str(uuid.uuid4()),
            "type": "refactor",
            "title": f"Fix issues found by {result.name}",
            "description": self._generate_description(result),
            "priority": 3,  # Medium priority for linting/quality issues
            "status": "pending",
            "source": self.SOURCE_EXTERNAL_TOOLS,
            "source_file": f"external_tool:{result.name}",
            "context": {
                "tool_name": result.name,
                "tool_command": result.command,
                "exit_code": result.exit_code,
                "output_preview": stdout_preview,
                "duration_seconds": result.duration_seconds,
                "discovered_by": "external_tool_discovery",
                "added_via": "sugar_loop",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        work_items.append(work_item)
        return work_items

    def _generate_description(self, result: ToolResult) -> str:
        """Generate a description for the work item based on tool output."""
        lines = []
        lines.append(f"External tool '{result.name}' found issues that need attention.")
        lines.append("")
        lines.append(f"**Command:** `{result.command}`")
        lines.append(f"**Exit Code:** {result.exit_code}")
        lines.append(f"**Duration:** {result.duration_seconds:.2f}s")
        lines.append("")

        # Include a preview of the output
        if result.stdout:
            lines.append("**Output Preview:**")
            lines.append("```")
            preview_lines = result.stdout.split("\n")[:20]
            lines.extend(preview_lines)
            if len(result.stdout.split("\n")) > 20:
                lines.append("... (truncated)")
            lines.append("```")

        if result.stderr:
            lines.append("")
            lines.append("**Stderr:**")
            lines.append("```")
            stderr_lines = result.stderr.split("\n")[:10]
            lines.extend(stderr_lines)
            if len(result.stderr.split("\n")) > 10:
                lines.append("... (truncated)")
            lines.append("```")

        return "\n".join(lines)

    async def _interpret_with_claude(self, result: ToolResult) -> List[Dict[str, Any]]:
        """
        Use Claude to interpret tool output and create granular work items.

        This method uses the same approach as the discover CLI command,
        passing the tool output to Claude for interpretation.

        Args:
            result: ToolResult from the orchestrator

        Returns:
            List of work item dictionaries
        """
        work_items = []

        if not self.claude_wrapper:
            logger.warning(
                "Claude interpretation requested but no wrapper available, "
                "falling back to simple parsing"
            )
            return await self._parse_tool_output(result)

        try:
            from sugar.discovery.prompt_templates import (
                create_tool_interpretation_prompt,
            )

            # Create interpretation prompt
            prompt = create_tool_interpretation_prompt(
                tool_name=result.name,
                command=result.command,
                output_file_path=result.output_path,
            )

            # Execute Claude to interpret the output
            claude_work_item = {
                "id": f"discover_{result.name}",
                "type": "discovery",
                "title": f"Interpret {result.name} output",
                "prompt": prompt,
                "context": {
                    "tool_name": result.name,
                    "tool_command": result.command,
                    "discovery_mode": True,
                },
            }

            claude_result = await self.claude_wrapper.execute_work(claude_work_item)

            if claude_result.get("success"):
                # Parse sugar add commands from Claude's output
                claude_output = claude_result.get("output", "") or claude_result.get(
                    "result", {}
                ).get("stdout", "")
                work_items = self._parse_sugar_add_commands(claude_output, result.name)
            else:
                logger.warning(
                    f"Claude interpretation failed for {result.name}: "
                    f"{claude_result.get('error', 'Unknown error')}"
                )
                # Fall back to simple parsing
                return await self._parse_tool_output(result)

        except Exception as e:
            logger.error(f"Error during Claude interpretation for {result.name}: {e}")
            # Fall back to simple parsing
            return await self._parse_tool_output(result)

        return work_items

    def _parse_sugar_add_commands(
        self, claude_output: str, tool_name: str
    ) -> List[Dict[str, Any]]:
        """
        Parse sugar add commands from Claude's output.

        This mirrors the parsing logic from the discover CLI command.

        Args:
            claude_output: Raw output from Claude
            tool_name: Name of the tool that produced the original output

        Returns:
            List of work item dictionaries
        """
        import re

        work_items = []

        # Pattern to match sugar add commands
        # Matches: sugar add "title" --type=X --priority=Y --description="Z"
        pattern = r'sugar\s+add\s+"([^"]+)"(?:\s+--type[=\s]+(\w+))?(?:\s+--priority[=\s]+(\d+))?(?:\s+--description[=\s]+"([^"]*)")?'

        matches = re.findall(pattern, claude_output, re.IGNORECASE)

        for match in matches:
            title, task_type, priority, description = match

            work_item = {
                "id": str(uuid.uuid4()),
                "type": task_type or "refactor",
                "title": title,
                "description": description or "",
                "priority": int(priority) if priority else 3,
                "status": "pending",
                "source": f"discover:{tool_name}",
                "context": {
                    "discovered_by": tool_name,
                    "added_via": "sugar_loop_claude",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
            work_items.append(work_item)

        return work_items

    async def health_check(self) -> Dict[str, Any]:
        """
        Return health status of external tool discovery.

        Returns:
            Dictionary with health information
        """
        return {
            "enabled": bool(self.external_tools),
            "configured_tools": len(self.external_tools),
            "tool_names": [t.name for t in self.external_tools],
            "working_dir": str(self.working_dir),
            "use_claude_interpretation": self.use_claude_interpretation,
            "max_tasks_per_tool": self.max_tasks_per_tool,
            "default_timeout": self.default_timeout,
        }
