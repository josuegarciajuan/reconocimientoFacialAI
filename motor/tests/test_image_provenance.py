import cv2
import numpy as np

from motor.core.image_provenance import build_image_metadata, select_max_resolution_frame


def test_select_max_resolution_frame_keeps_native_evidence():
    small = np.zeros((20, 30, 3), dtype=np.uint8)
    large = np.zeros((40, 50, 3), dtype=np.uint8)
    battery = [{"img": small}, {"img": large}]
    assert select_max_resolution_frame(small, [(None, 1, None)], battery) is large


def test_image_metadata_marks_limited_face_and_display_upscale():
    original = np.zeros((100, 120, 3), dtype=np.uint8)
    original[10:20, 10:22] = 255
    processed = cv2.resize(original[0:60, 0:60], (512, 512))
    metadata = build_image_metadata(
        original, (10, 10, 22, 20), processed,
        sr_applied=False, display_upscaled=True,
    )
    assert metadata["quality_label"] == "insufficient"
    assert metadata["display_upscaled"] is True
    assert metadata["original_width"] == 120
    assert metadata["processed_width"] == 512
