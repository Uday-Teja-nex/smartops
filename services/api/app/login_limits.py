"""Shared, atomic login throttling. Redis outages fail closed."""
import hashlib
import hmac
from functools import lru_cache

from fastapi import HTTPException
from redis import Redis
from redis.exceptions import RedisError

from app.config import get_settings

# Increment and expiration happen atomically, including across API workers.
SCRIPT = """
local retry = 0
for i, key in ipairs(KEYS) do
    local count = redis.call('INCR', key)
    if count == 1 then redis.call('EXPIRE', key, ARGV[1]) end
    if count > tonumber(ARGV[i + 1]) then
        retry = math.max(retry, redis.call('TTL', key), 1)
    end
end
return retry
"""


@lru_cache
def client():
    return Redis.from_url(get_settings().redis_url, socket_connect_timeout=2,
                          socket_timeout=2, decode_responses=True)


def enforce_login_limit(address: str, email: str):
    settings = get_settings()
    def key(kind, value):
        digest = hmac.new(settings.jwt_secret.encode(), value.encode(), hashlib.sha256).hexdigest()
        return f'smartops:login:{kind}:{digest}'
    try:
        retry = int(client().eval(SCRIPT, 2, key('ip', address),
                                 key('account', email.strip().lower()), 60, 30, 5))
    except (RedisError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail='Sign-in temporarily unavailable',
                            headers={'Retry-After': '5'}) from exc
    if retry > 0:
        raise HTTPException(status_code=429, detail='Too many sign-in attempts. Try again shortly.',
                            headers={'Retry-After': str(retry)})
