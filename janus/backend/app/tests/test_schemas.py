"""Testes dos schemas Pydantic (app.schemas)."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import CompanyOut, LoginResponse, UserOut
from app.schemas.common import ErrorResponse, PaginatedResponse


def test_user_out_valid():
    u = UserOut(id=1, email="a@b.com", full_name="Test", role="admin", companies=[])
    assert u.email == "a@b.com"
    assert u.role == "admin"


def test_user_out_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserOut(id=1, email="not-an-email", role="admin", companies=[])


def test_user_out_companies_default():
    u = UserOut(id=1, email="a@b.com", role="user")
    assert u.companies == []


def test_login_response_serializes():
    resp = LoginResponse(
        access_token="abc.def.ghi",
        token_type="bearer",
        user=UserOut(
            id=1,
            email="a@b.com",
            role="user",
            companies=[
                CompanyOut(id=10, name="ACME"),
            ],
        ),
    )
    data = resp.model_dump()
    assert data["access_token"] == "abc.def.ghi"
    assert data["user"]["companies"][0]["name"] == "ACME"


def test_paginated_response_generic():
    p = PaginatedResponse[int](items=[1, 2, 3], total=3, skip=0, limit=10)
    assert p.items == [1, 2, 3]
    assert p.total == 3


def test_error_response_optional_detail():
    e = ErrorResponse(error="not_found")
    assert e.error == "not_found"
    assert e.detail is None
