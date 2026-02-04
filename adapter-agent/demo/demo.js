async function loadJson(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function loadJsonFromFile(file) {
  return new Promise((resolve) => {
    if (!file) return resolve(null);
    const reader = new FileReader();
    reader.onload = () => {
      try {
        resolve(JSON.parse(reader.result));
      } catch {
        resolve(null);
      }
    };
    reader.onerror = () => resolve(null);
    reader.readAsText(file);
  });
}

function formatKV(target, data) {
  const entries = Object.entries(data || {});
  target.innerHTML = entries
    .map(([k, v]) => `<div>${k}</div><div>${v}</div>`)
    .join("\n");
}

function stringify(obj) {
  return obj ? JSON.stringify(obj, null, 2) : "(no data)";
}

function buildDiff(before, after) {
  if (!before || !after) return "(need both before/after)";
  const keys = ["ok", "message", "details.detect_health", "details.proxy_health"];
  const lines = [];
  for (const key of keys) {
    const b = getPath(before, key);
    const a = getPath(after, key);
    lines.push(`${key}: ${b}  ->  ${a}`);
  }
  return lines.join("\n");
}

function getPath(obj, path) {
  return path.split(".").reduce((acc, key) => (acc ? acc[key] : undefined), obj);
}

function statusChip(before, after) {
  if (before === after) return `<span class="chip ok">unchanged</span>`;
  if (after === true || after === "pass") return `<span class="chip ok">improved</span>`;
  if (after === false || after === "fail") return `<span class="chip bad">regressed</span>`;
  return `<span class="chip warn">changed</span>`;
}

function renderCompare(target, before, after) {
  const rows = [
    ["ok", getPath(before, "ok"), getPath(after, "ok")],
    ["config_written", getPath(before, "generated.config_written"), getPath(after, "generated.config_written")],
    ["detect_health", getPath(before, "details.detect_health"), getPath(after, "details.detect_health")],
    ["proxy_health", getPath(before, "details.proxy_health"), getPath(after, "details.proxy_health")],
    ["overall_risk", getPath(before, "details.detection_result.overall_risk_level"), getPath(after, "details.detection_result.overall_risk_level")],
  ];

  target.innerHTML = rows
    .map(([label, b, a]) => {
      const chip = statusChip(b, a);
      return `\n      <div class="row">\n        <div class="label">${label}</div>\n        <div>${b ?? "-"}</div>\n        <div>${a ?? "-"}</div>\n        <div>${chip}</div>\n      </div>`;
    })
    .join("\n");
}

function extractSummary(data) {
  if (!data) return null;
  return {
    ok: data.ok,
    tool: data.selected_tool,
    config_written: data.generated?.config_written,
    detect_health: data.details?.detect_health,
    proxy_health: data.details?.proxy_health,
    overall_risk: data.details?.detection_result?.overall_risk_level ?? data.details?.detection_result?.status_code,
    anonymized_text: data.details?.detection_result?.result?.data?.anonymized_text,
    suggest_action: data.details?.detection_result?.suggest_action,
  };
}

function renderPanel(prefix, data) {
  const summary = extractSummary(data);
  const kvTarget = document.getElementById(`${prefix}Summary`);
  const callout = document.getElementById(`${prefix}Callout`);
  const pill = document.getElementById(`${prefix}Pill`);
  const banner = document.getElementById(`${prefix}Banner`);

  if (!summary) {
    kvTarget.innerHTML = "<div>状态</div><div>-</div>";
    callout.textContent = "未加载数据。请上传 JSON 或输入文件路径。";
    pill.textContent = "No Data";
    return;
  }

  const riskValue = summary.overall_risk ?? "-";
  const riskClass = riskValue === "high_risk" ? "high" : "low";
  const riskDisplay = `<span class=\"risk-badge ${riskClass}\">${riskValue}</span>`;

  formatKV(kvTarget, {
    ok: summary.ok ?? "-",
    selected_tool: summary.tool ?? "-",
    config_written: summary.config_written ?? "-",
    detect_health: summary.detect_health ?? "-",
    proxy_health: summary.proxy_health ?? "-",
    overall_risk: riskDisplay,
  });

  if (summary.anonymized_text) {
    callout.textContent = `脱敏结果：${summary.anonymized_text}`;
  } else if (summary.suggest_action) {
    callout.textContent = `建议动作：${summary.suggest_action}`;
  } else {
    callout.textContent = "暂无检测样例结果。";
  }

  const ok = summary.ok === true;
  pill.textContent = ok ? "Deployment OK" : "Not Ready";
  if (ok) pill.classList.add("ok");

  if (banner) {
    const blocked = summary.suggest_action === "block" || summary.overall_risk === "high_risk";
    banner.textContent = blocked ? "已拦截" : "未拦截";
    banner.style.display = prefix === "after" ? "inline-block" : "none";
    banner.style.background = blocked ? "#ffe8e8" : "#e8f5e9";
    banner.style.color = blocked ? "var(--bad)" : "var(--ok)";
    banner.style.borderColor = blocked ? "#f5b5b5" : "#c6e6d3";
  }
}

async function render() {
  const beforeFile = document.getElementById("beforeFile").value.trim();
  const afterFile = document.getElementById("afterFile").value.trim();
  const beforeUpload = document.getElementById("beforeUpload").files[0];
  const afterUpload = document.getElementById("afterUpload").files[0];

  const before = beforeUpload ? await loadJsonFromFile(beforeUpload) : await loadJson(beforeFile);
  const after = afterUpload ? await loadJsonFromFile(afterUpload) : await loadJson(afterFile);

  const badge = document.getElementById("statusBadge");
  badge.textContent = after && after.ok ? "Deployment OK" : "No Data";
  badge.style.background = after && after.ok ? "#e8f5e9" : "#fff5e5";

  renderPanel("before", before);
  renderPanel("after", after);

  document.getElementById("beforeDetection").textContent = stringify(before?.details?.detection_result);
  document.getElementById("afterDetection").textContent = stringify(after?.details?.detection_result);

  document.getElementById("diff").textContent = buildDiff(before, after);
  renderCompare(document.getElementById("compare"), before, after);
}

render();
document.getElementById("reload").addEventListener("click", render);

document.querySelectorAll("[data-toggle]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.getAttribute("data-toggle");
    const target = document.getElementById(id);
    if (target) target.classList.toggle("collapsed");
  });
});

document.getElementById("scenario").addEventListener("change", (event) => {
  const value = event.target.value;
  const beforeInput = document.getElementById("beforeFile");
  const afterInput = document.getElementById("afterFile");
  const beforeUpload = document.getElementById("beforeUpload");
  const afterUpload = document.getElementById("afterUpload");

  if (value === "danger") {
    beforeInput.value = "demo_result_before_danger.json";
    afterInput.value = "demo_result_after_danger.json";
  } else {
    beforeInput.value = "demo_result_before.json";
    afterInput.value = "demo_result_after.json";
  }

  beforeUpload.value = "";
  afterUpload.value = "";
  render();
});
