import numpy as np

from app.overlays import annotate


def test_annotations_preserve_source_pixels_and_use_actual_boxes():
    source = np.zeros((100, 200, 3), dtype=np.uint8)
    boxes = [{'label': 'person', 'confidence': .9, 'bbox': {'x': .25, 'y': .25, 'w': .5, 'h': .5}}]
    rendered = annotate(source, boxes)
    assert not source.any()
    assert rendered[25, 50].any()
    assert rendered[75, 150].any()
    assert not rendered[90, 190].any()
    assert np.array_equal(annotate(source, []), source)
