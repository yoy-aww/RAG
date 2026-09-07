"""租户注册表 —— 多租户的钥匙串。

职责：
  1. 管理租户（创建 / 查询 / 删除 / 重置 key）
  2. 签发 API key（调用方凭 key 路由到自己的知识库）
  3. 持久化到 tenant_db/tenants.json，进程重启不丢

隔离模型：
  - 租户身份 = tenant_id，与向量库文件 index_{doc_id}.faiss 一一对应
  - 调用方持 api_key → get_by_key() 解出 tenant_id → 路由到该租户的 Retriever
  - 不同租户的数据物理隔离（独立向量库文件），钥匙不同谁也进不了谁的门

设计取舍：
  - JSON 文件存储：租户量级是几十个，不需要上数据库；文件可读可手工修
  - threading.Lock：uvicorn 多线程并发写文件，必须加锁防损坏
"""
import json
import os
import secrets
import threading
import time
from pathlib import Path


class TenantNotFound(Exception):
    pass


class TenantStore:
    def __init__(self, path: str = "tenant_db/tenants.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._tenants: dict[str, dict] = {}  # tenant_id -> record
        self._load()

    # ---------- 持久化 ----------
    def _load(self):
        if self.path.exists():
            try:
                self._tenants = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[WARN] 租户文件损坏，重建空注册表: {e}")
                self._tenants = {}
        else:
            self._tenants = {}

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._tenants, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.path)

    # ---------- 租户 CRUD ----------
    def create(self, name: str, tenant_id: str | None = None,
               api_key: str | None = None) -> dict:
        """创建租户，返回记录（含 api_key，仅此一次完整可见）。"""
        with self._lock:
            tid = tenant_id or f"tenant_{int(time.time())}"
            while tid in self._tenants:  # 时间戳撞车兜底
                tid += "_x"
            rec = {
                "tenant_id": tid,
                "name": name,
                "api_key": api_key or secrets.token_hex(16),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "active",
            }
            self._tenants[tid] = rec
            self._save()
            return dict(rec)

    def get(self, tenant_id: str) -> dict | None:
        with self._lock:
            rec = self._tenants.get(tenant_id)
            return dict(rec) if rec else None

    def get_by_key(self, api_key: str) -> dict | None:
        """凭 API key 查租户（登录校验的核心）。"""
        with self._lock:
            for rec in self._tenants.values():
                if rec["api_key"] == api_key:
                    return dict(rec)
            return None

    def list(self) -> list[dict]:
        """租户列表（不含完整 api_key，只给掩码）。"""
        with self._lock:
            out = []
            for rec in self._tenants.values():
                r = dict(rec)
                k = r.get("api_key", "")
                r["api_key_masked"] = k[:6] + "…" + k[-4:] if len(k) > 10 else "…"
                r.pop("api_key", None)
                out.append(r)
            return sorted(out, key=lambda r: r["created_at"])

    def delete(self, tenant_id: str) -> bool:
        with self._lock:
            if tenant_id not in self._tenants:
                raise TenantNotFound(tenant_id)
            del self._tenants[tenant_id]
            self._save()
            return True

    def reset_key(self, tenant_id: str) -> str:
        """重置 API key，返回新 key（旧 key 立即失效）。"""
        with self._lock:
            if tenant_id not in self._tenants:
                raise TenantNotFound(tenant_id)
            new_key = secrets.token_hex(16)
            self._tenants[tenant_id]["api_key"] = new_key
            self._save()
            return new_key

    # ---------- 默认租户 ----------
    @property
    def default_tenant_id(self) -> str:
        return "tenant_001"

    def ensure_default(self, default_key: str | None = None) -> dict:
        """确保默认租户存在（兼容升级前已有的 tenant_001 向量库数据）。

        key 来源：env DEFAULT_API_KEY；未配置则自动生成（打印出来）。
        """
        with self._lock:
            rec = self._tenants.get("tenant_001")
            if rec:
                return dict(rec)
            key = default_key or secrets.token_hex(16)
            rec = {
                "tenant_id": "tenant_001",
                "name": "默认租户",
                "api_key": key,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "active",
            }
            self._tenants["tenant_001"] = rec
            self._save()
            if not default_key:
                print(f"[tenant] 默认租户 tenant_001 已创建，API key: {key}")
            return dict(rec)
