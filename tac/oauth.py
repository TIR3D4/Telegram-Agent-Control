"""OAuth resource-server verification. Authorization/code/PKCE flows belong to the IdP."""

from functools import lru_cache
import jwt
from fastapi import HTTPException
from .config import settings


@lru_cache(maxsize=4)
def jwks_client(url):
    return jwt.PyJWKClient(url, cache_keys=False, cache_jwk_set=True, lifespan=300, timeout=5)


def verify(token):
    config = settings()
    if not config.oauth_issuer or not config.oauth_jwks_url or not config.oauth_audience:
        raise HTTPException(401, "OAuth is not configured")
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in {"RS256", "ES256"} or header.get("crit"):
            raise ValueError("Unsupported signing header")
        key = jwks_client(config.oauth_jwks_url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256", "ES256"],
            audience=config.oauth_audience,
            issuer=config.oauth_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        if claims["exp"] - claims["iat"] > config.oauth_max_lifetime:
            raise ValueError("Token lifetime too long")
        if not isinstance(claims["scope"], str) or not isinstance(claims["sub"], str):
            raise ValueError("Malformed claims")
        return claims
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(401, "Invalid OAuth access token") from None


def challenge():
    return (
        'Bearer resource_metadata="'
        + settings().public_url.rstrip("/")
        + '/.well-known/oauth-protected-resource", error="invalid_token"'
    )
