"""
Claude Invoker - Send tool output to Claude Code for interpretation.

This module bridges external development tools (linters, security scanners, test
runners) with Claude Code by sending their output for AI-powered interpretation.
Claude analyzes the output and generates `sugar add` commands to create actionable
tasks in the work queue.

Architecture Overview:
    1. External tools produce output (e.g., ESLint, pytest, bandit)
    2. Output is written to temp files by the ToolOrchestrator
    3. ToolOutputInterpreter sends file paths to Claude Code via ClaudeWrapper
    4. Claude reads the files, interprets findings, and generates commands
    5. Commands are parsed and optionally executed to create sugar tasks

Key Design Decisions:
    - File paths are passed instead of inline content for efficiency with large outputs
    - Prompt templates are used for consistent, tool-specific interpretation guidance
    - Command parsing handles quoted strings and validates all options before execution

Usage Example:
    >>> interpreter = ToolOutputInterpreter()
    >>> result = await interpreter.interpret_output(
    ...     tool_name="eslint",
    ...     command="npx eslint src/",
    ...     output_file_path=Path("/tmp/eslint_output.txt")
    ... )
    >>> if result.success:
    ...     interpreter.execute_commands(result.commands, dry_run=False)
"""

import asyncio
import logging
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..executor.claude_wrapper import ClaudeWrapper
from ..discovery.prompt_templates import create_tool_interpretation_prompt

logger = logging.getLogger(__name__)


@dataclass
class ParsedCommand:
    """
    A parsed `sugar add` command extracted from Claude's response.

    This dataclass represents a single task-creation command after parsing
    from Claude's interpretation output. It captures all supported options
    for the `sugar add` CLI command.

    Attributes:
        title: The task title (required). This is the positional argument
            in `sugar add "Fix authentication bug"`.
        task_type: Task category (default: "bug_fix"). Supported types include
            bug_fix, feature, refactor, documentation, test, security.
        priority: Task priority level 1-5 (default: 3). Lower numbers = higher priority.
        description: Optional detailed description of the task.
        urgent: Whether the task is marked urgent (default: False).
        status: Initial task status, either "pending" or "hold" (default: "pending").
        raw_command: The original command string before parsing (for debugging).
        valid: Whether parsing succeeded (default: True). Set False if parsing fails.
        validation_error: Error message if valid=False, empty string otherwise.

    Example:
        Command: `sugar add "Fix XSS vulnerability" --type security --priority 1 --urgent`
        Results in:
            ParsedCommand(
                title="Fix XSS vulnerability",
                task_type="security",
                priority=1,
                urgent=True,
                ...
            )
    """

    title: str
    task_type: str = "bug_fix"
    priority: int = 3
    description: str = ""
    urgent: bool = False
    status: str = "pending"
    raw_command: str = ""
    valid: bool = True
    validation_error: str = ""


@dataclass
class InterpretationResult:
    """
    Result of Claude's interpretation of external tool output.

    Contains both the parsed commands and metadata about the interpretation
    process, including timing and error information for diagnostics.

    Attributes:
        success: Whether Claude successfully interpreted the output.
            False indicates a communication error, timeout, or processing failure.
        commands: List of ParsedCommand objects extracted from Claude's response.
            Empty if success=False or if Claude found no issues to report.
        raw_response: The complete text response from Claude before command extraction.
            Useful for debugging or logging the full interpretation context.
        error_message: Description of what went wrong if success=False.
            Empty string on successful interpretation.
        execution_time: Time in seconds Claude took to process the interpretation.
            Useful for performance monitoring and timeout tuning.

    Note:
        A successful interpretation (success=True) may still have zero commands
        if the tool output contained no actionable issues.
    """

    success: bool
    commands: List[ParsedCommand] = field(default_factory=list)
    raw_response: str = ""
    error_message: str = ""
    execution_time: float = 0.0


class ToolOutputInterpreter:
    """
    Interprets external tool output using Claude Code to generate actionable tasks.

    This class serves as the bridge between external development tools and Sugar's
    task management system. It sends tool output to Claude Code for intelligent
    analysis, then parses the resulting `sugar add` commands into structured
    task objects.

    The interpreter uses ClaudeWrapper internally for Claude Code communication,
    supporting customizable prompt templates for different tool types (linters,
    security scanners, test runners, etc.).

    Typical workflow:
        1. Create interpreter (optionally with custom config)
        2. Call interpret_output() with tool details and output file path
        3. Either manually execute_commands() or use interpret_and_execute()

    Attributes:
        wrapper: ClaudeWrapper instance for Claude Code communication.
        custom_template: User-provided prompt template, or None to use defaults.

    Example:
        >>> interpreter = ToolOutputInterpreter()
        >>> result = await interpreter.interpret_output(
        ...     tool_name="ruff",
        ...     command="ruff check .",
        ...     output_file_path=Path("/tmp/ruff_output.txt"),
        ...     template_type="lint"
        ... )
        >>> print(f"Found {len(result.commands)} issues to fix")
    """

    def __init__(
        self,
        prompt_template: Optional[str] = None,
        wrapper_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the interpreter with optional custom configuration.

        Args:
            prompt_template: Custom prompt template string with placeholders.
                Supported placeholders: ${tool_name}, ${command}, ${output_file_path}.
                If not provided, uses templates from prompt_templates module which
                auto-detect the appropriate template based on tool name.
            wrapper_config: Configuration dict for ClaudeWrapper. Supported keys:
                - command (str): Claude CLI command (default: "claude")
                - timeout (int): Interpretation timeout in seconds (default: 300)
                - context_file (str): Path for context persistence
                - use_continuous (bool): Reuse sessions (default: False)
                - dry_run (bool): Skip actual execution (default: False)
                Any provided values override the defaults.
        """
        # Default wrapper config for tool interpretation
        default_config = {
            "command": "claude",
            "timeout": 300,  # 5 minutes for interpretation
            "context_file": ".sugar/claude_interpreter_context.json",
            "use_continuous": False,  # Fresh session for each interpretation
            "use_structured_requests": False,  # Use simple prompts
            "enable_agents": False,  # No agent selection needed
            "dry_run": False,  # Actually execute
        }

        if wrapper_config:
            default_config.update(wrapper_config)

        self.wrapper = ClaudeWrapper(default_config)
        self.custom_template = prompt_template
        logger.debug("ToolOutputInterpreter initialized with ClaudeWrapper")

    async def interpret_output(
        self,
        tool_name: str,
        command: str,
        output_file_path: Path,
        template_type: Optional[str] = None,
    ) -> InterpretationResult:
        """
        Send tool output to Claude Code for interpretation.

        Claude Code will read the output file directly at the given path.
        This approach is more efficient for large outputs and integrates
        with the orchestrator's temp file management.

        Args:
            tool_name: Name of the tool that generated the output
            command: The command that was executed
            output_file_path: Path to the file containing the tool output
            template_type: Optional template type (default, security, coverage, lint)

        Returns:
            InterpretationResult containing parsed sugar add commands
        """
        logger.info(f"Interpreting output from tool: {tool_name}")
        logger.debug(f"Output file path: {output_file_path}")

        # Build prompt from template
        if self.custom_template:
            # Use custom template with simple substitution
            prompt = self.custom_template.replace("${tool_name}", tool_name)
            prompt = prompt.replace("${command}", command)
            prompt = prompt.replace("${output_file_path}", str(output_file_path))
        else:
            # Use the standard template manager
            prompt = create_tool_interpretation_prompt(
                tool_name=tool_name,
                command=command,
                output_file_path=output_file_path,
                template_type=template_type,
            )

        # Execute via Claude wrapper
        try:
            result = await self._execute_claude_prompt(prompt)

            if not result.get("success", False):
                return InterpretationResult(
                    success=False,
                    error_message=result.get(
                        "error", "Unknown error during interpretation"
                    ),
                    raw_response=result.get("output", ""),
                    execution_time=result.get("execution_time", 0.0),
                )

            # Extract sugar add commands from response
            raw_response = result.get("output", "")
            commands = self._extract_commands(raw_response)

            logger.info(
                f"Extracted {len(commands)} valid commands from Claude response"
            )

            return InterpretationResult(
                success=True,
                commands=commands,
                raw_response=raw_response,
                execution_time=result.get("execution_time", 0.0),
            )

        except Exception as e:
            logger.error(f"Error interpreting tool output: {e}")
            return InterpretationResult(
                success=False,
                error_message=str(e),
            )

    async def _execute_claude_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Execute a prompt via the Claude wrapper's internal CLI execution.

        This is a low-level method that bypasses the full work item processing
        pipeline and directly invokes Claude CLI with the given prompt.

        Args:
            prompt: The complete prompt string to send to Claude Code.
                Should include all context needed for interpretation.

        Returns:
            Dict containing:
                - success (bool): Whether Claude responded without errors
                - output (str): Claude's stdout response text
                - error (str): Error message or stderr content if failed
                - execution_time (float): Processing duration in seconds
        """
        # Create a minimal work item for the wrapper
        work_item = {
            "id": "interpreter-task",
            "type": "interpretation",
            "title": "Tool Output Interpretation",
            "description": prompt,
            "priority": 3,
            "source": "tool_interpreter",
        }

        # Use legacy execution path for simple prompt execution
        try:
            # Access the internal CLI execution method
            context = self.wrapper._prepare_context(work_item, continue_session=False)
            result = await self.wrapper._execute_claude_cli(
                prompt, context, continue_session=False
            )

            return {
                "success": result.get("success", False),
                "output": result.get("stdout", ""),
                "error": result.get("stderr", ""),
                "execution_time": result.get("execution_time", 0.0),
            }

        except Exception as e:
            logger.error(f"Claude CLI execution failed: {e}")
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "execution_time": 0.0,
            }

    def _extract_commands(self, response: str) -> List[ParsedCommand]:
        """
        Extract and parse `sugar add` commands from Claude's response text.

        Scans each line of Claude's response for lines starting with "sugar add ",
        then parses each matching line into a ParsedCommand. Invalid or malformed
        commands are logged and skipped.

        Args:
            response: The complete raw response text from Claude Code.
                Expected to contain zero or more `sugar add` commands, one per line.

        Returns:
            List of successfully parsed ParsedCommand objects.
            Commands that fail validation are excluded from the result.
        """
        commands = []
        lines = response.split("\n")

        for line in lines:
            line = line.strip()

            # Skip empty lines and non-command lines
            if not line:
                continue

            # Look for lines starting with "sugar add"
            if line.startswith("sugar add "):
                parsed = self._parse_command(line)
                if parsed.valid:
                    commands.append(parsed)
                else:
                    logger.warning(
                        f"Skipping malformed command: {line} - {parsed.validation_error}"
                    )

        return commands

    def _parse_command(self, command_line: str) -> ParsedCommand:
        """
        Parse a single `sugar add` command line into its components.

        Uses shlex for proper handling of quoted strings, then iterates through
        tokens to extract the title (positional argument) and options (--flags).

        Supported options:
            --type <value>: Task type (bug_fix, feature, etc.)
            --priority <int>: Priority level 1-5
            --description <value>: Detailed task description
            --status <pending|hold>: Initial task status
            --urgent: Mark task as urgent (flag, no value)

        Args:
            command_line: Complete command string, e.g.:
                'sugar add "Fix bug in auth" --type bug_fix --priority 2'

        Returns:
            ParsedCommand with all fields populated. On parse failure:
                - valid=False
                - validation_error contains the failure reason
                - title may be empty

        Note:
            Unknown options are silently skipped with debug logging.
            The title must be a quoted or unquoted positional argument
            appearing after "sugar add".
        """
        parsed = ParsedCommand(title="", raw_command=command_line)

        try:
            # Use shlex to properly handle quoted strings
            parts = shlex.split(command_line)
        except ValueError as e:
            parsed.valid = False
            parsed.validation_error = f"Failed to parse command: {e}"
            return parsed

        if len(parts) < 3 or parts[0] != "sugar" or parts[1] != "add":
            parsed.valid = False
            parsed.validation_error = "Command must start with 'sugar add'"
            return parsed

        # Extract positional argument (title)
        # The title should be the first non-option argument after "sugar add"
        i = 2
        title = None

        while i < len(parts):
            if parts[i].startswith("--"):
                # Process option
                option = parts[i][2:]

                if option == "urgent":
                    parsed.urgent = True
                    i += 1
                elif option in ("type", "priority", "description", "status"):
                    if i + 1 >= len(parts):
                        parsed.valid = False
                        parsed.validation_error = f"Option --{option} requires a value"
                        return parsed

                    value = parts[i + 1]
                    if option == "type":
                        parsed.task_type = value
                    elif option == "priority":
                        try:
                            parsed.priority = int(value)
                        except ValueError:
                            parsed.valid = False
                            parsed.validation_error = (
                                f"Priority must be an integer, got: {value}"
                            )
                            return parsed
                    elif option == "description":
                        parsed.description = value
                    elif option == "status":
                        if value not in ("pending", "hold"):
                            parsed.valid = False
                            parsed.validation_error = (
                                f"Status must be 'pending' or 'hold', got: {value}"
                            )
                            return parsed
                        parsed.status = value

                    i += 2
                else:
                    # Unknown option, skip
                    logger.debug(f"Unknown option: --{option}")
                    i += 1
            else:
                # Positional argument (title)
                if title is None:
                    title = parts[i]
                i += 1

        if not title:
            parsed.valid = False
            parsed.validation_error = "Command must have a title"
            return parsed

        parsed.title = title
        return parsed

    def execute_commands(
        self,
        commands: List[ParsedCommand],
        dry_run: bool = False,
    ) -> int:
        """
        Execute parsed commands to create tasks in the Sugar work queue.

        Iterates through the provided commands and invokes the `sugar add`
        CLI for each valid command. Invalid commands (valid=False) are
        skipped with a warning.

        Args:
            commands: List of ParsedCommand objects to execute.
                Invalid commands are skipped automatically.
            dry_run: If True, log the commands that would be executed
                without actually creating tasks. Useful for testing.

        Returns:
            Count of successfully created tasks (or would-be-created in dry_run mode).

        Note:
            Each command execution has a 30-second timeout. Failures are logged
            but don't stop processing of subsequent commands.
        """
        successful = 0

        for cmd in commands:
            if not cmd.valid:
                logger.warning(f"Skipping invalid command: {cmd.validation_error}")
                continue

            # Build the command
            args = ["sugar", "add", cmd.title]

            if cmd.task_type:
                args.extend(["--type", cmd.task_type])
            if cmd.priority:
                args.extend(["--priority", str(cmd.priority)])
            if cmd.description:
                args.extend(["--description", cmd.description])
            if cmd.urgent:
                args.append("--urgent")
            if cmd.status and cmd.status != "pending":
                args.extend(["--status", cmd.status])

            if dry_run:
                logger.info(f"[DRY RUN] Would execute: {' '.join(args)}")
                successful += 1
                continue

            try:
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    logger.info(f"Created task: {cmd.title}")
                    successful += 1
                else:
                    logger.error(
                        f"Failed to create task '{cmd.title}': {result.stderr}"
                    )

            except subprocess.TimeoutExpired:
                logger.error(f"Timeout creating task: {cmd.title}")
            except Exception as e:
                logger.error(f"Error creating task '{cmd.title}': {e}")

        logger.info(f"Successfully created {successful}/{len(commands)} tasks")
        return successful

    async def interpret_and_execute(
        self,
        tool_name: str,
        command: str,
        output_file_path: Path,
        template_type: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Interpret tool output and execute resulting commands in a single operation.

        This is a convenience method that combines interpret_output() and
        execute_commands() for the common workflow of processing tool output
        end-to-end.

        Args:
            tool_name: Name of the tool (e.g., "eslint", "ruff", "pytest").
                Used for template selection and logging.
            command: The exact command that was executed to generate the output.
                Included in prompts for context.
            output_file_path: Path to the file containing tool output.
                Claude Code reads this file directly.
            template_type: Specific prompt template to use (e.g., "lint", "security").
                Auto-detected from tool_name if not provided.
            dry_run: If True, parse and validate commands but don't create tasks.
                Useful for testing interpretation without side effects.

        Returns:
            Dict containing:
                - success (bool): Whether interpretation succeeded
                - tasks_created (int): Number of tasks created (0 if dry_run or error)
                - commands_found (int): Number of valid commands parsed
                - execution_time (float): Claude's processing time in seconds
                - dry_run (bool): Echo of the dry_run parameter
                - error (str): Error message if success=False
        """
        result = await self.interpret_output(
            tool_name, command, output_file_path, template_type
        )

        if not result.success:
            return {
                "success": False,
                "error": result.error_message,
                "tasks_created": 0,
                "commands_found": 0,
            }

        tasks_created = self.execute_commands(result.commands, dry_run=dry_run)

        return {
            "success": True,
            "tasks_created": tasks_created,
            "commands_found": len(result.commands),
            "execution_time": result.execution_time,
            "dry_run": dry_run,
        }


# Export key components
__all__ = [
    "ToolOutputInterpreter",
    "ParsedCommand",
    "InterpretationResult",
]
