"""
API layer: run kubectl-ai for log analysis; supports multiple LLM providers.
"""
from __future__ import annotations
import os
import subprocess
import shutil
from typing import Optional, Tuple
from dataclasses import dataclass


# Supported LLM providers and their required environment variables
LLM_PROVIDERS = {
    "gemini": {
        "env_key": "GEMINI_API_KEY",
        "default_model": "gemini-2.0-flash",
        "help": "Google Gemini API",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "help": "OpenAI (GPT-4, GPT-4o)",
    },
    "azopenai": {
        "env_key": "AZURE_OPENAI_API_KEY",
        "env_endpoint": "AZURE_OPENAI_ENDPOINT",
        "default_model": "gpt-4o",
        "help": "Azure OpenAI",
    },
    "grok": {
        "env_key": "GROK_API_KEY",
        "default_model": "grok-2",
        "help": "xAI Grok",
    },
    "ollama": {
        "env_key": None,
        "default_model": "llama3",
        "help": "Local Ollama (no API key needed)",
    },
    "vertexai": {
        "env_key": None,
        "default_model": "gemini-2.0-flash",
        "help": "Google Cloud Vertex AI",
    },
}


@dataclass
class AnalysisRequest:
    log_content: str
    component_type: str
    component_name: str
    namespace: str
    time_range: Optional[str] = None
    prompt_extra: Optional[str] = None
    # LLM provider settings
    llm_provider: str = "gemini"  # gemini, openai, azopenai, grok, ollama, vertexai
    model: Optional[str] = None  # Optional model override (e.g. deepseek-chat)
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None  # For Azure OpenAI or custom endpoints
    kubeconfig: Optional[str] = None  # e.g. /opt/config
    max_iterations: int = 50  # kubectl-ai --max-iterations
    analysis_mode: str = "simple"  # simple | full_scan (Java 异常扫描+统计)
    skip_permissions: bool = True  # kubectl-ai --skip-permissions (RunOnce 需要)


def _kubectl_ai_available() -> bool:
    return shutil.which("kubectl-ai") is not None or shutil.which("kubectl") is not None


def _test_kubectl_connection(kubeconfig: Optional[str] = None) -> Tuple[str, str]:
    """Test if kubectl can connect to the cluster. Optional kubeconfig path."""
    if not shutil.which("kubectl"):
        return "", "kubectl not found in PATH"
    env = os.environ.copy()
    if kubeconfig:
        env["KUBECONFIG"] = kubeconfig
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            return "", result.stderr or "Failed to connect to cluster"
        return result.stdout.strip(), ""
    except subprocess.TimeoutExpired:
        return "", "kubectl connection timeout"
    except Exception as e:
        return "", str(e)


def _build_prompt_simple(request: AnalysisRequest) -> str:
    prompt = (
        "Analyze the following Kubernetes application logs. "
        "Identify and list: (1) errors and exceptions, (2) high-risk issues such as "
        "NullPointerException, OOM, panics, connection failures, (3) brief recommendations. "
        "Keep the answer concise and highlight the most critical issues.\n\n"
        f"Component: {request.component_type} / {request.component_name} "
        f"(namespace: {request.namespace}). "
    )
    if request.time_range:
        prompt += f"Time range: {request.time_range}. "
    if request.prompt_extra:
        prompt += request.prompt_extra + " "
    prompt += "\n\n--- Log content (preprocessed) ---\n\n"
    prompt += request.log_content[:120000]
    return prompt


def _build_prompt_full_scan(request: AnalysisRequest) -> str:
    """全量扫描模式：Java 异常抓取、格式化输出、统计与重点问题分析（与截图中的命令风格一致）。"""
    since = request.time_range or "10m"
    kube_hint = f"kubeconfig 路径: {request.kubeconfig}。" if request.kubeconfig else "使用默认 kubeconfig。"
    prompt = (
        f"{kube_hint} 请基于下面已采集的日志执行分析。\n\n"
        f"命名空间: {request.namespace}, 时间范围: {since}。\n\n"
        "请完成以下分析并直接给出结果:\n"
        "1. 从日志中抓取以下 Java 异常类型: RuntimeException 及其子类 (如 NullPointerException, IllegalArgumentException); "
        "Error 及其子类 (如 OutOfMemoryError); 以及包含 'Exception' 或 'Error' 关键字的行 (不区分大小写)。\n"
        "2. 输出格式: 每行包含 [时间] [Pod/容器] 异常类型: 异常信息。\n"
        "3. 附加统计和分析: 按异常类型分组统计次数 (降序); 标记高频异常的 Pod (>5次/分钟); "
        "关联异常最近发生时间并统计出现次数; 输出当前重点问题及分析。\n"
        "4. 若下面日志量过大, 可只针对关键异常行做统计。\n\n"
        "--- 已采集的日志内容 ---\n\n"
    )
    prompt += request.log_content[:120000]
    return prompt


def run_kubectl_ai(analysis_request: AnalysisRequest) -> Tuple[str, str]:
    """
    Run kubectl-ai in quiet mode with a prompt that includes the preprocessed log.
    Supports --max-iterations, KUBECONFIG, and full_scan analysis mode.
    Returns (stdout_response, error_message).
    """
    if not _kubectl_ai_available():
        return "", "kubectl-ai or kubectl not found in PATH"

    if analysis_request.analysis_mode == "full_scan":
        prompt = _build_prompt_full_scan(analysis_request)
    else:
        prompt = _build_prompt_simple(analysis_request)

    binary = "kubectl-ai" if shutil.which("kubectl-ai") else "kubectl"
    
    # Build command: --quiet, --max-iterations, --llm-provider, --model
    args = ["ai", "--quiet"] if binary == "kubectl" else ["--quiet"]
    args.extend(["--max-iterations", str(max(1, min(100, analysis_request.max_iterations)))])
    if analysis_request.skip_permissions:
        # Avoid RunOnce permission prompt failures in quiet mode.
        args.append("--skip-permissions")
    
    provider = analysis_request.llm_provider or "gemini"
    args.extend(["--llm-provider", provider])
    if analysis_request.model:
        args.extend(["--model", analysis_request.model])
    
    cmd = [binary] + args

    env = os.environ.copy()
    if analysis_request.kubeconfig:
        env["KUBECONFIG"] = analysis_request.kubeconfig
    
    if provider in LLM_PROVIDERS:
        provider_config = LLM_PROVIDERS[provider]
        
        # Set API key for the specific provider
        if provider_config.get("env_key") and analysis_request.api_key:
            env[provider_config["env_key"]] = analysis_request.api_key
        
        # Set endpoint for Azure OpenAI or custom endpoints
        if provider == "azopenai" and analysis_request.api_base_url:
            env["AZURE_OPENAI_ENDPOINT"] = analysis_request.api_base_url
        elif provider == "openai" and analysis_request.api_base_url:
            env["OPENAI_API_BASE"] = analysis_request.api_base_url
            env["OPENAI_BASE_URL"] = analysis_request.api_base_url

    timeout = 180 if analysis_request.analysis_mode == "full_scan" else 120
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if result.returncode != 0:
            return "", result.stderr or result.stdout or "kubectl-ai failed"
        return result.stdout.strip(), ""
    except subprocess.TimeoutExpired:
        return "", "kubectl-ai timeout"
    except Exception as e:
        return "", str(e)


def analyze_with_backend(
    request: AnalysisRequest,
    backend: str = "kubectl-ai",
) -> Tuple[str, str]:
    """
    Dispatch to the configured backend. Currently only kubectl-ai is implemented.
    """
    if backend in ("kubectl-ai", "kubectl_ai", ""):
        return run_kubectl_ai(request)
    return "", f"Unsupported backend: {backend}"
