"""Ansible inventory 生成 —— 从 Component 模型自动生成。"""

from typing import Any, Dict, List

from models.component import Component


def build(
    component: Component,
    hosts: List[dict],
    user_input: dict,
) -> dict:
    """
    从 Component 定义 + 用户输入生成 Ansible JSON inventory。

    规则：
      - 每个 HostGroup.name → 一个 inventory group
      - default="all" → 包含全部主机
      - show_when 条件不满足的组 → 跳过
      - 主机凭据注入 _meta.hostvars

    :param component: 从 conf.yaml 解析的 Component
    :param hosts: [{ip, ssh_user, ssh_password, ssh_port}]
    :param user_input: {hosts: {group_name: target}, vars: {name: value}}
    :return: Ansible JSON inventory dict
    """
    inventory: Dict[str, Any] = {"_meta": {"hostvars": {}}}
    user_hosts = user_input.get("hosts", {})
    user_vars = user_input.get("vars", {})

    for hg in component.hosts:
        # 条件显示的主机组，检查条件是否满足
        if hg.show_when:
            field_name = next(iter(hg.show_when))
            expected = hg.show_when[field_name]
            actual = user_vars.get(field_name, "")
            # bool 字段比较：checkbox 提交 "yes"，yaml 定义 true/false
            if expected is True and actual != "yes":
                continue
            elif expected is False and actual == "yes":
                continue
            elif expected is not True and expected is not False and str(actual) != str(expected):
                continue

        target = user_hosts.get(hg.name, hg.default)
        indices = _resolve(target, len(hosts))
        if not indices:
            continue        # 该组无主机，跳过

        group_name = hg.name
        if group_name not in inventory:
            inventory[group_name] = {"hosts": {}}

        for idx in sorted(indices):
            if idx >= len(hosts):
                continue
            h = hosts[idx]
            host_name = h.get("ip", f"host{idx}")
            inventory[group_name]["hosts"][host_name] = None

            if host_name not in inventory["_meta"]["hostvars"]:
                inventory["_meta"]["hostvars"][host_name] = {
                    "ansible_host": h.get("ip", ""),
                    "ansible_user": h.get("ssh_user", "root"),
                    "ansible_password": h.get("ssh_password", ""),
                    "ansible_port": int(h.get("ssh_port", 22)),
                }

    return inventory


def build_extra_vars(user_vars: dict) -> dict:
    """将用户填写的变量转为 ansible-playbook --extra-vars。"""
    return {k: v for k, v in (user_vars or {}).items()}


def _resolve(target, host_count: int) -> set:
    """解析主机索引。"""
    if target == "all" or target is None:
        return set(range(host_count))
    if isinstance(target, list):
        return {int(i) for i in target if 0 <= int(i) < host_count}
    try:
        idx = int(target)
        if 0 <= idx < host_count:
            return {idx}
    except (ValueError, TypeError):
        pass
    return set()
