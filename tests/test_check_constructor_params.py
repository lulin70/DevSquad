"""Tests for V4.2.1 P1-13 Constructor Parameter Counter."""

import textwrap
from pathlib import Path

from scripts.check_constructor_params import (
    check_constructor_params,
    extract_constructors,
)


class TestExtractConstructors:
    """Test constructor extraction from source code."""

    def test_extracts_init_methods(self, tmp_path: Path):
        """__init__ methods are extracted."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                class Foo:
                    def __init__(self, a, b):
                        pass

                class Bar:
                    def __init__(self, x):
                        pass
            """)
        )
        ctors = extract_constructors(tmp_path)
        assert len(ctors) == 2
        names = [c.class_name for c in ctors]
        assert "Foo" in names
        assert "Bar" in names

    def test_counts_params_excluding_self(self, tmp_path: Path):
        """self is not counted as a parameter."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                class Foo:
                    def __init__(self, a, b, c):
                        pass
            """)
        )
        ctors = extract_constructors(tmp_path)
        assert ctors[0].param_count == 3
        assert "self" not in ctors[0].param_names

    def test_counts_keyword_only_args(self, tmp_path: Path):
        """Keyword-only args are counted."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                class Foo:
                    def __init__(self, a, *, b, c):
                        pass
            """)
        )
        ctors = extract_constructors(tmp_path)
        assert ctors[0].param_count == 3
        assert "b" in ctors[0].param_names
        assert "c" in ctors[0].param_names

    def test_detects_kwargs(self, tmp_path: Path):
        """**kwargs presence is detected."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                class Foo:
                    def __init__(self, a, **kwargs):
                        pass
            """)
        )
        ctors = extract_constructors(tmp_path)
        assert ctors[0].has_kwargs is True

    def test_detects_varargs(self, tmp_path: Path):
        """*args presence is detected."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                class Foo:
                    def __init__(self, a, *args):
                        pass
            """)
        )
        ctors = extract_constructors(tmp_path)
        assert ctors[0].has_varargs is True

    def test_no_init_method(self, tmp_path: Path):
        """Classes without __init__ are skipped."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                class Foo:
                    def do_something(self):
                        pass
            """)
        )
        ctors = extract_constructors(tmp_path)
        assert ctors == []

    def test_handles_syntax_error(self, tmp_path: Path):
        """Syntax errors are skipped gracefully."""
        src = tmp_path / "bad.py"
        src.write_text("class Foo:\n    def __init__(\n")
        ctors = extract_constructors(tmp_path)
        assert ctors == []


class TestCheckConstructorParams:
    """Test parameter threshold checking."""

    def test_flags_exceeding_threshold(self, tmp_path: Path):
        """Constructors with >threshold params are flagged."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            textwrap.dedent("""
                class GodCtor:
                    def __init__(self, a, b, c, d, e, f, g, h):
                        pass

                class SmallCtor:
                    def __init__(self, a, b):
                        pass
            """)
        )
        report = check_constructor_params(src, threshold=7)
        assert report.total_constructors == 2
        assert len(report.flagged) == 1
        assert report.flagged[0].class_name == "GodCtor"
        assert report.flagged[0].param_count == 8

    def test_no_flagged_under_threshold(self, tmp_path: Path):
        """No constructors flagged when all are under threshold."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            textwrap.dedent("""
                class Small:
                    def __init__(self, a, b, c):
                        pass
            """)
        )
        report = check_constructor_params(src, threshold=7)
        assert len(report.flagged) == 0

    def test_sorted_by_param_count_desc(self, tmp_path: Path):
        """Flagged constructors sorted by param count descending."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            textwrap.dedent("""
                class A:
                    def __init__(self, a, b, c, d, e, f, g, h):
                        pass
                class B:
                    def __init__(self, a, b, c, d, e, f, g, h, i, j):
                        pass
            """)
        )
        report = check_constructor_params(src, threshold=7)
        assert report.flagged[0].param_count == 10
        assert report.flagged[1].param_count == 8

    def test_custom_threshold(self, tmp_path: Path):
        """Custom threshold works."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            textwrap.dedent("""
                class A:
                    def __init__(self, a, b, c):
                        pass
            """)
        )
        report = check_constructor_params(src, threshold=2)
        assert len(report.flagged) == 1

    def test_to_dict(self, tmp_path: Path):
        """to_dict returns correct structure."""
        report = check_constructor_params(tmp_path, threshold=7)
        d = report.to_dict()
        assert "total_constructors" in d
        assert "flagged_count" in d
        assert "threshold" in d
        assert "flagged" in d
