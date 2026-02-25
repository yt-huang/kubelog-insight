const $ = (id) => document.getElementById(id);

const elements = {
  componentType: $("componentType"),
  componentName: $("componentName"),
  namespace: $("namespace"),
  timeRange: $("timeRange"),
  tailLines: $("tailLines"),
  analysisMode: $("analysisMode"),
  kubeconfig: $("kubeconfig"),
  llmProvider: $("llmProvider"),
  model: $("model"),
  apiBaseUrl: $("apiBaseUrl"),
  apiKey: $("apiKey"),
  maxIterations: $("maxIterations"),
  btnAnalyze: $("btnAnalyze"),
  btnExportResultPdf: $("btnExportResultPdf"),
  btnExportProjectPdf: $("btnExportProjectPdf"),
  btnRefreshHistory: $("btnRefreshHistory"),
  status: $("status"),
  resultBox: $("resultBox"),
  historyList: $("historyList"),
};

let lastResult = null;

function setStatus(text) {
  elements.status.textContent = text;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderResult(text) {
  const escaped = escapeHtml(text || "");
  const highlighted = escaped.replace(
    /(exception|error|panic|fatal|nullpointer|npe|oom|out of memory|failed|critical|warning)/gi,
    '<span class="hl">$1</span>'
  );
  elements.resultBox.innerHTML = highlighted || "无结果";
}

async function callApi(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function collectPayload() {
  return {
    component_type: elements.componentType.value,
    component_name: elements.componentName.value.trim(),
    namespace: elements.namespace.value.trim(),
    time_range: elements.timeRange.value.trim(),
    tail_lines: Number(elements.tailLines.value || 5000),
    analysis_mode: elements.analysisMode.value,
    kubeconfig: elements.kubeconfig.value.trim(),
    llm_provider: elements.llmProvider.value,
    model: elements.model.value.trim(),
    api_base_url: elements.apiBaseUrl.value.trim(),
    api_key: elements.apiKey.value.trim(),
    max_iterations: Number(elements.maxIterations.value || 50),
  };
}

async function loadHistory() {
  try {
    const data = await callApi("/api/history");
    const list = data.entries || [];
    elements.historyList.innerHTML = "";
    if (!list.length) {
      elements.historyList.innerHTML = "<div class='history-meta'>暂无历史记录</div>";
      return;
    }
    list.forEach((item) => {
      const row = document.createElement("div");
      row.className = "history-item";
      row.innerHTML = `
        <div>
          <div><strong>${item.component_type}/${item.component_name}</strong> (${item.namespace})</div>
          <div class="history-meta">${item.timestamp || ""}</div>
        </div>
        <div class="history-actions">
          <button class="btn ghost" data-id="${item.id}" data-action="view">查看</button>
          <button class="btn ghost" data-id="${item.id}" data-action="delete">删除</button>
        </div>
      `;
      elements.historyList.appendChild(row);
    });
  } catch (error) {
    setStatus(`历史加载失败: ${error.message}`);
  }
}

async function handleHistoryClick(event) {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  const id = target.dataset.id;
  const action = target.dataset.action;
  if (!id || !action) return;

  if (action === "view") {
    try {
      const data = await callApi(`/api/history/${id}`);
      const entry = data.entry;
      renderResult(entry.analysis_text || entry.error_message || "");
      setStatus(`已加载历史记录: ${id}`);
    } catch (error) {
      setStatus(`加载失败: ${error.message}`);
    }
    return;
  }

  if (action === "delete") {
    if (!window.confirm("确定删除该记录？")) return;
    try {
      await callApi(`/api/history/${id}`, { method: "DELETE" });
      setStatus(`已删除: ${id}`);
      await loadHistory();
    } catch (error) {
      setStatus(`删除失败: ${error.message}`);
    }
  }
}

async function analyze() {
  const payload = collectPayload();
  if (!payload.component_name) {
    setStatus("请先填写组件名称");
    return;
  }
  elements.btnAnalyze.disabled = true;
  setStatus("分析中，请稍候...");
  renderResult("执行中...");
  try {
    const data = await callApi("/api/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    lastResult = data.result;
    if (!lastResult.success) {
      renderResult(`分析失败: ${lastResult.error_message || "未知错误"}`);
      setStatus("执行完成（失败）");
      return;
    }
    renderResult(lastResult.analysis_text || "无结果");
    setStatus("执行完成");
    await loadHistory();
  } catch (error) {
    renderResult(`调用失败: ${error.message}`);
    setStatus("执行失败");
  } finally {
    elements.btnAnalyze.disabled = false;
  }
}

async function exportProjectPdf() {
  setStatus("正在导出项目 PDF...");
  try {
    const data = await callApi("/api/export/project-pdf", { method: "POST", body: "{}" });
    setStatus(`项目 PDF 已保存: ${data.path}`);
  } catch (error) {
    setStatus(`导出失败: ${error.message}`);
  }
}

async function exportResultPdf() {
  if (!lastResult) {
    setStatus("请先执行一次分析");
    return;
  }
  setStatus("正在导出分析 PDF...");
  try {
    const data = await callApi("/api/export/analysis-pdf", {
      method: "POST",
      body: JSON.stringify({ result: lastResult }),
    });
    setStatus(`分析 PDF 已保存: ${data.path}`);
  } catch (error) {
    setStatus(`导出失败: ${error.message}`);
  }
}

elements.btnAnalyze.addEventListener("click", analyze);
elements.btnRefreshHistory.addEventListener("click", loadHistory);
elements.btnExportProjectPdf.addEventListener("click", exportProjectPdf);
elements.btnExportResultPdf.addEventListener("click", exportResultPdf);
elements.historyList.addEventListener("click", handleHistoryClick);

loadHistory();

