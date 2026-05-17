# sre-scaffold

自动化部署工具。中控机 `wget` 下载 → 执行 `install.sh` → 启动 Web 界面 → 完成全部部署。

## 部署流程

```
用户中控机（可访问外网）
  │
  ├─ wget 下载 sre-scaffold
  ├─ bash install.sh          # 安装依赖、构建 Go CLI、启动 Web
  ├─ 浏览器打开 Web 界面
  │   ├─ 步骤1: 选择要部署的组件和版本
  │   ├─ 步骤2: 配置目标主机 + 环境检测
  │   ├─ 步骤3: 逐组件配置参数
  │   └─ 步骤4: 确认并执行部署（实时日志）
  │
  └─ 从 toolkit/ 物料仓库读取 playbook → 从镜像仓库拉取镜像 → 分发到目标机
```

## 目录结构

```
sre-scaffold/
│
├── install.sh                # 一键安装脚本
│                               # 检测 Python/Go/ansible → 安装依赖
│                               # → 构建 scaffold 二进制 → 启动 web 服务
│
├── README.md                 # 本文件
│
├── scaffold/                 # Go CLI 工具（终端备用入口，编译为单二进制）
│   │
│   ├── main.go               # CLI 入口：子命令 plan / validate / run
│   │                           # 解析命令行参数，加载 YAML，分发到对应处理函数
│   │
│   ├── stack.go              # 数据模型 + YAML 解析
│   │                           # 定义 Stack/Layer/Item/Target 结构体
│   │                           # LoadStack() 将 YAML 反序列化为 Go 结构体
│   │
│   ├── engine.go             # 执行引擎
│   │                           # 按 Layer 书写顺序迭代
│   │                           # 对每个 Item 构造 ansible-playbook 命令并执行
│   │                           # YAML 中的 vars 通过 --extra-vars 透传给 Ansible
│   │
│   ├── gitops.go             # Git 物料仓库管理
│   │                           # CloneRepo() / CheckoutVersion() / PullLatest()
│   │                           # 支持按 tag 或分支切换物料版本
│   │
│   ├── go.mod                # Go 模块定义，依赖 gopkg.in/yaml.v3
│   │
│   ├── stacks/               # 示例栈定义 YAML 文件
│   │                           # 用户参考这些示例编写自己的栈定义
│   │
│   └── README.md             # Go CLI 模块详细说明
│
└── web/                      # Python Web 应用（主要入口，用户通过浏览器交互）
    │
    ├── app.py                # Flask 入口 + 全部路由
    │                           # /select /hosts /config /deploy 四步向导页面
    │                           # /api/check-host 主机连通性检测
    │                           # /api/deploy/stream SSE 实时日志推送
    │
    ├── config.py             # 全局配置
    │                           # 物料仓库路径、镜像仓库地址、ansible 路径等
    │                           # 所有配置可通过环境变量覆盖
    │
    ├── templates/            # Jinja2 页面模板（四步向导）
    │   ├── base.html         #   基础布局：头部 logo + 步骤导航条 + 底部
    │   ├── select.html       #   步骤1：展示可用组件列表，勾选要部署的组件和版本
    │   ├── hosts.html        #   步骤2：填写目标主机 IP/SSH 信息，一键检测连通性
    │   ├── config.html       #   步骤3：逐组件配置部署模式（单机/集群）、目标主机、专属参数
    │   └── deploy.html       #   步骤4：展示部署摘要，确认后执行，实时查看 Ansible 日志
    │
    ├── static/               # 前端静态资源
    │   ├── css/style.css     #   全部样式：布局、按钮、表单、日志输出、响应式
    │   └── js/app.js         #   前端交互：动态增删主机、连通性检测、SSE 日志接收
    │
    ├── services/             # 业务逻辑模块（空文件，待实现）
    │   ├── __init__.py       #   包初始化
    │   ├── ansible.py        #   ansible-runner 封装，执行 playbook，输出实时日志
    │   ├── gitops.py         #   Git 仓库操作：clone/list_components/list_versions
    │   ├── registry.py       #   镜像仓库操作：pull/push/distribute
    │   └── stack.py          #   YAML 栈定义管理：load/save/generate_inventory
    │
    └── README.md             # Web 模块详细说明

## 与物料仓库的关系

- `toolkit/` 目录本身就是物料仓库，sre-scaffold 直接读取
- 用户在 Web 界面选择的组件/版本，对应 `toolkit/ansible/roles/<组件>/<版本>/`
- sre-scaffold 执行部署时从物料仓库拉取对应版本的 playbook 和配置模板
