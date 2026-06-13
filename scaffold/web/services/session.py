"""服务端 session 存储 —— 文件系统实现。

cookie 中只存 session_id（UUID），实际数据存在服务端文件。
每个 session 一个目录：/tmp/sre-scaffold/<session_id>/state.json

过期策略：
  - 默认 TTL 24 小时（可配环境变量 SESSION_TTL_HOURS）
  - 每次访问更新 _accessed_at
  - 加载时发现过期 → 自动删除该 session 目录，返回空状态
  - 应用启动时自动清理所有过期 session
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import flask

BASE_DIR = Path("/tmp/sre-scaffold")
COOKIE_NAME = "sre_sid"
TTL_SECONDS = int(os.environ.get("SESSION_TTL_HOURS", 24)) * 3600

_current: "SessionStore | None" = None


class SessionStore:
    """单个 session 的读写封装。"""

    def __init__(self, sid: str, is_new: bool = False):
        self.sid = sid
        self.dir = BASE_DIR / sid
        self.file = self.dir / "state.json"
        self._is_new = is_new

    # ── 读 ──────────────────────────────────────────────────

    def load(self) -> dict:
        """读取完整状态，过期则返回空 dict 并删除目录。"""
        if not self.file.is_file():
            return self._new_state()

        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self._new_state()

        # 检查过期
        accessed = data.get("_accessed_at", 0)
        if time.time() - accessed > TTL_SECONDS:
            self.clear()
            return self._new_state()

        # 更新访问时间
        data["_accessed_at"] = time.time()
        self._write(data)
        return data

    def get(self, key: str, default: Any = None) -> Any:
        return self.load().get(key, default)

    # ── 写 ──────────────────────────────────────────────────

    def save(self, data: dict):
        data.setdefault("_created_at", time.time())
        data["_accessed_at"] = time.time()
        self._write(data)

    def set(self, key: str, value: Any):
        data = self.load()
        data[key] = value
        self.save(data)

    def update(self, **kwargs):
        data = self.load()
        data.update(kwargs)
        self.save(data)

    # ── 内部 ────────────────────────────────────────────────

    def _write(self, data: dict):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.file)       # 原子替换

    def _new_state(self) -> dict:
        return {"_created_at": time.time(), "_accessed_at": time.time()}

    # ── 清理 ────────────────────────────────────────────────

    def clear(self):
        """删除整个 session 目录。"""
        if self.dir.is_dir():
            import shutil
            shutil.rmtree(self.dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# 过期清理
# ═══════════════════════════════════════════════════════════════

def cleanup_expired() -> int:
    """
    扫描所有 session 目录，删除过期的。

    :return: 清理的 session 数量
    """
    if not BASE_DIR.is_dir():
        return 0

    now = time.time()
    removed = 0

    for session_dir in BASE_DIR.iterdir():
        if not session_dir.is_dir():
            continue
        state_file = session_dir / "state.json"
        try:
            if state_file.is_file():
                data = json.loads(state_file.read_text(encoding="utf-8"))
                accessed = data.get("_accessed_at", 0)
                if now - accessed > TTL_SECONDS:
                    import shutil
                    shutil.rmtree(session_dir, ignore_errors=True)
                    removed += 1
            else:
                # 无 state.json 的残留目录，直接清理
                import shutil
                shutil.rmtree(session_dir, ignore_errors=True)
                removed += 1
        except (json.JSONDecodeError, OSError):
            import shutil
            shutil.rmtree(session_dir, ignore_errors=True)
            removed += 1

    return removed


# ═══════════════════════════════════════════════════════════════
# 获取当前请求的 SessionStore
# ═══════════════════════════════════════════════════════════════

def get_session() -> SessionStore:
    """返回当前请求对应的 SessionStore（从 cookie 读取或新建）。"""
    global _current
    if _current is not None:
        return _current

    sid = flask.request.cookies.get(COOKIE_NAME)
    is_new = not sid
    if is_new:
        sid = uuid.uuid4().hex

    _current = SessionStore(sid, is_new=is_new)
    return _current


# ═══════════════════════════════════════════════════════════════
# 注册到 Flask
# ═══════════════════════════════════════════════════════════════

def init_app(app: flask.Flask):
    """注册 before_request / after_request 钩子，启动时清理过期 session。"""

    # 启动时清理
    removed = cleanup_expired()
    if removed:
        app.logger.info(f"session: cleaned {removed} expired session(s)")

    @app.before_request
    def _load():
        global _current
        _current = None
        get_session()

    @app.after_request
    def _set_cookie(response: flask.Response):
        s = _current
        if s is not None:
            response.set_cookie(
                COOKIE_NAME, s.sid,
                httponly=True, samesite="Lax",
                max_age=None,
            )
        return response
