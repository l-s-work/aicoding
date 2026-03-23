"""
Pydantic Schema 单元测试

覆盖重点：
- 用户名/密码/手机号等边界校验
- 订单与状态字段合法性
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.address_schema import AddressCreate
from app.schemas.auth_schema import (
    AccountRecoveryApplyRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    UserRegister,
)
from app.schemas.order_schema import OrderCreate, OrderItemCreate, OrderStatusUpdate


def test_user_register_should_accept_valid_payload() -> None:
    payload = UserRegister(
        username="valid_user_1",
        email="valid@example.com",
        password="Pass1234",
    )
    assert payload.username == "valid_user_1"


def test_user_register_should_reject_invalid_username_chars() -> None:
    with pytest.raises(ValidationError):
        UserRegister(
            username="invalid-user",
            email="valid@example.com",
            password="Pass1234",
        )


@pytest.mark.parametrize("password", ["A123456", "A12345678901234567890"])
def test_user_register_should_reject_password_length_boundary(password: str) -> None:
    with pytest.raises(ValidationError):
        UserRegister(
            username="valid_user",
            email="valid@example.com",
            password=password,
        )


def test_change_password_should_reject_password_without_digit() -> None:
    with pytest.raises(ValidationError):
        ChangePasswordRequest(
            current_password="OldPass123",
            new_password="OnlyLetters",
        )


def test_forgot_password_should_reject_invalid_username() -> None:
    with pytest.raises(ValidationError):
        ForgotPasswordRequest(
            username="ab",
            email="valid@example.com",
            new_password="Pass1234",
        )


def test_recovery_apply_should_trim_and_validate_reason() -> None:
    payload = AccountRecoveryApplyRequest(username="user_1", reason="   账号被误封，请恢复   ")
    assert payload.reason == "账号被误封，请恢复"


def test_recovery_apply_should_reject_short_reason() -> None:
    with pytest.raises(ValidationError):
        AccountRecoveryApplyRequest(username="user_1", reason="短")


def test_order_create_should_reject_empty_items() -> None:
    with pytest.raises(ValidationError):
        OrderCreate(address_id=1, items=[])


def test_order_item_create_should_reject_non_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        OrderItemCreate(product_id=1, quantity=0)


def test_order_status_update_should_reject_unknown_status() -> None:
    with pytest.raises(ValidationError):
        OrderStatusUpdate(status="processing")


def test_address_create_should_reject_invalid_phone() -> None:
    with pytest.raises(ValidationError):
        AddressCreate(
            receiver_name="张三",
            phone="123456",
            province="上海市",
            city="上海市",
            district="浦东新区",
            detail_address="世纪大道 1 号",
            is_default=0,
        )
