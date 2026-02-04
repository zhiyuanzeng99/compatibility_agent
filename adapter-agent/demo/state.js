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

async function render() {
  const stateFile = document.getElementById("stateFile").value.trim();
  const stateUpload = document.getElementById("stateUpload").files[0];

  const state = stateUpload ? await loadJsonFromFile(stateUpload) : await loadJson(stateFile);

  const badge = document.getElementById("statusBadge");
  badge.textContent = state ? "Loaded" : "No Data";
  badge.style.background = state ? "#e8f5e9" : "#fff5e5";

  formatKV(document.getElementById("decision"), {
    target_app: state?.decision?.target_app ?? "-",
    tool: state?.decision?.tool ?? "-",
    reasons: state?.decision?.reasons?.join(", ") ?? "-",
  });

  formatKV(document.getElementById("deploy"), {
    ok: state?.v0?.ok ?? "-",
    config_written: state?.v0?.config_written ?? "-",
    backup_path: state?.v0?.backup_path ?? "-",
  });

  formatKV(document.getElementById("verify"), {
    detect_health: state?.v0?.detect_health ?? "-",
    proxy_health: state?.v0?.proxy_health ?? "-",
    overall_risk: state?.v0?.detection_result?.overall_risk_level ?? "-",
    suggest_action: state?.v0?.detection_result?.suggest_action ?? "-",
  });

  document.getElementById("sample").textContent = stringify(state?.v0?.detection_result);
  document.getElementById("raw").textContent = stringify(state);
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
