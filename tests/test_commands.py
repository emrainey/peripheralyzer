"""Tests for utility commands."""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pytest

from peripheralyzer.map_diff import MapDiffCommand
from peripheralyzer.merge_name_maps import MergeNameMapsCommand
from peripheralyzer.track_name_map_changes import TrackNameMapChangesCommand
from peripheralyzer.verify_name_map import VerifyNameMapCommand
from peripheralyzer.peripheral_duplicate_finder import PeripheralDuplicateFinderCommand


class TestMapDiffCommand:
    """Tests for MapDiffCommand (now used as 'diff' under 'name-map')."""

    def test_command_exists(self) -> None:
        """Test that MapDiffCommand can be instantiated."""
        command = MapDiffCommand()
        assert command is not None

    def test_command_original_name(self) -> None:
        """Test command original name before being used in group."""
        command = MapDiffCommand()
        assert command.name == "name-map-diff"
        assert len(command.help) > 0


class TestMergeNameMapsCommand:
    """Tests for MergeNameMapsCommand (now used as 'merge' under 'name-map')."""

    def test_command_exists(self) -> None:
        """Test that MergeNameMapsCommand can be instantiated."""
        command = MergeNameMapsCommand()
        assert command is not None

    def test_command_original_name(self) -> None:
        """Test command original name before being used in group."""
        command = MergeNameMapsCommand()
        assert command.name == "merge-name-maps"
        assert len(command.help) > 0

    def test_parser_configuration(self) -> None:
        """Test parser configuration."""
        command = MergeNameMapsCommand()
        parser = argparse.ArgumentParser()
        # Should not raise
        command.configure_parser(parser)


class TestTrackNameMapChangesCommand:
    """Tests for TrackNameMapChangesCommand (now used as 'track' under 'name-map')."""

    def test_command_exists(self) -> None:
        """Test that TrackNameMapChangesCommand can be instantiated."""
        command = TrackNameMapChangesCommand()
        assert command is not None

    def test_command_original_name(self) -> None:
        """Test command original name before being used in group."""
        command = TrackNameMapChangesCommand()
        assert command.name == "track-name-map-changes"
        assert len(command.help) > 0


class TestVerifyNameMapCommand:
    """Tests for VerifyNameMapCommand (now used as 'verify' under 'name-map')."""

    def test_command_exists(self) -> None:
        """Test that VerifyNameMapCommand can be instantiated."""
        command = VerifyNameMapCommand()
        assert command is not None

    def test_command_original_name(self) -> None:
        """Test command original name before being used in group."""
        command = VerifyNameMapCommand()
        assert command.name == "verify-name-map"
        assert len(command.help) > 0


class TestPeripheralDuplicateFinderCommand:
    """Tests for PeripheralDuplicateFinderCommand."""

    def test_command_exists(self) -> None:
        """Test that PeripheralDuplicateFinderCommand can be instantiated."""
        command = PeripheralDuplicateFinderCommand()
        assert command is not None

    def test_command_name_and_help(self) -> None:
        """Test command name and help."""
        command = PeripheralDuplicateFinderCommand()
        assert command.name == "find-duplicates"
        assert len(command.help) > 0

    def test_parser_configuration(self) -> None:
        """Test parser configuration."""
        command = PeripheralDuplicateFinderCommand()
        parser = argparse.ArgumentParser()
        # Should not raise
        command.configure_parser(parser)
