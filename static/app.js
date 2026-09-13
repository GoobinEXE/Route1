let currentDrives = [];
let selectedDrive = null;
let lastLogIndex = 0;
let apiReady = false;
let busy = false;
let logPollTimer = null;
let logPollInFlight = false;
let activeActionBtn = null;
let activeActionLabel = null;
let appMode = "wizard"; // wizard | advanced | about
let aboutLoadInFlight = false;

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
  "sd-report": "sd_report",
  "setup-godmode9i": "setup_godmode9i",
  "install-cheats": "install_cheats",
  "install-boxarts": "install_boxarts",
  "copy-nand": "copy_nand_backup",
};

const MODE_STORAGE_KEY = "route_1_kit_mode";

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
  if (saved === "advanced" || saved === "wizard" || saved === "about") {
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
    if (appMode === "about") {
      loadAboutPage();
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
      "Organizar jogos e apps irá:\n" +
        "• mover jogos para /roms/nds/ (lista flat, acesso rápido)\n" +
        "• mover homebrew/apps para /roms/apps/\n" +
        "• sincronizar saves\n" +
        "• APAGAR .txt/.jpg/.nfo/.html etc. apenas dentro de /roms/\n\n" +
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
      "Instalar boxarts irá:\n" +
        "• descarregar capas do GameTDB (requer internet)\n" +
        "• e/ou importar packs PNG/zip de Downloads/Desktop\n" +
        "• gravar em /_nds/TWiLightMenu/boxart/\n\n" +
        "No TWiLight, ative a visualização de capas nas definições.\n\n" +
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
    `Formatar ${selectedDrive.name} em FAT32 (cluster 32 KB)?\n\n` +
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
  if (mode === "advanced") appMode = "advanced";
  else if (mode === "about") appMode = "about";
  else appMode = "wizard";
  sessionStorage.setItem(MODE_STORAGE_KEY, appMode);

  const wizard = document.getElementById("view-wizard");
  const advanced = document.getElementById("view-advanced");
  const about = document.getElementById("view-about");
  const btnWizard = document.getElementById("mode-wizard");
  const btnAdvanced = document.getElementById("mode-advanced");
  const btnAbout = document.getElementById("mode-about");
  const btnId = document.getElementById("btn-id-guide");
  const btnRefresh = document.getElementById("btn-refresh");

  if (wizard) wizard.classList.toggle("hidden", appMode !== "wizard");
  if (advanced) advanced.classList.toggle("hidden", appMode !== "advanced");
  if (about) about.classList.toggle("hidden", appMode !== "about");
  if (btnWizard) {
    const on = appMode === "wizard";
    btnWizard.classList.toggle("mode-tab--active", on);
    btnWizard.setAttribute("aria-selected", on ? "true" : "false");
  }
  if (btnAdvanced) {
    const on = appMode === "advanced";
    btnAdvanced.classList.toggle("mode-tab--active", on);
    btnAdvanced.setAttribute("aria-selected", on ? "true" : "false");
  }
  if (btnAbout) {
    const on = appMode === "about";
    btnAbout.classList.toggle("mode-tab--active", on);
    btnAbout.setAttribute("aria-selected", on ? "true" : "false");
  }
  if (btnId) btnId.classList.toggle("hidden", appMode !== "advanced");
  if (btnRefresh) btnRefresh.classList.toggle("hidden", appMode === "about");

  if (appMode === "wizard" && typeof Wizard !== "undefined" && Wizard.render) {
    Wizard.render();
  }
  if (appMode === "about") {
    loadAboutPage();
  }
}

function setAppMode(mode) {
  applyAppMode(mode);
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
