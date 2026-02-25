const $ = (id) => document.getElementById(id);

const elements = {
  timeRange: $("timeRange"),
  tailLines: $("tailLines"),
  analysisMode: $("analysisMode"),
  kubeconfig: $("kubeconfig"),
  kubeconfigFile: $("kubeconfigFile"),
  btnUploadKubeconfig: $("btnUploadKubeconfig"),
  btnTestKubeconfig: $("btnTestKubeconfig"),
  kubeconfigState: $("kubeconfigState"),
  llmProvider: $("llmProvider"),
  model: $("model"),
  apiBaseUrl: $("apiBaseUrl"),
  apiKey: $("apiKey"),
  maxIterations: $("maxIterations"),
  btnAnalyze: $("btnAnalyze"),
  btnAddComponent: $("btnAddComponent"),
  btnExportResultPdf: $("btnExportResultPdf"),
  btnExportProjectPdf: $("btnExportProjectPdf"),
  btnRefreshHistory: $("btnRefreshHistory"),
  status: $("status"),
  resultBox: $("resultBox"),
  historyList: $("historyList"),
  componentRows: $("componentRows"),
  componentRowTemplate: $("componentRowTemplate"),
};

let lastResult = null;
let cachedNamespaces = [];

function initDefaults() {
  elements.llmProvider.value = "openai";
  if (!elements.model.value) elements.model.value = "deepseek-chat";
  if (!elements.apiBaseUrl.value) elements.apiBaseUrl.value = "https://api.deepseek.com";
}

function setStatus(text) {
  elements.status.textContent = text;
}

function setKubeconfigState(connected, text) {
  elements.kubeconfigState.textContent = text;
  elements.kubeconfigState.classList.toggle("ok", Boolean(connected));
}

function escapeHtml(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
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
  if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function fetchNamespaces() {
  const kubeconfig = elements.kubeconfig.value.trim();
  const url = `/api/k8s/namespaces?kubeconfig=${encodeURIComponent(kubeconfig)}`;
  const data = await callApi(url);
  cachedNamespaces = data.items || [];
  return cachedNamespaces;
}

async function fetchComponents(kind, namespace) {
  const kubeconfig = elements.kubeconfig.value.trim();
  const url = `/api/k8s/components?component_type=${encodeURIComponent(kind)}&namespace=${encodeURIComponent(
    namespace
  )}&kubeconfig=${encodeURIComponent(kubeconfig)}`;
  const data = await callApi(url);
  return data.items || [];
}

function getAllRows() {
  return Array.from(elements.componentRows.querySelectorAll(".component-row"));
}

async function refreshRowComponents(row) {
  const typeSelect = row.querySelector(".componentType");
  const nsSelect = row.querySelector(".namespaceSelect");
  const nameSelect = row.querySelector(".componentNameSelect");
  if (!cachedNamespaces.length) {
    nameSelect.innerHTML = `<option value="">请先连接 kubeconfig 并加载命名空间</option>`;
    return;
  }
  if (!nsSelect.value) {
    nameSelect.innerHTML = `<option value="">请先选择命名空间</option>`;
    return;
  }
  const items = await fetchComponents(typeSelect.value, nsSelect.value);
  nameSelect.innerHTML = "";
  if (!items.length) {
    nameSelect.innerHTML = `<option value="">无组件</option>`;
    return;
  }
  items.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    nameSelect.appendChild(opt);
  });
}

function fillNamespaceOptions(row) {
  const nsSelect = row.querySelector(".namespaceSelect");
  nsSelect.innerHTML = "";
  const namespaces = cachedNamespaces.length ? cachedNamespaces : ["default"];
  namespaces.forEach((ns) => {
    const opt = document.createElement("option");
    opt.value = ns;
    opt.textContent = ns;
    nsSelect.appendChild(opt);
  });
}

async function addComponentRow(defaults = {}) {
  const node = elements.componentRowTemplate.content.cloneNode(true);
  const row = node.querySelector(".component-row");
  const typeSelect = row.querySelector(".componentType");
  const nsSelect = row.querySelector(".namespaceSelect");
  const removeBtn = row.querySelector(".btnRemoveComponent");

  if (defaults.component_type) typeSelect.value = defaults.component_type;
  fillNamespaceOptions(row);
  if (defaults.namespace) nsSelect.value = defaults.namespace;

  typeSelect.addEventListener("change", () => refreshRowComponents(row).catch((e) => setStatus(e.message)));
  nsSelect.addEventListener("change", () => refreshRowComponents(row).catch((e) => setStatus(e.message)));
  removeBtn.addEventListener("click", () => {
    if (getAllRows().length <= 1) {
      setStatus("至少保留一个组件");
      return;
    }
    row.remove();
  });

  elements.componentRows.appendChild(row);
  await refreshRowComponents(row);
  if (defaults.component_name) {
    row.querySelector(".componentNameSelect").value = defaults.component_name;
  }
}

function collectPayload() {
  const components = getAllRows().map((row) => ({
    component_type: row.querySelector(".componentType").value,
    namespace: row.querySelector(".namespaceSelect").value,
    component_name: row.querySelector(".componentNameSelect").value,
  }));
  return {
    components,
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

async function loadK8sSelections() {
  try {
    const namespaces = await fetchNamespaces();
    setStatus(`kubeconfig 连接成功，发现命名空间 ${namespaces.length} 个`);
    setKubeconfigState(true, `连接成功（命名空间 ${namespaces.length} 个）`);
    const rows = getAllRows();
    for (const row of rows) {
      fillNamespaceOptions(row);
      await refreshRowComponents(row);
    }
  } catch (error) {
    setStatus(`连接/加载失败: ${error.message}`);
    setKubeconfigState(false, "连接失败");
  }
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
      renderResult(data.entry.analysis_text || data.entry.error_message || "");
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
  const invalid = payload.components.find((c) => !c.component_name);
  if (invalid) {
    setStatus("请先选择每个组件的名称");
    return;
  }
  elements.btnAnalyze.disabled = true;
  setStatus("分析中，请稍候...");
  renderResult("执行中...");
  try {
    const data = await callApi("/api/analyze-multi", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    lastResult = {
      success: data.summary.success > 0,
      analysis_text: data.merged_text,
      component_type: "multiple",
      component_name: `${data.summary.total} components`,
      namespace: "mixed",
      time_range: payload.time_range,
      raw_log_preview: "",
      preprocessed_log_preview: "",
      error_message: data.summary.failed ? `${data.summary.failed} 个组件失败` : "",
    };
    renderResult(data.merged_text || "无结果");
    setStatus(`执行完成：成功 ${data.summary.success} / 失败 ${data.summary.failed}`);
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

async function uploadKubeconfig() {
  const file = elements.kubeconfigFile.files?.[0];
  if (!file) {
    setStatus("请先选择 kubeconfig 文件");
    return;
  }
  const form = new FormData();
  form.append("file", file);
  elements.btnUploadKubeconfig.disabled = true;
  setStatus("正在上传 kubeconfig...");
  try {
    const response = await fetch("/api/upload/kubeconfig", { method: "POST", body: form });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
    elements.kubeconfig.value = data.path || "";
    setStatus(`kubeconfig 已上传: ${data.path}`);
    await testKubeconfig();
  } catch (error) {
    setStatus(`上传失败: ${error.message}`);
    setKubeconfigState(false, "上传失败");
  } finally {
    elements.btnUploadKubeconfig.disabled = false;
  }
}

async function testKubeconfig() {
  const kubeconfig = elements.kubeconfig.value.trim();
  if (!kubeconfig) {
    setStatus("请先填写或上传 kubeconfig 路径");
    setKubeconfigState(false, "未连接");
    return;
  }
  if (kubeconfig === "/") {
    setStatus("kubeconfig 路径不能是目录 /，请填写具体文件路径");
    setKubeconfigState(false, "路径无效");
    return;
  }
  elements.btnTestKubeconfig.disabled = true;
  setStatus("正在测试 kubeconfig 连接...");
  try {
    const data = await callApi(`/api/k8s/test-connection?kubeconfig=${encodeURIComponent(kubeconfig)}`);
    setKubeconfigState(true, `连接成功（命名空间 ${data.namespace_count || 0} 个）`);
    setStatus(data.message || "kubeconfig 连接成功");
    await loadK8sSelections();
  } catch (error) {
    setKubeconfigState(false, "连接失败");
    setStatus(`连接失败: ${error.message}`);
  } finally {
    elements.btnTestKubeconfig.disabled = false;
  }
}

elements.btnAnalyze.addEventListener("click", analyze);
elements.btnRefreshHistory.addEventListener("click", loadHistory);
elements.btnExportProjectPdf.addEventListener("click", exportProjectPdf);
elements.btnExportResultPdf.addEventListener("click", exportResultPdf);
elements.btnUploadKubeconfig.addEventListener("click", uploadKubeconfig);
elements.btnTestKubeconfig.addEventListener("click", testKubeconfig);
elements.btnAddComponent.addEventListener("click", () => addComponentRow().catch((e) => setStatus(e.message)));
elements.historyList.addEventListener("click", handleHistoryClick);
elements.kubeconfig.addEventListener("change", () => {
  setKubeconfigState(false, "待测试");
});

async function bootstrap() {
  initDefaults();
  setKubeconfigState(false, "未连接");
  await addComponentRow({ component_type: "deployment", namespace: "default" });
  await loadHistory();
}

bootstrap().catch((err) => setStatus(err.message));

