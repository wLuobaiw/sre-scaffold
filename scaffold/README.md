# scaffold — Go CLI 工具

`sre-scaffold` 的命令行入口，编译为单二进制文件，供终端用户使用。

## 文件职责

| 文件 | 职责 |
|------|------|
| `main.go` | CLI 入口。解析子命令 `plan` / `validate` / `run`，加载 YAML 栈定义，分发到对应处理函数 |
| `stack.go` | 数据模型定义。`Stack` / `Layer` / `Item` / `Target` 结构体与 YAML 栈文件一一对应。包含 `LoadStack()` 函数，用 `yaml.v3` 将栈定义文件反序列化为 Go 结构体 |
| `engine.go` | 执行引擎。按 Layer 书写顺序迭代，对每个 Item 构造 `ansible-playbook` 命令并执行。用户 YAML 中的 `vars` 通过 `--extra-vars` 透传给 Ansible |
| `gitops.go` | Git 物料仓库管理。提供 `CloneRepo()` / `CheckoutVersion()` / `PullLatest()` 等函数，支持按 tag 或分支切换版本 |
| `stacks/` | 示例栈定义 YAML 文件目录 |
| `go.mod` | Go 模块定义。依赖 `gopkg.in/yaml.v3` |

## 子命令

```
scaffold plan stacks/example.yml       # 预览执行计划，不实际操作
scaffold validate stacks/example.yml   # 校验语法 + playbook 存在性 + SSH 连通性
scaffold run stacks/example.yml        # 执行完整部署
```

## 数据流

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

## 与 Web 的关系

Go CLI 和 Python Web 读同一套 YAML 栈定义格式。Web 后端直接调用 `ansible-runner`（Python 原生库），不走 Go CLI。两者互为备选入口。
