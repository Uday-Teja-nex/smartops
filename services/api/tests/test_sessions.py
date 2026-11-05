"""Refresh rotation, logout revocation and password hashing upgrades."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import engine
from app.models import UserModel
from app.security import hash_password, needs_rehash, verify_password


@pytest.fixture
def browser(client):
    # Own cookie jar per test; the shared `client` already ran app startup.
    from app.main import app
    with TestClient(app) as fresh:
        yield fresh


def sign_in(browser, email='operator@smartops.local'):
    response = browser.post('/v1/auth/login', json={'email': email, 'password': 'smartops-demo'})
    assert response.status_code == 200, response.text
    cookie = response.headers['set-cookie']
    assert 'smartops_refresh=' in cookie and 'HttpOnly' in cookie
    assert 'Path=/v1/auth' in cookie and 'samesite=strict' in cookie.lower()
    assert response.json()['expiresInSeconds'] == 15 * 60
    return {'Authorization': 'Bearer ' + response.json()['token']}


def test_refresh_rotates_and_detects_replay(browser):
    headers = sign_in(browser)
    first = browser.cookies.get('smartops_refresh')
    refreshed = browser.post('/v1/auth/refresh')
    assert refreshed.status_code == 200
    second = browser.cookies.get('smartops_refresh')
    assert second and second != first
    new_headers = {'Authorization': 'Bearer ' + refreshed.json()['token']}
    assert browser.get('/v1/auth/me', headers=new_headers).status_code == 200

    # Replaying the rotated token revokes the session, including live access tokens.
    browser.cookies.clear()
    replay = browser.post('/v1/auth/refresh', cookies={'smartops_refresh': first})
    assert replay.status_code == 401
    assert browser.get('/v1/auth/me', headers=new_headers).status_code == 401
    assert browser.get('/v1/auth/me', headers=headers).status_code == 401
    assert browser.post('/v1/auth/refresh', cookies={'smartops_refresh': second}).status_code == 401


def test_logout_revokes_access_refresh_and_stream_tickets(browser):
    headers = sign_in(browser)
    ticket = browser.post('/v1/auth/stream-ticket', headers=headers).json()['ticket']
    refresh_token = browser.cookies.get('smartops_refresh')
    assert browser.post('/v1/auth/logout', headers=headers).status_code == 204
    assert browser.get('/v1/auth/me', headers=headers).status_code == 401
    assert browser.get('/v1/incidents/stream', params={'ticket': ticket}).status_code == 401
    browser.cookies.clear()
    assert browser.post('/v1/auth/refresh', cookies={'smartops_refresh': refresh_token}).status_code == 401


def test_logout_one_session_keeps_other_sessions(browser, client):
    from app.main import app
    first = sign_in(browser)
    with TestClient(app) as other:
        second = sign_in(other)
        assert other.post('/v1/auth/logout', headers=second).status_code == 204
    assert browser.get('/v1/auth/me', headers=first).status_code == 200


def test_refresh_requires_cookie_and_active_account(browser):
    assert browser.post('/v1/auth/refresh').status_code == 401
    sign_in(browser, 'viewer@smartops.local')
    with Session(engine) as session:
        user = session.query(UserModel).filter_by(email='viewer@smartops.local').one()
        user.active = False
        session.commit()
    try:
        assert browser.post('/v1/auth/refresh').status_code == 401
    finally:
        with Session(engine) as session:
            session.query(UserModel).filter_by(email='viewer@smartops.local').one().active = True
            session.commit()


def test_tokens_without_session_are_rejected(client):
    import jwt
    from datetime import UTC, datetime, timedelta
    from app.config import get_settings
    legacy = jwt.encode({'sub': 'usr-admin', 'org': 'org-demo', 'role': 'admin',
                         'exp': datetime.now(UTC) + timedelta(minutes=5)},
                        get_settings().jwt_secret, algorithm='HS256')
    assert client.get('/v1/auth/me', headers={'Authorization': 'Bearer ' + legacy}).status_code == 401


def test_argon2id_hashes_and_legacy_pbkdf2_upgrade(browser):
    stored = hash_password('correct horse')
    assert stored.startswith('$argon2id$')
    assert verify_password('correct horse', stored) and not verify_password('wrong', stored)
    assert not needs_rehash(stored)

    import hashlib
    salt = '00' * 16
    legacy = 'pbkdf2_sha256$1000$' + salt + '$' + hashlib.pbkdf2_hmac(
        'sha256', b'smartops-demo', bytes.fromhex(salt), 1000).hex()
    assert verify_password('smartops-demo', legacy) and needs_rehash(legacy)
    with Session(engine) as session:
        user = session.query(UserModel).filter_by(email='supervisor@smartops.local').one()
        user.password_hash = legacy
        session.commit()
    sign_in(browser, 'supervisor@smartops.local')
    with Session(engine) as session:
        upgraded = session.query(UserModel).filter_by(email='supervisor@smartops.local').one().password_hash
    assert upgraded.startswith('$argon2id$')
