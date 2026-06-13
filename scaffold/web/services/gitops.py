"""Git 物料仓库操作：拉取、列出组件和版本。"""

import subprocess
from pathlib import Path

import yaml


def ensure_repo(repo_url, local_path):
    """
    确保物料仓库在本地可用。

    repo_url 为空时（co-located 模式），仅校验本地路径是否存在；
    repo_url 非空时，执行 git clone 或 git pull（远程模式）。

    :param repo_url: Git 仓库远程地址，空字符串表示 co-located 模式
    :param local_path: 本地存储目录
    :raises FileNotFoundError: co-located 模式下路径不存在
    :raises subprocess.CalledProcessError: git 命令执行失败时抛出
    """
    local = Path(local_path)

    # co-located 模式 —— toolkit 与 sre-scaffold 同仓库管理，无需 clone
    if not repo_url:
        if not local.is_dir():
            raise FileNotFoundError(
                f"物料仓库未找到: {local_path}。"
                "请确认 toolkit/ 已挂载或 MATERIALS_LOCAL_PATH 设置正确。"
            )
        return

    # 远程模式 —— 通过 git 获取
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
    """
    扫描 ansible/roles/ 目录，返回三层分类组件列表。

    目录结构：ansible/roles/<类别>/<组件>/<版本>/tasks/main.yml

    :param local_path: 物料仓库本地路径
    :return: 分类列表 [{name, key, components: [{name, key, versions}]}]，
             目录不存在或无有效内容时返回空列表
    """
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


def get_component_dir(local_path, category, component, version):
    """
    根据分类 / 组件 / 版本拼装组件目录路径。

    :param local_path: 物料仓库本地路径
    :param category: 分类名（system / middleware / ...）
    :param component: 组件名（nginx / mysql / ...）
    :param version: 版本号（8.0 / 7.4 / ...）
    :return: 组件版本目录的 Path 对象
    """
    return (
        Path(local_path)
        / "ansible" / "roles" / category / component / version
    )


def load_conf(comp_dir):
    """
    从组件目录读取 conf.yaml，解析为配置字段列表，并做兼容性标准化。

    支持简写：
      option: [...]             → 标准化为 options: [...]
      depends_on: <field_name>  → 标准化为 show_if: {field: <field_name>, value: "yes"}

    字段类型映射：number / text / password / select / bool / target_hosts
     size 参数：非 select 字段控制栅格宽度（12=全行，6=半行）；
              select+multiple 字段控制可见行数。

    编写示例见 toolkit/template/example_conf.yaml。

    :param comp_dir: get_component_dir 返回的组件目录路径
    :return: conf.yaml 解析结果 dict，含标准化后的 key "fields"。
             文件不存在 / 解析失败 / fields 为空时返回 {}。
    """
    conf_file = Path(comp_dir) / "conf.yaml"

    if not conf_file.is_file():
        return {}

    try:
        with open(conf_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return {}

    if not data:
        return {}

    fields = data.get("fields")
    if not fields:
        return {}

    # 标准化：option → options / depends_on → show_if（仅 bool 联动）
    for field in fields:
        if "option" in field and "options" not in field:
            field["options"] = field.pop("option")
        if "depends_on" in field and "show_if" not in field:
            field["show_if"] = field.pop("depends_on")

    return data
