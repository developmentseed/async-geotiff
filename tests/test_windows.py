"""Tests for the Window class."""

from __future__ import annotations

import pytest

from async_geotiff import Window
from async_geotiff.exceptions import WindowError


class TestWindowCreation:
    """Tests for Window creation."""

    def test_create_window(self) -> None:
        """Test basic window creation."""
        w = Window(col_off=10, row_off=20, width=100, height=50)
        assert w.col_off == 10
        assert w.row_off == 20
        assert w.width == 100
        assert w.height == 50

    def test_negative_offset_raises(self) -> None:
        """Test that negative offsets raise WindowError."""
        with pytest.raises(WindowError, match="non-negative"):
            Window(col_off=-1, row_off=0, width=10, height=10)

    def test_negative_width_raises(self) -> None:
        """Test that negative width raises WindowError."""
        with pytest.raises(WindowError, match="must be positive"):
            Window(col_off=0, row_off=0, width=-1, height=10)

    def test_negative_height_raises(self) -> None:
        """Test that negative height raises WindowError."""
        with pytest.raises(WindowError, match="must be positive"):
            Window(col_off=0, row_off=0, width=10, height=-1)

    def test_zero_width_raises(self) -> None:
        """Test that zero width raises WindowError."""
        with pytest.raises(WindowError, match="must be positive"):
            Window(col_off=0, row_off=0, width=0, height=10)

    def test_zero_height_raises(self) -> None:
        """Test that zero height raises WindowError."""
        with pytest.raises(WindowError, match="must be positive"):
            Window(col_off=0, row_off=0, width=10, height=0)


class TestIntersection:
    """Tests for Window.intersection()."""

    def test_overlapping_windows(self) -> None:
        """Test intersection of overlapping windows."""
        w1 = Window(col_off=0, row_off=0, width=100, height=100)
        w2 = Window(col_off=50, row_off=50, width=100, height=100)
        result = w1.intersection(w2)
        assert result.col_off == 50
        assert result.row_off == 50
        assert result.width == 50
        assert result.height == 50

    def test_contained_window(self) -> None:
        """Test intersection where one window contains another."""
        outer = Window(col_off=0, row_off=0, width=100, height=100)
        inner = Window(col_off=25, row_off=25, width=50, height=50)
        result = outer.intersection(inner)
        assert result == inner

    def test_non_overlapping_raises(self) -> None:
        """Test that non-overlapping windows raise error."""
        w1 = Window(col_off=0, row_off=0, width=50, height=50)
        w2 = Window(col_off=100, row_off=100, width=50, height=50)
        with pytest.raises(WindowError, match="do not intersect"):
            w1.intersection(w2)

    def test_touching_windows_do_not_intersect(self) -> None:
        """Test that touching but non-overlapping windows raise error."""
        w1 = Window(col_off=0, row_off=0, width=50, height=50)
        w2 = Window(col_off=50, row_off=0, width=50, height=50)
        with pytest.raises(WindowError, match="do not intersect"):
            w1.intersection(w2)
