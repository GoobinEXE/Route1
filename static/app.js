let currentDrives = [];
let selectedDrive = null;
let lastLogIndex = 0;
let apiReady = false;
let busy = false;
let logPollTimer = null;
let activeActionBtn = null;
let activeActionLabel = null;

const ACTION_MAP = {
  "setup-nand-dump": "setup_nand_dump",
  "setup-unlaunch": "setup_unlaunch",
  "setup-gei": "setup_gei",
  "organize-roms": "organize_roms",
  backup: "backup",
  "clean-sd": "clean_sd",
  "format-sd": "format_sd",
};

function getApi() {
  return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
}

function waitForApi(timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const existing = getApi();
    if (existing) {
      apiReady = true;
      resolve(existing);
      return;
    }

    const started = Date.now();
    const onReady = () => {
      const api = getApi();
      if (api) {
        apiReady = true;
        window.removeEventListener("pywebviewready", onReady);
        resolve(api);
      }
    };
    window.addEventListener("pywebviewready", onReady);

    const poll = setInterval(() => {
      const api = getApi();
      if (api) {
        clearInterval(poll);
        window.removeEventListener("pywebviewready", onReady);
        apiReady = true;
        resolve(api);
      } else if (Date.now() - started > timeoutMs) {
        clearInterval(poll);
        window.removeEventListener("pywebviewready", onReady);
        reject(new Error("API do app não ficou disponível a tempo."));
      }
    }, 50);
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    await waitForApi();
    fetchDrives();
    startLogPolling();
  } catch (err) {
    appendLog(`Falha ao iniciar bridge: ${err.message}`, "error");
  }
});

function stripLogDecorators(msg) {
  return String(msg)
    .replace(/[✅❌⚠️🎉💾🎮ℹ️🔍]/g, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function appendLog(msg, type = "info") {
  const container = document.getElementById("log-container");
  const div = document.createElement("div");
  const clean = stripLogDecorators(msg);

  const time = new Date().toLocaleTimeString();
  let color = "text-ink-soft";
  if (type === "success" || msg.includes("✅") || msg.includes("🎉")) color = "text-ok";
  if (type === "error" || msg.includes("❌") || /erro/i.test(msg)) color = "text-danger";
  if (type === "warn" || msg.includes("⚠️")) color = "text-warn";
  if (msg.includes("===")) color = "text-brand-deep font-medium mt-2";

  div.className = `${color} leading-relaxed`;
  div.innerHTML = `<span class="text-ink-mute/70 mr-2">[${time}]</span>${escapeHtml(clean)}`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function clearLogs() {
  const container = document.getElementById("log-container");
  container.innerHTML = '<div class="text-ink-mute">Atividade limpa.</div>';
  lastLogIndex = 0;
  try {
    const api = getApi();
    if (api) await api.clear_logs();
  } catch (e) {}
}

function setDriveStatus(hasDrive) {
  const dot = document.getElementById("drive-status-dot");
  if (!dot) return;
  dot.classList.toggle("status-dot--live", !!hasDrive);
  dot.classList.toggle("status-dot--idle", !hasDrive);
}

function actionButtons() {
  return Array.from(
    document.querySelectorAll(
      "button.btn-primary, button.btn-secondary, button.util-btn, #btn-refresh"
    )
  );
}

function setBusy(isBusy, sourceBtn) {
  busy = !!isBusy;
  actionButtons().forEach((btn) => {
    btn.disabled = busy;
    btn.classList.toggle("opacity-50", busy);
    btn.classList.toggle("pointer-events-none", busy);
  });

  if (busy && sourceBtn) {
    activeActionBtn = sourceBtn;
    activeActionLabel = sourceBtn.innerHTML;
    sourceBtn.innerHTML = '<span class="inline-flex items-center gap-2"><span class="spinning-dot" aria-hidden="true"></span> Em andamento…</span>';
  } else if (!busy && activeActionBtn && activeActionLabel != null) {
    activeActionBtn.innerHTML = activeActionLabel;
    activeActionBtn = null;
    activeActionLabel = null;
  }

  scheduleLogPolling();
}

async function fetchDrives() {
  if (busy) return;
  const select = document.getElementById("drive-select");
  const refreshBtn = document.getElementById("btn-refresh");
  const refreshIcon = document.getElementById("refresh-icon");
  refreshBtn.classList.add("opacity-50", "pointer-events-none");
  if (refreshIcon) refreshIcon.classList.add("spinning");

  try {
    const api = getApi() || (await waitForApi());
    const data = await api.get_disks();
    currentDrives = data.drives || [];

    const previous = selectedDrive ? selectedDrive.mount_path : null;
    select.innerHTML = "";
    if (currentDrives.length === 0) {
      select.innerHTML = '<option value="">Nenhum cartão SD ou disco externo detectado</option>';
      document.getElementById("drive-info-badge").classList.add("hidden");
      selectedDrive = null;
      setDriveStatus(false);
    } else {
      currentDrives.forEach((d) => {
        const opt = document.createElement("option");
        opt.value = d.mount_path;
        opt.textContent = `${d.name} · ${d.total_size_gb} GB · ${d.fs_type}`;
        select.appendChild(opt);
      });
      const keep = currentDrives.find((d) => d.mount_path === previous);
      selectedDrive = keep || currentDrives[0];
      select.value = selectedDrive.mount_path;
      updateDriveBadge();
      setDriveStatus(true);
    }
  } catch (err) {
    appendLog(`Erro ao buscar unidades: ${err.message}`, "error");
    setDriveStatus(false);
  } finally {
    if (!busy) {
      refreshBtn.classList.remove("opacity-50", "pointer-events-none");
    }
    if (refreshIcon) refreshIcon.classList.remove("spinning");
  }
}

function onDriveSelected() {
  const select = document.getElementById("drive-select");
  const path = select.value;
  selectedDrive = currentDrives.find((d) => d.mount_path === path) || null;
  updateDriveBadge();
  setDriveStatus(!!selectedDrive);
}

function updateDriveBadge() {
  const badge = document.getElementById("drive-info-badge");
  if (!selectedDrive) {
    badge.classList.add("hidden");
    return;
  }
  badge.classList.remove("hidden");
  document.getElementById("info-fs").textContent = selectedDrive.fs_type;
  document.getElementById("info-size").textContent = `${selectedDrive.total_size_gb} GB`;
  document.getElementById("info-free").textContent = `${selectedDrive.free_size_gb} GB`;
}

function findActionButton(endpoint) {
  const map = {
    "setup-nand-dump": "runAction('setup-nand-dump')",
    "setup-unlaunch": "runAction('setup-unlaunch')",
    "setup-gei": "runAction('setup-gei')",
    "organize-roms": "runAction('organize-roms')",
    backup: "runAction('backup')",
    "clean-sd": "runAction('clean-sd')",
    "format-sd": "confirmFormat()",
  };
  const needle = map[endpoint];
  if (!needle) return null;
  return Array.from(document.querySelectorAll("button")).find(
    (b) => (b.getAttribute("onclick") || "").includes(needle)
  );
}

async function runAction(endpoint) {
  if (busy) {
    appendLog("Aguarde a operação em andamento terminar.", "warn");
    return;
  }
  if (!selectedDrive) {
    alert("Selecione um cartão SD primeiro.");
    return;
  }

  const methodName = ACTION_MAP[endpoint];
  if (!methodName) {
    appendLog(`Ação desconhecida: ${endpoint}`, "error");
    return;
  }

  const cameraVersion = document.querySelector('input[name="camera-version"]:checked')?.value || "facebook";
  const hasFacebook = cameraVersion === "facebook";
  const sourceBtn = findActionButton(endpoint);

  appendLog(`Iniciando: ${endpoint} em ${selectedDrive.name}…`, "info");
  setBusy(true, sourceBtn);

  try {
    const api = getApi() || (await waitForApi());
    let result;
    if (methodName === "setup_nand_dump") {
      result = await api.setup_nand_dump(selectedDrive.mount_path, hasFacebook);
    } else {
      result = await api[methodName](selectedDrive.mount_path);
    }

    if (result.success) {
      appendLog(result.message || "Operação concluída.", "success");
    } else {
      appendLog(`Erro: ${result.error}`, "error");
    }
  } catch (err) {
    appendLog(`Falha na operação: ${err.message}`, "error");
  } finally {
    setBusy(false);
    fetchDrives();
  }
}

function toggleIdGuide() {
  const panel = document.getElementById("id-guide-panel");
  const chevron = document.getElementById("id-guide-chevron");
  if (!panel) return;
  const opening = panel.classList.contains("hidden");
  panel.classList.toggle("hidden", !opening);
  if (chevron) chevron.classList.toggle("rotate-180", opening);
  if (opening) panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function confirmFormat() {
  if (busy) {
    appendLog("Aguarde a operação em andamento terminar.", "warn");
    return;
  }
  if (!selectedDrive) {
    alert("Selecione um cartão para formatar.");
    return;
  }
  const conf = confirm(
    `Formatar ${selectedDrive.name} (${selectedDrive.mount_path}) em FAT32?\n\nTodos os dados do cartão serão apagados.`
  );
  if (!conf) return;

  runAction("format-sd");
}

async function pollLogsOnce() {
  try {
    const api = getApi();
    if (!api) return;
    const data = await api.get_logs(lastLogIndex);
    if (data.logs && data.logs.length > 0) {
      data.logs.forEach((l) => appendLog(l));
      lastLogIndex = data.next_index;
    }
  } catch (e) {}
}

function scheduleLogPolling() {
  if (logPollTimer) {
    clearInterval(logPollTimer);
    logPollTimer = null;
  }
  const interval = busy ? 1000 : 4000;
  logPollTimer = setInterval(pollLogsOnce, interval);
}

function startLogPolling() {
  pollLogsOnce();
  scheduleLogPolling();
}
