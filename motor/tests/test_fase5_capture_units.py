"""Tests de la Fase 5: publicación de unidades durante la grabación."""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

from motor.core.capture_units import (
    CaptureUnitPublisher,
    unit_frames_for,
)
from motor.core.video import VideoConfig


def _frame(w: int = 16, h: int = 16, value: int = 0) -> np.ndarray:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :] = value
    return arr


def _cfg() -> VideoConfig:
    return VideoConfig(crf=28, preset="ultrafast", fps=10)


@pytest.mark.skipif(not os.path.exists("/usr/bin/ffmpeg"), reason="ffmpeg no disponible")
class TestCaptureUnitPublisher:
    def test_rotates_segments_and_writes_descriptors(self, tmp_path):
        closed = []
        pub = CaptureUnitPublisher(
            str(tmp_path), "1", "cam1", (16, 16), 10, _cfg(),
            unit_frames=4, event_id="evt",
            on_unit_closed=closed.append,
        )
        for i in range(10):
            pub.write(_frame(value=i * 10))
        units = pub.close()

        assert len(units) == 3
        assert len(closed) == 3
        assert [u.frame_count for u in units] == [4, 4, 2]
        assert units[0].frame_start == 0 and units[0].frame_end == 4
        assert units[1].frame_start == 4 and units[1].frame_end == 8
        assert units[2].frame_start == 8 and units[2].frame_end == 10

        for u in units:
            assert os.path.exists(u.segment_path)
            assert os.path.getsize(u.segment_path) > 0
            desc = u.segment_path + ".unit.json"
            assert os.path.exists(desc)
            with open(desc, encoding="utf-8") as fh:
                data = json.load(fh)
            assert data["unit_id"] == u.unit_id
            assert data["camera_id"] == "cam1"
            assert data["frame_count"] == u.frame_count

    def test_close_is_idempotent(self, tmp_path):
        pub = CaptureUnitPublisher(
            str(tmp_path), "1", "cam1", (16, 16), 10, _cfg(),
            unit_frames=100, event_id="evt",
        )
        pub.write(_frame())
        first = pub.close()
        second = pub.close()
        assert len(first) == 1
        assert len(second) == 1

    def test_concat_multiple_segments(self, tmp_path):
        pub = CaptureUnitPublisher(
            str(tmp_path), "1", "cam1", (16, 16), 10, _cfg(),
            unit_frames=3, event_id="evt",
        )
        for i in range(7):
            pub.write(_frame(value=i * 10))
        pub.close()
        final = str(tmp_path / "final.mp4")
        assert pub.concat(final) is True
        assert os.path.exists(final)
        assert os.path.getsize(final) > 0

    def test_concat_single_segment(self, tmp_path):
        pub = CaptureUnitPublisher(
            str(tmp_path), "1", "cam1", (16, 16), 10, _cfg(),
            unit_frames=100, event_id="evt",
        )
        for i in range(3):
            pub.write(_frame(value=i * 10))
        pub.close()
        final = str(tmp_path / "final.mp4")
        assert pub.concat(final) is True
        assert os.path.exists(final)


class TestUnitFramesFor:
    def test_basic(self):
        assert unit_frames_for(10.0, 20.0) == 200

    def test_minimum(self):
        assert unit_frames_for(1.0, 1.0, minimum=30) == 30
