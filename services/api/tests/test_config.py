import pytest
from pydantic import ValidationError

from app.config import Settings


def production_settings(**overrides):
    values = dict(environment='production', jwt_secret='j' * 40,
                  internal_token='i' * 40, minio_access_key='deployment-user',
                  minio_secret_key='s' * 40, seed_demo_data=False,
                  evidence_storage_enabled=True,
                  cors_origins='https://console.example.com',
                  refresh_cookie_secure=True, platform_admin_emails='ops@example.com',
                  secrets_key='x' * 44)
    return Settings(**(values | overrides))


@pytest.mark.parametrize('overrides', [
    {'jwt_secret': 'smartops-dev-secret-change-me'},
    {'jwt_secret': 'short'},
    {'internal_token': 'smartops-internal-dev-token'},
    {'minio_secret_key': 'smartopsminio'},
    {'seed_demo_data': True},
    {'cors_origins': '*'},
    {'refresh_cookie_secure': False},
    {'platform_admin_emails': 'admin@smartops.local'},
    {'secrets_key': ''},
    {'cors_origins': 'https://console.example.com,*'},
])
def test_production_rejects_unsafe_configuration(overrides):
    with pytest.raises(ValidationError):
        production_settings(**overrides)


def test_explicit_production_configuration_is_accepted():
    assert production_settings().environment == 'production'


def test_development_keeps_local_demo_defaults():
    assert Settings(environment='development').seed_demo_data


def test_validation_error_does_not_print_secrets():
    secret = 'private-value-not-for-logs'
    with pytest.raises(ValidationError) as error:
        production_settings(jwt_secret=secret)
    assert secret not in str(error.value)
