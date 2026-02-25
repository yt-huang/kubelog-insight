"""
Extract logs from Kubernetes Deployment / StatefulSet / DaemonSet via kubectl.
Supports time range and outputs raw log stream for preprocessing.
"""
from __future__ import annotations
import json
import subprocess
import shutil
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class ExtractParams:
    component_type: str  # "deployment" | "statefulset" | "daemonset"
    name: str
    namespace: str = "default"
    since: Optional[str] = None  # e.g. "1h", "30m", "24h"
    tail_lines: Optional[int] = None  # limit lines
    container: Optional[str] = None
    kubeconfig: Optional[str] = None


def _kubectl_available() -> bool:
    return shutil.which("kubectl") is not None


def get_pod_selector(component_type: str, name: str, namespace: str, kubeconfig: Optional[str] = None) -> Tuple[str, str]:
    """Resolve label selector for Deployment / StatefulSet / DaemonSet."""
    cmd = [
        "kubectl", "get", component_type, name,
        "-n", namespace,
        "-o", "jsonpath={.spec.selector.matchLabels}"
    ]
    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode != 0:
            return "", out.stderr or "unknown error"
        labels = json.loads(out.stdout) if out.stdout.strip() else {}
        parts = [f"{k}={v}" for k, v in labels.items()]
        selector = ",".join(parts)
        return selector, ""
    except subprocess.TimeoutExpired:
        return "", "kubectl get selector timeout"
    except Exception as e:
        return "", str(e)


def extract_logs(params: ExtractParams) -> Tuple[str, str]:
    """
    Extract logs from all pods matching Deployment/StatefulSet/DaemonSet.
    Returns (stdout_text, error_message). error_message non-empty on failure.
    """
    if not _kubectl_available():
        return "", "kubectl not found in PATH"

    kind = params.component_type.strip().lower()
    if kind == "stateefulset":
        kind = "statefulset"
    if kind not in ("deployment", "statefulset", "daemonset"):
        return "", f"Unsupported component_type: {params.component_type}"

    selector, err = get_pod_selector(kind, params.name, params.namespace, params.kubeconfig)
    if err:
        return "", f"Failed to get selector: {err}"

    # kubectl logs -l key=value -n ns --all-containers --since=... --tail=...
    cmd = [
        "kubectl", "logs",
        "-l", selector,
        "-n", params.namespace,
        "--all-containers=true",
        "--prefix=true",
        "--timestamps=true",
    ]
    if params.kubeconfig:
        cmd.extend(["--kubeconfig", params.kubeconfig])
    if params.since:
        cmd.extend(["--since", params.since])
    if params.tail_lines is not None and params.tail_lines > 0:
        cmd.extend(["--tail", str(params.tail_lines)])
    
    if params.container:
        cmd = [
            "kubectl", "logs",
            "-l", selector,
            "-n", params.namespace,
            "-c", params.container,
            "--prefix=true",
            "--timestamps=true",
        ]
        if params.kubeconfig:
            cmd.extend(["--kubeconfig", params.kubeconfig])
        if params.since:
            cmd.extend(["--since", params.since])
        if params.tail_lines is not None and params.tail_lines > 0:
            cmd.extend(["--tail", str(params.tail_lines)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            return "", result.stderr or result.stdout or "kubectl logs failed"
        return result.stdout, ""
    except subprocess.TimeoutExpired:
        return "", "kubectl logs timeout (300s)"
    except Exception as e:
        return "", str(e)
