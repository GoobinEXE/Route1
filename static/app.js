let currentDrives = [];
let selectedDrive = null;
let lastLogIndex = 0;
let apiReady = false;
let busy = false;
/** Soft busy: spinner/CTA sem bloquear tabs nem Actualizar (leituras / UI leve). */
let softBusy = false;
let logPollTimer = null;
let logPollInFlight = false;
let fetchDrivesInFlight = false;
let activeActionBtn = null;
let activeActionLabel = null;
let appMode = "wizard"; // wizard | advanced | about | dspico
let aboutLoadInFlight = false;
let advancedSection = "prepare"; // prepare | card | apps
let homebrewCatalog = null;
let homebrewCatalogLoadInFlight = false;
let homebrewCategory = "all";

const LOG_DOM_MAX = 500;

const ACTION_MAP = {
  "setup-nand-dump": "setup_nand_dump",
  "setup-unlaunch": "setup_unlaunch",
  "setup-gei": "setup_gei",
  "setup-r4": "setup_r4",
  "setup-dspico": "setup_dspico",
  "setup-hiya": "setup_hiya",
  "organize-roms": "organize_roms",
  backup: "backup",
  "clean-sd": "clean_sd",
  "format-sd": "format_sd",
  "quarantine-dcim": "quarantine_dcim",
  "sd-report": "sd_report",
  "setup-godmode9i": "setup_godmode9i",
  "install-cheats": "install_cheats",
  "install-boxarts": "install_boxarts",
  "copy-nand": "copy_nand_backup",
};

const MODE_STORAGE_KEY = "route_1_kit_mode";
const ADV_SECTION_KEY = "route_1_kit_adv_section";

/** Só considera pronta quando a bridge tem métodos (api começa como {}). */
function getApi() {
  const api = window.pywebview && window.pywebview.api ? window.pywebview.api : null;
  return api && typeof api.get_disks === "function" ? api : null;
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
  if (
    saved === "advanced" ||
    saved === "wizard" ||
    saved === "about" ||
    saved === "dspico"
  ) {
    appMode = saved;
  }
  const savedAdv = sessionStorage.getItem(ADV_SECTION_KEY);
  if (savedAdv === "prepare" || savedAdv === "card" || savedAdv === "apps") {
    advancedSection = savedAdv;
  }
  // Shell v2 gere a navegação; applyAppMode fica como compatibilidade.
  if (!(window.R1K && R1K.shell)) {
    applyAppMode(appMode, { silent: true });
    applyAdvancedSection(advancedSection);
  }

  if (window.R1K && R1K.events) {
    R1K.events.on("log", (p) => {
      if (p && p.message) appendLog(p.message, p.level || "info");
    });
    R1K.events.on("busy", (p) => {
      if (p && typeof p.busy === "boolean") {
        setBusy(!!p.busy);
        if (p.busy) {
          showBusyOpProgress(p);
        }
      }
    });
    R1K.events.on("progress", (p) => {
      updateOpProgress(p);
    });
  }

  try {
    await waitForApi();
    fetchDrives();
    // Fallback curto; push via web_events substitui o polling contínuo.
    startLogPolling();
    setTimeout(() => {
      if (window.R1K && R1K.events && logPollTimer) {
        clearInterval(logPollTimer);
        logPollTimer = null;
      }
    }, 2500);
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
    document.getElementById("dspico-log-container"),
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
  const dspicoLog = document.getElementById("dspico-log-container");
  if (advanced) {
    advanced.innerHTML = '<div class="text-fg-mute">Atividade limpa.</div>';
  }
  if (wizardLog) {
    wizardLog.innerHTML = '<div class="text-fg-mute">Atividade do assistente.</div>';
  }
  if (dspicoLog) {
    dspicoLog.innerHTML = '<div class="text-fg-mute">Atividade limpa.</div>';
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
      "button.btn-primary, button.btn-secondary, button.util-btn, button.action-row, #btn-refresh, .wizard-cta, .mode-tab, .adv-tab, .hb-install-btn"
    )
  );
}

function isHardBusy() {
  return !!busy && !softBusy;
}

function setBusy(isBusy, sourceBtn, options) {
  const soft = !!(options && options.soft);
  const opHint = options && options.op ? String(options.op) : "";
  const labelHint =
    options && options.label ? String(options.label) : "A iniciar…";
  if (isBusy) {
    busy = true;
    softBusy = soft;
  } else {
    busy = false;
    softBusy = false;
  }
  actionButtons().forEach((btn) => {
    const isNavTab =
      btn.classList.contains("mode-tab") || btn.classList.contains("adv-tab");
    const isRefresh = btn.id === "btn-refresh";
    if (!busy) {
      if (isNavTab || isRefresh) {
        btn.disabled = false;
        btn.classList.remove("opacity-50", "pointer-events-none");
        return;
      }
      btn.disabled = false;
      btn.classList.remove("opacity-50", "pointer-events-none");
      return;
    }
    // Soft busy: tabs + Actualizar continuam usáveis (USB MSC / listagens).
    if (softBusy && (isNavTab || isRefresh)) {
      btn.disabled = false;
      btn.classList.remove("opacity-50", "pointer-events-none");
      return;
    }
    btn.disabled = true;
    btn.classList.add("opacity-50", "pointer-events-none");
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

  if (busy) {
    showBusyOpProgress({
      busy: true,
      op: opHint,
      label: labelHint,
    });
  } else {
    hideOpProgress();
  }

  scheduleLogPolling();
  scheduleProgressPolling();
  if (typeof RomExplorer !== "undefined" && RomExplorer.updateRemoveBtn) {
    RomExplorer.updateRemoveBtn();
  }
  if (typeof Wizard !== "undefined" && Wizard.onBusyChange) {
    Wizard.onBusyChange(busy);
  }
}

const _OP_LABELS_PT = {
  dspico_import_games: "Importar jogos",
  dspico_artwork_batch: "Capas DSPico",
  twilight_artwork_batch: "Capas TWiLight",
  generate_dspico_artwork_batch: "Capas DSPico",
  generate_dspico_covers_batch: "Capas DSPico",
  generate_twilight_artwork_batch: "Capas TWiLight",
  dspico_organize: "Organizar DSPico",
  organize_dspico: "Organizar DSPico",
  import_roms: "Importar ROMs",
  organize_roms: "Organizar ROMs",
  setup_dspico: "Preparar DSPico",
  setup_gei: "Kernel GEi",
  setup_r4: "Kernel R4",
  setup_nand_dump: "Passo 1 (dump)",
  setup_unlaunch: "Passo 2 (Unlaunch)",
  setup_hiya: "hiyaCFW",
  setup_godmode9i: "GodMode9i",
  format_sd: "Formatar cartão",
  backup_sd: "Backup do cartão",
  backup_drive: "Backup do cartão",
  backup: "Backup do cartão",
  download: "Descarregar",
  cache_download: "Descarregar",
};

function opLabelPt(op, fallback) {
  const key = String(op || "").trim();
  if (_OP_LABELS_PT[key]) return _OP_LABELS_PT[key];
  if (fallback) return String(fallback);
  return key ? key.replace(/_/g, " ") : "Operação";
}

function formatProgressBytes(n) {
  const v = Number(n);
  if (!Number.isFinite(v) || v < 0) return "";
  if (v < 1024) return `${Math.round(v)} B`;
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} KiB`;
  if (v < 1024 * 1024 * 1024) return `${(v / (1024 * 1024)).toFixed(1)} MiB`;
  return `${(v / (1024 * 1024 * 1024)).toFixed(2)} GiB`;
}

function formatProgressSpeed(payload) {
  const bps = Number(payload && payload.speed_bps);
  if (Number.isFinite(bps) && bps > 0) {
    if (bps < 1024) return `${Math.round(bps)} B/s`;
    if (bps < 1024 * 1024) return `${(bps / 1024).toFixed(1)} KiB/s`;
    return `${(bps / (1024 * 1024)).toFixed(1)} MiB/s`;
  }
  const ips = Number(payload && payload.speed_ips);
  if (Number.isFinite(ips) && ips > 0) {
    if (ips >= 10) return `${Math.round(ips)}/s`;
    return `${ips.toFixed(1)}/s`;
  }
  return "";
}

function formatProgressEta(sec) {
  const s = Math.max(0, Math.round(Number(sec)));
  if (!Number.isFinite(s)) return "";
  if (s < 60) return `~${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m < 60) return r ? `~${m}m ${r}s` : `~${m}m`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm ? `~${h}h ${rm}m` : `~${h}h`;
}

const _CANCELLABLE_ARTWORK_OPS = {
  twilight_artwork_batch: true,
  dspico_artwork_batch: true,
  generate_twilight_artwork_batch: true,
  generate_dspico_artwork_batch: true,
  generate_dspico_covers_batch: true,
  install_boxarts: true,
};

function hideOpProgress() {
  const root = document.getElementById("r1k-op-progress");
  if (!root) return;
  root.classList.add("hidden");
  root.setAttribute("aria-hidden", "true");
  const bar = document.getElementById("r1k-op-progress-bar");
  if (bar) {
    bar.classList.remove("r1k-op-progress-bar--indeterminate");
    bar.style.width = "0%";
  }
  const cancelBtn = document.getElementById("r1k-op-progress-cancel");
  if (cancelBtn) {
    cancelBtn.classList.add("hidden");
    cancelBtn.disabled = false;
  }
}

async function cancelBusyOp() {
  const cancelBtn = document.getElementById("r1k-op-progress-cancel");
  if (cancelBtn) {
    cancelBtn.disabled = true;
    cancelBtn.textContent = "A cancelar…";
  }
  try {
    const api = typeof getApi === "function" ? getApi() : null;
    if (api && typeof api.cancel_op === "function") {
      await api.cancel_op();
    }
  } catch (e) {
    /* best-effort */
  }
}

function showBusyOpProgress(payload) {
  if (!payload || !payload.busy) return;
  updateOpProgress({
    op: payload.op || "",
    label: payload.label || "A iniciar…",
    done: false,
  });
}

function updateOpProgress(payload) {
  if (!payload || typeof payload !== "object") return;
  // Aceitar progresso mesmo se o evento busy ainda não chegou (race push/poll).

  const root = document.getElementById("r1k-op-progress");
  const bar = document.getElementById("r1k-op-progress-bar");
  const titleEl = document.getElementById("r1k-op-progress-title");
  const metricsEl = document.getElementById("r1k-op-progress-metrics");
  const labelEl = document.getElementById("r1k-op-progress-label");
  // Compat: HTML antigo só tinha count; HTML novo tem metrics.
  const countEl = document.getElementById("r1k-op-progress-count");
  if (!root || !bar || !labelEl) return;
  if (!metricsEl && !countEl) return;

  const op = payload.op || "";
  if (titleEl) titleEl.textContent = opLabelPt(op, payload.title);

  const total = Math.max(0, parseInt(payload.total, 10) || 0);
  const current = Math.max(0, parseInt(payload.current, 10) || 0);
  const bytesDone = Math.max(0, parseInt(payload.bytes_done, 10) || 0);
  const bytesTotal = Math.max(0, parseInt(payload.bytes_total, 10) || 0);
  let pct =
    payload.pct != null && payload.pct !== ""
      ? Math.max(0, Math.min(100, parseInt(payload.pct, 10) || 0))
      : null;
  if (pct == null) {
    if (bytesTotal > 0) {
      pct = Math.min(100, Math.round((bytesDone / bytesTotal) * 100));
    } else if (total > 0) {
      pct = Math.min(100, Math.round((current / total) * 100));
    }
  }
  if (payload.done && (total > 0 || bytesTotal > 0)) {
    pct = 100;
  }

  const parts = [];
  if (total > 0) {
    parts.push(`${payload.done ? total : current} / ${total}`);
  }
  if (pct != null) {
    parts.push(`${pct}%`);
  }
  if (bytesDone > 0 || bytesTotal > 0) {
    if (bytesTotal > 0) {
      parts.push(
        `${formatProgressBytes(bytesDone)} / ${formatProgressBytes(bytesTotal)}`
      );
    } else {
      parts.push(formatProgressBytes(bytesDone));
    }
  }
  if (!payload.done) {
    const speed = formatProgressSpeed(payload);
    if (speed) parts.push(speed);
    const eta = formatProgressEta(payload.eta_s);
    if (eta) parts.push(eta);
  } else if (parts.length === 0) {
    parts.push("Concluído");
  }

  const metricsText = parts.join(" · ");
  if (metricsEl) metricsEl.textContent = metricsText;
  if (countEl) countEl.textContent = metricsText || (payload.done ? "Concluído" : "…");
  labelEl.textContent = String(payload.label || (payload.done ? "Concluído" : "A processar…"));

  const determinate = pct != null;
  bar.classList.toggle("r1k-op-progress-bar--indeterminate", !determinate && !payload.done);
  if (determinate || payload.done) {
    bar.style.width = `${payload.done ? 100 : pct}%`;
  } else {
    bar.style.width = "36%";
  }

  const cancelBtn = document.getElementById("r1k-op-progress-cancel");
  if (cancelBtn) {
    const showCancel =
      !payload.done &&
      (payload.cancellable === true ||
        !!_CANCELLABLE_ARTWORK_OPS[op] ||
        !!_CANCELLABLE_ARTWORK_OPS[String(payload.op || "")]);
    cancelBtn.classList.toggle("hidden", !showCancel);
    if (payload.cancelling) {
      cancelBtn.disabled = true;
      cancelBtn.textContent = "A cancelar…";
    } else {
      cancelBtn.disabled = false;
      cancelBtn.textContent = "Cancelar";
    }
  }

  root.classList.remove("hidden");
  root.setAttribute("aria-hidden", "false");
}

let progressPollTimer = null;
let progressPollInFlight = false;

async function pollOpProgressOnce() {
  if (progressPollInFlight || !busy) return;
  const api = typeof getApi === "function" ? getApi() : null;
  if (!api || typeof api.get_op_progress !== "function") return;
  progressPollInFlight = true;
  try {
    const res = await api.get_op_progress();
    if (res && res.success && res.progress && typeof res.progress === "object") {
      updateOpProgress(res.progress);
    }
  } catch (e) {
    /* poll best-effort */
  } finally {
    progressPollInFlight = false;
  }
}

function scheduleProgressPolling() {
  if (progressPollTimer) {
    clearInterval(progressPollTimer);
    progressPollTimer = null;
  }
  if (!busy) return;
  // Fallback quando evaluate_js não chega durante a chamada API (comum no macOS).
  progressPollTimer = setInterval(pollOpProgressOnce, 400);
  pollOpProgressOnce();
}

function syncDriveSelects() {
  const selects = [
    document.getElementById("drive-select"),
    document.getElementById("wizard-drive-select"),
    document.getElementById("dspico-drive-select"),
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

async function fetchDrives(options) {
  const quiet = !!(options && options.quiet);
  // Hard busy bloqueia; soft busy e idle permitem (USB MSC a montar/desmontar).
  if (isHardBusy()) return;
  if (fetchDrivesInFlight) return;
  fetchDrivesInFlight = true;
  const refreshBtn = document.getElementById("btn-refresh");
  const refreshIcon = document.getElementById("refresh-icon");
  if (!quiet && refreshBtn) refreshBtn.classList.add("opacity-50", "pointer-events-none");
  if (!quiet && refreshIcon) refreshIcon.classList.add("spinning");

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
      let pick = keep || null;
      if (!pick && typeof appMode !== "undefined" && appMode === "dspico") {
        pick =
          currentDrives.find((d) => d && d.dspico_likely) ||
          currentDrives[0];
      }
      selectedDrive = pick || currentDrives[0];
      setDriveStatus(true);
      updateDriveBadge();
    }
    syncDriveSelects();
    if (typeof Wizard !== "undefined" && Wizard.onDrivesUpdated) {
      Wizard.onDrivesUpdated();
    }
    if (
      typeof appMode !== "undefined" &&
      appMode === "dspico" &&
      typeof Dspico !== "undefined" &&
      Dspico.onDrivesUpdated
    ) {
      Dspico.onDrivesUpdated();
    }
  } catch (err) {
    if (!quiet) appendLog(`Erro ao buscar unidades: ${err.message}`, "error");
    setDriveStatus(false);
  } finally {
    fetchDrivesInFlight = false;
    if (!isHardBusy() && refreshBtn) {
      refreshBtn.classList.remove("opacity-50", "pointer-events-none");
    }
    if (refreshIcon) refreshIcon.classList.remove("spinning");
  }
}

function onDriveSelected(fromWizard) {
  let selectId = "drive-select";
  if (fromWizard === true || fromWizard === "wizard") {
    selectId = "wizard-drive-select";
  } else if (fromWizard === "dspico") {
    selectId = "dspico-drive-select";
  }
  const select = document.getElementById(selectId);
  if (!select) return;
  const path = select.value;
  selectedDrive = currentDrives.find((d) => d.mount_path === path) || null;
  syncDriveSelects();
  updateDriveBadge();
  setDriveStatus(!!selectedDrive);
  if (window.R1K && R1K.shell) {
    R1K.shell.refreshRoleBadge();
    R1K.shell.updateHomeDrive();
  }
  const view = window.R1K && R1K.shell ? R1K.shell.current() : null;
  if (
    (advancedSection === "card" && appMode === "advanced") ||
    view === "card"
  ) {
    if (typeof RomExplorer !== "undefined" && RomExplorer.refresh) {
      RomExplorer.refresh();
    }
  }
  if (
    (appMode === "dspico" || view === "dspico") &&
    typeof Dspico !== "undefined" &&
    Dspico.refresh
  ) {
    Dspico.refresh();
  }
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

  badges.push({
    badge: document.getElementById("dspico-drive-badge"),
    fs: "dspico-info-fs",
    size: "dspico-info-size",
    free: "dspico-info-free",
  });

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
    "quarantine-dcim": "runAction('quarantine-dcim')",
    "sd-report": "runAction('sd-report')",
    "setup-godmode9i": "runAction('setup-godmode9i')",
    "install-cheats": "runAction('install-cheats')",
    "install-boxarts": "runAction('install-boxarts')",
    "copy-nand": "runAction('copy-nand')",
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
 *   nandPath?: string,   // setup_hiya
 *   updateOnly?: boolean,// setup_hiya
 *   confirmOrganize?: boolean,
 *   layout?: "console"|"franchise"|"both", // organize_roms
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
    const layout = options.layout || "console";
    let layoutLine;
    if (layout === "franchise") {
      layoutLine = "• mover jogos para /roms/<franquia>/ (ex. Pokemon, Mario)\n";
    } else if (layout === "both") {
      layoutLine =
        "• mover jogos para /roms/<consola>/<franquia>/ (ex. /roms/nds/Pokemon/)\n";
    } else {
      layoutLine = "• mover jogos para /roms/<consola>/ (ex. /roms/nds/)\n";
    }
    const conf = confirm(
      "Organizar jogos e apps irá:\n" +
        layoutLine +
        "• criar as pastas de destino em falta\n" +
        "• mover homebrew/apps para /roms/apps/\n" +
        "• sincronizar saves e estados de emuladores (GameYob .sav/.yss, …)\n" +
        "• remover pastas vazias sobrantes\n" +
        "• APAGAR .txt/.jpg/.nfo/.html etc. apenas dentro de /roms/\n\n" +
        "Continuar?"
    );
    if (!conf) return { success: false, error: "cancelled" };
  }

  if (methodName === "organize_dspico" && options.confirmOrganize !== false) {
    const layout = options.layout || "games";
    let layoutLine;
    if (layout === "franchise") {
      layoutLine =
        "• jogos e ROMs retro em Games/<franquia>/ (ex. Pokemon, Mario)\n";
    } else if (layout === "platform") {
      layoutLine =
        "• jogos e ROMs retro em Games/<plataforma>/ (nds, dsi, gb, gba, …)\n";
    } else if (layout === "root") {
      layoutLine =
        "• jogos e ROMs retro soltos na raiz, ao lado de _picoboot.nds\n";
    } else {
      layoutLine = "• jogos e ROMs retro soltos em Games/\n";
    }
    const conf = confirm(
      "Organizar pastas DSPico irá:\n" +
        layoutLine +
        "• apps/homebrew em Games/Apps/\n" +
        "• sincronizar saves junto de cada jogo\n" +
        "• REMOVER pastas/ficheiros de outros sistemas (_nds, MoonShell, hiya, kernels R4/GEi, …)\n" +
        "• manter: _picoboot.nds, _pico/, Games/, Emulators/, _gba/, data/, emunand e snemul.cfg\n" +
        "  (ROMs/ só se tiver BIOS — jogos retro migram para Games/)\n\n" +
        "Esta acção é destrutiva para conteúdo que não seja DSPico.\n\n" +
        "Continuar?"
    );
    if (!conf) return { success: false, error: "cancelled" };
  }

  if (methodName === "install_cheats") {
    const conf = confirm(
      "Instalar cheats procura usrcheat.dat em Downloads/Desktop e copia para:\n" +
        "/_nds/TWiLightMenu/extras/usrcheat.dat\n\n" +
        "Continuar?"
    );
    if (!conf) return { success: false, error: "cancelled" };
  }

  if (methodName === "install_boxarts") {
    const conf = confirm(
      "Instalar capas e ícones irá:\n" +
        "• descarregar capas GameTDB para jogos NDS (por game code)\n" +
        "• descarregar capas e ecrãs de título Libretro para outras consolas\n" +
        "• e/ou importar packs PNG/zip de Downloads/Desktop\n" +
        "• gravar em /_nds/TWiLightMenu/boxart/ e icons/\n\n" +
        "No TWiLight, ative capas/ícones personalizados nas definições.\n\n" +
        "Continuar?"
    );
    if (!conf) return { success: false, error: "cancelled" };
  }

  if (methodName === "copy_nand_backup") {
    const conf = confirm(
      "Copiar dump(s) NAND (DT*/nand.bin) para uma pasta no Desktop?\n" +
        "O ficheiro no cartão NÃO será apagado."
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
    } else if (methodName === "setup_hiya") {
      result = await api.setup_hiya(
        mount,
        options.nandPath || options.nandRelPath || "",
        typeof options.updateOnly === "boolean" ? options.updateOnly : false
      );
    } else if (methodName === "install_homebrew") {
      result = await api.install_homebrew(mount, options.appId || "");
    } else if (methodName === "organize_roms") {
      result = await api.organize_roms(mount, options.layout || "console");
    } else if (methodName === "organize_dspico") {
      result = await api.organize_dspico(mount, options.layout || "games");
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
    if (
      methodName === "organize_roms" ||
      methodName === "import_roms" ||
      methodName === "delete_roms" ||
      methodName === "move_roms"
    ) {
      RomExplorer.refresh();
    }
    if (
      methodName === "setup_dspico" ||
      methodName === "import_dspico_games" ||
      methodName === "delete_dspico_games" ||
      methodName === "move_dspico_games" ||
      methodName === "mkdir_dspico_games" ||
      methodName === "organize_dspico" ||
      methodName === "ensure_dspico_emunand" ||
      methodName === "import_dspico_bios" ||
      methodName === "import_dspico_twl_font" ||
      methodName === "set_dspico_settings"
    ) {
      if (typeof Dspico !== "undefined" && Dspico.refresh) {
        Dspico.refresh();
      }
    }
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
  const organizeLayout =
    document.querySelector('input[name="organize-layout"]:checked')?.value ||
    "console";

  await runMountOp({
    method: methodName,
    hasFacebook,
    sourceBtn,
    confirmOrganize: true,
    layout: organizeLayout,
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
  const typed = prompt(
    `Formatar ${selectedDrive.name} em FAT32 (cluster 32 KB)?\n\n` +
      `Caminho: ${selectedDrive.mount_path}\n` +
      `Capacidade: ${size}\n` +
      `Sistema: ${fs}\n` +
      `Barramento: ${bus}\n\n` +
      `Todos os dados do cartão serão apagados.\n\n` +
      `Escreva FORMATAR para confirmar:`
  );
  if (!typed || String(typed).trim().toUpperCase() !== "FORMATAR") {
    return { success: false, error: "cancelled" };
  }

  return runMountOp({
    method: "format_sd",
    sourceBtn: findActionButton("format-sd"),
  });
}

function applyAppMode(mode, { silent } = {}) {
  // Shell v2: mapear modos legados → vistas.
  if (window.R1K && R1K.shell && typeof R1K.shell.navigate === "function") {
    const map = {
      wizard: "softmod",
      dspico: "dspico",
      about: "settings",
      advanced: "card",
    };
    const view = map[mode] || "home";
    if (mode === "advanced") appMode = "advanced";
    else if (mode === "about") appMode = "about";
    else if (mode === "dspico") appMode = "dspico";
    else appMode = "wizard";
    try {
      sessionStorage.setItem(MODE_STORAGE_KEY, appMode);
    } catch (e) {
      /* ignore */
    }
    R1K.shell.navigate(view, { silent });
    return;
  }

  if (busy && !silent) {
    alert("Aguarde a operação em andamento terminar antes de mudar de modo.");
    return;
  }
  if (mode === "advanced") appMode = "advanced";
  else if (mode === "about") appMode = "about";
  else if (mode === "dspico") appMode = "dspico";
  else appMode = "wizard";
  sessionStorage.setItem(MODE_STORAGE_KEY, appMode);

  const wizard = document.getElementById("view-wizard");
  const advanced = document.getElementById("view-advanced");
  const dspico = document.getElementById("view-dspico");
  const about = document.getElementById("view-about");
  if (wizard) wizard.classList.toggle("hidden", appMode !== "wizard");
  if (advanced) advanced.classList.toggle("hidden", appMode !== "advanced");
  if (dspico) dspico.classList.toggle("hidden", appMode !== "dspico");
  if (about) about.classList.toggle("hidden", appMode !== "about");

  if (appMode === "wizard" && typeof Wizard !== "undefined" && Wizard.render) {
    Wizard.render();
  }
  if (appMode === "about") {
    loadAboutPage();
  }
  if (appMode === "advanced") {
    applyAdvancedSection(advancedSection);
    if (advancedSection === "apps") {
      loadHomebrewCatalog();
    }
  }
  if (appMode === "dspico" && typeof Dspico !== "undefined" && Dspico.enter) {
    Dspico.enter();
  }
}

function setAppMode(mode) {
  applyAppMode(mode);
}

function applyAdvancedSection(section) {
  if (section === "card" || section === "apps") advancedSection = section;
  else advancedSection = "prepare";
  sessionStorage.setItem(ADV_SECTION_KEY, advancedSection);

  const sections = {
    prepare: document.getElementById("adv-section-prepare"),
    card: document.getElementById("adv-section-card"),
    apps: document.getElementById("adv-section-apps"),
  };
  const tabs = {
    prepare: document.getElementById("adv-tab-prepare"),
    card: document.getElementById("adv-tab-card"),
    apps: document.getElementById("adv-tab-apps"),
  };
  for (const key of Object.keys(sections)) {
    const el = sections[key];
    if (el) el.classList.toggle("hidden", advancedSection !== key);
    const tab = tabs[key];
    if (tab) {
      const on = advancedSection === key;
      tab.classList.toggle("adv-tab--active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
    }
  }
}

function setAdvancedSection(section) {
  if (busy) {
    alert("Aguarde a operação em andamento terminar antes de mudar de secção.");
    return;
  }
  applyAdvancedSection(section);
  if (advancedSection === "apps") {
    loadHomebrewCatalog();
  }
  if (advancedSection === "card") {
    RomExplorer.refresh();
  }
}

async function loadHomebrewCatalog() {
  if (homebrewCatalog) {
    renderHomebrewCatalog();
    return;
  }
  if (homebrewCatalogLoadInFlight) return;
  homebrewCatalogLoadInFlight = true;
  const root = document.getElementById("hb-catalog");
  try {
    const api = getApi() || (await waitForApi());
    if (!api || typeof api.get_homebrew_catalog !== "function") {
      if (root) {
        root.innerHTML =
          '<p class="text-[12px] text-danger sm:col-span-2">Catálogo indisponível.</p>';
      }
      return;
    }
    const data = await api.get_homebrew_catalog();
    if (!data || !data.success) {
      if (root) {
        root.innerHTML = `<p class="text-[12px] text-danger sm:col-span-2">${escapeHtml(
          (data && data.error) || "Falha ao carregar catálogo."
        )}</p>`;
      }
      return;
    }
    homebrewCatalog = data;
    const attr = document.getElementById("hb-attribution");
    if (attr && data.attribution) {
      attr.textContent = data.attribution;
      attr.classList.remove("hidden");
    }
    renderHomebrewCategoryChips();
    renderHomebrewCatalog();
  } catch (err) {
    if (root) {
      root.innerHTML = `<p class="text-[12px] text-danger sm:col-span-2">${escapeHtml(
        err.message || "Erro"
      )}</p>`;
    }
  } finally {
    homebrewCatalogLoadInFlight = false;
  }
}

function renderHomebrewCategoryChips() {
  const wrap = document.getElementById("hb-category-chips");
  if (!wrap || !homebrewCatalog) return;
  const cats = Array.isArray(homebrewCatalog.categories)
    ? homebrewCatalog.categories
    : [];
  const items = [{ id: "all", label: "Todos" }].concat(cats);
  wrap.innerHTML = items
    .map((c) => {
      const on = homebrewCategory === c.id;
      return (
        `<button type="button" class="hb-chip${on ? " hb-chip--active" : ""}" ` +
        `data-cat="${escapeHtml(c.id)}" onclick="setHomebrewCategory('${escapeHtml(
          c.id
        )}')">${escapeHtml(c.label)}</button>`
      );
    })
    .join("");
}

function setHomebrewCategory(catId) {
  homebrewCategory = catId || "all";
  renderHomebrewCategoryChips();
  renderHomebrewCatalog();
}

function renderHomebrewCatalog() {
  const root = document.getElementById("hb-catalog");
  if (!root || !homebrewCatalog) return;
  const apps = Array.isArray(homebrewCatalog.apps) ? homebrewCatalog.apps : [];
  const qEl = document.getElementById("hb-search");
  const q = (qEl && qEl.value ? qEl.value : "").trim().toLowerCase();

  const filtered = apps.filter((a) => {
    if (homebrewCategory !== "all" && a.category !== homebrewCategory) {
      return false;
    }
    if (!q) return true;
    const hay = [a.title, a.author, a.description, a.version]
      .map((x) => String(x || "").toLowerCase())
      .join(" ");
    return hay.includes(q);
  });

  if (!filtered.length) {
    root.innerHTML =
      '<p class="text-[12px] text-fg-mute sm:col-span-2">Nenhum app corresponde à pesquisa.</p>';
    return;
  }

  root.innerHTML = filtered
    .map((a) => {
      const warn = a.warn_nand
        ? `<span class="chip chip--warn">NAND</span>`
        : "";
      const ver = a.version
        ? `<span class="text-[11px] text-fg-mute">v${escapeHtml(a.version)}</span>`
        : "";
      const gbUrl = escapeHtml(a.gamebrew_url || "");
      const ghUrl = escapeHtml(a.github_url || "");
      const appId = escapeHtml(a.id || "");
      const notes = Array.isArray(a.setup_notes) ? a.setup_notes : [];
      const notesHtml = notes.length
        ? `<ul class="hb-notes">${notes
            .map((n) => `<li>${escapeHtml(n)}</li>`)
            .join("")}</ul>`
        : "";
      const sources = Array.isArray(a.download_sources) ? a.download_sources : [];
      const sourcesHtml = sources.length
        ? `<ul class="hb-sources" aria-label="Fontes de download">` +
          sources
            .map((s) => {
              const label = escapeHtml((s && s.label) || "Download");
              const openUrl = escapeHtml((s && s.open_url) || "");
              const rawUrl = String((s && s.url) || "");
              const shortUrl =
                rawUrl.length > 64 ? `${rawUrl.slice(0, 61)}…` : rawUrl;
              const openBtn = openUrl
                ? `<button type="button" class="hb-source-link" onclick="openExternal('${openUrl}')">abrir</button>`
                : "";
              return (
                `<li><span class="hb-source-label">${label}</span>` +
                (shortUrl
                  ? ` <code class="hb-source-url" title="${escapeHtml(
                      rawUrl
                    )}">${escapeHtml(shortUrl)}</code>`
                  : "") +
                (openBtn ? ` ${openBtn}` : "") +
                `</li>`
              );
            })
            .join("") +
          `</ul>`
        : "";
      return (
        `<article class="hb-card">` +
        `<div class="hb-card-body">` +
        `<div class="flex items-start justify-between gap-2">` +
        `<h4 class="text-[13px] font-semibold text-fg leading-snug">${escapeHtml(
          a.title || ""
        )}</h4>` +
        `<div class="flex items-center gap-1.5 shrink-0">${warn}${ver}</div>` +
        `</div>` +
        `<p class="text-[12px] text-fg-mute leading-relaxed mt-1">${escapeHtml(
          a.description || ""
        )}</p>` +
        `<p class="text-[11px] text-fg-soft mt-2">${escapeHtml(
          a.author || ""
        )} · ${escapeHtml(a.category_label || a.category || "")}</p>` +
        notesHtml +
        sourcesHtml +
        `</div>` +
        `<div class="hb-card-actions">` +
        `<button type="button" class="btn-primary hb-install-btn !py-1.5 !px-3 text-[11px]" ` +
        `data-app-id="${appId}" data-warn-nand="${a.warn_nand ? "1" : "0"}" ` +
        `data-title="${escapeHtml(a.title || "")}" ` +
        `onclick="installHomebrewApp(this)">Instalar no SD</button>` +
        (ghUrl
          ? `<button type="button" class="btn-ghost !py-1.5 !px-2.5 text-[11px]" onclick="openExternal('${ghUrl}')">GitHub</button>`
          : "") +
        (gbUrl
          ? `<button type="button" class="btn-ghost !py-1.5 !px-2.5 text-[11px]" onclick="openExternal('${gbUrl}')">GameBrew</button>`
          : "") +
        `</div>` +
        `</article>`
      );
    })
    .join("");
}

async function installHomebrewApp(btn) {
  if (!btn || busy) return;
  const appId = btn.getAttribute("data-app-id") || "";
  const title = btn.getAttribute("data-title") || appId;
  const warnNand = btn.getAttribute("data-warn-nand") === "1";
  if (!appId) return;

  let msg =
    `Instalar ${title} no cartão?\n` +
    "Será descarregado (SHA-256), copiado para /roms/apps/ e aplicada a configuração da guia GameBrew (pastas/ficheiros).";
  if (warnNand) {
    msg +=
      "\n\nAVISO: esta ferramenta pode alterar a NAND do DSi. " +
      "Tenha backup da NAND e Unlaunch instalado antes de a usar no console.";
  }
  if (!confirm(msg)) return;

  await runMountOp({
    method: "install_homebrew",
    appId,
    sourceBtn: btn,
  });
}

async function openExternal(url) {
  try {
    const api = getApi();
    if (!api || typeof api.open_external_url !== "function") return;
    await api.open_external_url(url);
  } catch (_e) {
    /* best-effort */
  }
}

function renderAboutPage(data) {
  const root = document.getElementById("about-root");
  if (!root) return;

  const creator = data.creator || {};
  const project = data.project || {};
  const warnings = Array.isArray(data.warnings) ? data.warnings : [];
  const legal = Array.isArray(data.legal) ? data.legal : [];
  const goals = Array.isArray(project.goals) ? project.goals : [];
  const release = data.latest_release || null;

  const goalsHtml = goals
    .map((g) => `<li>${escapeHtml(g)}</li>`)
    .join("");
  const warningsHtml = warnings
    .map(
      (w) =>
        `<li><strong>${escapeHtml(w.title || "")}</strong>${escapeHtml(
          w.text || ""
        )}</li>`
    )
    .join("");
  const legalHtml = legal
    .map((line) => `<li>${escapeHtml(line)}</li>`)
    .join("");

  let patchHtml = "";
  if (release) {
    const parts = [];
    if (release.summary) {
      parts.push(`<p>${escapeHtml(release.summary)}</p>`);
    }
    const sections = Array.isArray(release.sections) ? release.sections : [];
    sections.forEach((sec) => {
      parts.push(`<h4>${escapeHtml(sec.title || "")}</h4>`);
      const items = Array.isArray(sec.items) ? sec.items : [];
      parts.push(
        `<ul class="about-bullets">${items
          .map((it) => `<li>${escapeHtml(it)}</li>`)
          .join("")}</ul>`
      );
    });
    const verLabel = release.date
      ? `${escapeHtml(release.version)} · ${escapeHtml(release.date)}`
      : escapeHtml(release.version || "");
    patchHtml = `
      <section class="panel p-5">
        <div class="flex items-center justify-between gap-3 mb-2">
          <h2 class="section-label">Última versão</h2>
          <span class="chip chip--accent">${verLabel}</span>
        </div>
        <div class="about-patch">${parts.join("") || "<p>Sem notas nesta versão.</p>"}</div>
        <div class="about-links">
          <button type="button" class="btn-ghost !px-2.5 !py-1.5 text-[11px]" data-ext="${escapeHtml(
            data.releases_url || ""
          )}">Releases no GitHub</button>
        </div>
      </section>
    `;
  } else {
    patchHtml = `
      <section class="panel p-5">
        <h2 class="section-label mb-2">Última versão</h2>
        <p class="text-[12px] text-fg-mute">
          App <strong class="text-fg">${escapeHtml(data.version || "")}</strong>.
          ${
            data.changelog_error
              ? "Não foi possível ler o CHANGELOG neste build."
              : "Sem notas de versão disponíveis."
          }
        </p>
      </section>
    `;
  }

  root.innerHTML = `
    <section class="panel p-5">
      <div class="about-hero">
        <img src="assets/logo.svg" alt="" width="48" height="48" class="brand-mark">
        <div class="min-w-0">
          <h2 class="text-[15px] font-semibold text-fg leading-none">${escapeHtml(
            data.app_name || "Route 1 Kit"
          )}</h2>
          <p class="text-[12px] text-fg-mute mt-1.5 leading-relaxed">
            ${escapeHtml(project.tagline || "")}
          </p>
          <div class="about-meta">
            <span class="chip chip--accent">v${escapeHtml(data.version || "")}</span>
            <span class="chip">${escapeHtml(data.license || "GPL-3.0")}</span>
            <span class="chip">${escapeHtml(
              (data.studio && data.studio.name) || "Dark Room"
            )}</span>
          </div>
        </div>
      </div>
      <div class="about-links">
        <button type="button" class="btn-ghost !px-2.5 !py-1.5 text-[11px]" data-ext="${escapeHtml(
          data.repo_url || ""
        )}">Repositório</button>
        <button type="button" class="btn-ghost !px-2.5 !py-1.5 text-[11px]" data-ext="${escapeHtml(
          data.guide_url || ""
        )}">dsi.cfw.guide</button>
        <button type="button" class="btn-ghost !px-2.5 !py-1.5 text-[11px]" data-ext="${escapeHtml(
          data.license_url || ""
        )}">Licença GPL-3.0</button>
      </div>
    </section>

    <div class="about-grid">
      <section class="panel p-5">
        <h2 class="section-label mb-2">Projeto</h2>
        <p class="text-[12px] text-fg-soft leading-relaxed">${escapeHtml(
          project.blurb || ""
        )}</p>
        <ul class="about-bullets">${goalsHtml}</ul>
      </section>

      <section class="panel p-5">
        <h2 class="section-label mb-2">Estúdio</h2>
        <p class="text-[13px] font-semibold text-fg">${escapeHtml(
          (data.studio && data.studio.name) || "Dark Room"
        )}</p>
        <p class="text-[11px] text-fg-mute mt-0.5">${escapeHtml(
          (data.studio && data.studio.role) || "Estúdio"
        )}</p>
        <p class="text-[12px] text-fg-soft leading-relaxed mt-2">${escapeHtml(
          (data.studio && data.studio.blurb) || ""
        )}</p>
        <div class="my-4 h-px" style="background: rgb(var(--c-line))"></div>
        <h2 class="section-label mb-2">Criador</h2>
        <p class="text-[13px] font-semibold text-fg">${escapeHtml(
          creator.name || ""
        )}</p>
        <p class="text-[11px] text-fg-mute mt-0.5">${escapeHtml(
          creator.role || ""
        )}</p>
        <p class="text-[12px] text-fg-soft leading-relaxed mt-2">${escapeHtml(
          creator.blurb || ""
        )}</p>
        <div class="about-links">
          <button type="button" class="btn-ghost !px-2.5 !py-1.5 text-[11px]" data-ext="${escapeHtml(
            creator.url || data.repo_url || ""
          )}">GitHub · ${escapeHtml(creator.name || "GoobinEXE")}</button>
        </div>
      </section>
    </div>

    <section class="panel p-5">
      <h2 class="section-label mb-2">Avisos essenciais</h2>
      <ul class="about-list">${warningsHtml}</ul>
    </section>

    <section class="panel p-5">
      <h2 class="section-label mb-2">Legal (resumo)</h2>
      <ul class="about-list">${legalHtml}</ul>
    </section>

    ${patchHtml}
  `;

  root.querySelectorAll("[data-ext]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const url = btn.getAttribute("data-ext");
      if (url) openExternal(url);
    });
  });
}

async function loadAboutPage() {
  const root = document.getElementById("about-root");
  if (!root) return;
  if (aboutLoadInFlight) return;
  aboutLoadInFlight = true;
  try {
    const api = getApi();
    if (!api || typeof api.get_about !== "function") {
      root.innerHTML =
        '<p class="text-[12px] text-danger">API Sobre indisponível.</p>';
      return;
    }
    const data = await api.get_about();
    if (!data || data.success === false) {
      root.innerHTML = `<p class="text-[12px] text-danger">${escapeHtml(
        (data && data.error) || "Falha ao carregar Sobre."
      )}</p>`;
      return;
    }
    renderAboutPage(data);
  } catch (err) {
    root.innerHTML = `<p class="text-[12px] text-danger">${escapeHtml(
      err && err.message ? err.message : "Falha ao carregar Sobre."
    )}</p>`;
  } finally {
    aboutLoadInFlight = false;
  }
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
