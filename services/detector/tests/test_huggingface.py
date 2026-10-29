import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from app.backends.huggingface import HuggingFaceBackend


class Frame:
    shape = (100, 200, 3)


def test_pixel_boxes_normalized_and_threshold_applied(monkeypatch):
    def handler(request):
        assert request.headers['authorization'] == 'Bearer test-key'
        assert request.content == b'jpeg'
        return httpx.Response(200,json=[{'label':'person','score':.9,'box':{'xmin':20,'ymin':10,'xmax':100,'ymax':90}},
                                       {'label':'bag','score':.1,'box':{'xmin':0,'ymin':0,'xmax':10,'ymax':10}}])
    backend=HuggingFaceBackend('test-key', transport=httpx.MockTransport(handler))
    monkeypatch.setattr(backend,'encode',lambda _:b'jpeg')
    result=backend.detect([Frame()],.5)
    assert len(result)==1 and len(result[0])==1
    box=result[0][0]
    assert (box.x,box.y,box.w,box.h)==(.1,.1,.4,.8)


@pytest.mark.parametrize('response', [httpx.Response(429),httpx.Response(503),
    httpx.Response(200,json=[{'label':'person','score':.9,'box':{'xmin':50,'ymin':0,'xmax':10,'ymax':10}}])])
def test_failed_inference_is_not_empty_scene(monkeypatch,response):
    backend=HuggingFaceBackend('test-key',transport=httpx.MockTransport(lambda _:response))
    monkeypatch.setattr(backend,'encode',lambda _:b'jpeg')
    with pytest.raises((httpx.HTTPStatusError,ValueError)):
        backend.detect([Frame()],.5)
