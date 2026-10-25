import importlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace


def test_cpu_predictor_serializes_initialization_and_preserves_thread_budget(monkeypatch):
    calls = []
    sizes = []
    class Model:
        active = 0
        peak = 0
        def __init__(self, path):
            pass
        def predict(self, images, **kwargs):
            self.active += 1
            self.peak = max(self.peak, self.active)
            calls.append(kwargs['device'])
            sizes.append(kwargs.get('imgsz'))
            time.sleep(.02)
            self.active -= 1
            return []
    budgets = []
    device = object()
    monkeypatch.setenv('SMARTOPS_DETECTOR_CPU_THREADS', '2')
    monkeypatch.setenv('SMARTOPS_DETECTOR_IMAGE_SIZE', '512')
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(set_num_threads=budgets.append, device=lambda name: device))
    monkeypatch.setitem(sys.modules, 'ultralytics', SimpleNamespace(YOLO=Model))
    sys.modules.pop('app.backends.ultralytics_cpu', None)
    backend = importlib.import_module('app.backends.ultralytics_cpu').UltralyticsCpuBackend()
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: backend.detect([object()], .25), range(3)))
    assert backend.model.peak == 1
    assert budgets and all(value == 2 for value in budgets)
    assert calls == [device] * 3
    assert sizes == [512] * 3
