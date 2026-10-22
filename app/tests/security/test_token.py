from datetime import timedelta
from uuid import uuid4

import pytest
from jwt import decode, ExpiredSignatureError, InvalidSignatureError

from app.security.token import create_access_token, SECRET_KEY, ALGORITHM


class TestCreateAccessToken:

    def test_create_access_token_returns_token(self):
        access_token = create_access_token(user_id=str(uuid4()))

        assert access_token is not None
        assert isinstance(access_token, str)

    def test_access_token_contains_user_id(self):
        user_id = uuid4()

        access_token = create_access_token(user_id=str(user_id))

        payload = decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == str(user_id)

    def test_access_token_contains_expiration(self):
        access_token = create_access_token(user_id=str(uuid4()))

        payload = decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])

        assert "exp" in payload

    def test_access_token_does_not_contain_role(self):
        access_token = create_access_token(user_id=str(uuid4()))

        payload = decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])

        assert "role" not in payload

    def test_expired_token_is_rejected(self):
        access_token = create_access_token(
            user_id=str(uuid4()),
            expires_delta=timedelta(seconds=-1),
        )

        with pytest.raises(ExpiredSignatureError):
            decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])

    def test_token_signed_with_other_key_is_rejected(self):
        access_token = create_access_token(user_id=str(uuid4()))

        with pytest.raises(InvalidSignatureError):
            decode(access_token, "a-different-secret-key-of-32-bytes!!", algorithms=[ALGORITHM])