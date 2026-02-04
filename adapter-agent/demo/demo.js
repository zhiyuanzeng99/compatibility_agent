async function loadJson(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
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

async function render() {
  const beforeFile = document.getElementById("beforeFile").value.trim();
  const afterFile = document.getElementById("afterFile").value.trim();
  const before = await loadJson(beforeFile);
  const after = await loadJson(afterFile);

  const badge = document.getElementById("statusBadge");
  badge.textContent = after && after.ok ? "Deployment OK" : "No Data";
  badge.style.background = after && after.ok ? "#e8f5e9" : "#fff5e5";

  const summary = document.getElementById("summary");
  formatKV(summary, {
    ok: after?.ok ?? "-",
    message: after?.message ?? "-",
    selected_tool: after?.selected_tool ?? "-",
    config_written: after?.generated?.config_written ?? "-",
    backup_path: after?.generated?.backup_path ?? "-",
  });

  const health = document.getElementById("health");
  formatKV(health, {
    detect_health: after?.details?.detect_health ?? "-",
    proxy_health: after?.details?.proxy_health ?? "-",
    detection_status: after?.details?.detection_result?.overall_risk_level ?? after?.details?.detection_result?.status_code ?? "-",
  });

  document.getElementById("detection").textContent = stringify(after?.details?.detection_result);
  document.getElementById("diff").textContent = buildDiff(before, after);
}

render();
document.getElementById("reload").addEventListener("click", render);
