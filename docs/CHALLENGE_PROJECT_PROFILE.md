## KubeLog Insight —— 用 AI Agent 构建的 Kubernetes 日志智能分析平台

### 项目简介

`KubeLog Insight` 是一个围绕 Kubernetes 生产日志排障打造的开源工具。  
它将日志提取、日志预处理、异常识别、AI 总结、历史追踪和报告导出整合为统一工作流，目标是让开发和运维在最短时间内定位高风险问题。

该项目同时提供 **Web UI、Tkinter 和 CLI** 三种入口，既适合日常手工排障，也适合脚本化与自动化集成。

---

### 核心能力

**日志覆盖与分析能力**
- 支持 Kubernetes `Deployment` / `StatefulSet` 组件日志分析
- 支持按命名空间、组件名、时间范围拉取日志
- 内置异常关键词优先策略，可快速定位 `NullPointerException`、`OOM`、`panic` 等高危问题
- 提供两种分析模式：
  - `simple`：快速摘要与修复建议
  - `full_scan`：结构化异常明细 + 聚合统计 + 高频 Pod 标记

**工程能力**
- 多模型接入：`gemini / openai / azopenai / grok / ollama / vertexai`
- 支持 `model`、`api_base_url`、`kubeconfig`、`max_iterations` 等参数调优
- 历史记录本地持久化，可追溯与复盘
- 支持导出单次分析 PDF 与项目文档 PDF

**交互体验**
- 默认 Web UI（HTML/CSS/JS）风格简洁实用，适合展示与演示
- 保留 Tkinter 兼容入口，降低迁移成本
- CLI 适配脚本和批处理任务

---

### AI Agent 全程参与的开发过程

这个项目是一次“**AI 协同研发**”的完整实践，AI Agent 深度参与了从需求分析到交付的全过程：

**需求建模与架构拆分**
- 将“日志排障”问题拆成 `extract -> preprocess -> analyze` 三段式流水线
- 明确了核心模块边界：提取、预处理、模型调用、历史存储、报告生成

**实现与重构**
- 在保留原有 Tkinter 方案的同时，完成 Web UI 重构
- 构建前后端协作接口（分析、历史、导出）并统一参数结构
- 设计兼容多模型的调用层，降低后续 Provider 替换成本

**稳定性优化**
- 修复 GUI 卡顿问题（高亮逻辑异步化/分批处理）
- 修复 `python3 webui/server.py` 直跑导入问题，提升部署稳定性
- 保持 CLI 与 UI 的同源分析引擎，减少分叉维护成本

**文档化与展示**
- 将技术实现沉淀为可展示文档（README、挑战赛介绍）
- 强化“作品可讲述性”，方便在比赛和技术分享中快速传达价值

---

### 总结

`KubeLog Insight` 是一个以“实战排障效率”为导向、由 AI Agent 深度协同构建的云原生工具。  
它验证了一个事实：借助 AI Agent，个人开发者也可以快速实现结构清晰、可扩展、可展示的工程化项目，并在真实场景中持续迭代优化。

如果你的目标是让 Kubernetes 日志分析从“人工翻日志”升级为“自动化智能诊断”，这个项目就是一条可落地的路径。

