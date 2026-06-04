"""Tests for vyperling.unity — vendored Unity C asset accessors."""

from pathlib import Path

import pytest

from vyperling.errors import ForgeError
from vyperling.unity import (
    get_forge_mock_c_path,
    get_unity_c_path,
    get_unity_include_dir,
)


class TestGetUnityIncludeDir:
    def test_returns_path(self):
        assert isinstance(get_unity_include_dir(), Path)

    def test_is_absolute(self):
        assert get_unity_include_dir().is_absolute()

    def test_is_directory(self):
        assert get_unity_include_dir().is_dir()

    def test_unity_h_present(self):
        assert (get_unity_include_dir() / "unity.h").is_file()

    def test_unity_internals_h_present(self):
        assert (get_unity_include_dir() / "unity_internals.h").is_file()

    def test_unity_fixture_h_present(self):
        assert (get_unity_include_dir() / "unity_fixture.h").is_file()


class TestGetUnityCPath:
    def test_returns_path(self):
        assert isinstance(get_unity_c_path(), Path)

    def test_is_absolute(self):
        assert get_unity_c_path().is_absolute()

    def test_is_file(self):
        assert get_unity_c_path().is_file()

    def test_filename(self):
        assert get_unity_c_path().name == "unity.c"

    def test_content_is_real_unity(self):
        content = get_unity_c_path().read_text(encoding="utf-8")
        assert "UnityBegin" in content

    def test_collocated_with_include_dir(self):
        assert get_unity_c_path().parent == get_unity_include_dir()


class TestBrokenInstall:
    """Error paths for incomplete/broken installs — vendored asset missing."""

    def test_get_unity_c_path_missing_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.unity._unity_dir", lambda: tmp_path)
        with pytest.raises(ForgeError, match="unity.c not found"):
            get_unity_c_path()

    def test_get_forge_mock_c_path_missing_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.unity._unity_dir", lambda: tmp_path)
        with pytest.raises(ForgeError, match="forge_mock.c not found"):
            get_forge_mock_c_path()

    def test_get_unity_include_dir_missing_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "vyperling.unity._unity_dir", lambda: tmp_path / "nope"
        )
        with pytest.raises(ForgeError, match="include dir not found"):
            get_unity_include_dir()
