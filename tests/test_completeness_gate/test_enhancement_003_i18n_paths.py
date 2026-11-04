"""Test Enhancement 003: Internationalization Path Testing (AC-008)."""

import pytest
import tempfile
from pathlib import Path
from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate


def test_unicode_chinese_filenames():
    """Test S1 Gate with Chinese file names.
    
    Acceptance Criteria: AC-008
    - Handle Unicode (CJK) file names correctly
    - Process content without encoding errors
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    test_files = [
        temp_dir / "测试模块.py",
        temp_dir / "用户认证.py",
        temp_dir / "数据库连接.py",
    ]
    
    for f in test_files:
        f.write_text("def test(): pass", encoding="utf-8")
    
    gate = ImplementationCompletenessGate()
    result = gate.check(test_files)
    
    # Should handle all paths correctly
    assert result["verdict"] == "PASS"
    assert result["completeness_score"] == 1.0


def test_unicode_japanese_filenames():
    """Test S1 Gate with Japanese file names."""
    temp_dir = Path(tempfile.mkdtemp())
    
    test_files = [
        temp_dir / "テストモジュール.py",
        temp_dir / "ユーザー認証.py",
        temp_dir / "データベース接続.py",
    ]
    
    for f in test_files:
        f.write_text("def test(): pass", encoding="utf-8")
    
    gate = ImplementationCompletenessGate()
    result = gate.check(test_files)
    
    assert result["verdict"] == "PASS"
    assert result["completeness_score"] == 1.0


def test_unicode_mixed_languages():
    """Test S1 Gate with mixed language file names."""
    temp_dir = Path(tempfile.mkdtemp())
    
    test_files = [
        temp_dir / "test_テスト_测试.py",
        temp_dir / "混合_mixed_ミックス.py",
        temp_dir / "user_用户_ユーザー.py",
    ]
    
    for f in test_files:
        f.write_text("def test(): pass", encoding="utf-8")
    
    gate = ImplementationCompletenessGate()
    result = gate.check(test_files)
    
    assert result["verdict"] == "PASS"


def test_unicode_emoji_filenames():
    """Test S1 Gate with emoji in file names."""
    temp_dir = Path(tempfile.mkdtemp())
    
    test_files = [
        temp_dir / "test_😀_emoji.py",
        temp_dir / "module_🚀_rocket.py",
        temp_dir / "utils_✨_sparkle.py",
    ]
    
    for f in test_files:
        f.write_text("def test(): pass", encoding="utf-8")
    
    gate = ImplementationCompletenessGate()
    result = gate.check(test_files)
    
    assert result["verdict"] == "PASS"
    assert result["completeness_score"] == 1.0


def test_unicode_paths_with_subdirs():
    """Test S1 Gate with Unicode in directory paths."""
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create nested directories with Unicode names
    chinese_dir = temp_dir / "中文目录"
    chinese_dir.mkdir()
    
    japanese_dir = temp_dir / "日本語ディレクトリ"
    japanese_dir.mkdir()
    
    emoji_dir = temp_dir / "emoji_🎉_dir"
    emoji_dir.mkdir()
    
    test_files = [
        chinese_dir / "模块.py",
        japanese_dir / "モジュール.py",
        emoji_dir / "module.py",
    ]
    
    for f in test_files:
        f.write_text("def test(): pass", encoding="utf-8")
    
    gate = ImplementationCompletenessGate()
    result = gate.check(test_files)
    
    assert result["verdict"] == "PASS"


def test_unicode_content_in_files():
    """Test S1 Gate with Unicode content in Python files."""
    temp_dir = Path(tempfile.mkdtemp())
    
    test_file = temp_dir / "unicode_content.py"
    content = """
def greet_chinese():
    return "你好，世界！"

def greet_japanese():
    return "こんにちは、世界！"

def greet_emoji():
    return "Hello 🌍 World 🚀"
"""
    test_file.write_text(content, encoding="utf-8")
    
    gate = ImplementationCompletenessGate()
    result = gate.check([test_file])
    
    assert result["verdict"] == "PASS"
    assert result["completeness_score"] == 1.0


def test_unicode_paths_with_spaces():
    """Test S1 Gate with Unicode and spaces in paths."""
    temp_dir = Path(tempfile.mkdtemp())
    
    test_files = [
        temp_dir / "测试 模块 with spaces.py",
        temp_dir / "テスト モジュール with spaces.py",
        temp_dir / "test 😀 emoji with spaces.py",
    ]
    
    for f in test_files:
        f.write_text("def test(): pass", encoding="utf-8")
    
    gate = ImplementationCompletenessGate()
    result = gate.check(test_files)
    
    assert result["verdict"] == "PASS"


def test_unicode_special_characters():
    """Test S1 Gate with special Unicode characters."""
    temp_dir = Path(tempfile.mkdtemp())
    
    test_files = [
        temp_dir / "module_with_ñ.py",
        temp_dir / "module_with_ü.py",
        temp_dir / "module_with_ø.py",
        temp_dir / "module_with_ß.py",
    ]
    
    for f in test_files:
        f.write_text("def test(): pass", encoding="utf-8")
    
    gate = ImplementationCompletenessGate()
    result = gate.check(test_files)
    
    assert result["verdict"] == "PASS"


def test_unicode_rtl_languages():
    """Test S1 Gate with right-to-left language file names."""
    temp_dir = Path(tempfile.mkdtemp())
    
    # Arabic and Hebrew file names
    test_files = [
        temp_dir / "مودول.py",  # Arabic
        temp_dir / "מודול.py",  # Hebrew
    ]
    
    for f in test_files:
        f.write_text("def test(): pass", encoding="utf-8")
    
    gate = ImplementationCompletenessGate()
    result = gate.check(test_files)
    
    assert result["verdict"] == "PASS"
