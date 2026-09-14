import secrets
import string

_ALPHABET = string.ascii_lowercase + string.digits


def new_id():
    """25-char lowercase id shaped like the Kintana cuids we imported, so old and new rows look alike."""
    return 'c' + ''.join(secrets.choice(_ALPHABET) for _ in range(24))


def new_token(nbytes=24):
    return secrets.token_urlsafe(nbytes)
