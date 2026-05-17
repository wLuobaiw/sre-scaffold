# web — Python Web 应用

sre-scaffold 的主入口。四步向导式 Web 界面，用户从选择组件到执行部署全流程在浏览器完成。

## 技术栈

| 技术 | 用途 |
|------|------|
| **Flask** | Web 框架，处理路由、请求、session |
| **Jinja2** | 页面模板引擎（Flask 内置），继承式布局 |
| **SSE**（Server-Sent Events） | 服务器向浏览器单向推送日志流 |
| **ansible-runner** | Python 原生 Ansible 执行库（services/ansible.py 预留） |

## 文件说明

### app.py — Flask 应用入口

| 路由 | 方法 | 页面 | 说明 |
|------|------|------|------|
| `/` | GET | — | 重定向到 `/select` |
| `/select` | GET/POST | select.html | 步骤1：展示组件列表，提交选中的组件和版本到 session |
| `/hosts` | GET/POST | hosts.html | 步骤2：配置目标主机信息，提交到 session |
| `/config` | GET/POST | config.html | 步骤3：逐组件配置部署参数，提交到 session |
| `/deploy` | GET | deploy.html | 步骤4：展示部署摘要，等待用户点击执行 |
| `/api/check-host` | POST | — | AJAX 端点：检测单台主机 SSH 连通性，返回 JSON |
| `/api/deploy/stream` | GET | — | SSE 端点：推送 ansible-playbook 实时日志流 |

数据通过 Flask session（cookie）在步骤间传递：
```
session["selected_components"]  →  用户勾选的组件列表
session["component_versions"]   →  每个组件的版本号
session["hosts"]                →  目标主机列表
session["component_configs"]    →  每个组件的详细配置
```

### config.py — 全局配置

所有配置项支持环境变量覆盖：

| 配置项 | 环境变量 | 默认值 |
|--------|---------|--------|
| `SECRET_KEY` | `SECRET_KEY` | 开发用固定值 |
| `DEBUG` | `DEBUG` | true |
| `MATERIALS_LOCAL_PATH` | `MATERIALS_LOCAL_PATH` | `../../toolkit` |
| `REGISTRY_URL` | `REGISTRY_URL` | registry.example.com |
| `ANSIBLE_PLAYBOOK_BIN` | `ANSIBLE_PLAYBOOK_BIN` | ansible-playbook |

### templates/ — 四步向导页面

```
base.html → select.html → hosts.html → config.html → deploy.html
 (布局)      (步骤1)       (步骤2)       (步骤3)       (步骤4)
```

页面使用 Jinja2 模板继承：`base.html` 定义头部导航和底部，各步骤页面通过 `{% extends "base.html" %}` 继承并填充 `{% block content %}`。

每个步骤页面重写 `{% block steps %}` 控制步骤导航的高亮状态（active / done / 默认）。

### static/css/style.css — 样式

CSS 变量控制全局配色，主要区块：

- `.header` / `.steps` — 顶部步骤导航
- `.component-group` / `.comp-item` — 组件选择卡片
- `.host-card` / `.host-fields` — 主机配置表单（四列网格）
- `.config-section` / `.config-row` — 逐组件配置表单
- `.deploy-layout` — 部署页双栏布局（摘要 + 日志）
- `.log-output` — 深色终端风格日志区

### static/js/app.js — 前端交互

| 函数 | 页面 | 用途 |
|------|------|------|
| `addHost()` | hosts | 动态添加主机输入行 |
| `checkHost(index)` | hosts | AJAX 调用 `/api/check-host` 检测单台主机 |
| `checkAllHosts()` | hosts | 遍历所有主机执行检测 |
| `toggleConfig(key)` | config | 展开/折叠组件的配置区域 |
| `toggleHostSelect(key, mode)` | config | 单机/集群切换时改 input type |
| `startDeploy()` | deploy | 建立 SSE 连接接收日志流，渲染到日志区 |

### services/ — 业务模块

| 文件 | 职责 | 状态 |
|------|------|------|
| `ansible.py` | ansible-runner 封装。`run_playbook(playbook, hosts, extra_vars)` → 生成日志回调 | 空文件 |
| `gitops.py` | Git 仓库操作。`list_components()` 扫描 roles 目录返回组件和版本列表 | 空文件 |
| `registry.py` | 镜像仓库操作。`pull_image()` / `distribute_to_hosts()` 拉取镜像分发到目标机 | 空文件 |
| `stack.py` | YAML 栈管理。`load_stack()` / `save_stack()` / `generate_inventory()` 生成 Ansible inventory | 空文件 |

当前 app.py 中 `get_available_middleware()` 和 `check_host()` 使用的模拟数据，在 service 实现后替换为真实调用。

## 启动

```bash
cd recipes/sre-scaffold/web
pip install flask
python app.py
# 浏览器访问 http://localhost:5000
```
