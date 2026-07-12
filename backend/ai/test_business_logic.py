"""
tests/unit/test_business_logic.py
----------------------------------
Unit tests for Phase 1 business logic modules.
Covers edge cases: line touching, direction reversal, zone boundary, loitering.

Run:  pytest backend/tests/unit/ -v
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers to build synthetic tracks and events
# ---------------------------------------------------------------------------

def make_track(track_id: int, cx: float, cy: float) -> MagicMock:
    """Create a minimal Track-like mock for testing."""
    t = MagicMock()
    t.track_id = track_id
    t.centroid = (cx, cy)
    t.bbox = (int(cx) - 20, int(cy) - 40, int(cx) + 20, int(cy) + 40)
    t.confidence = 0.85
    return t


# ---------------------------------------------------------------------------
# EntryExitCounter tests
# ---------------------------------------------------------------------------

class TestEntryExitCounter:

    def _make_counter(self):
        from backend.ai.business_logic.entry_exit_counter import EntryExitCounter
        return EntryExitCounter(
            line_start=(0, 200),
            line_end=(640, 200),
            in_direction="down",
            debounce_frames=5,
        )

    def test_no_crossing_before_line(self):
        counter = self._make_counter()
        track = make_track(1, 320, 100)  # above line (y=200)
        events = counter.analyze([track], [])
        assert counter.count_in == 0
        assert counter.count_out == 0

    def test_single_downward_crossing_counts_as_in(self):
        counter = self._make_counter()
        track_above = make_track(1, 320, 150)
        track_below = make_track(1, 320, 250)

        # Frame 1 — above line
        counter.analyze([track_above], [])
        assert counter.count_in == 0

        # Frame 2 — below line → crossing IN
        counter.analyze([track_below], [])
        assert counter.count_in == 1
        assert counter.count_out == 0

    def test_upward_crossing_counts_as_out(self):
        counter = self._make_counter()
        # Start below
        counter.analyze([make_track(2, 320, 250)], [])
        # Move above
        counter.analyze([make_track(2, 320, 150)], [])
        assert counter.count_out == 1
        assert counter.count_in == 0

    def test_debounce_prevents_double_count(self):
        counter = self._make_counter()
        # Cross once
        counter.analyze([make_track(3, 320, 150)], [])
        counter.analyze([make_track(3, 320, 250)], [])
        # Immediately cross back — should be debounced
        counter.analyze([make_track(3, 320, 150)], [])
        # Still within debounce window
        assert counter.count_in + counter.count_out == 1

    def test_multiple_tracks_independent(self):
        counter = self._make_counter()
        t1_above = make_track(1, 100, 150)
        t2_above = make_track(2, 200, 150)
        counter.analyze([t1_above, t2_above], [])
        t1_below = make_track(1, 100, 250)
        t2_below = make_track(2, 200, 250)
        counter.analyze([t1_below, t2_below], [])
        assert counter.count_in == 2

    def test_reset_clears_counts(self):
        counter = self._make_counter()
        counter.analyze([make_track(1, 320, 150)], [])
        counter.analyze([make_track(1, 320, 250)], [])
        assert counter.count_in == 1
        counter.reset_counts()
        assert counter.count_in == 0
        assert counter.count_out == 0

    def test_person_touching_line_does_not_double_count(self):
        """A centroid exactly on the line (side=0) should not oscillate counts."""
        counter = self._make_counter()
        counter.analyze([make_track(5, 320, 150)], [])   # above
        counter.analyze([make_track(5, 320, 200)], [])   # ON line (y == line_y)
        counter.analyze([make_track(5, 320, 250)], [])   # below
        # Only one IN crossing expected
        assert counter.count_in == 1

    def test_reversing_direction_before_debounce_expiry(self):
        """Track crosses IN then quickly reverses — OUT should be suppressed."""
        counter = self._make_counter()
        counter.analyze([make_track(6, 320, 150)], [])   # above
        counter.analyze([make_track(6, 320, 250)], [])   # below  → IN
        # Immediately reverse (frames 3-4, within debounce_frames=5)
        counter.analyze([make_track(6, 320, 150)], [])   # above  → OUT suppressed
        assert counter.count_in == 1
        assert counter.count_out == 0


# ---------------------------------------------------------------------------
# ZoneMonitor tests
# ---------------------------------------------------------------------------

class TestZoneMonitor:

    def _make_monitor(self):
        from backend.ai.business_logic.zone_monitor import ZoneConfig, ZoneMonitor
        zones = [
            ZoneConfig(
                zone_id=1,
                name="Test Zone",
                polygon=[(100, 100), (500, 100), (500, 500), (100, 500)],
                threshold=2,
                alert_cooldown_s=0.0,  # no cooldown in tests
            )
        ]
        return ZoneMonitor(zones), zones

    def test_person_inside_zone_increments_occupancy(self):
        monitor, _ = self._make_monitor()
        track = make_track(1, 300, 300)  # inside polygon
        events = monitor.analyze([track], [])
        occupancy_events = [e for e in events if e["type"] == "zone_occupancy"]
        assert occupancy_events[0]["occupancy"] == 1

    def test_person_outside_zone_not_counted(self):
        monitor, _ = self._make_monitor()
        track = make_track(1, 50, 50)  # outside polygon
        events = monitor.analyze([track], [])
        occupancy_events = [e for e in events if e["type"] == "zone_occupancy"]
        assert occupancy_events[0]["occupancy"] == 0

    def test_threshold_breach_emits_alert(self):
        monitor, _ = self._make_monitor()
        tracks = [make_track(i, 300, 300) for i in range(3)]  # 3 > threshold=2
        events = monitor.analyze(tracks, [])
        alert_events = [e for e in events if e["type"] == "zone_overcrowding"]
        assert len(alert_events) == 1
        assert alert_events[0]["severity"] == "high"

    def test_below_threshold_no_alert(self):
        monitor, _ = self._make_monitor()
        tracks = [make_track(i, 300, 300) for i in range(2)]  # == threshold
        events = monitor.analyze(tracks, [])
        alert_events = [e for e in events if e["type"] == "zone_overcrowding"]
        assert len(alert_events) == 1  # >= threshold triggers alert

    def test_one_person_below_threshold_no_alert(self):
        monitor, _ = self._make_monitor()
        tracks = [make_track(1, 300, 300)]  # 1 < threshold=2
        events = monitor.analyze(tracks, [])
        alert_events = [e for e in events if e["type"] == "zone_overcrowding"]
        assert len(alert_events) == 0

    def test_empty_zone_zero_occupancy(self):
        monitor, _ = self._make_monitor()
        events = monitor.analyze([], [])
        occupancy_events = [e for e in events if e["type"] == "zone_occupancy"]
        assert occupancy_events[0]["occupancy"] == 0

    def test_person_on_boundary_counted(self):
        """Vertex of polygon should be inside (pointPolygonTest >= 0)."""
        monitor, _ = self._make_monitor()
        track = make_track(1, 100, 100)  # corner vertex
        events = monitor.analyze([track], [])
        occupancy_events = [e for e in events if e["type"] == "zone_occupancy"]
        assert occupancy_events[0]["occupancy"] == 1


# ---------------------------------------------------------------------------
# BehaviorAnalyzer tests
# ---------------------------------------------------------------------------

class TestBehaviorAnalyzer:

    def _make_analyzer(self):
        from backend.ai.business_logic.behavior_analyzer import BehaviorAnalyzer
        return BehaviorAnalyzer(
            loitering_threshold_s=0.1,  # tiny threshold for unit tests
            movement_threshold_px=10.0,
            alert_cooldown_s=0.0,
        )

    def test_no_alert_on_first_frame(self):
        analyzer = self._make_analyzer()
        track = make_track(1, 300, 300)
        events = analyzer.analyze([track], [])
        loiter = [e for e in events if e["type"] == "loitering"]
        assert len(loiter) == 0

    def test_alert_after_stationary_threshold(self):
        analyzer = self._make_analyzer()
        track = make_track(1, 300, 300)
        analyzer.analyze([track], [])
        time.sleep(0.15)  # exceed loitering_threshold_s=0.1
        events = analyzer.analyze([track], [])
        loiter = [e for e in events if e["type"] == "loitering"]
        assert len(loiter) == 1
        assert loiter[0]["track_id"] == 1

    def test_no_alert_if_moving(self):
        analyzer = self._make_analyzer()
        track_a = make_track(2, 300, 300)
        analyzer.analyze([track_a], [])
        time.sleep(0.15)
        track_b = make_track(2, 320, 340)  # moved > 10px
        events = analyzer.analyze([track_b], [])
        loiter = [e for e in events if e["type"] == "loitering"]
        assert len(loiter) == 0
