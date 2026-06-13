# sre-scaffold

自动化部署工具。

控制机 `wget` 下载 → 执行 `install.sh` → 启动 Web 界面 → 完成全部部署。

## 部署流程

```
用户控制机（可访问外网）
  │
  ├─ wget 下载 sre-scaffold
  │
  ├─ sh install.sh          # 安装依赖、构建 Go CLI、启动 Web
  │
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
├── install.sh                   # 一键安装脚本
├── README.md                    # 本文件
├── scaffold/                    # 构建目录：Dockerfile + Web 应用 + Go CLI
│   ├── Dockerfile               #   Docker 镜像定义（多阶段构建）
│   ├── build.sh                 #   构建脚本
│   ├── main.go                  #   Go CLI 入口（预留）
│   ├── stack.go                 #   数据模型（预留）
│   ├── engine.go                #   执行引擎（预留）
│   ├── gitops.go                #   Git 物料操作（预留）
│   ├── go.mod                   #   Go 模块定义
│   ├── stacks/                  #   示例栈定义 YAML 文件
│   ├── web/                     #   Python Web 应用（主要入口）
│   │   ├── app.py               #     Flask 入口 + 全部路由
│   │   ├── config.py            #     全局配置
│   │   ├── templates/           #     Jinja2 页面模板（四步向导）
│   │   │   ├── base.html        #       基础布局
│   │   │   ├── select.html      #       步骤1：选择组件
│   │   │   ├── hosts.html       #       步骤2：配置主机
│   │   │   ├── config.html      #       步骤3：组件参数
│   │   │   └── deploy.html      #       步骤4：执行部署
│   │   ├── static/              #     前端静态资源
│   │   │   ├── css/style.css
│   │   │   └── js/app.js
│   │   ├── services/            #     业务逻辑模块
│   │   │   ├── ansible.py       #       ansible-runner 封装
│   │   │   ├── gitops.py        #       物料仓库操作
│   │   │   ├── registry.py      #       镜像仓库操作
│   │   │   └── stack.py         #       YAML 栈定义管理
│   │   └── README.md
│   └── README.md                #   构建模块说明
└── toolkit/                     #   运维物料仓库（co-located，无需额外 clone）
    ├── ansible/roles/
    │   ├── middleware/
    │   │   ├── mysql/8.0/
    │   │   ├── mysql/8.4/
    │   │   └── redis/7.4/
    │   └── system/
    │       └── linux-init/1.0.0/
    ├── conf/
    └── template/
```

## 与物料仓库的关系

- toolkit/ 目录与 sre-scaffold 同仓库管理（co-located），无需额外 git clone
- 容器启动时通过 `-v` 将 toolkit/ 挂载到 `/app/toolkit`
- app.py 启动时通过 `MATERIALS_LOCAL_PATH`（默认 `/app/toolkit`）直接读取物料
- 用户在 Web 界面选择的组件/版本，对应 `toolkit/ansible/roles/<分类>/<组件>/<版本>/`
- sre-scaffold 执行部署时从物料仓库读取对应版本的 playbook 和配置模板
