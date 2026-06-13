"""组件定义模型 —— conf.yaml 的强类型表示。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# ═══════════════════════════════════════════════════════════════
# 基础数据类
# ═══════════════════════════════════════════════════════════════

@dataclass
class HostGroup:
    """
    主机组 —— 对应 Ansible inventory group。

    default="all" 时不渲染前端选择器。
    """
    name: str                                           # inventory group 名
    label: str = ""
    default: str = "all"
    multiple: bool = False
    show_when: Optional[dict] = None                    # {field: value}


@dataclass
class Field:
    """
    配置字段 —— 对应 Ansible playbook vars 中的一个变量。

    widget 决定前端渲染成什么控件：
        text / number / password / select / bool
    """
    name: str                                           # Ansible 变量名
    label: str = ""
    widget: str = "text"
    default: Any = None
    required: bool = False
    readonly: bool = False
    placeholder: str = ""
    options: List[dict] = field(default_factory=list)   # [{value, label}]
    show_when: Optional[dict] = None                    # {field: value}


@dataclass
class Section:
    """
    配置分区 —— 一组字段的逻辑分组。

    collapsed=True 时前端默认折叠。
    """
    name: str = ""
    collapsed: bool = False
    fields: List[Field] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# Component
# ═══════════════════════════════════════════════════════════════

@dataclass
class Component:
    """
    从 conf.yaml 解析出的组件定义。

    这是核心模型 —— scanner 扫描到它，routes 把它传给模板，
    inventory 从它生成 Ansible inventory。
    """
    key: str                                            # 目录名，如 "mysql"
    name: str = ""
    description: str = ""
    version: str = ""
    playbook: str = "tasks/main.yml"
    hosts: List[HostGroup] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)

    # ── 判断属性 ──────────────────────────────────────────

    @property
    def needs_host_ui(self) -> bool:
        """
        是否有需要在 UI 中渲染的主机选择器。

        show_when 不为 None 的组 → 必须渲染（用户操作可能触发显示）
        default != "all" 的组 → 需要用户选择
        全部 default="all" 且无 show_when → 无需 UI
        """
        for h in self.hosts:
            if h.show_when is not None:
                return True
            if h.default != "all":
                return True
        return False

    @property
    def needs_vars_ui(self) -> bool:
        """是否有需要用户填写的变量（non-readonly）。"""
        for s in self.sections:
            for f in s.fields:
                if not f.readonly:
                    return True
        return False

    @property
    def visible_sections(self) -> List[Section]:
        """返回有可见字段的 section 列表。"""
        return [s for s in self.sections if s.fields]

    @property
    def all_fields(self) -> List[Field]:
        """展平所有 section 的字段。"""
        result = []
        for s in self.sections:
            result.extend(s.fields)
        return result

    @property
    def playbook_path(self) -> str:
        return self.playbook

    # ── 构造方法 ──────────────────────────────────────────

    @classmethod
    def from_yaml(cls, comp_dir: Path, key: str = "", version: str = "") -> "Component":
        """
        从组件目录加载 conf.yaml 并构造 Component。

        :param comp_dir: ansible/roles/<cat>/<comp>/<ver>/ 目录
        :param key: 组件 key（目录名）
        :param version: 版本号
        """
        conf_file = comp_dir / "conf.yaml"
        if not conf_file.is_file():
            return cls(key=key, name=key, version=version)

        try:
            with open(conf_file, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except (yaml.YAMLError, OSError):
            return cls(key=key, name=key, version=version)

        if not isinstance(raw, dict):
            return cls(key=key, name=key, version=version)

        return cls(
            key=key,
            name=raw.get("name", key),
            description=raw.get("description", ""),
            version=version,
            playbook=raw.get("playbook", "tasks/main.yml"),
            hosts=_parse_hosts(raw.get("hosts")),
            sections=_parse_sections(raw.get("sections")),
        )


# ═══════════════════════════════════════════════════════════════
# 解析函数
# ═══════════════════════════════════════════════════════════════

def _parse_hosts(raw) -> List[HostGroup]:
    """解析 hosts 配置。单 dict → 列表，列表 → 保留。"""
    if not raw:
        return []

    # 单 dict
    if isinstance(raw, dict):
        return [HostGroup(
            name=raw.get("name", "target"),
            label=raw.get("label", "目标主机"),
            default=raw.get("default", "all"),
            multiple=raw.get("multiple", False),
            show_when=_normalize_show_when(raw.get("show_when")),
        )]

    # 列表
    result = []
    for h in raw:
        if not isinstance(h, dict) or "name" not in h:
            continue
        result.append(HostGroup(
            name=h["name"],
            label=h.get("label", h["name"]),
            default=h.get("default", "all"),
            multiple=h.get("multiple", False),
            show_when=_normalize_show_when(h.get("show_when")),
        ))
    return result


def _parse_sections(raw) -> List[Section]:
    """解析 sections。"""
    if not raw:
        return []

    result = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        fields = []
        for f in s.get("fields") or []:
            if not isinstance(f, dict) or "name" not in f:
                continue
            fields.append(_parse_field(f))
        if fields or s.get("name"):
            result.append(Section(
                name=s.get("name", ""),
                collapsed=s.get("collapsed", False),
                fields=fields,
            ))
    return result


def _parse_field(raw: dict) -> Field:
    """解析单个字段。"""
    options = []
    for o in raw.get("options") or []:
        if isinstance(o, dict):
            options.append(o)
        else:
            options.append({"value": o, "label": str(o)})

    widget = raw.get("widget", "text")
    default = raw.get("default", _default_for_widget(widget))

    # bool 默认值统一为 bool 类型
    if widget == "bool" and "default" in raw:
        default = bool(raw["default"])

    # select 多选时 default 为 list
    if widget == "select" and raw.get("multiple"):
        if default is not None and not isinstance(default, list):
            default = [default]

    return Field(
        name=raw["name"],
        label=raw.get("label", raw["name"]),
        widget=widget,
        default=default,
        required=raw.get("required", False),
        readonly=raw.get("readonly", False),
        placeholder=raw.get("placeholder", ""),
        options=options,
        show_when=_normalize_show_when(raw.get("show_when")),
    )


def _normalize_show_when(raw) -> Optional[dict]:
    """标准化 show_when：字符串 → {field: "yes"}，dict → 保留。"""
    if raw is None:
        return None
    if isinstance(raw, str):
        return {raw: "yes"}
    if isinstance(raw, dict):
        return raw
    return None


def _default_for_widget(widget: str) -> Any:
    return {
        "bool": False, "number": 0,
        "text": "", "password": "", "select": "",
    }.get(widget, "")
