"""
AI 服务纯函数单元测试

覆盖重点：
- 文本相似度兜底逻辑
- 预算/约束解析边界
- 向量相似度异常降级
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from app.db.models import Product, UserAddress
from app.services.ai_service import (
    build_full_address,
    build_order_list_answer,
    build_similarity_tokens,
    compute_text_similarity,
    compute_vector_similarity,
    extract_product_request_constraints,
    normalize_budget_value,
    normalize_similarity_text,
    parse_receiver_info,
    product_matches_constraints,
)


def test_normalize_similarity_text_should_strip_symbols_and_lowercase() -> None:
    normalized = normalize_similarity_text("  AirPods!! Pro，二代  ")
    assert normalized == "airpods pro 二代"


def test_build_similarity_tokens_should_include_chinese_bigrams() -> None:
    tokens = build_similarity_tokens("蓝牙耳机")
    assert {"蓝牙", "牙耳", "耳机"}.issubset(tokens)


def test_compute_text_similarity_should_return_zero_for_empty_input() -> None:
    assert compute_text_similarity("", "蓝牙耳机") == 0.0
    assert compute_text_similarity("蓝牙耳机", "") == 0.0


def test_compute_text_similarity_should_be_high_for_substring_match() -> None:
    score = compute_text_similarity("耳机", "主动降噪蓝牙耳机")
    assert score > 0.6
    assert score <= 1.0


def test_normalize_budget_value_should_support_k_and_wan() -> None:
    assert normalize_budget_value("3", "3k") == 3000
    assert normalize_budget_value("0.5", "0.5万") == 5000
    # 兼容“3-5000”省略写法，低位按千处理
    assert normalize_budget_value("3", "3-5000", counterpart=5000) == 3000


def test_extract_product_request_constraints_should_parse_range_count_and_category() -> None:
    constraints = extract_product_request_constraints("推荐 3-5000 的手机，来 2 款")
    assert constraints["price_min"] == 3000
    assert constraints["price_max"] == 5000
    assert constraints["requested_count"] == 2
    assert "手机" in constraints["categories"]


def test_product_matches_constraints_should_filter_by_budget_and_category() -> None:
    product = Product(
        id=1,
        name="主动降噪耳机",
        description="蓝牙 5.3，长续航",
        price=899.0,
        stock=5,
        tags=json.dumps(["耳机", "蓝牙"], ensure_ascii=False),
        status="on_sale",
    )

    assert product_matches_constraints(
        product,
        {"price_min": 500, "price_max": 1000, "categories": ["耳机"]},
    ) is True
    assert product_matches_constraints(
        product,
        {"price_min": 1000, "price_max": None, "categories": ["耳机"]},
    ) is False
    assert product_matches_constraints(
        product,
        {"price_min": None, "price_max": 1000, "categories": ["手机"]},
    ) is False


def test_compute_vector_similarity_should_return_none_for_invalid_json() -> None:
    query = np.array([1.0, 0.0], dtype=np.float32)
    assert compute_vector_similarity(query, "not-json", product_id=1) is None


def test_compute_vector_similarity_should_return_none_for_shape_mismatch() -> None:
    query = np.array([1.0, 0.0], dtype=np.float32)
    assert compute_vector_similarity(query, "[1.0, 0.0, 0.0]", product_id=1) is None


def test_compute_vector_similarity_should_handle_zero_vector() -> None:
    query = np.array([0.0, 0.0], dtype=np.float32)
    score = compute_vector_similarity(query, "[0.0, 0.0]", product_id=1)
    assert score == 0.0


def test_compute_vector_similarity_should_calculate_cosine_similarity() -> None:
    query = np.array([1.0, 1.0], dtype=np.float32)
    score = compute_vector_similarity(query, "[1.0, 1.0]", product_id=1)
    assert score == pytest.approx(1.0)


def test_parse_receiver_info_should_return_empty_dict_for_invalid_json() -> None:
    assert parse_receiver_info("not-json") == {}
    assert parse_receiver_info('["wrong-shape"]') == {}


def test_build_full_address_should_support_dict_and_model() -> None:
    address_dict = {
        "province": "浙江省",
        "city": "杭州市",
        "district": "西湖区",
        "detail_address": "文三路 88 号",
    }
    assert build_full_address(address_dict) == "浙江省 杭州市 西湖区 文三路 88 号"

    address_model = UserAddress(
        receiver_name="王五",
        phone="13800000000",
        province="广东省",
        city="深圳市",
        district="南山区",
        detail_address="科技园 66 号",
    )
    assert build_full_address(address_model) == "广东省 深圳市 南山区 科技园 66 号"


@pytest.mark.parametrize(
    ("order_count", "shown_count", "expected"),
    [
        (0, 0, "你现在还没有订单。"),
        (5, 0, "我查到你一共有 5 笔订单，但当前没有可展示的订单。"),
        (2, 2, "你一共有 2 笔订单，我已经把全部订单都展示出来了。"),
        (9, 3, "你一共有 9 笔订单，我先给你展示最近 3 笔，方便你快速查看。"),
    ],
)
def test_build_order_list_answer_should_cover_boundaries(order_count: int, shown_count: int, expected: str) -> None:
    assert build_order_list_answer(order_count, shown_count) == expected
