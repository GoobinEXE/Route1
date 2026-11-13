/**
 * Partes do DSPico que não vivem em dspico.js: temas do Pico Launcher
 * (DSPico → Launcher) e apps USB oficiais do LNH (DSPico → Emuladores e apps).
 * Depende de waitForApi / escapeHtml / setBusy / selectedDrive (app.js).
 */
(function () {
  function drivePath() {
    return (typeof selectedDrive !== "undefined" && selectedDrive && selectedDrive.mount_path) || "";
  }

  async function writeOp(fn) {
    const path = drivePath();
    if (!path) {
      alert("Selecione o microSD do DSPico na barra de cima.");
      return null;
    }
    try {
      if (typeof setBusy === "function") setBusy(true);
      const api = await waitForApi();
      return await fn(api, path);
    } catch (e) {
      alert(String((e && e.message) || e));
      return null;
    } finally {
      if (typeof setBusy === "function") setBusy(false);
    }
  }

  // ------------------------------------------------------------------ Temas Pico Launcher

  let themesHost = null;

  async function renderPicoThemes(el) {
    if (el) themesHost = el;
    if (!themesHost) return;
    const host = themesHost;
    host.innerHTML = `<section class="panel p-5"><p class="text-[12px] text-fg-mute">A carregar temas do launcher…</p></section>`;
    let res;
    try {
      const api = await waitForApi();
      res = await api.list_pico_themes(drivePath());
    } catch (e) {
      res = { success: false, error: (e && e.message) || String(e) };
    }
    if (!res || !res.success) {
      host.innerHTML = `<section class="panel p-5"><p class="text-[12px] text-danger">${escapeHtml(
        (res && res.error) || "Falha ao ler /_pico/themes."
      )}</p></section>`;
      return;
    }
    const active = res.active || res.active_theme || "";
    const rows = (res.themes || [])
      .map((t) => {
        const folder = String(t.folder || "");
        const on = folder === active;
        return `<div class="flex items-center justify-between gap-2 p-2 rounded border border-line">
          <div class="min-w-0"><div class="text-[13px] font-medium truncate">${escapeHtml(t.name || folder)}</div>
          <div class="text-[11px] text-fg-mute">${escapeHtml(`${t.type || "?"} · ${t.author || "?"}`)}</div></div>
          ${
            on
              ? '<span class="text-[11px] text-ok">em uso</span>'
              : `<button type="button" class="btn-ghost !text-[11px]" data-theme-folder="${escapeHtml(folder)}">Usar</button>`
          }
        </div>`;
      })
      .join("");
    host.innerHTML = `
      <section class="panel p-5 space-y-3">
        <div>
          <h3 class="section-label">Temas do launcher</h3>
          <p class="text-[12px] text-fg-mute mt-1">Pastas em <code>/_pico/themes/</code>. O tema em uso fica em <code>settings.json</code>.</p>
        </div>
        <div class="space-y-2">${rows || '<p class="text-[12px] text-fg-mute">Nenhum tema no cartão.</p>'}</div>
        <div class="flex flex-wrap gap-2">
          <button type="button" class="btn-primary" id="pico-theme-import">Importar tema…</button>
          <button type="button" class="btn-ghost" id="pico-theme-material">Criar tema material</button>
        </div>
      </section>`;
    host.querySelectorAll("[data-theme-folder]").forEach((btn) => {
      btn.onclick = async () => {
        const r = await writeOp((api, path) => api.set_pico_theme(path, btn.getAttribute("data-theme-folder")));
        if (r && r.success) renderPicoThemes();
        else if (r) alert(r.error || "Falha ao trocar o tema.");
      };
    });
    host.querySelector("#pico-theme-import").onclick = async () => {
      const api = await waitForApi();
      const pick = await api.pick_folder();
      if (!pick || pick.cancelled || !pick.path) return;
      const r = await writeOp((a, path) => a.import_pico_theme(path, pick.path));
      if (r) alert(r.message || r.error || "Concluído");
      renderPicoThemes();
    };
    host.querySelector("#pico-theme-material").onclick = async () => {
      const name = prompt("Nome do tema material:", "Route Pico");
      if (!name) return;
      const r = await writeOp((api, path) => api.create_pico_material_theme(path, name, 109, 139, 255, true));
      if (r) alert(r.message || r.error || "Concluído");
      renderPicoThemes();
    };
  }

  // ------------------------------------------------------------------ Apps USB (LNH)

  function renderUsbApps(el) {
    if (!el) return;
    el.innerHTML = `
      <section class="panel p-5 space-y-2">
        <h3 class="section-label">Apps USB oficiais (LNH)</h3>
        <p class="text-[12px] text-fg-mute">mass-storage, usb-speaker, usb-video e usb-microphone de <code>dspico-usb-examples</code>.
        Depois de um reset com USB ligado pode ser preciso desligar e voltar a ligar o console (bug conhecido do firmware).</p>
        <button type="button" class="btn-primary" id="dspico-usb-install">Instalar apps USB no cartão</button>
        <div id="dspico-usb-msg" class="text-[12px] text-fg-mute" role="status"></div>
      </section>`;
    el.querySelector("#dspico-usb-install").onclick = async () => {
      const r = await writeOp((api, path) => api.install_dspico_usb_apps(path));
      const msg = el.querySelector("#dspico-usb-msg");
      if (r && msg) msg.textContent = r.message || r.error || "";
    };
  }

  window.R1K = window.R1K || {};
  window.R1K.launcherExtras = { renderPicoThemes, renderUsbApps };
})();
