"""Git 物料仓库操作：拉取、列出组件和版本。"""

import subprocess
from pathlib import Path

import yaml


def ensure_repo(repo_url, local_path):
    """确保物料仓库在本地存在且最新。
    存在 → git pull；不存在 → git clone"""
    local = Path(local_path)

    if (local / ".git").is_dir():
        subprocess.run(
            ["git", "-C", str(local), "pull", "--ff-only"],
            check=True,
            capture_output=True,
            timeout=30,
        )
    else:
        local.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", repo_url, str(local)],
            check=True,
            capture_output=True,
            timeout=90,
        )


def scan_components(local_path):
    """扫描 ansible/roles/ 目录，返回三层结构分类列表。
    目录结构：ansible/roles/<类别>/<组件>/<版本>/tasks/main.yml

    返回格式：[{"name": "System", "key": "system", "components": [
                  {"name": "Ntp", "key": "ntp", "versions": ["1.0"]},
                  ...
               ]}, ...]"""
    roles_dir = Path(local_path) / "ansible" / "roles"

    if not roles_dir.is_dir():
        return []

    categories = []
    for cat in sorted(roles_dir.iterdir()):
        if not cat.is_dir() or cat.name.startswith("."):
            continue

        items = []
        for comp in sorted(cat.iterdir()):
            if not comp.is_dir() or comp.name.startswith("."):
                continue
            versions = [
                v.name for v in sorted(comp.iterdir())
                if v.is_dir() and not v.name.startswith(".")
            ]
            if versions:
                items.append({
                    "name": comp.name.capitalize(),
                    "key": comp.name,
                    "versions": versions,
                })

        if items:
            categories.append({
                "name": cat.name.capitalize(),
                "key": cat.name,
                "components": items,
            })

    return categories


def load_conf(local_path, category, component, version):
    """读取组件配置定义文件，供前端 config 页面渲染表单。

    文件路径：ansible/roles/<category>/<component>/<version>/conf.yaml

    完整格式示例::

        fields:
          - name: port                  # 字段标识（提交时的 key）
            label: 端口                 # 表单标签
            type: number                # number / text / password / select / bool / host_select
            required: true              # 是否必填
            default: 3306               # 默认值
            placeholder: "请输入端口"    # 输入提示（可选）

          - name: deploy_type           # select 类型示例
            label: 部署方式
            type: select
            required: true
            default: "standalone"
            options:                    # type=select 时必填，选项列表
              - "standalone"
              - "replication"

          - name: vip                   # 条件字段示例
            label: VIP 地址
            type: text
            required: true
            placeholder: "10.0.0.100"
            show_if:                    # 条件显示：仅当日志部署模式为 cluster 时才渲染此字段
              field: deploy_mode
              value: "cluster"

    各 type 对应的 HTML 控件::

        number      → <input type="number">
        text        → <input type="text">
        password    → <input type="password">
        select      → <select>，需配合 options 列表
        bool        → <input type="checkbox">
        host_select → <select>，选项自动填入步骤 2 配置的主机 IP

    返回值：dict，key "fields" 为字段定义列表；文件不存在时返回 {"fields": []}。
    """
    conf_path = (
        Path(local_path)
        / "ansible" / "roles" / category / component / version
        / "conf.yaml"
    )
    if not conf_path.is_file():
        return {"fields": []}

    with open(conf_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"fields": []}
