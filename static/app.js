let currentDrives = [];
let selectedDrive = null;
let lastLogIndex = 0;
let apiReady = false;
let busy = false;
let logPollTimer = null;
let logPollInFlight = false;
let activeActionBtn = null;
let activeActionLabel = null;
let appMode = "wizard"; // wizard | advanced

const LOG_DOM_MAX = 500;

const ACTION_MAP = {
  "setup-nand-dump": "setup_nand_dump",
  "setup-unlaunch": "setup_unlaunch",
  "setup-gei": "setup_gei",
  "setup-r4": "setup_r4",
  "organize-roms": "organize_roms",
  backup: "backup",
  "clean-sd": "clean_sd",
  "format-sd": "format_sd",
  "quarantine-dcim": "quarantine_dcim",
};

const MODE_STORAGE_KEY = "route_1_kit_mode";

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
  const saved = sessionStorage.getItem(MODE_STORAGE_KEY);
  if (saved === "advanced" || saved === "wizard") {
    appMode = saved;
  }
  applyAppMode(appMode, { silent: true });

  try {
    await waitForApi();
    fetchDrives();
    startLogPolling();
    if (typeof Wizard !== "undefined" && Wizard.init) {
      Wizard.init();
    }
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
  const containers = [
    document.getElementById("log-container"),
    document.getElementById("wizard-log"),
  ].filter(Boolean);

  const clean = stripLogDecorators(msg);
  const time = new Date().toLocaleTimeString();
  let color = "text-fg-soft";
  if (type === "success" || msg.includes("✅") || msg.includes("🎉")) color = "text-ok";
  if (type === "error" || msg.includes("❌") || /erro/i.test(msg)) color = "text-danger";
  if (type === "warn" || msg.includes("⚠️")) color = "text-warn";
  if (msg.includes("===")) color = "text-accent-fg font-medium mt-2";

  containers.forEach((container) => {
    const div = document.createElement("div");
    div.className = `${color} leading-relaxed`;
    div.innerHTML = `<span class="text-fg-mute/70 mr-2">[${time}]</span>${escapeHtml(clean)}`;
    container.appendChild(div);
    while (container.childElementCount > LOG_DOM_MAX) {
      container.removeChild(container.firstElementChild);
    }
    container.scrollTop = container.scrollHeight;
  });
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function clearLogs() {
  const advanced = document.getElementById("log-container");
  const wizardLog = document.getElementById("wizard-log");
  if (advanced) {
    advanced.innerHTML = '<div class="text-fg-mute">Atividade limpa.</div>';
  }
  if (wizardLog) {
    wizardLog.innerHTML = '<div class="text-fg-mute">Atividade do assistente.</div>';
  }
  lastLogIndex = 0;
  try {
    const api = getApi();
    if (api) await api.clear_logs();
  } catch (e) {}
}

function setDriveStatus(hasDrive) {
  document.querySelectorAll("#drive-status-dot, #wizard-drive-status-dot").forEach((dot) => {
    dot.classList.toggle("status-dot--live", !!hasDrive);
    dot.classList.toggle("status-dot--idle", !hasDrive);
  });
}

function actionButtons() {
  return Array.from(
    document.querySelectorAll(
      "button.btn-primary, button.btn-secondary, button.util-btn, #btn-refresh, .wizard-cta, .mode-tab"
    )
  );
}

function setBusy(isBusy, sourceBtn) {
  busy = !!isBusy;
  actionButtons().forEach((btn) => {
    if (btn.classList.contains("mode-tab") && !busy) {
      btn.disabled = false;
      btn.classList.remove("opacity-50", "pointer-events-none");
      return;
    }
    btn.disabled = busy;
    btn.classList.toggle("opacity-50", busy);
    btn.classList.toggle("pointer-events-none", busy);
  });

  if (busy && sourceBtn) {
    activeActionBtn = sourceBtn;
    activeActionLabel = sourceBtn.innerHTML;
    sourceBtn.innerHTML =
      '<span class="inline-flex items-center gap-2"><span class="spinning-dot" aria-hidden="true"></span> Em andamento…</span>';
  } else if (!busy && activeActionBtn && activeActionLabel != null) {
    activeActionBtn.innerHTML = activeActionLabel;
    activeActionBtn = null;
    activeActionLabel = null;
  }

  scheduleLogPolling();
  if (typeof Wizard !== "undefined" && Wizard.onBusyChange) {
    Wizard.onBusyChange(busy);
  }
}

function syncDriveSelects() {
  const selects = [
    document.getElementById("drive-select"),
    document.getElementById("wizard-drive-select"),
  ].filter(Boolean);

  selects.forEach((select) => {
    const previous = select.value || (selectedDrive ? selectedDrive.mount_path : null);
    select.innerHTML = "";
    if (currentDrives.length === 0) {
      select.innerHTML =
        '<option value="">Nenhum cartão SD ou disco externo detectado</option>';
    } else {
      currentDrives.forEach((d) => {
        const opt = document.createElement("option");
        opt.value = d.mount_path;
        opt.textContent = `${d.name} · ${d.total_size_gb} GB · ${d.fs_type}`;
        select.appendChild(opt);
      });
      const keep = currentDrives.find((d) => d.mount_path === previous);
      const pick = keep || selectedDrive || currentDrives[0];
      if (pick) select.value = pick.mount_path;
    }
  });
}

async function fetchDrives() {
  if (busy) return;
  const refreshBtn = document.getElementById("btn-refresh");
  const refreshIcon = document.getElementById("refresh-icon");
  if (refreshBtn) refreshBtn.classList.add("opacity-50", "pointer-events-none");
  if (refreshIcon) refreshIcon.classList.add("spinning");

  try {
    const api = getApi() || (await waitForApi());
    const data = await api.get_disks();
    currentDrives = data.drives || [];

    const previous = selectedDrive ? selectedDrive.mount_path : null;
    if (currentDrives.length === 0) {
      selectedDrive = null;
      setDriveStatus(false);
      document.getElementById("drive-info-badge")?.classList.add("hidden");
      document.getElementById("wizard-drive-badge")?.classList.add("hidden");
    } else {
      const keep = currentDrives.find((d) => d.mount_path === previous);
      selectedDrive = keep || currentDrives[0];
      setDriveStatus(true);
      updateDriveBadge();
    }
    syncDriveSelects();
    if (typeof Wizard !== "undefined" && Wizard.onDrivesUpdated) {
      Wizard.onDrivesUpdated();
    }
  } catch (err) {
    appendLog(`Erro ao buscar unidades: ${err.message}`, "error");
    setDriveStatus(false);
  } finally {
    if (!busy && refreshBtn) {
      refreshBtn.classList.remove("opacity-50", "pointer-events-none");
    }
    if (refreshIcon) refreshIcon.classList.remove("spinning");
  }
}

function onDriveSelected(fromWizard) {
  const select = document.getElementById(
    fromWizard ? "wizard-drive-select" : "drive-select"
  );
  if (!select) return;
  const path = select.value;
  selectedDrive = currentDrives.find((d) => d.mount_path === path) || null;
  syncDriveSelects();
  updateDriveBadge();
  setDriveStatus(!!selectedDrive);
  if (typeof Wizard !== "undefined" && Wizard.onDriveSelected) {
    Wizard.onDriveSelected();
  }
}

function updateDriveBadge() {
  const badges = [
    {
      badge: document.getElementById("drive-info-badge"),
      fs: "info-fs",
      size: "info-size",
      free: "info-free",
    },
    {
      badge: document.getElementById("wizard-drive-badge"),
      fs: "wizard-info-fs",
      size: "wizard-info-size",
      free: "wizard-info-free",
    },
  ];

  badges.forEach(({ badge, fs, size, free }) => {
    if (!badge) return;
    if (!selectedDrive) {
      badge.classList.add("hidden");
      return;
    }
    badge.classList.remove("hidden");
    const fsEl = document.getElementById(fs);
    const sizeEl = document.getElementById(size);
    const freeEl = document.getElementById(free);
    if (fsEl) fsEl.textContent = selectedDrive.fs_type;
    if (sizeEl) sizeEl.textContent = `${selectedDrive.total_size_gb} GB`;
    if (freeEl) freeEl.textContent = `${selectedDrive.free_size_gb} GB`;
  });
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
  return Array.from(document.querySelectorAll("#view-advanced button")).find((b) =>
    (b.getAttribute("onclick") || "").includes(needle)
  );
}

/**
 * Operação partilhada pelo painel avançado e pelo assistente.
 * options: {
 *   method: 'setup_nand_dump' | ...,
 *   hasFacebook?: boolean,
 *   sourceDir?: string,  // setup_r4
 *   confirmOrganize?: boolean,
 *   sourceBtn?: HTMLElement,
 *   mountPath?: string,
 * }
 */
async function runMountOp(options = {}) {
  if (busy) {
    appendLog("Aguarde a operação em andamento terminar.", "warn");
    return { success: false, error: "busy" };
  }

  const methodName = options.method;
  if (!methodName) {
    appendLog("Ação desconhecida.", "error");
    return { success: false, error: "unknown" };
  }

  const mount =
    options.mountPath || (selectedDrive && selectedDrive.mount_path) || null;
  if (!mount) {
    alert("Selecione um cartão SD primeiro.");
    return { success: false, error: "no_drive" };
  }

  if (methodName === "organize_roms" && options.confirmOrganize !== false) {
    const conf = confirm(
      "Organizar jogos irá:\n" +
        "• mover ROMs para /roms/<plataforma>/\n" +
        "• sincronizar saves\n" +
        "• APAGAR arquivos .txt/.jpg/.nfo/.html etc. apenas dentro de /roms/\n\n" +
        "Continuar?"
    );
    if (!conf) return { success: false, error: "cancelled" };
  }

  const driveName = selectedDrive?.name || mount;
  appendLog(`Iniciando: ${methodName} em ${driveName}…`, "info");
  setBusy(true, options.sourceBtn || null);

  try {
    const api = getApi() || (await waitForApi());
    let result;
    if (methodName === "setup_nand_dump") {
      const hasFacebook =
        typeof options.hasFacebook === "boolean" ? options.hasFacebook : true;
      result = await api.setup_nand_dump(mount, hasFacebook);
    } else if (methodName === "setup_r4") {
      result = await api.setup_r4(mount, options.sourceDir || "");
    } else {
      result = await api[methodName](mount);
    }

    if (result && result.success) {
      appendLog(result.message || "Operação concluída.", "success");
    } else {
      appendLog(`Erro: ${(result && result.error) || "resposta vazia da API"}`, "error");
    }
    return result || { success: false, error: "resposta vazia da API" };
  } catch (err) {
    appendLog(`Falha na operação: ${err.message}`, "error");
    return { success: false, error: err.message };
  } finally {
    setBusy(false);
    fetchDrives();
  }
}

async function runAction(endpoint) {
  const methodName = ACTION_MAP[endpoint];
  if (!methodName) {
    appendLog(`Ação desconhecida: ${endpoint}`, "error");
    return;
  }

  const cameraVersion =
    document.querySelector('input[name="camera-version"]:checked')?.value ||
    "facebook";
  const hasFacebook = cameraVersion === "facebook";
  const sourceBtn = findActionButton(endpoint);

  await runMountOp({
    method: methodName,
    hasFacebook,
    sourceBtn,
    confirmOrganize: true,
  });
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
    return { success: false, error: "busy" };
  }
  if (!selectedDrive) {
    alert("Selecione um cartão para formatar.");
    return { success: false, error: "no_drive" };
  }
  const bus = selectedDrive.bus_protocol || "USB/SD";
  const size =
    selectedDrive.total_size_gb != null ? `${selectedDrive.total_size_gb} GB` : "?";
  const fs = selectedDrive.fs_type || "?";
  const conf = confirm(
    `Formatar ${selectedDrive.name} em FAT32?\n\n` +
      `Caminho: ${selectedDrive.mount_path}\n` +
      `Capacidade: ${size}\n` +
      `Sistema: ${fs}\n` +
      `Barramento: ${bus}\n\n` +
      `Todos os dados do cartão serão apagados.`
  );
  if (!conf) return { success: false, error: "cancelled" };

  return runMountOp({
    method: "format_sd",
    sourceBtn: findActionButton("format-sd"),
  });
}

function applyAppMode(mode, { silent } = {}) {
  if (busy && !silent) {
    alert("Aguarde a operação em andamento terminar antes de mudar de modo.");
    return;
  }
  appMode = mode === "advanced" ? "advanced" : "wizard";
  sessionStorage.setItem(MODE_STORAGE_KEY, appMode);

  const wizard = document.getElementById("view-wizard");
  const advanced = document.getElementById("view-advanced");
  const btnWizard = document.getElementById("mode-wizard");
  const btnAdvanced = document.getElementById("mode-advanced");
  const btnId = document.getElementById("btn-id-guide");

  if (wizard) wizard.classList.toggle("hidden", appMode !== "wizard");
  if (advanced) advanced.classList.toggle("hidden", appMode !== "advanced");
  if (btnWizard) btnWizard.classList.toggle("mode-tab--active", appMode === "wizard");
  if (btnAdvanced) {
    btnAdvanced.classList.toggle("mode-tab--active", appMode === "advanced");
  }
  if (btnId) btnId.classList.toggle("hidden", appMode !== "advanced");

  if (appMode === "wizard" && typeof Wizard !== "undefined" && Wizard.render) {
    Wizard.render();
  }
}

function setAppMode(mode) {
  applyAppMode(mode);
}

async function pollLogsOnce() {
  if (logPollInFlight) return;
  logPollInFlight = true;
  try {
    const api = getApi();
    if (!api) return;
    const since = lastLogIndex;
    const data = await api.get_logs(since);
    if (data.logs && data.logs.length > 0) {
      data.logs.forEach((l) => appendLog(l));
    }
    if (typeof data.next_index === "number") {
      lastLogIndex = Math.max(lastLogIndex, data.next_index);
    }
  } catch (e) {
    /* polling best-effort */
  } finally {
    logPollInFlight = false;
  }
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
