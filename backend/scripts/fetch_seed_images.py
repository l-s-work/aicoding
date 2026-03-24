"""
种子商品图片抓取脚本（推荐使用图库 API，避免通用网页爬虫的版权与反爬风险）

用途：
1. 根据 seed_catalog.py 中的 image_query 搜索图片；
2. 下载到 backend/uploads/products；
3. 输出 backend/scripts/seed_images.json 供 init_db.py 初始化时引用。

执行示例（PowerShell）：
  cd D:\AICoding作业\backend
  $env:PEXELS_API_KEY="你的Key"
  python scripts\fetch_seed_images.py
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx

from seed_catalog import PRODUCT_SEEDS, build_placeholder_image_url

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads" / "products"
IMAGE_MAP_FILE = Path(__file__).resolve().with_name("seed_images.json")


def _safe_stem(text: str) -> str:
    """
    将商品名转成安全文件名片段，避免路径非法字符。
    """
    normalized = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5]+", "-", text).strip("-").lower()
    if not normalized:
        return "seed-product"
    return normalized[:40]


def _pick_photo_url(api_data: dict) -> str | None:
    """
    从 Pexels 响应里选择最合适的图片地址。
    """
    photos = api_data.get("photos", [])
    if not photos:
        return None

    src = photos[0].get("src") or {}
    return (
        src.get("large2x")
        or src.get("large")
        or src.get("medium")
        or src.get("original")
    )


def _search_one_photo(client: httpx.Client, api_key: str, query: str) -> str | None:
    """
    按关键词搜索一张图片 URL。
    """
    response = client.get(
        PEXELS_SEARCH_URL,
        headers={"Authorization": api_key},
        params={
            "query": query,
            "per_page": 1,
            "orientation": "square",
            "size": "medium",
        },
    )
    response.raise_for_status()
    return _pick_photo_url(response.json())


def _download_image(client: httpx.Client, image_url: str, save_path: Path) -> None:
    """
    下载图片到本地路径。
    """
    response = client.get(image_url, follow_redirects=True)
    response.raise_for_status()
    save_path.write_bytes(response.content)


def main() -> None:
    """
    主流程：
    - 有 PEXELS_API_KEY：下载真实图片；
    - 无 PEXELS_API_KEY：生成占位图映射，保证初始化不中断。
    """
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    image_map: dict[str, str] = {}
    downloaded = 0
    fallback_count = 0

    if not api_key:
        print("⚠️  未检测到 PEXELS_API_KEY，改为生成占位图映射。")
        for product in PRODUCT_SEEDS:
            product_name = product["name"]
            image_map[product_name] = build_placeholder_image_url(product_name)
            fallback_count += 1
    else:
        with httpx.Client(timeout=30.0) as client:
            for index, product in enumerate(PRODUCT_SEEDS, start=1):
                product_name = product["name"]
                query = product["image_query"]
                stem = _safe_stem(product_name)
                filename = f"seed_{index:02d}_{stem}.jpg"
                save_path = UPLOAD_DIR / filename

                try:
                    photo_url = _search_one_photo(client, api_key, query)
                    if not photo_url:
                        raise RuntimeError("搜索结果为空")

                    _download_image(client, photo_url, save_path)
                    image_map[product_name] = f"/uploads/products/{filename}"
                    downloaded += 1
                    print(f"✅ 已下载: {product_name} -> {filename}")
                except Exception as exc:  # noqa: BLE001
                    image_map[product_name] = build_placeholder_image_url(product_name)
                    fallback_count += 1
                    print(f"⚠️  下载失败，使用占位图: {product_name} ({exc})")

    IMAGE_MAP_FILE.write_text(
        json.dumps(image_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n==============================")
    print("🎉 图片映射生成完成")
    print(f"下载成功: {downloaded} 张")
    print(f"占位图回退: {fallback_count} 张")
    print(f"映射文件: {IMAGE_MAP_FILE}")
    print("==============================")
    print("下一步可执行：python scripts\\init_db.py")


if __name__ == "__main__":
    main()
