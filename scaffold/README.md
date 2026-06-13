# scaffold —— 构建模块

scaffold/ 是 sre-scaffold 的**构建目录**，包含 Dockerfile 以及 Go CLI 和 Web 应用源码。

## 构建

```bash
bash build.sh                    # 构建 Docker 镜像（默认标签 sre-scaffold:1.0）
bash build.sh my-image:v2        # 指定自定义标签
```

构建上下文为 `scaffold/` 目录自身，Dockerfile 中的 `COPY web/requirements.txt .` 基于此上下文。

## 目录结构

| 路径 | 说明 |
|------|------|
| `Dockerfile` | 多阶段构建，python:3.12-slim 基础镜像 |
| `build.sh` | 构建入口脚本 |
| `main.go` | Go CLI 入口（预留，尚未实现） |
| `stack.go` | 数据模型（预留） |
| `engine.go` | 执行引擎（预留） |
| `gitops.go` | Git 物料管理（预留） |
| `go.mod` | Go 模块定义（预留） |
| `stacks/` | 示例栈定义 YAML 文件（预留） |
| `web/` | Python Flask Web 应用（已实现） |
| `web/README.md` | Web 模块详细说明 |

> **注意**：Go CLI 当前为预留状态（`.go` 文件为占位 stub），所有功能通过 Web 界面提供。

## Go CLI 设计（预留）

以下为 Go CLI 的预期设计，尚未实现。

### 文件职责

| 文件 | 职责 |
|------|------|
| `main.go` | CLI 入口。解析子命令 `plan` / `validate` / `run`，加载 YAML 栈定义，分发到对应处理函数 |
| `stack.go` | 数据模型定义。`Stack` / `Layer` / `Item` / `Target` 结构体与 YAML 栈文件一一对应。包含 `LoadStack()` 函数，用 `yaml.v3` 将栈定义文件反序列化为 Go 结构体 |
| `engine.go` | 执行引擎。按 Layer 书写顺序迭代，对每个 Item 构造 `ansible-playbook` 命令并执行。用户 YAML 中的 `vars` 通过 `--extra-vars` 透传给 Ansible |
| `gitops.go` | Git 物料仓库管理。提供 `CloneRepo()` / `CheckoutVersion()` / `PullLatest()` 等函数，支持按 tag 或分支切换版本 |
| `stacks/` | 示例栈定义 YAML 文件目录 |
| `go.mod` | Go 模块定义。依赖 `gopkg.in/yaml.v3` |

### 子命令

```
scaffold plan stacks/example.yml       # 预览执行计划，不实际操作
scaffold validate stacks/example.yml   # 校验语法 + playbook 存在性 + SSH 连通性
scaffold run stacks/example.yml        # 执行完整部署
```

### 数据流

```
栈定义 YAML  →  stack.go (LoadStack)  →  engine.go (迭代执行)
                                              │
                              ┌────────────────┘
                              ▼
              ansible-playbook -i <host>, -u <user>
                               --key-file <key> --extra-vars "..."
                               <playbook>

                              变量传递：YAML vars → --extra-vars → Ansible {{ var }}
```

### 与 Web 的关系

Go CLI 和 Python Web 读同一套 YAML 栈定义格式。Web 后端直接调用 `ansible-runner`（Python 原生库），不走 Go CLI。两者互为备选入口。
