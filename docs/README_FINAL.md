# KubeLog Insight

一个面向 Kubernetes 日志排障的 AI 分析工具。  
它把 `kubectl` 日志提取、日志预处理、`kubectl-ai` 智能分析、历史记录管理和 PDF 报告导出串成一条完整流程，提供 **Web UI / Tkinter / CLI** 三种使用方式。

---

## 项目简介

在 Kubernetes 环境中，日志量巨大、排障时间长、异常定位难。  
`KubeLog Insight` 的目标是：**让用户只输入组件和时间范围，就能快速得到结构化异常分析结果**。

核心场景：
- 快速识别 `NullPointerException`、`OOM`、`panic`、连接失败等高风险问题
- 支持 Deployment / StatefulSet 两类工作负载
- 支持 OpenAI / Gemini / Azure OpenAI / Grok / Ollama / VertexAI 等多模型接入
- 支持分析历史沉淀与 PDF 报告输出，便于复盘和汇报

---

## 核心能力

### 1) 一站式日志分析流水线
- 自动执行：日志提取 -> 预处理 -> AI 分析
- 日志提取：基于 `kubectl get` + `kubectl logs -l` 获取目标组件日志
- 预处理：关键字过滤、采样（优先异常行 + 头尾样本）、内容裁剪
- 智能分析：统一封装 `kubectl-ai` 调用，返回可读的异常总结与建议

### 2) 多种分析模式
- `simple`：快速排查，输出核心异常与建议
- `full_scan`：偏运维排障风格，输出：
  - Java 异常抓取（RuntimeException/Error/Exception|Error 关键字）
  - 结构化结果（时间、Pod/容器、异常类型、异常信息）
  - 按异常类型聚合统计、高频 Pod 标记、关键问题分析

### 3) 多模型与企业环境兼容
- 支持 `llm_provider` + `model` 动态配置（如 `openai + deepseek-chat`）
- 支持 `api_base_url`（兼容 OpenAI 风格网关）
- 支持自定义 `kubeconfig` 路径（如 `/opt/config`）
- 支持 `max_iterations` 调优（默认 50）

### 4) 三种入口，适配不同用户
- **Web UI（默认）**：现代化 HTML 界面，风格简洁清晰
- **Tkinter UI（兼容）**：保留桌面端入口
- **CLI**：便于脚本化、CI 或远程机器使用

### 5) 可追溯与可输出
- 历史记录本地持久化：`~/.config/k8s-log-analyzer/history/`
- 结果可导出 PDF：
  - 单次分析报告
  - 项目说明文档

---

## 技术架构

```text
Web/Tkinter/CLI
      |
      v
analysis_engine.run_analysis()
      |
      +--> log_extractor.py   (kubectl get / kubectl logs)
      +--> preprocessor.py    (regex filter + sampling + cap)
      +--> api_layer.py       (kubectl-ai provider/model dispatch)
      +--> history_store.py   (json files)
      +--> pdf_report.py      (ReportLab)
```

---

## 安装与启动

### 1) 环境准备
- Python 3.8+
- 可访问 Kubernetes 集群的 `kubectl`
- `kubectl-ai` 已安装并可执行
- 对应模型的 API Key（按你选择的 Provider）

### 2) 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) 启动方式

#### Web UI（默认）

```bash
python3 main.py
# 或
python3 webui/server.py
```

默认地址：`http://127.0.0.1:8787`

#### Tkinter UI

```bash
python3 main.py --ui tkinter
```

#### CLI

```bash
python3 run_analysis_cli.py \
  --type deployment \
  --name nginx \
  --namespace default \
  --since 1h \
  --llm-provider openai \
  --model deepseek-chat \
  --kubeconfig /opt/config
```

---

## License

Apache-2.0

