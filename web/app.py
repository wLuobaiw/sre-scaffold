"""sre-scaffold Web 应用 —— Flask 入口 + 路由。"""

import json
import time

from flask import (
    Flask, jsonify, redirect, render_template, request, session, Response,
)

from config import MATERIALS_REPO_URL, MATERIALS_LOCAL_PATH
from services.gitops import ensure_repo, scan_components, load_conf

app = Flask(__name__)
app.config.from_object("config")


def get_categories():
    """扫描物料仓库，返回三层分类列表。"""
    return scan_components(MATERIALS_LOCAL_PATH)


# ── 路由 ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect("/select")


# ── 步骤 1：选择组件 ──────────────────────────────────────────────

@app.route("/select", methods=["GET", "POST"])
def select():
    # 每次进入选择页时拉取最新物料仓库
    clone_error = None
    try:
        ensure_repo(MATERIALS_REPO_URL, MATERIALS_LOCAL_PATH)
    except Exception as e:
        clone_error = f"物料仓库拉取失败: {e}"

    categories = get_categories()

    if request.method == "POST":
        selected = request.form.getlist("components")
        versions = {}
        comp_categories = {}
        for comp in selected:
            v = request.form.get(f"version_{comp}")
            if v:
                versions[comp] = v
        # 记录每个组件所属类别 + 系统组件标记（无需 config）
        system_keys = set()
        for cat in categories:
            for c in cat["components"]:
                if c["key"] in selected:
                    comp_categories[c["key"]] = cat["key"]
            if cat["key"] == "system":
                system_keys = {c["key"] for c in cat["components"]}
        session["no_config_keys"] = list(system_keys)
        session["component_categories"] = comp_categories
        session["selected_components"] = selected
        session["component_versions"] = versions
        return redirect("/hosts")

    return render_template(
        "select.html",
        categories=categories,
        clone_error=clone_error,
    )


# ── 步骤 2：配置主机 ──────────────────────────────────────────────

@app.route("/hosts", methods=["GET", "POST"])
def hosts():
    if "selected_components" not in session:
        return redirect("/select")

    if request.method == "POST":
        hosts_data = []
        i = 0
        while f"host_{i}_ip" in request.form:
            hosts_data.append({
                "ip": request.form.get(f"host_{i}_ip", ""),
                "ssh_user": request.form.get(f"host_{i}_user", "root"),
                "ssh_password": request.form.get(f"host_{i}_password", ""),
                "ssh_port": request.form.get(f"host_{i}_port", "22"),
            })
            i += 1
        session["hosts"] = hosts_data
        return redirect("/config")

    return render_template("hosts.html")


# ── API：检测单台主机连通性 ──────────────────────────────────────

@app.route("/api/check-host", methods=["POST"])
def check_host():
    """SSH 连通性检测。后期由 services/ansible.py 实现。"""
    data = request.get_json()
    time.sleep(0.5)
    # 检测逻辑：优先用密码（sshpass），否则尝试密钥
    auth_method = "password" if data.get("ssh_password") else "key"
    return jsonify({
        "host": data.get("ip"),
        "status": "ok",
        "auth_method": auth_method,
        "checks": {
            "ssh": {"status": "ok", "detail": "22 端口可达"},
            "python": {"status": "ok", "detail": "Python 3.12.2"},
            "disk": {"status": "ok", "detail": "42G 可用"},
        },
    })


# ── 步骤 3：逐组件配置 ──────────────────────────────────────────

@app.route("/config", methods=["GET", "POST"])
def config():
    if "selected_components" not in session:
        return redirect("/select")
    if "hosts" not in session:
        return redirect("/hosts")

    components = session["selected_components"]
    versions = session.get("component_versions", {})

    if request.method == "POST":
        configs = {}
        for comp in components:
            configs[comp] = {
                "deploy_mode": request.form.get(f"mode_{comp}", "single"),
                "target_hosts": request.form.getlist(f"hosts_{comp}"),
                "vars": {},
            }
            prefix = f"var_{comp}_"
            for key in request.form:
                if key.startswith(prefix):
                    var_name = key[len(prefix):]
                    configs[comp]["vars"][var_name] = request.form[key]
        session["component_configs"] = configs
        return redirect("/deploy")

    # 系统组件（来自 system 类别）无需配置，其余组件读取 conf.yaml
    no_config_keys = set(session.get("no_config_keys", []))
    categories = session.get("component_categories", {})
    config_items = []
    for key in components:
        info = {"key": key, "version": versions.get(key, "latest")}
        info["no_config"] = key in no_config_keys
        if not info["no_config"]:
            cat = categories.get(key, "middleware")
            conf = load_conf(
                MATERIALS_LOCAL_PATH, cat, key, info["version"]
            )
            info["fields"] = conf.get("fields", [])
        config_items.append(info)

    return render_template(
        "config.html",
        components=config_items,
        hosts=session["hosts"],
    )


# ── 步骤 4：部署确认 + 执行 ──────────────────────────────────────

@app.route("/deploy", methods=["GET", "POST"])
def deploy():
    if "selected_components" not in session:
        return redirect("/select")

    components = session["selected_components"]
    versions = session.get("component_versions", {})
    hosts = session.get("hosts", [])
    configs = session.get("component_configs", {})

    summary_items = []
    for key in components:
        info = {
            "key": key,
            "version": versions.get(key, "latest"),
            "deploy_mode": configs.get(key, {}).get("deploy_mode", "single"),
            "target_hosts": configs.get(key, {}).get("target_hosts", []),
            "vars": configs.get(key, {}).get("vars", {}),
        }
        summary_items.append(info)

    return render_template(
        "deploy.html",
        hosts=hosts,
        summary_items=summary_items,
    )


# ── SSE：部署日志流 ──────────────────────────────────────────────

@app.route("/api/deploy/stream")
def deploy_stream():
    """SSE 端点 —— 实时推送 ansible-playbook 日志。
    后期由 services/ansible.py 实现。"""

    def generate():
        layers = [
            ("system", "NTP"),
            ("system", "DNS"),
            ("ops", "Docker"),
        ]
        components = session.get("selected_components", [])
        middleware = [c for c in components if c not in ("ntp", "dns", "docker")]
        for comp in middleware:
            layers.append(("middleware", comp))

        event_id = 0
        for layer_name, item_name in layers:
            yield f"id: {event_id}\ndata: {json.dumps({'type': 'layer_start', 'layer': layer_name, 'item': item_name})}\n\n"
            event_id += 1

            lines = [
                f"PLAY [部署 {item_name}] ****************",
                f"TASK [创建目录] **********************",
                f"ok: [192.168.1.10]",
                f"TASK [启动服务] **********************",
                f"changed: [192.168.1.10]",
                f"✓ {item_name} 完成",
            ]
            for text in lines:
                yield f"id: {event_id}\ndata: {json.dumps({'type': 'log', 'text': text})}\n\n"
                event_id += 1
                time.sleep(0.4)

        yield f"id: {event_id}\ndata: {json.dumps({'type': 'complete'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
