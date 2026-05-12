"""Integration tests for the generate command with real template rendering."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from peripheralyzer.cli import PeripheralyzerCLI, default_commands


@pytest.fixture
def test_data_dir() -> Path:
    """Return path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def output_dir() -> Path:
    """Create and return a temporary output directory."""
    tmpdir = Path(tempfile.mkdtemp(prefix="peripheralyzer_test_"))
    yield tmpdir
    # Cleanup
    if tmpdir.exists():
        shutil.rmtree(tmpdir)


class TestGenerateWithTestPeripheral:
    """Integration tests using real YAML test data."""

    def test_generate_test_peripheral_creates_files(
        self, test_data_dir: Path, output_dir: Path
    ) -> None:
        """Test that generate creates C++ files from test peripheral YAML."""
        cli = PeripheralyzerCLI(default_commands())

        # Run: peripheralyzer generate -yr test -o out -y peripheral_test.yml -t peripheral.hpp.jinja -t unittest.cpp.jinja
        argv = [
            "generate",
            "-yr", str(test_data_dir),
            "-o", str(output_dir),
            "-y", "peripheral_test.yml",
            "-t", "peripheral.hpp.jinja",
            "-t", "unittest.cpp.jinja",
            "-b",  # banner
            "-a",  # anonymous
            "-v",  # verbose
        ]

        result = cli.run(argv)
        assert result == 0

        # Verify output files were created
        hpp_file = output_dir / "TestPeripheral.hpp"
        cpp_file = output_dir / "TestPeripheral.cpp"

        assert hpp_file.exists(), f"Expected {hpp_file} to be created"
        assert cpp_file.exists(), f"Expected {cpp_file} to be created"

        # Verify files have content
        hpp_content = hpp_file.read_text()
        cpp_content = cpp_file.read_text()

        assert len(hpp_content) > 0
        assert len(cpp_content) > 0

        # Verify files contain expected markers
        assert "#ifndef" in hpp_content, "Header should have include guard"
        assert "#endif" in hpp_content, "Header should have include guard end"
        assert "struct Test" in hpp_content or "struct TestPeripheral" in hpp_content

    def test_generate_all_test_files(self, test_data_dir: Path, output_dir: Path) -> None:
        """Test generating code from all test YAML files."""
        cli = PeripheralyzerCLI(default_commands())

        # Get all peripheral YAML files
        test_yamls = sorted(test_data_dir.glob("peripheral_*.yml"))
        assert len(test_yamls) > 0, "No test peripheral files found"

        for test_yaml in test_yamls:
            argv = [
                "generate",
                "-yr", str(test_data_dir),
                "-o", str(output_dir),
                "-y", test_yaml.name,
                "-t", "peripheral.hpp.jinja",
                "-b",
                "-a",
            ]

            result = cli.run(argv)
            assert result == 0, f"Failed to generate from {test_yaml.name}"

    @pytest.mark.skipif(
        shutil.which("clang-format") is None,
        reason="clang-format not available"
    )
    def test_generated_code_can_be_formatted(
        self, test_data_dir: Path, output_dir: Path
    ) -> None:
        """Test that generated code can be formatted with clang-format."""
        cli = PeripheralyzerCLI(default_commands())

        argv = [
            "generate",
            "-yr", str(test_data_dir),
            "-o", str(output_dir),
            "-y", "peripheral_test.yml",
            "-t", "peripheral.hpp.jinja",
            "-t", "unittest.cpp.jinja",
            "-b",
            "-a",
        ]

        result = cli.run(argv)
        assert result == 0

        # Format generated files
        generated_files = list(output_dir.glob("*.hpp")) + list(output_dir.glob("*.cpp"))
        assert len(generated_files) > 0, "No generated files to format"

        for filepath in generated_files:
            try:
                subprocess.run(
                    ["clang-format", "-Werror", "-i", str(filepath)],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                pytest.fail(
                    f"clang-format failed on {filepath.name}:\n"
                    f"stdout: {e.stdout.decode()}\n"
                    f"stderr: {e.stderr.decode()}"
                )

    @pytest.mark.skipif(
        shutil.which("g++") is None,
        reason="g++ compiler not available"
    )
    def test_generated_code_compiles(
        self, test_data_dir: Path, output_dir: Path
    ) -> None:
        """Test that generated C++ code compiles successfully."""
        cli = PeripheralyzerCLI(default_commands())

        argv = [
            "generate",
            "-yr", str(test_data_dir),
            "-o", str(output_dir),
            "-y", "peripheral_test.yml",
            "-t", "peripheral.hpp.jinja",
            "-t", "unittest.cpp.jinja",
            "-b",
            "-a",
        ]

        result = cli.run(argv)
        assert result == 0

        # Format the generated code
        if shutil.which("clang-format"):
            generated_files = list(output_dir.glob("*.hpp")) + list(output_dir.glob("*.cpp"))
            for filepath in generated_files:
                subprocess.run(
                    ["clang-format", "-Werror", "-i", str(filepath)],
                    check=True,
                    capture_output=True,
                )

        # Compile the test
        cpp_file = output_dir / "TestPeripheral.cpp"
        executable = output_dir / "test_peripheral"

        assert cpp_file.exists(), f"Expected {cpp_file} to be created"

        try:
            subprocess.run(
                [
                    "g++",
                    "-std=c++14",
                    "-Wall",
                    "-Werror",
                    "-Wextra",
                    "-pedantic",
                    "-o", str(executable),
                    f"-I{output_dir}",
                    str(cpp_file),
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            pytest.fail(
                f"g++ compilation failed:\n"
                f"stdout: {e.stdout.decode()}\n"
                f"stderr: {e.stderr.decode()}"
            )

        assert executable.exists(), f"Compilation did not produce executable {executable}"

    @pytest.mark.skipif(
        shutil.which("g++") is None,
        reason="g++ compiler not available"
    )
    def test_generated_code_runs(
        self, test_data_dir: Path, output_dir: Path
    ) -> None:
        """Test that compiled test code runs successfully."""
        cli = PeripheralyzerCLI(default_commands())

        argv = [
            "generate",
            "-yr", str(test_data_dir),
            "-o", str(output_dir),
            "-y", "peripheral_test.yml",
            "-t", "peripheral.hpp.jinja",
            "-t", "unittest.cpp.jinja",
            "-b",
            "-a",
        ]

        result = cli.run(argv)
        assert result == 0

        # Format the generated code
        if shutil.which("clang-format"):
            generated_files = list(output_dir.glob("*.hpp")) + list(output_dir.glob("*.cpp"))
            for filepath in generated_files:
                subprocess.run(
                    ["clang-format", "-Werror", "-i", str(filepath)],
                    check=True,
                    capture_output=True,
                )

        # Compile the test
        cpp_file = output_dir / "TestPeripheral.cpp"
        executable = output_dir / "test_peripheral"

        try:
            subprocess.run(
                [
                    "g++",
                    "-std=c++14",
                    "-Wall",
                    "-Werror",
                    "-Wextra",
                    "-pedantic",
                    "-o", str(executable),
                    f"-I{output_dir}",
                    str(cpp_file),
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            pytest.fail(
                f"g++ compilation failed:\n"
                f"stdout: {e.stdout.decode()}\n"
                f"stderr: {e.stderr.decode()}"
            )

        # Run the executable
        try:
            result = subprocess.run(
                [str(executable)],
                check=True,
                capture_output=True,
                timeout=10,
            )
            assert result.returncode == 0, f"Test executable returned {result.returncode}"
        except subprocess.CalledProcessError as e:
            pytest.fail(
                f"Test executable failed:\n"
                f"stdout: {e.stdout.decode()}\n"
                f"stderr: {e.stderr.decode()}"
            )
        except subprocess.TimeoutExpired:
            pytest.fail("Test executable timed out")
