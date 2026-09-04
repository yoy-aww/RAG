#!/usr/bin/env python3
"""
商城数据 → RAG 向量库 导入脚本

用法：
  python scripts/import_mall.py              # 全量导入
  python scripts/import_mall.py --dry-run    # 只预览，不入库
  python scripts/import_mall.py --table products  # 只导指定表
"""
import sqlite3
import json
import sys
import os
import requests

DB_PATH = os.environ.get("MALL_DB", r"C:\yoyac-work\小程序商城\server\mall.db")
RAG_URL = os.environ.get("RAG_URL", "http://localhost:8000")

# ── 各表导出为文本 ──────────────────────────────────

def export_categories(conn):
    rows = conn.execute("SELECT name FROM categories ORDER BY sortOrder").fetchall()
    lines = ["# 产品分类\n"]
    for i, (name,) in enumerate(rows, 1):
        lines.append(f"{i}. {name}")
    return "\n".join(lines)


def export_products(conn):
    rows = conn.execute("""
        SELECT p.name, p.originalPrice, p.discountedPrice, p.categoryId,
               c.name as catName, p.description, p.stock, p.tags
        FROM products p
        LEFT JOIN categories c ON p.categoryId = c.id
        WHERE p.enabled = 1 OR p.enabled IS NULL
        ORDER BY p.originalPrice DESC
    """).fetchall()
    lines = ["# 商品列表\n"]
    for name, price, disc_price, _, cat, desc, stock, tags in rows:
        final = disc_price or price
        tag_list = json.loads(tags) if tags else []
        lines.append(f"## {name}")
        lines.append(f"价格：¥{price}" + (f"（现价 ¥{disc_price}）" if disc_price else ""))
        if cat:
            lines.append(f"分类：{cat}")
        if desc:
            lines.append(f"描述：{desc}")
        lines.append(f"库存：{stock} 件")
        if tag_list:
            lines.append(f"标签：{'、'.join(tag_list)}")
        lines.append("")
    return "\n".join(lines)


def export_banners(conn):
    rows = conn.execute("SELECT title, subtitle, link FROM banners WHERE enabled=1 ORDER BY sortOrder").fetchall()
    lines = ["# 促销活动\n"]
    for i, (title, subtitle, link) in enumerate(rows, 1):
        lines.append(f"{i}. {title}")
        if subtitle:
            lines.append(f"   副标题：{subtitle}")
        if link:
            lines.append(f"   链接：{link}")
    return "\n".join(lines)


def export_reviews(conn):
    rows = conn.execute("""
        SELECT r.rating, r.content, p.name as productName
        FROM reviews r
        LEFT JOIN products p ON r.productId = p.id
        ORDER BY r.createdAt DESC
    """).fetchall()
    lines = ["# 用户评价\n"]
    for rating, content, product in rows:
        star = "⭐" * rating
        product_label = f"「{product}」" if product else ""
        lines.append(f"- {star} {product_label} {content}")
    return "\n".join(lines)


def export_orders(conn):
    rows = conn.execute("""
        SELECT o.status, o.totalAmount, o.items, o.receiverName, o.receiverPhone,
               o.shippingAddress, o.remark, o.createdAt, o.paidAt
        FROM orders o
        ORDER BY o.createdAt DESC
    """).fetchall()
    lines = ["# 订单记录\n"]
    status_map = {
        "pending": "待付款", "paid": "已付款", "shipped": "已发货",
        "delivered": "已签收", "completed": "已完成", "cancelled": "已取消",
    }
    for status, total, items_raw, receiver, phone, address, remark, created, paid in rows:
        items = json.loads(items_raw) if items_raw else []
        item_names = "、".join(it.get("productName", "") for it in items) if items else ""
        lines.append(f"## 订单（{status_map.get(status, status)}）")
        if item_names:
            lines.append(f"商品：{item_names}")
        lines.append(f"金额：¥{total:.2f}")
        if receiver:
            lines.append(f"收货人：{receiver} {phone}")
        if address:
            lines.append(f"地址：{address}")
        if remark:
            lines.append(f"备注：{remark}")
        if paid:
            lines.append(f"付款时间：{paid}")
        lines.append(f"下单时间：{created}")
        lines.append("")
    return "\n".join(lines)


def export_aftersales(conn):
    rows = conn.execute("""
        SELECT a.status, a.reason, a.description, a.items, a.handledAt
        FROM aftersales a
        ORDER BY a.createdAt DESC
    """).fetchall()
    status_map = {"pending": "待审核", "approved": "已同意", "rejected": "已拒绝"}
    lines = ["# 售后记录\n"]
    for status, reason, desc, items_raw, handled in rows:
        items = json.loads(items_raw) if items_raw else []
        item_names = "、".join(it.get("productName", "") for it in items) if items else ""
        lines.append(f"- 状态：{status_map.get(status, status)} | 原因：{reason}")
        if item_names:
            lines.append(f"  涉及商品：{item_names}")
        if desc:
            lines.append(f"  描述：{desc}")
        if handled:
            lines.append(f"  处理时间：{handled}")
    return "\n".join(lines)


TABLES = {
    "categories": export_categories,
    "products": export_products,
    "banners": export_banners,
    "reviews": export_reviews,
    "orders": export_orders,
    "aftersales": export_aftersales,
}

# ── 主流程 ─────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv
    only = [t for a in sys.argv[1:] if a.startswith("--table=")] or None
    only = only[0] if only else None

    conn = sqlite3.connect(DB_PATH)
    tables = TABLES if not only else {only: TABLES.get(only)}

    if not tables:
        print(f"未知表: {only}，可选: {', '.join(TABLES)}")
        conn.close()
        return

    total_chunks = 0
    for name, func in tables.items():
        text = func(conn)
        word_count = len(text)
        print(f"  {name}: {word_count} 字符")

        if dry_run:
            print(f"    [dry-run] 跳过入库\n")
            continue

        # 写入临时文件
        tmp = os.path.join("data", f"mall_{name}.md")
        os.makedirs("data", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)

        # 调 RAG 入库
        try:
            r = requests.post(f"{RAG_URL}/ingest/file", files={"file": open(tmp, "rb")}, timeout=120)
            data = r.json()
            n = data.get("chunks_added", 0)
            total_chunks += n
            print(f"    → 入库 {n} chunks\n")
        except Exception as e:
            print(f"    → 入库失败: {e}\n")

    conn.close()
    print(f"完成！共入库 {total_chunks} chunks")


if __name__ == "__main__":
    main()
