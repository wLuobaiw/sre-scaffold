"""步骤 3：逐组件配置。"""

from pathlib import Path

from flask import Blueprint, redirect, render_template, request

from config import MATERIALS_LOCAL_PATH
from models.component import Component
from services.session import get_session

bp = Blueprint("config", __name__)


@bp.route("/config", methods=["GET", "POST"])
def config():
    store = get_session()
    selected = store.get("selected_components")
    hosts_data = store.get("hosts")

    if not selected:
        return redirect("/select")
    if not hosts_data:
        return redirect("/hosts")

    if request.method == "POST":
        configs = {}
        for cat_key, comps in selected.items():
            for comp_key in comps:
                # 主机组
                hosts_sel = {}
                h_prefix = f"hosts_{comp_key}_"
                for key in request.form:
                    if key.startswith(h_prefix):
                        gname = key[len(h_prefix):]
                        vals = request.form.getlist(key)
                        hosts_sel[gname] = vals[0] if len(vals) == 1 else vals

                # 变量
                vars_sel = {}
                v_prefix = f"var_{comp_key}_"
                seen = set()
                for key in request.form:
                    if key.startswith(v_prefix):
                        vname = key[len(v_prefix):]
                        if vname in seen:
                            continue
                        seen.add(vname)
                        vals = request.form.getlist(key)
                        vars_sel[vname] = vals[0] if len(vals) == 1 else vals

                configs[comp_key] = {"hosts": hosts_sel, "vars": vars_sel}

        store.set("component_configs", configs)
        return redirect("/deploy")

    # GET —— 加载 conf.yaml
    config_items = []
    base_path = Path(MATERIALS_LOCAL_PATH) / "ansible" / "roles"

    for cat_key, comps in selected.items():
        for comp_key, version in comps.items():
            comp_dir = base_path / cat_key / comp_key / version
            comp = Component.from_yaml(comp_dir, key=comp_key, version=version)

            config_items.append({
                "key": comp.key,
                "version": comp.version,
                "name": comp.name,
                "description": comp.description,
                "hosts": [{
                    "name": h.name, "label": h.label,
                    "default": h.default, "multiple": h.multiple,
                    "show_when": h.show_when,
                } for h in comp.hosts],
                "needs_host_ui": comp.needs_host_ui,
                "needs_vars_ui": comp.needs_vars_ui,
                "sections": [{
                    "name": s.name, "collapsed": s.collapsed,
                    "fields": [{
                        "name": f.name, "label": f.label,
                        "widget": f.widget, "default": f.default,
                        "required": f.required, "readonly": f.readonly,
                        "placeholder": f.placeholder, "options": f.options,
                        "show_when": f.show_when,
                    } for f in s.fields],
                } for s in comp.visible_sections],
                "_hosts": hosts_data,
            })

    saved_configs = store.get("component_configs") or {}
    return render_template("config.html", components=config_items, saved_configs=saved_configs)
