# KubeLog Insight

一个面向 Kubernetes 日志排障的 AI 智能分析工具。  
将 `kubectl` 日志提取、日志预处理、AI 分析、历史记录管理和 PDF 报告导出串成完整流程，提供 **Web UI / Tkinter / CLI** 三种使用方式。

---

## 项目背景

在 Kubernetes 环境中，日志量巨大、排障时间长、异常定位难。  
**KubeLog Insight** 的目标是：让用户只输入组件和时间范围，就能快速得到结构化的异常分析结果。

典型痛点：
- 手动 `kubectl logs` 输出量大，难以快速定位 `NullPointerException`、`OOM`、`panic` 等高风险问题
- 多 Pod、多容器日志分散，关联分析费时费力
- 排障结果无法留存，难以形成复盘材料

---

## 核心能力

### 1. 一站式日志分析流水线

自动完成三个阶段：**日志提取 → 预处理 → AI 分析**

- **日志提取**：通过 `kubectl get` 解析 label selector，再用 `kubectl logs -l` 批量拉取 Pod 日志，支持 `--since`、`--tail`、`--all-containers`、`--timestamps`
- **预处理**：正则关键字过滤、优先异常行 + 头尾采样，最多保留 2000 行，防止超出 AI 上下文限制（硬上限 120,000 字符）
- **AI 分析**：调用 `kubectl-ai` 将处理后的日志连同分析提示词一起输入，返回结构化异常摘要与修复建议

### 2. 两种分析模式

| 模式 | 说明 |
|------|------|
| `simple` | 快速排查，输出核心异常列表与建议 |
| `full_scan` | 全量扫描，抓取 Java 异常（RuntimeException / Error / Exception 关键字），输出结构化明细（时间、Pod、异常类型）、按异常类型聚合统计、高频 Pod 标记 |

### 3. 多 LLM Provider 支持

| Provider | 环境变量 | 默认模型 |
|----------|----------|----------|
| `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `azopenai` | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | `gpt-4o` |
| `grok` | `GROK_API_KEY` | `grok-2` |
| `ollama` | 无需 API Key | `llama3` |
| `vertexai` | 无需 API Key | `gemini-2.0-flash` |

- 支持自定义 `api_base_url`（兼容 OpenAI 风格网关，如 DeepSeek）
- 支持自定义 `kubeconfig` 路径（企业多集群场景）
- 支持 `max_iterations` 调优（默认 50，范围 1–100）

### 4. 三种使用入口

- **Web UI**（默认）：Flask + HTML/CSS/JS，现代化界面，支持多组件批量分析
- **Tkinter UI**：桌面端 GUI，含异常关键字高亮（红底标注）
- **CLI**：脚本化/CI 场景，参数化调用，结果输出到 stdout

### 5. 历史记录与 PDF 导出

- 每次成功分析自动保存到 `~/.config/k8s-log-analyzer/history/`（JSON 文件，每条一个文件）
- 历史记录按时间倒序列出，支持查看、删除（最多显示 100 条）
- 导出 PDF：单次分析报告 / 项目说明文档（基于 ReportLab）

---

## 技术架构

```
Web UI / Tkinter UI / CLI
          │
          ▼
  analysis_engine.run_analysis()        ← 流水线编排器
          │
          ├─► log_extractor.py          kubectl get (selector) → kubectl logs -l
          │                             支持: deployment / statefulset / daemonset
          │                             超时: 300s
          │
          ├─► preprocessor.py           正则过滤 → 优先行采样 → 头尾截取
          │                             最大保留: 2000 行
          │
          ├─► api_layer.py              构建 prompt → stdin 管道给 kubectl-ai
          │                             支持: simple / full_scan 两种 prompt 模板
          │                             超时: simple=120s / full_scan=180s
          │
          ├─► history_store.py          JSON 文件存储，路径: ~/.config/k8s-log-analyzer/history/
          │
          └─► pdf_report.py             ReportLab 渲染（懒加载，可选依赖）
```

---

## 目录结构

```
.
├── main.py                    # 统一入口（默认 Web UI，--ui tkinter 回退桌面端）
├── run_analysis_cli.py        # 命令行入口
├── requirements.txt           # flask>=3.0.0, reportlab>=4.0.0
│
├── gui/
│   └── app.py                 # Tkinter MainWindow（含异常高亮、历史、PDF 导出）
│
├── webui/
│   ├── server.py              # Flask 应用工厂，所有 REST API
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── style.css
│       └── app.js
│
└── k8s_log_analyzer/          # 核心分析引擎（纯 Python，无框架依赖）
    ├── analysis_engine.py     # 流水线编排，返回 AnalysisResult
    ├── log_extractor.py       # kubectl 日志提取
    ├── preprocessor.py        # 预处理：过滤 + 采样
    ├── api_layer.py           # kubectl-ai 调用封装，LLM provider 配置
    ├── history_store.py       # 历史记录 JSON 读写
    ├── config_store.py        # 配置持久化（kubeconfig 路径、api_base_url）
    └── pdf_report.py          # ReportLab PDF 生成
```

---

## 安装与启动

### 环境准备

- Python 3.8+
- 已配置好的 `kubectl`（可访问目标集群）
- `kubectl-ai` 已安装并在 `PATH` 中可执行
- 对应 LLM Provider 的 API Key（按需配置环境变量）

> 若系统中未安装独立的 `kubectl-ai` 二进制，工具会自动回退到 `kubectl ai`（kubectl plugin 模式）。

### 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` 内容：

```
flask>=3.0.0
reportlab>=4.0.0   # PDF 导出可选，不安装则 PDF 功能不可用
```

### 启动方式

#### Web UI（默认，推荐）

```bash
python3 main.py
# 或直接运行 Web 服务
python3 webui/server.py
```

默认监听 `http://127.0.0.1:8787`，支持自定义：

```bash
python3 main.py --host 0.0.0.0 --port 9000
```

#### Tkinter 桌面 UI

```bash
python3 main.py --ui tkinter
```

#### CLI

```bash
python3 run_analysis_cli.py \
  --type deployment \
  --name my-app \
  --namespace production \
  --since 1h \
  --tail 5000 \
  --llm-provider openai \
  --model deepseek-chat \
  --api-base https://api.deepseek.com \
  --kubeconfig /opt/k8s/config
```

CLI 完整参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--type` / `-t` | `deployment` | 组件类型：`deployment` / `statefulset` / `daemonset` |
| `--name` / `-n` | 必填 | 组件名称 |
| `--namespace` / `-N` | `default` | 命名空间 |
| `--since` / `-s` | `1h` | 时间范围，如 `30m`、`2h`、`24h` |
| `--tail` | `5000` | 最多拉取行数 |
| `--llm-provider` | `gemini` | LLM Provider |
| `--model` | Provider 默认 | 模型名称 |
| `--kubeconfig` / `-k` | 系统默认 | kubeconfig 文件路径 |
| `--api-key` | 环境变量 | API Key（不会保存到磁盘） |
| `--api-base` | 无 | API Base URL |
| `--no-save` | 否 | 不写入历史记录 |

#### Docker 运行

镜像内已包含 `kubectl` 与 `kubectl-ai`，直接启动 Web UI：

```bash
# 构建并运行（需挂载 kubeconfig 以便访问集群）
docker build -t k8s-log-analyzer:latest .
docker run -d --rm -p 8787:8787 \
  -v ${HOME}/.kube/config:/root/.kube/config:ro \
  -v k8s-log-analyzer-data:/root/.config/k8s-log-analyzer \
  --name k8s-log-analyzer \
  k8s-log-analyzer:latest
```

访问 `http://localhost:8787`。自定义端口可通过环境变量 `PORT` 覆盖（需同时映射端口）：

```bash
docker run -d --rm -p 9090:9090 -e PORT=9090 \
  -v ${HOME}/.kube/config:/root/.kube/config:ro \
  k8s-log-analyzer:latest
```

使用 Docker Compose：

```bash
docker compose up -d
# 可选：仅运行 CLI 示例
docker compose --profile cli run --rm k8s-log-analyzer-cli
```

镜像支持多架构（amd64 / arm64），构建时可通过 `--platform` 或 Buildx 指定。

---

## Web API

Web UI 后端提供以下 REST 接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | Web UI 主页 |
| `GET` | `/api/k8s/test-connection` | 测试 kubectl 集群连接 |
| `GET` | `/api/k8s/namespaces` | 列出命名空间 |
| `GET` | `/api/k8s/components` | 列出指定类型的组件 |
| `POST` | `/api/analyze` | 单组件分析 |
| `POST` | `/api/analyze-multi` | 多组件批量分析 |
| `GET` | `/api/history` | 历史记录列表（最多 100 条） |
| `GET` | `/api/history/<id>` | 历史记录详情 |
| `DELETE` | `/api/history/<id>` | 删除历史记录 |
| `POST` | `/api/export/analysis-pdf` | 导出单次分析 PDF |
| `POST` | `/api/export/project-pdf` | 导出项目说明 PDF |
| `POST` | `/api/upload/kubeconfig` | 上传 kubeconfig 文件 |

---

## 典型使用场景

### 场景 1：快速定位线上异常

选择组件类型、填写组件名，分析模式选 `simple`，时间范围选 `1h`，点击开始分析，即可得到核心异常摘要与修复建议。

### 场景 2：Java 服务异常全量扫描

分析模式切换为 `full_scan`，工具将：
1. 抓取所有 RuntimeException、Error、Exception 相关行
2. 按异常类型分组统计（降序排列）
3. 标记高频异常 Pod（> 5次/分钟）
4. 输出当前重点问题及分析建议

适合定期排查高频问题 Pod、生成复盘材料。

### 场景 3：多集群 / 自定义 kubeconfig

```bash
python3 run_analysis_cli.py \
  --type statefulset \
  --name redis-cluster \
  --namespace data \
  --kubeconfig /opt/clusters/prod-config
```

Web UI 同样支持上传或填写 kubeconfig 路径，并提供一键测试连接功能。

### 场景 4：对接企业内部 LLM 网关（OpenAI 兼容）

```bash
export OPENAI_API_KEY=your_key
python3 run_analysis_cli.py \
  --type deployment \
  --name api-server \
  --llm-provider openai \
  --model deepseek-chat \
  --api-base https://api.deepseek.com
```

### 场景 5：使用本地 Ollama 模型（无需 API Key）

```bash
python3 run_analysis_cli.py \
  --type deployment \
  --name my-app \
  --llm-provider ollama \
  --model llama3
```

---

## 关键实现细节

| 特性 | 说明 |
|------|------|
| 日志提取超时 | `kubectl logs` 300s，`kubectl get` 30s |
| AI 分析超时 | `simple` 模式 120s，`full_scan` 模式 180s |
| 日志大小上限 | 发送给 AI 前硬截断至 120,000 字符 |
| 预处理采样策略 | 优先保留含 `exception/error/panic/fatal/nullpointer/npe` 的行，剩余取头尾各半，总上限 2000 行 |
| 历史存储路径 | `~/.config/k8s-log-analyzer/history/<YYYYMMDD-HHMMSS>.json`，每条记录仅保留前 1000 字符预览 |
| PDF 存储路径 | `~/.config/k8s-log-analyzer/reports/`，ReportLab 懒加载，未安装时返回错误提示 |
| 配置持久化 | `~/.config/k8s-log-analyzer/settings.json`，保存 kubeconfig 路径和 api_base_url，**API Key 不持久化** |
| GUI 线程安全 | 分析在 `daemon=True` 线程中运行，所有 Tkinter 控件更新通过 `root.after(0, callback)` 派发 |
| Subprocess 安全 | 所有 `subprocess.run()` 均使用列表参数，不使用 `shell=True` |

---

## License

Apache-2.0
