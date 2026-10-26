import importlib.util
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).parents[1] / 'publish.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def test_prepared_clip_reused_and_invalidated_by_input_change(tmp_path):
    source = tmp_path / 'input.mp4'
    source.write_bytes(b'original')
    calls = []
    def encode(command):
        calls.append(command)
        Path(command[-1]).write_bytes(b'encoded')
    first = publisher.prepare_clip(source, tmp_path / 'cache', encode)
    assert first.read_bytes() == b'encoded'
    assert publisher.prepare_clip(source, tmp_path / 'cache', encode) == first
    assert len(calls) == 1
    source.write_bytes(b'changed content')
    assert publisher.prepare_clip(source, tmp_path / 'cache', encode) != first
    assert len(calls) == 2


def test_failed_preparation_never_becomes_a_cached_clip(tmp_path):
    source = tmp_path / 'input.mp4'
    source.write_bytes(b'bad video')
    def fail(command):
        Path(command[-1]).write_bytes(b'partial')
        raise subprocess.CalledProcessError(1, 'ffmpeg')
    with pytest.raises(subprocess.CalledProcessError):
        publisher.prepare_clip(source, tmp_path / 'cache', fail)
    assert not list((tmp_path / 'cache').glob('*.mp4'))
