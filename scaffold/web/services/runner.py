"""Ansible 执行引擎 —— 通过 ansible-runner 执行 playbook，实时回调日志。"""

import json
import shutil
import tempfile
import threading
from pathlib import Path

try:
    import ansible_runner
    _available = True
except (ImportError, ModuleNotFoundError):
    _available = False


def run_playbook(playbook_path, inventory, extra_vars, event_callback):
    """
    使用 ansible-runner 在后台线程执行 playbook，通过回调推送事件。

    回调事件格式：
      {"type": "runner_event", "event": "...", "stdout": "..."}
      {"type": "runner_complete", "status": "successful"|"failed"}
      {"type": "runner_error", "message": "..."}

    :param playbook_path: str —— playbook 文件路径
    :param inventory: dict —— build_inventory 输出的 inventory
    :param extra_vars: dict —— 额外变量
    :param event_callback: callable(dict) —— 每收到事件时调用，参数为可 JSON 序列化的 dict
    :return: threading.Thread —— 已启动的执行线程
    """
    if not _available:
        event_callback({
            "type": "runner_error",
            "message": "ansible-runner 不可用（需要 Linux 环境）。请在 Docker 容器中运行。",
        })
        return None

    # 准备临时目录
    private_dir = tempfile.mkdtemp(prefix="ansible_runner_")
    inventory_path = Path(private_dir) / "inventory.json"
    with open(inventory_path, "w") as f:
        json.dump(inventory, f)

    def _event_handler(event_data):
        """ansible-runner 事件 → 标准化 dict → callback"""
        event_type = event_data.get("event", "")
        stdout = event_data.get("stdout", "")

        if stdout:
            event_callback({
                "type": "runner_event",
                "event": event_type,
                "stdout": stdout.strip(),
            })

    def _run():
        """在独立线程中执行 ansible-runner。"""
        try:
            runner = ansible_runner.run(
                private_data_dir=private_dir,
                playbook=playbook_path,
                inventory=str(inventory_path),
                extravars=extra_vars,
                event_handler=_event_handler,
                quiet=True,
            )
            event_callback({
                "type": "runner_complete",
                "status": runner.status,
                "rc": runner.rc,
            })
        except Exception as e:
            event_callback({
                "type": "runner_error",
                "message": str(e),
            })
        finally:
            shutil.rmtree(private_dir, ignore_errors=True)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
