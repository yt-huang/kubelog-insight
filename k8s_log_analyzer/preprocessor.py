"""
Log preprocessing: keyword filtering (regex), sampling/sharding, optional gzip.
Reduces data volume before sending to AI for analysis.
"""
import re
import gzip
import io
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class PreprocessConfig:
    # Keyword / regex: keep only lines matching any of these (if non-empty)
    include_patterns: list[str] = field(default_factory=list)
    # Exclude lines matching these
    exclude_patterns: list[str] = field(default_factory=list)
    # High-risk keywords to always keep (e.g. exception, error, panic)
    priority_keywords: list[str] = field(
        default_factory=lambda: ["exception", "error", "panic", "fatal", "nullpointer", "npe"]
    )
    # Max lines to send (sample by taking head + tail + priority matches)
    max_lines: int = 2000
    # Use gzip when persisting/sending (smaller payload)
    use_gzip: bool = False


def _compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p, re.IGNORECASE))
        except re.error:
            compiled.append(re.compile(re.escape(p), re.IGNORECASE))
    return compiled


def filter_by_patterns(text: str, include: list[re.Pattern], exclude: list[re.Pattern]) -> str:
    lines = text.splitlines()
    out = []
    for line in lines:
        if exclude and any(r.search(line) for r in exclude):
            continue
        if include and not any(r.search(line) for r in include):
            continue
        out.append(line)
    return "\n".join(out)


def sample_lines(text: str, config: PreprocessConfig) -> str:
    """
    Reduce lines: keep lines with priority keywords, then head + tail up to max_lines.
    """
    lines = text.splitlines()
    if len(lines) <= config.max_lines:
        return text

    priority_re = [
        re.compile(re.escape(k), re.IGNORECASE)
        for k in config.priority_keywords
    ]
    priority_lines = []
    other_lines = []
    for line in lines:
        if any(r.search(line) for r in priority_re):
            priority_lines.append(line)
        else:
            other_lines.append(line)

    # unique priority + head/tail of others
    half = (config.max_lines - len(priority_lines)) // 2
    if half < 0:
        half = 0
    head = other_lines[:half]
    tail = other_lines[-half:] if half else []
    selected = list(dict.fromkeys(priority_lines)) + head + tail
    return "\n".join(selected[: config.max_lines])


def preprocess(
    raw_log: str,
    config: Optional[PreprocessConfig] = None,
) -> str:
    if not raw_log.strip():
        return raw_log
    config = config or PreprocessConfig()

    include = _compile_patterns(config.include_patterns)
    exclude = _compile_patterns(config.exclude_patterns)

    if include or exclude:
        raw_log = filter_by_patterns(raw_log, include, exclude)
    raw_log = sample_lines(raw_log, config)
    return raw_log


def compress_log(text: str) -> bytes:
    return gzip.compress(text.encode("utf-8"))


def decompress_log(data: bytes) -> str:
    return gzip.decompress(data).decode("utf-8")
