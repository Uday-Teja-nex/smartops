from app.rules import ZoneRule, RuleEngine, Observation
from datetime import datetime


POLYGON = [(0, 0), (0.5, 0), (0.5, 1), (0, 1)]


def person(track=1, x=0.2):
    return Observation(track, 'person', x, 0.5, 0.9)


def test_crowd_requires_continuous_duration_and_rearms_after_clear():
    engine = RuleEngine([ZoneRule('lobby', POLYGON, 'crowding', threshold=1, duration=2)])
    assert engine.update(0, [person(1), person(2)]) == []
    assert engine.update(1, [person(1)]) == []
    assert engine.update(2, [person(1), person(2)]) == []
    assert engine.update(3, [person(1), person(2)]) == []
    assert len(engine.update(4, [person(1), person(2)])) == 1
    assert engine.update(5, [person(1), person(2)]) == []
    engine.update(6, [])
    engine.update(7, [person(1), person(2)])
    engine.update(8, [person(1), person(2)])
    assert len(engine.update(9, [person(1), person(2)])) == 1


def test_loitering_is_per_track_and_outside_points_do_not_count():
    engine = RuleEngine([ZoneRule('door', POLYGON, 'loitering', duration=2)])
    engine.update(0, [person(1), person(2, .8)])
    engine.update(1, [person(3), person(2, .8)])
    assert engine.update(2, [person(3), person(2, .8)]) == []
    events = engine.update(3, [person(3), person(2, .8)])
    assert len(events) == 1 and events[0]['trackIds'] == [3]


def test_missing_observations_do_not_count_as_continuous_dwell():
    engine = RuleEngine([ZoneRule('door', POLYGON, 'loitering', duration=2)])
    engine.update(0, [person()])
    assert engine.update(30, [person()]) == []


def test_restricted_entry_is_one_event_until_track_leaves():
    engine = RuleEngine([ZoneRule('door', POLYGON, 'restricted_entry')])
    assert len(engine.update(0, [person()])) == 1
    assert engine.update(1, [person()]) == []
    engine.update(2, [person(x=.8)])
    assert len(engine.update(3, [person()])) == 1


def test_bag_requires_stationary_unattended_duration():
    engine = RuleEngine([ZoneRule('bench', POLYGON, 'unattended_object', duration=2, radius=.1)])
    bag = Observation(2, 'backpack', .2, .5, .8)
    assert engine.update(0, [bag, person()]) == []
    assert engine.update(1, [bag, person(x=.8)]) == []
    assert engine.update(2, [bag, person(x=.8)]) == []
    assert len(engine.update(3, [bag, person(x=.8)])) == 1
    engine.update(4, [bag, person()])
    assert engine.update(5, [bag]) == []


def test_moving_bag_does_not_trigger_stationary_rule():
    engine = RuleEngine([ZoneRule('bench', POLYGON, 'unattended_object', duration=2)])
    for t in range(5):
        assert engine.update(t, [Observation(2, 'backpack', .1 + t * .05, .5, .8)]) == []


def test_one_missed_detection_does_not_repeat_entry_alert():
    engine = RuleEngine([ZoneRule('door', POLYGON, 'restricted_entry')])
    assert len(engine.update(0, [person()])) == 1
    engine.update(.33, [])
    assert engine.update(.66, [person()]) == []


def test_after_hours_uses_zone_timezone_and_overnight_schedule():
    rule = ZoneRule('door', POLYGON, 'after_hours_entry', timezone='Asia/Kolkata',
                    allowed_hours=[{'days': [0], 'start': '22:00', 'end': '06:00'}])
    engine = RuleEngine([rule])
    # Tuesday 05:00 local is still inside Monday's overnight opening window.
    allowed = datetime.fromisoformat('2026-10-26T23:30:00+00:00').timestamp()
    assert engine.update(0, [person()], wall_time=allowed) == []
    outside = datetime.fromisoformat('2026-10-27T01:30:00+00:00').timestamp()
    assert len(engine.update(1, [person()], wall_time=outside)) == 1


def test_aggregate_cooldown_suppresses_flapping_counts():
    engine = RuleEngine([ZoneRule('lobby', POLYGON, 'crowding', threshold=1, duration=1, cooldown=10)])
    crowd = [person(1), person(2)]
    engine.update(0, crowd)
    assert len(engine.update(1, crowd)) == 1
    engine.update(2, [person(1)])            # dips below threshold
    engine.update(3, crowd)
    assert engine.update(4, crowd) == []     # would re-fire without cooldown
    for t in range(5, 12):
        assert engine.update(t, crowd if t != 8 else [person(1)]) == []
    engine.update(12, [person(1)])           # zone clears after the cooldown
    engine.update(13, crowd)
    assert len(engine.update(14, crowd)) == 1  # cooldown elapsed: a new incident


def test_config_defaults_cooldown_for_aggregate_rules_only():
    from app.continuous import DEFAULT_AGGREGATE_COOLDOWN, load_rules
    rules = load_rules({'detectionConfig': {'zones': [{'id': 'z', 'polygon': POLYGON, 'rules': [
        {'type': 'queue_build_up', 'threshold': 2}, {'type': 'restricted_entry'},
        {'type': 'crowding', 'threshold': 3, 'cooldownSeconds': 30}]}]}})
    assert [rule.cooldown for rule in rules] == [DEFAULT_AGGREGATE_COOLDOWN, 0, 30]


def test_rule_incidents_are_categorized_and_worded_for_operators():
    from app.continuous import RULE_PRESENTATION, incident_payload
    from app.rules import ZoneRule
    source = {'id': 's', 'buildingId': 'b', 'floor': 'G', 'zone': 'Store'}
    queue = incident_payload(source, {'zoneId': 'Checkout queue', 'type': 'queue_build_up', 'trackIds': [1, 2, 3],
                                      'count': 3, 'durationSeconds': 8.04, 'confidence': .5}, 0)
    assert (queue['category'], queue['severity']) == ('Queue & Crowd', 'low')
    assert queue['shortSummary'] == '3 people queuing in Checkout queue for 8s'
    assert queue['modelProvider'] == 'rule-engine'
    kinds = {'crowding', 'queue_build_up', 'loitering', 'restricted_entry', 'blocked_exit',
             'unattended_object', 'after_hours_entry'}
    assert set(RULE_PRESENTATION) == kinds
