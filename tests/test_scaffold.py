"""Tests for vyperling.scaffold — `vpl new` skeleton generator."""

import shutil
import subprocess
from pathlib import Path

import pytest

from vyperling.config import load_config
from vyperling.errors import ForgeScaffoldError
from vyperling.scaffold import create_project
from vyperling.runnergen import generate_runner
from vyperling.unity import (
    get_forge_mock_c_path,
    get_forge_mock_include_dir,
    get_unity_c_path,
    get_unity_include_dir,
)

EXPECTED_FILES = [
    "forge.yml",
    "README.md",
    "src/example.h",
    "src/example.c",
    "test/test_example.c",
    "mocks/.gitkeep",
]


def test_creates_expected_tree(tmp_path: Path) -> None:
    root = create_project("demo", tmp_path)
    assert root == tmp_path / "demo"
    for rel in EXPECTED_FILES:
        assert (root / rel).is_file(), f"missing {rel}"


def test_forge_yml_round_trips(tmp_path: Path) -> None:
    root = create_project("demo", tmp_path)
    config = load_config(root / "forge.yml")
    assert config["project"]["name"] == "demo"
    assert config["targets"]["default"] == "native"


def test_raises_if_exists(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    with pytest.raises(ForgeScaffoldError):
        create_project("demo", tmp_path)


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not available")
def test_generated_test_compiles_and_passes(tmp_path: Path) -> None:
    root = create_project("demo", tmp_path)
    test_file = root / "test" / "test_example.c"
    runner_path = tmp_path / "test_example_runner.c"
    generate_runner(test_file, runner_path, mocks=[])

    binary = tmp_path / "test_example"
    cmd = [
        "gcc",
        "-I", str(get_unity_include_dir()),
        "-I", str(get_forge_mock_include_dir()),
        "-I", str(root / "src"),
        str(test_file),
        str(runner_path),
        str(root / "src" / "example.c"),
        str(get_unity_c_path()),
        str(get_forge_mock_c_path()),
        "-o", str(binary),
    ]
    compile_proc = subprocess.run(cmd, capture_output=True, text=True)
    assert compile_proc.returncode == 0, compile_proc.stderr

    run_proc = subprocess.run([str(binary)], capture_output=True, text=True)
    assert run_proc.returncode == 0, run_proc.stdout + run_proc.stderr
    assert "PASS" in run_proc.stdout
