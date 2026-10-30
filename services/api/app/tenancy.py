"""Request-scoped ORM visibility; authentication uses a separate unscoped session."""
from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

from app.auth import Principal, get_current_principal
from app.db import SessionLocal
from app.models import BuildingModel, SourceModel, IncidentModel, EvidenceItemModel, DetectionModel, UserModel


def get_tenant_session(principal: Principal = Depends(get_current_principal)):
    with SessionLocal() as session:
        def scope_query(state):
            if state.is_select:
                state.statement = state.statement.options(*[
                    with_loader_criteria(model, model.org_id == principal.org_id, include_aliases=True)
                    for model in (BuildingModel, SourceModel, IncidentModel, EvidenceItemModel, DetectionModel, UserModel)
                ])
        event.listen(session, 'do_orm_execute', scope_query)
        yield session
