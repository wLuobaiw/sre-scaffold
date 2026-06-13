"""应用全局配置。"""

import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"

# 物料仓库 —— 容器内挂载路径
MATERIALS_LOCAL_PATH = os.environ.get("MATERIALS_LOCAL_PATH", "/app/toolkit")

# Ansible
ANSIBLE_PLAYBOOK_BIN = os.environ.get("ANSIBLE_PLAYBOOK_BIN", "ansible-playbook")
