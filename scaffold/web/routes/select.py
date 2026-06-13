"""步骤 1 + 2：选择组件 + 配置主机。"""

import re
from pathlib import Path

from flask import Blueprint, redirect, render_template, request

from config import MATERIALS_LOCAL_PATH
from services.session import get_session

bp = Blueprint("select", __name__)


@bp.route("/")
def index():
    return redirect("/select")


# ═══════════════════════════════════════════════════════════════
# 步骤 1：选择组件
# ═══════════════════════════════════════════════════════════════

@bp.route("/select", methods=["GET", "POST"])
def select():
    store = get_session()
    categories = _scan_categories()

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

        if not comp_by_cat:
            return render_template(
                "select.html", categories=categories,
                selected_map={}, error="请至少选择一个组件并指定版本",
            ), 400

        store.set("selected_components", comp_by_cat)
        return redirect("/hosts")

    selected_map = {}
    for comps in (store.get("selected_components") or {}).values():
        for comp_key, version in comps.items():
            selected_map[comp_key] = version

    return render_template("select.html", categories=categories, selected_map=selected_map)


# ═══════════════════════════════════════════════════════════════
# 步骤 2：配置主机
# ═══════════════════════════════════════════════════════════════

@bp.route("/hosts", methods=["GET", "POST"])
def hosts():
    store = get_session()
    if not store.get("selected_components"):
        return redirect("/select")

    if request.method == "POST":
        indices = set()
        for key in request.form:
            m = re.match(r"host_(\d+)_ip", key)
            if m:
                indices.add(int(m.group(1)))
        hosts_data = []
        for i in sorted(indices):
            hosts_data.append({
                "ip": request.form.get(f"host_{i}_ip", ""),
                "ssh_user": request.form.get(f"host_{i}_user", "root"),
                "ssh_password": request.form.get(f"host_{i}_password", ""),
                "ssh_port": request.form.get(f"host_{i}_port", "22"),
            })
        store.set("hosts", hosts_data)
        return redirect("/config")

    return render_template("hosts.html", hosts=store.get("hosts") or [])


# ═══════════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════════

def _scan_categories():
    """扫描物料仓库，返回三层分类列表。"""
    roles_dir = Path(MATERIALS_LOCAL_PATH) / "ansible" / "roles"
    if not roles_dir.is_dir():
        return []

    categories = []
    for cat_dir in sorted(roles_dir.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        items = []
        for comp_dir in sorted(cat_dir.iterdir()):
            if not comp_dir.is_dir() or comp_dir.name.startswith("."):
                continue
            versions = sorted(
                v.name for v in comp_dir.iterdir()
                if v.is_dir() and not v.name.startswith(".")
            )
            if versions:
                items.append({"name": comp_dir.name, "key": comp_dir.name, "versions": versions})
        if items:
            categories.append({"name": cat_dir.name, "key": cat_dir.name, "components": items})
    return categories
