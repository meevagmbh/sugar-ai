"""
Integration tests for ToolOutputInterpreter that verify end-to-end workflows.

These tests differ from the unit tests in test_interpret_output.py by testing
complete workflows through multiple components:
- Full interpretation flow: file reading → prompt construction → Claude invocation → command extraction
- Command parsing with edge cases: various input formats and boundary conditions

The integration tests use mocked Claude responses but test the actual flow
of data through the entire interpretation pipeline.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

from sugar.quality.claude_invoker import ToolOutputInterpreter


class TestIntegration:
    """
    Integration tests verifying end-to-end ToolOutputInterpreter workflows.

    Tests complete flows including:
    - interpret_and_execute: Full pipeline from tool output file to parsed task commands
    - Command parsing edge cases: Various input formats that stress-test the parser
    """

    def setup_method(self):
        """
        Create a temporary JSON file simulating eslint output.

        The JSON format matches typical eslint --format json output structure
        with errorCount and warningCount fields that the interpreter would
        analyze to generate task recommendations.
        """
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self.temp_file.write('{"errorCount": 23, "warningCount": 15}')
        self.temp_file.close()
        self.output_path = Path(self.temp_file.name)

    def teardown_method(self):
        """Remove temporary test file created in setup_method."""
        if self.output_path.exists():
            self.output_path.unlink()

    @pytest.mark.asyncio
    async def test_full_interpretation_flow(self):
        """
        Test complete pipeline: file → Claude interpretation → parsed commands.

        Verifies the interpret_and_execute method correctly:
        1. Reads the tool output file
        2. Constructs a prompt for Claude
        3. Parses the Claude response into individual task commands
        4. Returns correct counts for commands found and tasks created

        Uses a realistic eslint analysis scenario where Claude suggests
        multiple grouped refactoring tasks based on violation patterns.
        """
        interpreter = ToolOutputInterpreter()

        # Mock Claude response with realistic output
        mock_response = """Based on the eslint output, I've identified the following tasks:

sugar add "Fix 15 unused-import violations in src/components/" --type refactor --priority 2 --description "Remove unused imports across component files"
sugar add "Fix 5 no-unused-vars warnings in src/utils/" --type refactor --priority 2 --description "Clean up unused variable declarations"
sugar add "Fix 3 prefer-const errors in src/api/" --type bug_fix --priority 3 --description "Convert let declarations to const where appropriate"

These tasks group related issues for efficient resolution."""

        with patch.object(
            interpreter, "_execute_claude_prompt", new_callable=AsyncMock
        ) as mock_prompt:
            mock_prompt.return_value = {
                "success": True,
                "output": mock_response,
                "error": "",
                "execution_time": 5.0,
            }

            result = await interpreter.interpret_and_execute(
                tool_name="eslint",
                command="eslint src/ --format json",
                output_file_path=self.output_path,
                dry_run=True,
            )

            assert result["success"] is True
            assert result["commands_found"] == 3
            assert result["tasks_created"] == 3

    def test_command_parsing_edge_cases(self):
        """
        Verify _parse_command handles unusual but valid input formats.

        Tests three edge cases that could break naive parsing:

        1. Escaped quotes in description: Ensures shlex-based parsing correctly
           handles escaped double quotes within argument values.

        2. Multiple consecutive spaces: Verifies whitespace normalization works
           and doesn't create empty tokens or misalign argument parsing.

        3. Empty title validation: Confirms the parser rejects commands with
           empty string titles, marking them as invalid.

        Each test case is a tuple of (command_string, expected_validity, expected_title).
        """
        interpreter = ToolOutputInterpreter()

        test_cases = [
            # Case 1: Command with escaped quotes in description
            # Tests shlex handling of backslash-escaped quotes
            (
                'sugar add "Task" --description "Fix the \\"important\\" bug"',
                True,
                "Task",
            ),
            # Case 2: Command with multiple spaces between arguments
            # Tests whitespace normalization during parsing
            (
                'sugar add   "Task with spaces"   --type   bug_fix',
                True,
                "Task with spaces",
            ),
            # Case 3: Empty title (invalid)
            # Tests validation that rejects empty titles
            (
                'sugar add "" --type bug_fix',
                False,
                None,
            ),
        ]

        for cmd_str, expected_valid, expected_title in test_cases:
            cmd = interpreter._parse_command(cmd_str)
            assert cmd.valid == expected_valid, f"Failed for: {cmd_str}"
            if expected_valid:
                assert cmd.title == expected_title, f"Title mismatch for: {cmd_str}"
