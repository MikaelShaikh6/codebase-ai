from app.core.auth import create_access_token, hash_password, verify_password


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_access_token_has_three_signed_segments() -> None:
    token = create_access_token("user-1")

    assert len(token.split(".")) == 3
