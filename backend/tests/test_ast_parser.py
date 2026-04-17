"""Tests for the AST parser module."""

from pathlib import Path

from app.ast_parser import FileParser, parse_file

FIXTURE = str(Path(__file__).resolve().parent / "fixtures" / "sample.py")


class TestFileParser:
    def test_extract_functions_finds_all(self):
        fp = FileParser(FIXTURE)
        funcs = fp.extract_functions()
        names = [f.name for f in funcs]
        assert "__init__" in names
        assert "used_method" in names
        assert "used_function" in names
        assert "caller" in names
        assert "dead_function" in names
        assert "another_dead" in names

    def test_extract_functions_line_ranges(self):
        fp = FileParser(FIXTURE)
        funcs = {f.name: f for f in fp.extract_functions()}
        # __init__ starts at line 5 in sample.py
        assert funcs["__init__"].line_start == 5

    def test_extract_calls(self):
        fp = FileParser(FIXTURE)
        calls = fp.extract_calls()
        assert "used_function" in calls
        assert "used_method" in calls
        assert "Example" in calls

    def test_dead_function_not_in_calls(self):
        fp = FileParser(FIXTURE)
        calls = fp.extract_calls()
        assert "dead_function" not in calls
        assert "another_dead" not in calls


class TestParseFile:
    def test_returns_parsed_file(self):
        pf = parse_file(FIXTURE)
        assert pf.path == FIXTURE
        assert len(pf.functions) >= 5
        assert len(pf.calls) >= 2

    def test_unsupported_extension_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unsupported"):
            parse_file("something.rs")
