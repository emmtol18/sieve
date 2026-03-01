import uuid

from sieve.api.auth.deps import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)


def test_password_hashing():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(str(user_id))
    decoded_id = verify_token(token)
    assert decoded_id == str(user_id)


def test_jwt_invalid_token():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        verify_token("invalid-token")
    assert exc.value.status_code == 401
