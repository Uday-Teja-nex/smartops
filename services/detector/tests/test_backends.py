"""Backend selection: CPU, CUDA (fails clearly without a GPU) and remote."""
import httpx
import numpy as np
import pytest


def test_remote_backend_round_trips_the_detector_contract():
    from app.backends.remote import RemoteBackend
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        body = __import__("json").loads(request.content)
        seen["frames"] = len(body["frames"])
        return httpx.Response(200, json={"modelName": "yolov8n.pt", "backend": "ultralytics-cuda", "inferenceMs": 4,
                                         "detections": [{"frameIndex": 1, "timestampSeconds": 0, "label": "person",
                                                         "confidence": 0.9,
                                                         "bbox": {"x": .1, "y": .2, "w": .3, "h": .4}}]})

    client = httpx.Client(base_url="http://gpu-box:8200", transport=httpx.MockTransport(handler),
                          headers={"Authorization": "Bearer t"})
    backend = RemoteBackend("http://gpu-box:8200", "t", client=client)
    frames = [np.zeros((32, 32, 3), dtype=np.uint8), np.zeros((32, 32, 3), dtype=np.uint8)]
    result = backend.detect(frames, 0.25)
    assert seen == {"auth": "Bearer t", "frames": 2}
    assert result[0] == [] and result[1][0].label == "person" and result[1][0].h == .4
    assert backend.model_name == "remote:yolov8n.pt"


def test_remote_backend_rejects_bad_urls_and_frame_indexes():
    from app.backends.remote import RemoteBackend
    with pytest.raises(ValueError):
        RemoteBackend("gpu-box:8200")
    bad = httpx.Client(base_url="http://x", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
        "detections": [{"frameIndex": 7, "label": "person", "confidence": 1, "bbox": {"x": 0, "y": 0, "w": 1, "h": 1}}]})))
    with pytest.raises(ValueError, match="frame index"):
        RemoteBackend("http://x", client=bad).detect([np.zeros((8, 8, 3), dtype=np.uint8)], .25)


def _fake_torch(monkeypatch, cuda_available):
    import importlib
    import sys
    from types import SimpleNamespace
    devices = []
    torch = SimpleNamespace(set_num_threads=lambda n: None, device=lambda name: devices.append(name) or name,
                            cuda=SimpleNamespace(is_available=lambda: cuda_available))
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda path: object()))
    sys.modules.pop("app.backends.ultralytics_cpu", None)
    return importlib.import_module("app.backends.ultralytics_cpu"), devices


def test_cuda_backend_fails_clearly_without_a_gpu(monkeypatch):
    module, _ = _fake_torch(monkeypatch, cuda_available=False)
    with pytest.raises(RuntimeError, match="no CUDA device"):
        module.UltralyticsCudaBackend()


def test_cuda_backend_uses_the_configured_gpu(monkeypatch):
    module, devices = _fake_torch(monkeypatch, cuda_available=True)
    monkeypatch.setenv("SMARTOPS_DETECTOR_DEVICE", "cuda:1")
    backend = module.UltralyticsCudaBackend()
    assert backend.name == "ultralytics-cuda" and devices == ["cuda:1"]


def test_registry_selects_remote(monkeypatch):
    from app.backends import get_backend
    from app.backends.remote import RemoteBackend
    monkeypatch.setenv("SMARTOPS_DETECTOR_BACKEND", "remote")
    monkeypatch.setenv("SMARTOPS_DETECTOR_REMOTE_URL", "https://gpu.example.test")
    assert isinstance(get_backend(), RemoteBackend)
