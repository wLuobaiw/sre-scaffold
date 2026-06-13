"""步骤 4 + API：部署确认、SSE 日志流、主机检测。"""

import json
import queue
import subprocess
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, Response

from config import MATERIALS_LOCAL_PATH
from models.component import Component
from services.inventory import build as build_inventory, build_extra_vars
from services.runner import run_playbook
from services.scanner import get_playbook_path
from services.session import get_session

bp = Blueprint("deploy", __name__)


@bp.route("/deploy")
def deploy():
    store = get_session()
    if not store.get("selected_components"):
        return redirect("/select")
    if not store.get("hosts"):
        return redirect("/hosts")
    if not store.get("component_configs"):
        return redirect("/config")

    selected = store.get("selected_components")
    hosts_data = store.get("hosts")
    configs = store.get("component_configs")

    deploy_groups = []
    for cat_key, comps in selected.items():
        items = []
        for comp_key, version in comps.items():
            comp_cfg = configs.get(comp_key, {})
            items.append({"key": comp_key, "version": version, "vars": comp_cfg.get("vars", {})})
        deploy_groups.append({"category": cat_key, "components": items})

    return render_template("deploy.html", hosts=hosts_data, deploy_groups=deploy_groups)


@bp.route("/api/check-host", methods=["POST"])
def check_host():
    data = request.get_json() or {}
    host = data.get("ip", "")
    user = data.get("ssh_user", "root")
    password = data.get("ssh_password", "")
    port = data.get("ssh_port", "22")

    checks = {}
    ssh_ok = _check_ssh(host, user, password, port)
    checks["ssh"] = {
        "status": "ok" if ssh_ok else "fail",
        "detail": f"端口 {port} 可达" if ssh_ok else f"端口 {port} 不可达或认证失败",
    }

    if ssh_ok:
        py_ver = _ssh_exec(host, user, password, port, "python3 --version 2>&1")
        checks["python"] = {
            "status": "ok" if py_ver else "fail",
            "detail": py_ver.strip() if py_ver else "未检测到 Python3",
        }
        disk = _ssh_exec(host, user, password, port, "df -h / | tail -1 | awk '{print $4}'")
        checks["disk"] = {
            "status": "ok" if disk else "fail",
            "detail": f"可用 {disk.strip()}" if disk else "无法获取磁盘信息",
        }
    else:
        checks["python"] = {"status": "fail", "detail": "SSH 不通，跳过"}
        checks["disk"] = {"status": "fail", "detail": "SSH 不通，跳过"}

    return jsonify({"host": host, "status": "ok" if all(
        c["status"] == "ok" for c in checks.values()
    ) else "fail", "checks": checks})


@bp.route("/api/deploy/stream")
def deploy_stream():
    store = get_session()
    selected = store.get("selected_components") or {}
    hosts_data = store.get("hosts") or []
    configs = store.get("component_configs") or {}
    base_path = Path(MATERIALS_LOCAL_PATH) / "ansible" / "roles"

    def generate():
        event_id = 0
        q = queue.Queue()

        def push(data):
            nonlocal event_id
            event_id += 1
            q.put({"id": event_id, "data": data})

        def drain():
            msgs = []
            while True:
                try:
                    m = q.get_nowait()
                    msgs.append(f"id: {m['id']}\ndata: {json.dumps(m['data'])}\n\n")
                except queue.Empty:
                    break
            return msgs

        for cat_key, comps in selected.items():
            for comp_key, version in comps.items():
                comp_dir = base_path / cat_key / comp_key / version
                comp = Component.from_yaml(comp_dir, key=comp_key, version=version)
                playbook = get_playbook_path(comp_dir, comp.playbook)

                if not playbook.is_file():
                    push({"type": "status", "comp": comp_key, "status": "error"})
                    push({"type": "log", "text": f"✗ {comp_key}: playbook 不存在"})
                    continue

                push({"type": "status", "comp": comp_key, "status": "installing"})
                push({"type": "log", "text": f"PLAY [{comp_key} {version}] *******"})

                user_input = configs.get(comp_key, {"hosts": {}, "vars": {}})
                inventory = build_inventory(comp, hosts_data, user_input)
                extra_vars = build_extra_vars(user_input.get("vars", {}))

                if hosts_data:
                    h0 = hosts_data[0]
                    extra_vars.setdefault("ansible_user", h0.get("ssh_user", "root"))
                    extra_vars.setdefault("ansible_password", h0.get("ssh_password", ""))
                    extra_vars.setdefault("ansible_port", int(h0.get("ssh_port", 22)))

                done = {"flag": False, "status": "failed", "rc": -1}

                def on_event(ev):
                    if ev["type"] == "runner_event":
                        push({"type": "log", "text": ev["stdout"]})
                    elif ev["type"] == "runner_complete":
                        done["flag"] = True
                        done["status"] = ev.get("status", "failed")
                        done["rc"] = ev.get("rc", -1)
                    elif ev["type"] == "runner_error":
                        done["flag"] = True
                        done["status"] = "error"
                        push({"type": "log", "text": f"✗ {ev['message']}"})

                run_playbook(str(playbook), inventory, extra_vars, on_event)

                while not done["flag"]:
                    try:
                        m = q.get(timeout=0.1)
                        yield f"id: {m['id']}\ndata: {json.dumps(m['data'])}\n\n"
                    except queue.Empty:
                        yield ": keepalive\n\n"

                for s in drain():
                    yield s

                if done["status"] == "successful":
                    push({"type": "status", "comp": comp_key, "status": "done"})
                    push({"type": "log", "text": f"✓ {comp_key} 完成"})
                else:
                    push({"type": "status", "comp": comp_key, "status": "error"})
                    push({"type": "log", "text": f"✗ {comp_key} 失败 (rc={done['rc']})"})

                for s in drain():
                    yield s

        push({"type": "complete"})
        for s in drain():
            yield s

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _check_ssh(host, user, password, port):
    try:
        result = subprocess.run(
            ["sshpass", "-p", password, "ssh",
             "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-p", str(port), f"{user}@{host}", "echo ok"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False


def _ssh_exec(host, user, password, port, cmd):
    try:
        result = subprocess.run(
            ["sshpass", "-p", password, "ssh",
             "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-p", str(port), f"{user}@{host}", cmd],
            capture_output=True, text=True, timeout=15,
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""
