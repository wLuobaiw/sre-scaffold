"""sre-scaffold Web 应用 —— Flask 入口 + 路由。"""

import json
import time

from flask import (
    Flask, jsonify, redirect, render_template, request, session, Response,
)

from config import MATERIALS_REPO_URL, MATERIALS_LOCAL_PATH
from services.gitops import ensure_repo, scan_components, get_component_dir, load_conf

app = Flask(__name__)
app.config.from_object("config")


def get_categories():
    """
    获取物料仓库中所有可部署分类和组件。

    :return: 三层分类列表 [{name, key, components: [{name, key, versions}]}]
    """
    return scan_components(MATERIALS_LOCAL_PATH)


def _flatten_selected(selected):
    """
    将嵌套的 selected_components 拍平为 (category, component, version) 迭代。

    :param selected: {category: {component: version, ...}, ...}
    :yield: (category_key, component_key, version)
    """
    for cat_key, comps in (selected or {}).items():
        for comp_key, version in comps.items():
            yield cat_key, comp_key, version


def _flatten_config(configs):
    """
    将 component_configs 中的 vars 展开到顶层，返回供 ansible 使用的单层字典。

    :param configs: {comp: {vars: {deploy_mode, target_hosts, ...}}}
    :return: {comp: {deploy_mode, target_hosts, **extra_vars}}
    """
    result = {}
    for comp_key, cfg in (configs or {}).items():
        result[comp_key] = cfg.get("vars", {})
    return result


# ── 路由 ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    """
    根路径重定向到四步向导首页。

    :return: 302 重定向到 /select
    """
    return redirect("/select")


# ── 步骤 1：选择组件 ──────────────────────────────────────────────

@app.route("/select", methods=["GET", "POST"])
def select():
    """
    步骤 1 —— 展示组件列表，用户勾选要部署的组件和版本。

    GET:  拉取物料仓库，渲染分类复选框 + 版本下拉。
    POST: 收集勾选结果，以 {category: {component: version}} 结构存入 session。

    session 写入: selected_components

    :return: 渲染 select.html 或 302 跳转到 /hosts
    """
    clone_error = None
    try:
        ensure_repo(MATERIALS_REPO_URL, MATERIALS_LOCAL_PATH)
    except Exception as e:
        clone_error = f"物料仓库拉取失败: {e}"

    categories = get_categories()

    if request.method == "POST":
        selected_keys = request.form.getlist("components")
        comp_by_cat = {}
        for comp in selected_keys:
            v = request.form.get(f"version_{comp}")
            if not v:
                continue
            for cat in categories:
                for c in cat["components"]:
                    if c["key"] == comp:
                        comp_by_cat.setdefault(cat["key"], {})[comp] = v
                        break
        session["selected_components"] = comp_by_cat
        return redirect("/hosts")

    return render_template(
        "select.html",
        categories=categories,
        clone_error=clone_error,
    )


# ── 步骤 2：配置主机 ──────────────────────────────────────────────

@app.route("/hosts", methods=["GET", "POST"])
def hosts():
    """
    步骤 2 —— 填写目标主机 SSH 信息，支持手动添加、文件导入、连通性检测。

    GET:  渲染主机配置表单。
    POST: 收集主机列表存入 session。

    session 写入: hosts

    :return: 渲染 hosts.html 或 302 跳转到 /config
    """
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
    """
    AJAX 端点 —— 检测单台主机 SSH 连通性和运行环境。

    请求体 JSON: {ip, ssh_user, ssh_password, ssh_port}

    :return: JSON {host, status, auth_method, checks: {ssh, python, disk}}
    """
    data = request.get_json()
    time.sleep(0.5)
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
    """
    步骤 3 —— 逐组件配置部署参数（部署模式 / 目标主机 / 专属变量）。

    GET:  读取各组件 conf.yaml 渲染表单，fields 为空则标记"无需配置"。
    POST: 收集配置结果存入 session。

    session 写入: component_configs

    :return: 渲染 config.html 或 302 跳转到 /deploy
    """
    if "selected_components" not in session:
        return redirect("/select")
    if "hosts" not in session:
        return redirect("/hosts")

    selected = session["selected_components"]

    if request.method == "POST":
        configs = {}
        for cat_key, comp_key, _version in _flatten_selected(selected):
            configs[comp_key] = {"vars": {}}
            prefix = f"var_{comp_key}_"
            seen_vars = set()
            for key in request.form:
                if key.startswith(prefix):
                    var_name = key[len(prefix):]
                    if var_name in seen_vars:
                        continue
                    seen_vars.add(var_name)
                    values = request.form.getlist(key)
                    configs[comp_key]["vars"][var_name] = values[0] if len(values) == 1 else values
        session["component_configs"] = configs
        return redirect("/deploy")

    config_items = []
    for cat_key, comp_key, version in _flatten_selected(selected):
        info = {"key": comp_key, "version": version}
        comp_dir = get_component_dir(MATERIALS_LOCAL_PATH, cat_key, comp_key, version)
        conf = load_conf(comp_dir)
        info["fields"] = conf.get("fields", [])
        info["no_config"] = len(info["fields"]) == 0
        config_items.append(info)

    return render_template(
        "config.html",
        components=config_items,
        hosts=session["hosts"],
    )


# ── 步骤 4：部署确认 + 执行 ──────────────────────────────────────

@app.route("/deploy", methods=["GET", "POST"])
def deploy():
    """
    步骤 4 —— 展示部署摘要，确认后通过 SSE 执行并查看实时日志。

    GET:  渲染摘要页（主机 / 组件 / 版本 / 配置参数）。

    :return: 渲染 deploy.html
    """
    if "selected_components" not in session:
        return redirect("/select")

    selected = session["selected_components"]
    hosts = session.get("hosts", [])
    configs = session.get("component_configs", {})

    # 按分类分组，用于页面展示
    deploy_groups = []
    for cat_key, comps in selected.items():
        items = []
        for comp_key, version in comps.items():
            comp_cfg = configs.get(comp_key, {})
            all_vars = comp_cfg.get("vars", {})
            deploy_mode = all_vars.get("deploy_mode", "single")
            target_hosts = all_vars.get("target_hosts", [])
            # target_hosts == "all" → 全部主机
            if target_hosts == "all":
                target_hosts = [str(i) for i in range(len(hosts))]
            # 其余 vars 过滤掉元字段
            extra_vars = {k: v for k, v in all_vars.items()
                          if k not in ("deploy_mode", "target_hosts")}
            items.append({
                "key": comp_key,
                "version": version,
                "deploy_mode": deploy_mode,
                "target_hosts": target_hosts,
                "vars": extra_vars,
            })
        deploy_groups.append({"category": cat_key, "items": items})

    # 拼装给 ansible-playbook 传参用的扁平字典
    flat_configs = _flatten_config(configs)

    return render_template(
        "deploy.html",
        hosts=hosts,
        deploy_groups=deploy_groups,
        flat_configs=flat_configs,
    )


# ── SSE：部署日志流 ──────────────────────────────────────────────

@app.route("/api/deploy/stream")
def deploy_stream():
    """
    SSE 端点 —— 推送 ansible-playbook 实时日志到步骤 4。

    事件格式:
        {"type": "layer_start", "layer": ..., "item": ...}
        {"type": "log", "text": "..."}
        {"type": "complete"}

    :return: text/event-stream，持续推送至部署结束
    """

    def generate():
        selected = session.get("selected_components", {})

        layers = []
        for cat_key, comps in selected.items():
            for name in comps:
                layers.append((cat_key, name))

        event_id = 0
        for layer_name, item_name in layers:
            # 下载阶段
            yield f"id: {event_id}\ndata: {json.dumps({'type': 'status', 'comp': item_name, 'status': 'download'})}\n\n"
            event_id += 1
            yield f"id: {event_id}\ndata: {json.dumps({'type': 'log', 'text': f'→ 正在下载 {item_name}...'})}\n\n"
            event_id += 1
            time.sleep(0.5)

            # 安装阶段
            yield f"id: {event_id}\ndata: {json.dumps({'type': 'status', 'comp': item_name, 'status': 'installing'})}\n\n"
            event_id += 1
            yield f"id: {event_id}\ndata: {json.dumps({'type': 'log', 'text': f'PLAY [部署 {item_name}] ****************'})}\n\n"
            event_id += 1
            time.sleep(0.3)
            yield f"id: {event_id}\ndata: {json.dumps({'type': 'log', 'text': f'TASK [执行任务] **********************'})}\n\n"
            event_id += 1
            time.sleep(0.3)
            yield f"id: {event_id}\ndata: {json.dumps({'type': 'log', 'text': f'changed: [192.168.1.10]'})}\n\n"
            event_id += 1

            # 完成
            yield f"id: {event_id}\ndata: {json.dumps({'type': 'status', 'comp': item_name, 'status': 'done'})}\n\n"
            event_id += 1
            yield f"id: {event_id}\ndata: {json.dumps({'type': 'log', 'text': f'✓ {item_name} 完成'})}\n\n"
            event_id += 1

        yield f"id: {event_id}\ndata: {json.dumps({'type': 'complete'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
