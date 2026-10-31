"""Computed reports over stored incidents, independent of console pagination."""
from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_viewer
from app.models import BuildingModel, IncidentModel
from app.tenancy import get_tenant_session

router = APIRouter(prefix='/v1/reports', tags=['reports'], dependencies=[Depends(require_viewer)])


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@router.get('/summary')
def summary(
    start: datetime,
    end: datetime,
    building_id: str | None = Query(default=None, alias='buildingId'),
    session: Session = Depends(get_tenant_session),
):
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status_code=422, detail='Report timestamps require timezones')
    start, end = utc(start), utc(end)
    if end <= start or end - start > timedelta(days=31):
        raise HTTPException(status_code=422, detail='Report interval must be positive and at most 31 days')
    if building_id and session.get(BuildingModel, building_id) is None:
        raise HTTPException(status_code=404, detail='Building not found')
    query = select(IncidentModel).where(IncidentModel.start_time >= start, IncidentModel.start_time < end)
    if building_id:
        query = query.where(IncidentModel.building_id == building_id)
    categories, types, statuses, days = Counter(), Counter(), Counter(), Counter()
    total = ack_count = resolve_count = 0
    ack_sum = resolve_sum = 0.0
    for incident in session.scalars(query.execution_options(yield_per=500)):
        total += 1
        categories[incident.category] += 1
        types[incident.event_type] += 1
        statuses[incident.status] += 1
        started = utc(incident.start_time)
        days[started.date().isoformat()] += 1
        for field, kind in ((incident.ack_time, 'ack'), (incident.resolved_time, 'resolve')):
            if field is None:
                continue
            minutes = (utc(field) - started).total_seconds() / 60
            if minutes < 0:
                continue
            if kind == 'ack':
                ack_count += 1
                ack_sum += minutes
            else:
                resolve_count += 1
                resolve_sum += minutes
    # Include zero-count dates; first and last dates may cover partial UTC days.
    day = start.date()
    while day <= (end - timedelta(microseconds=1)).date():
        days.setdefault(day.isoformat(), 0)
        day += timedelta(days=1)
    completed = statuses['resolved'] + statuses['false_positive']
    return {
        'start': start, 'end': end, 'timezone': 'UTC', 'buildingId': building_id,
        'totalIncidents': total, 'categories': dict(categories), 'types': dict(types),
        'statuses': dict(statuses),
        'daily': [{'date': date, 'count': days[date]} for date in sorted(days)],
        'acknowledgedCount': ack_count, 'resolvedTimeCount': resolve_count,
        'averageAckMinutes': ack_sum / ack_count if ack_count else None,
        'averageResolveMinutes': resolve_sum / resolve_count if resolve_count else None,
        'completionRate': completed / total if total else None,
        'falsePositiveRate': statuses['false_positive'] / total if total else None,
    }
