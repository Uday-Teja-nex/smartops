import pytest
from pydantic import ValidationError

from app.schemas import SourceUpdateRequest


def config(polygon=None, rule=None):
    return {'zones': [{'id': 'entry', 'polygon': polygon or [[0, 0], [1, 0], [1, 1], [0, 1]],
                       'rules': [rule or {'type': 'restricted_entry'}]}]}


@pytest.mark.parametrize('value', [
    config([[0, 0], [1, 1], [0, 1], [1, 0]]),
    config([[0, 0], [1, 0], [2, 1]]),
    config(rule={'type': 'imaginary_rule'}),
    config(rule={'type': 'loitering', 'durationSeconds': -1}),
    config(rule={'type': 'after_hours_entry', 'timezone': 'Invalid/Zone'}),
    config(rule={'type': 'after_hours_entry', 'allowedHours': [{'days': [9], 'start': '09:00', 'end': '18:00'}]}),
])
def test_source_update_rejects_invalid_zone_rules(value):
    with pytest.raises(ValidationError):
        SourceUpdateRequest(detectionConfig=value)


def test_source_update_preserves_legacy_config_and_valid_zone_schedule():
    value = config(rule={'type': 'after_hours_entry', 'timezone': 'Asia/Kolkata',
                         'allowedHours': [{'days': [0, 1], 'start': '22:00', 'end': '06:00'}]})
    value['minConfidence'] = .4
    result = SourceUpdateRequest(detectionConfig=value)
    assert result.detectionConfig == value
