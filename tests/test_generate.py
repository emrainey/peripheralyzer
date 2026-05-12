"""Tests for the generate command."""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from peripheralyzer.generate import (
    GenerateCommand,
    GenerateOptions,
    YamlLoader,
    camel_to_snake_case,
)
from peripheralyzer.paths import package_templates_root


def test_camel_to_snake_case() -> None:
    """Test CamelCase to snake_case conversion."""
    assert camel_to_snake_case("CamelCase") == "camel_case"
    assert camel_to_snake_case("HTTPServer") == "h_t_t_p_server"
    assert camel_to_snake_case("alreadySnake") == "already_snake"
    assert camel_to_snake_case("A") == "a"


def test_generate_options_from_namespace() -> None:
    """Test GenerateOptions construction from argparse namespace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        args = argparse.Namespace(
            banner=True,
            template=["test.jinja"],
            yaml=["test.yml"],
            verbose=True,
            output=tmpdir,
            template_root=str(package_templates_root()),
            yaml_root=tmpdir,
            anonymous=False,
        )

        opts = GenerateOptions.from_namespace(args)
        assert opts.banner is True
        assert opts.templates == ["test.jinja"]
        assert opts.yaml_files == ["test.yml"]
        assert opts.verbose is True


def test_yaml_loader_load_nonexistent_file() -> None:
    """Test that loading a nonexistent file raises FileNotFoundError."""
    loader = YamlLoader(None)
    with pytest.raises(FileNotFoundError):
        loader.load("nonexistent.yml")


def test_yaml_loader_caches_loaded_files() -> None:
    """Test that YamlLoader caches parsed YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yaml_file = tmpdir_path / "test.yml"
        yaml_file.write_text("key: value\n")

        loader = YamlLoader(tmpdir_path)

        # Load the same file twice
        data1 = loader.load("test.yml")
        data2 = loader.load("test.yml")

        # Should be the same object (cached)
        assert data1 is data2
        assert data1["key"] == "value"


def test_yaml_loader_invalid_yaml_content() -> None:
    """Test that loading invalid YAML raises an error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yaml_file = tmpdir_path / "invalid.yml"
        yaml_file.write_text("- item1\n- item2\n")  # YAML list, not dict

        loader = YamlLoader(tmpdir_path)
        with pytest.raises(ValueError, match="Expected YAML mapping"):
            loader.load("invalid.yml")


def test_generate_command_parser_configuration() -> None:
    """Test that GenerateCommand configures parser correctly."""
    command = GenerateCommand()
    parser = argparse.ArgumentParser()
    command.configure_parser(parser)

    # Should parse with required arguments
    args = parser.parse_args([
        "-y", "test.yml",
        "-t", "test.jinja",
    ])

    assert args.yaml == ["test.yml"]
    assert args.template == ["test.jinja"]
    assert args.banner is False
    assert args.verbose is False


def test_generate_command_parser_multiple_templates() -> None:
    """Test that parser accepts multiple templates."""
    command = GenerateCommand()
    parser = argparse.ArgumentParser()
    command.configure_parser(parser)

    args = parser.parse_args([
        "-y", "test.yml",
        "-t", "template1.jinja",
        "-t", "template2.jinja",
    ])

    assert args.template == ["template1.jinja", "template2.jinja"]


def test_generate_command_parser_multiple_yamls() -> None:
    """Test that parser accepts multiple YAML files."""
    command = GenerateCommand()
    parser = argparse.ArgumentParser()
    command.configure_parser(parser)

    args = parser.parse_args([
        "-y", "file1.yml",
        "-y", "file2.yml",
        "-t", "test.jinja",
    ])

    assert args.yaml == ["file1.yml", "file2.yml"]


def test_generate_command_template_root_default() -> None:
    """Test that template root defaults to package templates."""
    command = GenerateCommand()
    parser = argparse.ArgumentParser()
    command.configure_parser(parser)

    args = parser.parse_args([
        "-y", "test.yml",
        "-t", "test.jinja",
    ])

    assert Path(args.template_root) == package_templates_root()


def test_generate_command_custom_template_root() -> None:
    """Test that custom template root can be specified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        command = GenerateCommand()
        parser = argparse.ArgumentParser()
        command.configure_parser(parser)

        args = parser.parse_args([
            "-y", "test.yml",
            "-t", "test.jinja",
            "-tr", tmpdir,
        ])

        assert Path(args.template_root) == Path(tmpdir)


def test_generate_command_parser_anonymous_flag() -> None:
    """Test that anonymous flag is parsed correctly."""
    command = GenerateCommand()
    parser = argparse.ArgumentParser()
    command.configure_parser(parser)

    args = parser.parse_args([
        "-y", "test.yml",
        "-t", "test.jinja",
        "-a",
    ])

    assert args.anonymous is True


def test_generate_command_parser_verbose_banner_flags() -> None:
    """Test that verbose and banner flags work."""
    command = GenerateCommand()
    parser = argparse.ArgumentParser()
    command.configure_parser(parser)

    args = parser.parse_args([
        "-y", "test.yml",
        "-t", "test.jinja",
        "-v",
        "-b",
    ])

    assert args.verbose is True
    assert args.banner is True


def test_generate_command_name_and_help() -> None:
    """Test command name and help attributes."""
    command = GenerateCommand()
    assert command.name == "generate"
    assert "peripheral" in command.help.lower()
    assert "yaml" in command.help.lower()
