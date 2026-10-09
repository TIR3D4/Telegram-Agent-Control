"""Password hashing shared with the dependency-free installer."""

import hashlib
import hmac
import secrets


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"pbkdf2_sha256:600000:{salt}:{digest}"


def verify_password(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split(":")
        if algorithm != "pbkdf2_sha256" or int(rounds) != 600_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
