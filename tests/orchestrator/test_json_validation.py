"""
Tests for JSON output validation in ToolResult.

Tests the JSON validation feature that checks if tool output is valid JSON,
logs warnings for invalid JSON, and handles edge cases like empty output,
large JSON output, and non-JSON tools.
"""

import json
import logging
import tempfile
from pathlib import Path

import pytest

from sugar.discovery.orchestrator import ToolResult


def create_tool_result_with_output(
    name: str,
    command: str,
    stdout_content: str,
    stderr: str = "",
    exit_code: int = 0,
    success: bool = True,
    duration_seconds: float = 0.0,
    error_message: str = None,
    timed_out: bool = False,
    tool_not_found: bool = False,
) -> ToolResult:
    """Helper to create ToolResult with stdout content written to a temp file."""
    if stdout_content:
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt")
        tmp.write(stdout_content)
        tmp.close()
        output_path = Path(tmp.name)
    else:
        output_path = None

    return ToolResult(
        name=name,
        command=command,
        output_path=output_path,
        stderr=stderr,
        exit_code=exit_code,
        success=success,
        duration_seconds=duration_seconds,
        error_message=error_message,
        timed_out=timed_out,
        tool_not_found=tool_not_found,
    )


class TestJsonValidationBasics:
    """Tests for basic JSON validation functionality"""

    def test_is_json_output_with_valid_json_object(self):
        """Test is_json_output returns True for valid JSON object"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content='{"key": "value", "number": 42}',
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_is_json_output_with_valid_json_array(self):
        """Test is_json_output returns True for valid JSON array"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content='[1, 2, 3, "four"]',
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_is_json_output_with_valid_json_string(self):
        """Test is_json_output returns True for valid JSON primitive (string)"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content='"just a string"',
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_is_json_output_with_valid_json_number(self):
        """Test is_json_output returns True for valid JSON primitive (number)"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content="42.5",
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_is_json_output_with_valid_json_boolean(self):
        """Test is_json_output returns True for valid JSON primitive (boolean)"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content="true",
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_is_json_output_with_valid_json_null(self):
        """Test is_json_output returns True for valid JSON primitive (null)"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content="null",
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None


class TestInvalidJsonHandling:
    """Tests for invalid JSON output handling"""

    def test_is_json_output_with_invalid_json(self):
        """Test is_json_output returns False for invalid JSON"""
        result = create_tool_result_with_output(
            name="test_tool",
            command="cmd",
            stdout_content="This is not JSON",
        )
        assert result.is_json_output is False
        assert result.json_parse_error is not None
        assert "Expecting value" in result.json_parse_error

    def test_is_json_output_with_malformed_json_missing_brace(self):
        """Test is_json_output returns False for malformed JSON (missing brace)"""
        result = create_tool_result_with_output(
            name="test_tool",
            command="cmd",
            stdout_content='{"key": "value"',  # Missing closing brace
        )
        assert result.is_json_output is False
        assert result.json_parse_error is not None

    def test_is_json_output_with_malformed_json_trailing_comma(self):
        """Test is_json_output returns False for malformed JSON (trailing comma)"""
        result = create_tool_result_with_output(
            name="test_tool",
            command="cmd",
            stdout_content='{"key": "value",}',  # Trailing comma
        )
        assert result.is_json_output is False
        assert result.json_parse_error is not None

    def test_is_json_output_with_malformed_json_single_quotes(self):
        """Test is_json_output returns False for malformed JSON (single quotes)"""
        result = create_tool_result_with_output(
            name="test_tool",
            command="cmd",
            stdout_content="{'key': 'value'}",  # Single quotes not valid JSON
        )
        assert result.is_json_output is False
        assert result.json_parse_error is not None

    def test_invalid_json_logs_warning(self, caplog):
        """Test that invalid JSON logs a warning"""
        with caplog.at_level(logging.WARNING):
            result = create_tool_result_with_output(
                name="my_tool",
                command="cmd",
                stdout_content="invalid json content",
            )
            _ = result.is_json_output  # Trigger validation

        assert "my_tool" in caplog.text
        assert "not valid JSON" in caplog.text

    def test_valid_json_does_not_log_warning(self, caplog):
        """Test that valid JSON does not log a warning"""
        with caplog.at_level(logging.WARNING):
            result = create_tool_result_with_output(
                name="my_tool",
                command="cmd",
                stdout_content='{"valid": true}',
            )
            _ = result.is_json_output  # Trigger validation

        assert "not valid JSON" not in caplog.text

    def test_invalid_json_proceeds_without_exception(self):
        """Test that invalid JSON doesn't raise exception, just returns False"""
        result = create_tool_result_with_output(
            name="test_tool",
            command="cmd",
            stdout_content="This will fail to parse",
        )
        # Should not raise any exception
        is_json = result.is_json_output
        error = result.json_parse_error
        assert is_json is False
        assert error is not None


class TestEmptyOutputHandling:
    """Tests for empty output handling"""

    def test_is_json_output_with_empty_output(self):
        """Test is_json_output returns False for empty output"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content="",
        )
        assert result.is_json_output is False
        assert result.json_parse_error is None  # No error for empty output

    def test_is_json_output_with_whitespace_only(self):
        """Test is_json_output returns False for whitespace-only output"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content="   \n\t  ",
        )
        assert result.is_json_output is False
        assert result.json_parse_error is None  # No error for whitespace-only

    def test_is_json_output_with_json_and_leading_whitespace(self):
        """Test is_json_output handles JSON with leading/trailing whitespace"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content='  \n {"key": "value"} \n  ',
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_empty_output_does_not_log_warning(self, caplog):
        """Test that empty output does not log a warning"""
        with caplog.at_level(logging.WARNING):
            result = create_tool_result_with_output(
                name="test",
                command="cmd",
                stdout_content="",
            )
            _ = result.is_json_output  # Trigger validation

        assert "not valid JSON" not in caplog.text

    def test_no_output_file(self):
        """Test is_json_output when output_path is None"""
        result = ToolResult(
            name="test",
            command="cmd",
            output_path=None,
            stderr="",
            exit_code=0,
            success=True,
        )
        assert result.is_json_output is False
        assert result.json_parse_error is None


class TestLargeJsonOutput:
    """Tests for large JSON output handling"""

    def test_large_json_object(self):
        """Test is_json_output with a large JSON object"""
        # Create a large JSON object (about 100KB)
        large_data = {f"key_{i}": f"value_{i}" * 100 for i in range(500)}
        large_json = json.dumps(large_data)

        result = create_tool_result_with_output(
            name="large_json_tool",
            command="cmd",
            stdout_content=large_json,
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None
        assert len(result.stdout) > 100000  # Verify it's actually large

    def test_large_json_array(self):
        """Test is_json_output with a large JSON array"""
        # Create a large JSON array (about 50KB)
        large_array = [{"item": i, "data": "x" * 100} for i in range(500)]
        large_json = json.dumps(large_array)

        result = create_tool_result_with_output(
            name="large_array_tool",
            command="cmd",
            stdout_content=large_json,
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_deeply_nested_json(self):
        """Test is_json_output with deeply nested JSON structure"""
        # Create a deeply nested JSON structure
        nested = {"level": 0}
        current = nested
        for i in range(1, 50):
            current["nested"] = {"level": i}
            current = current["nested"]
        nested_json = json.dumps(nested)

        result = create_tool_result_with_output(
            name="nested_json_tool",
            command="cmd",
            stdout_content=nested_json,
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_large_invalid_json_truncates_in_warning(self, caplog):
        """Test that large invalid output is truncated in warning message"""
        large_invalid = "x" * 200  # Invalid JSON, > 100 chars

        with caplog.at_level(logging.WARNING):
            result = create_tool_result_with_output(
                name="test_tool",
                command="cmd",
                stdout_content=large_invalid,
            )
            _ = result.is_json_output  # Trigger validation

        # Warning should contain truncated output (first 100 chars + "...")
        assert "..." in caplog.text
        assert "x" * 100 in caplog.text  # First 100 chars should be present

    def test_json_with_unicode_characters(self):
        """Test is_json_output with JSON containing unicode characters"""
        unicode_json = json.dumps(
            {
                "emoji": "test",
                "japanese": "test",
                "arabic": "test",
                "chinese": "test",
            }
        )

        result = create_tool_result_with_output(
            name="unicode_tool",
            command="cmd",
            stdout_content=unicode_json,
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_json_with_escaped_characters(self):
        """Test is_json_output with JSON containing escaped characters"""
        escaped_json = json.dumps(
            {
                "newline": "line1\nline2",
                "tab": "col1\tcol2",
                "quote": 'He said "hello"',
                "backslash": "path\\to\\file",
            }
        )

        result = create_tool_result_with_output(
            name="escaped_tool",
            command="cmd",
            stdout_content=escaped_json,
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None


class TestNonJsonTools:
    """Tests for tools that don't produce JSON output.

    These tests verify that the JSON validation correctly identifies
    non-JSON output from tools that aren't configured to output JSON.
    """

    def test_plain_text_linter_output(self):
        """Test that plain text linter output is not identified as JSON"""
        plain_output = """
        src/main.py:10:5: E303 too many blank lines (3)
        src/main.py:15:1: W291 trailing whitespace
        src/utils.py:20:80: E501 line too long (95 > 79 characters)
        
        3 errors found
        """
        result = create_tool_result_with_output(
            name="flake8",
            command="flake8 src/",  # No --format json flag
            stdout_content=plain_output,
        )
        assert result.is_json_output is False
        assert result.json_parse_error is not None

    def test_table_format_output(self):
        """Test that table-formatted output is not identified as JSON"""
        table_output = """
        +----------+--------+-------+
        | File     | Errors | Warns |
        +----------+--------+-------+
        | main.py  | 2      | 1     |
        | utils.py | 0      | 3     |
        +----------+--------+-------+
        """
        result = create_tool_result_with_output(
            name="coverage",
            command="coverage report",  # Table format output
            stdout_content=table_output,
        )
        assert result.is_json_output is False

    def test_xml_output_is_not_json(self):
        """Test that XML output is not identified as JSON"""
        xml_output = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuite name="tests" tests="5" errors="0" failures="1">
            <testcase classname="tests.test_main" name="test_foo"/>
        </testsuite>
        """
        result = create_tool_result_with_output(
            name="pytest",
            command="pytest --junit-xml=report.xml",
            stdout_content=xml_output,
        )
        assert result.is_json_output is False

    def test_yaml_output_is_not_json(self):
        """Test that YAML output is not identified as JSON"""
        yaml_output = """
        name: test
        version: 1.0.0
        dependencies:
          - package1
          - package2
        """
        result = create_tool_result_with_output(
            name="config-tool",
            command="cat config.yaml",
            stdout_content=yaml_output,
        )
        assert result.is_json_output is False

    def test_ansi_colored_output_is_not_json(self):
        """Test that ANSI-colored output is not identified as JSON"""
        ansi_output = (
            "\x1b[31mError:\x1b[0m Something went wrong\n\x1b[32mSuccess:\x1b[0m Done"
        )
        result = create_tool_result_with_output(
            name="colorful-tool",
            command="colorful --color=always",
            stdout_content=ansi_output,
        )
        assert result.is_json_output is False

    def test_mixed_json_with_text_prefix_is_not_valid(self):
        """Test that JSON mixed with text prefix is not valid JSON"""
        mixed_output = 'Running linter...\n{"errors": [], "warnings": []}'
        result = create_tool_result_with_output(
            name="verbose-linter",
            command="linter --verbose --format json",
            stdout_content=mixed_output,
        )
        # This should NOT be valid JSON because of the text prefix
        assert result.is_json_output is False

    def test_json_tool_with_valid_json(self):
        """Test that a JSON-formatted tool output is correctly identified"""
        json_output = json.dumps(
            {
                "errors": [
                    {"file": "main.py", "line": 10, "message": "undefined variable"}
                ],
                "warnings": [],
                "summary": {"total_errors": 1, "total_warnings": 0},
            }
        )
        result = create_tool_result_with_output(
            name="eslint",
            command="npx eslint . --format json",  # Has --format json flag
            stdout_content=json_output,
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None

    def test_tool_without_json_flag_can_still_have_json_output(self):
        """Test that even without explicit JSON flag, valid JSON is recognized"""
        # Some tools output JSON by default
        json_output = '{"version": "1.0.0"}'
        result = create_tool_result_with_output(
            name="version-checker",
            command="version-checker",  # No explicit JSON flag
            stdout_content=json_output,
        )
        assert result.is_json_output is True
        assert result.json_parse_error is None


class TestJsonValidationCaching:
    """Tests for JSON validation caching behavior"""

    def test_json_validation_is_cached(self):
        """Test that JSON validation result is cached"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content='{"cached": true}',
        )
        # First access
        assert result.is_json_output is True
        assert result._json_validated is True

        # Modify the cached value (testing cache behavior)
        result._is_json_output = False

        # Second access should return cached value
        assert result.is_json_output is False

    def test_json_parse_error_uses_cached_validation(self):
        """Test that json_parse_error uses cached validation"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content="invalid",
        )
        # Access is_json_output first
        _ = result.is_json_output
        cached_error = result._json_parse_error

        # Accessing json_parse_error should use cached result
        assert result.json_parse_error == cached_error

    def test_validation_not_triggered_until_property_access(self):
        """Test that validation is lazy (not triggered until property access)"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content="some content",
        )
        # Before accessing any JSON property
        assert result._json_validated is False

        # Trigger validation
        _ = result.is_json_output

        # After accessing JSON property
        assert result._json_validated is True


class TestToDictWithJsonFields:
    """Tests for to_dict serialization including JSON validation fields"""

    def test_to_dict_includes_json_fields_for_valid_json(self):
        """Test to_dict includes is_json_output and json_parse_error for valid JSON"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content='{"valid": true}',
        )
        d = result.to_dict()
        assert "is_json_output" in d
        assert "json_parse_error" in d
        assert d["is_json_output"] is True
        assert d["json_parse_error"] is None

    def test_to_dict_includes_json_fields_for_invalid_json(self):
        """Test to_dict with invalid JSON includes error message"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content="not json",
        )
        d = result.to_dict()
        assert d["is_json_output"] is False
        assert d["json_parse_error"] is not None

    def test_to_dict_includes_json_fields_for_empty_output(self):
        """Test to_dict with empty output includes JSON fields"""
        result = create_tool_result_with_output(
            name="test",
            command="cmd",
            stdout_content="",
        )
        d = result.to_dict()
        assert d["is_json_output"] is False
        assert d["json_parse_error"] is None
