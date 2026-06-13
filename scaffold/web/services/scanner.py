"""物料仓库扫描 —— 发现组件并构造 Component 对象。"""

from pathlib import Path
from typing import List

from models.component import Component


def scan(local_path: str) -> List[Component]:
    """
    扫描 ansible/roles/ 目录树，返回 Component 列表。

    目录结构：ansible/roles/<category>/<component>/<version>/conf.yaml
    """
    roles_dir = Path(local_path) / "ansible" / "roles"
    if not roles_dir.is_dir():
        return []

    components = []
    for cat_dir in sorted(roles_dir.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue

        for comp_dir in sorted(cat_dir.iterdir()):
            if not comp_dir.is_dir() or comp_dir.name.startswith("."):
                continue

            for ver_dir in sorted(comp_dir.iterdir()):
                if not ver_dir.is_dir() or ver_dir.name.startswith("."):
                    continue

                comp = Component.from_yaml(
                    comp_dir=ver_dir,
                    key=comp_dir.name,
                    version=ver_dir.name,
                )
                # 没有 conf.yaml 且没有 sections → 只是目录骨架，跳过
                if not comp.sections and not comp.hosts:
                    conf = ver_dir / "conf.yaml"
                    if not conf.is_file():
                        continue

                components.append(comp)

    return components


def get_playbook_path(comp_dir: Path, playbook_rel: str) -> Path:
    """返回组件 playbook 的完整路径。"""
    p = comp_dir / playbook_rel
    # 兼容 .yml / .yaml
    if not p.is_file():
        yaml_path = comp_dir / (playbook_rel.rsplit(".", 1)[0] + ".yaml")
        if yaml_path.is_file():
            return yaml_path
        yml_path = comp_dir / (playbook_rel.rsplit(".", 1)[0] + ".yml")
        if yml_path.is_file():
            return yml_path
    return p


def group_by_category(components: List[Component]) -> list:
    """
    按分类分组，返回前端步骤1所需的三层结构。

    :return: [{name, key, components: [{name, key, versions}]}]
    """
    cat_map = {}
    for comp in components:
        # 从路径推导 category： ansible/roles/<cat>/<comp>/<ver>
        cat_name = "other"
        # 传入时 component 已携带 category 信息，由 scan 方决定
        # 这里做简化：通过 key 推断
        if comp.key not in cat_map:
            cat_map[comp.key] = []

    # 实际实现：返回 Component 列表，由 routes 自行分组
    return components
