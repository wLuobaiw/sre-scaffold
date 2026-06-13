"""应用配置。"""

import os

# Flask
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"

# 物料仓库
MATERIALS_REPO_URL = os.environ.get("MATERIALS_REPO_URL", "")
MATERIALS_LOCAL_PATH = os.environ.get("MATERIALS_LOCAL_PATH", "/app/toolkit")

# 镜像仓库
REGISTRY_URL = os.environ.get("REGISTRY_URL", "registry.example.com")

# Ansible
ANSIBLE_PLAYBOOK_BIN = os.environ.get("ANSIBLE_PLAYBOOK_BIN", "ansible-playbook")
