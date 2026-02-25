"""
Orchestrates log extraction, preprocessing, and AI analysis.
"""
from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field

from .log_extractor import ExtractParams, extract_logs
from .preprocessor import PreprocessConfig, preprocess
from .api_layer import AnalysisRequest, analyze_with_backend


@dataclass
class AnalysisResult:
    success: bool
    raw_log_preview: str = ""
    preprocessed_log_preview: str = ""
    analysis_text: str = ""
    error_message: str = ""
    component_type: str = ""
    component_name: str = ""
    namespace: str = ""
    time_range: Optional[str] = None


def run_analysis(
    component_type: str,
    component_name: str,
    namespace: str = "default",
    time_range: Optional[str] = None,
    tail_lines: Optional[int] = 5000,
    preprocess_config: Optional[PreprocessConfig] = None,
    backend: str = "kubectl-ai",
    kubeconfig: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base_url: Optional[str] = None,
    llm_provider: str = "gemini",
    model: Optional[str] = None,
    max_iterations: int = 50,
    analysis_mode: str = "simple",
) -> AnalysisResult:
    """
    Full pipeline: extract -> preprocess -> analyze.
    """
    result = AnalysisResult(
        success=False,
        component_type=component_type,
        component_name=component_name,
        namespace=namespace,
        time_range=time_range,
    )

    params = ExtractParams(
        component_type=component_type,
        name=component_name,
        namespace=namespace,
        since=time_range,
        tail_lines=tail_lines,
        kubeconfig=kubeconfig,
    )
    raw_log, err = extract_logs(params)
    if err:
        result.error_message = f"Log extraction failed: {err}"
        return result

    result.raw_log_preview = raw_log[:2000] + ("..." if len(raw_log) > 2000 else "")

    preprocess_config = preprocess_config or PreprocessConfig()
    processed = preprocess(raw_log, preprocess_config)
    result.preprocessed_log_preview = processed[:2000] + ("..." if len(processed) > 2000 else "")

    if not processed.strip():
        result.error_message = "No log lines after preprocessing."
        return result

    request = AnalysisRequest(
        log_content=processed,
        component_type=component_type,
        component_name=component_name,
        namespace=namespace,
        time_range=time_range,
        api_key=api_key,
        api_base_url=api_base_url,
        llm_provider=llm_provider,
        model=model,
        kubeconfig=kubeconfig,
        max_iterations=max_iterations,
        analysis_mode=analysis_mode,
    )
    analysis_text, analysis_err = analyze_with_backend(request, backend=backend)
    if analysis_err:
        result.error_message = f"Analysis failed: {analysis_err}"
        return result

    result.analysis_text = analysis_text
    result.success = True
    return result
