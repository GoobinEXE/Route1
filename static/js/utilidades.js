/**
 * Área Utilidades — Emuladores, Apps, Capas/Ícones, Temas.
 */
(function () {
  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function panel() {
    return document.getElementById("utilidades-panel");
  }

  function drivePath() {
    if (typeof selectedDrive !== "undefined" && selectedDrive && selectedDrive.mount_path) {
      return selectedDrive.mount_path;
    }
    return "";
  }

  function ensure() {
    const appsHost = document.getElementById("util-apps-host");
    if (appsHost) appsHost.classList.add("hidden");
  }

  async function open(cat) {
    const el = panel();
    if (!el) return;
    document.querySelectorAll(".util-card").forEach((c) => {
      c.classList.toggle("ring-1", c.getAttribute("data-util") === cat);
    });
    const appsHost = document.getElementById("util-apps-host");
    if (appsHost) appsHost.classList.toggle("hidden", cat !== "apps");

    if (cat === "emulators") {
      el.innerHTML =
        '<p class="text-[13px] text-fg-mute mb-3">Catálogo oficial de emuladores Pico. Também disponível em DSPico → Emuladores.</p>' +
        '<button type="button" class="btn-primary" onclick="R1K.shell.navigate(\'dspico\'); setTimeout(()=>Dspico&&Dspico.setSection&&Dspico.setSection(\'emulators\'),50)">Abrir emuladores DSPico</button>';
      return;
    }
    if (cat === "apps") {
      el.innerHTML =
        '<p class="text-[13px] text-fg-mute">Homebrew do catálogo abaixo. Bloco DSPico USB (mass-storage, speaker, video, microfone) requer API <code>install_dspico_usb_apps</code>.</p>';
      if (typeof loadHomebrewCatalog === "function") loadHomebrewCatalog();
      renderUsbBlock(el);
      return;
    }
    if (cat === "artwork") {
      el.innerHTML = `
        <p class="text-[13px] text-fg-mute mb-3">Dois fluxos isolados — nunca misturam pastas DSPico e TWiLight.</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="rounded-lg border border-line p-3 space-y-2">
            <div class="text-[13px] font-semibold text-fg">DSPico (Pico Launcher)</div>
            <p class="text-[11px] text-fg-mute">BMP em <code>/_pico/covers</code> e <code>icons</code>. Jogos em <code>Games/</code>.</p>
            <button type="button" class="btn-primary" onclick="R1K.utilidades.batchDspicoArt()">Buscar capas e ícones DSPico</button>
            <button type="button" class="btn-ghost !text-[11px]" onclick="R1K.shell.navigate('dspico'); setTimeout(()=>Dspico&&Dspico.setSection&&Dspico.setSection('games'),50)">Abrir Jogos DSPico</button>
          </div>
          <div class="rounded-lg border border-line p-3 space-y-2">
            <div class="text-[13px] font-semibold text-fg">TWiLight Menu++</div>
            <p class="text-[11px] text-fg-mute">PNG em <code>/_nds/TWiLightMenu/boxart</code> e <code>icons</code>. Jogos em <code>/roms/</code>.</p>
            <button type="button" class="btn-primary" onclick="R1K.utilidades.batchTwilightArt()">Buscar capas e ícones TWiLight</button>
            <button type="button" class="btn-ghost !text-[11px]" onclick="runMountOp && runMountOp({method:'install_boxarts'})">Instalar capas (pack local + lote clássico)</button>
          </div>
        </div>
        <div id="util-art-result" class="text-[12px] text-fg-mute mt-3"></div>
        <div id="util-art-missing" class="hidden space-y-2 mt-3"></div>`;
      return;
    }
    if (cat === "themes") {
      await renderThemes(el);
      return;
    }
    el.innerHTML = '<p class="text-[13px] text-fg-mute">Escolha uma categoria.</p>';
  }

  async function renderUsbBlock(el) {
    const box = document.createElement("div");
    box.className = "mt-4 p-3 rounded-lg border border-line space-y-2";
    box.innerHTML = `
      <div class="text-[13px] font-semibold">DSPico USB (LNH)</div>
      <p class="text-[12px] text-fg-mute">Exemplos oficiais: mass-storage, usb-speaker, usb-video, usb-microphone.
      Após reset + USB novamente pode ser necessário ciclo de energia (bug conhecido do firmware).</p>
      <button type="button" class="btn-primary" id="util-usb-install">Instalar apps USB no cartão</button>
      <div id="util-usb-msg" class="text-[12px] text-fg-mute"></div>`;
    el.appendChild(box);
    const btn = box.querySelector("#util-usb-install");
    btn.onclick = async () => {
      const path = drivePath();
      if (!path) return alert("Seleccione um cartão.");
      try {
        const api = await waitForApi();
        if (!api.install_dspico_usb_apps) {
          document.getElementById("util-usb-msg").textContent =
            "API ainda não ligada — disponível após Fase 4.";
          return;
        }
        setBusy && setBusy(true);
        const res = await api.install_dspico_usb_apps(path);
        document.getElementById("util-usb-msg").textContent =
          (res && (res.message || res.error)) || JSON.stringify(res);
      } catch (e) {
        alert(String(e.message || e));
      } finally {
        setBusy && setBusy(false);
      }
    };
  }

  async function renderThemes(el) {
    el.innerHTML = '<p class="text-[12px] text-fg-mute">A carregar temas…</p>';
    const path = drivePath();
    try {
      const api = await waitForApi();
      if (!api.list_pico_themes) {
        el.innerHTML =
          '<p class="text-[13px] text-fg-mute">Temas Pico Launcher: API <code>list_pico_themes</code> será ligada na Fase 4. Pasta: <code>/_pico/themes/</code>.</p>' +
          `<div class="mt-3 flex flex-wrap gap-2">
            <button type="button" class="btn-ghost" onclick="R1K.shell.navigate('dspico'); setTimeout(()=>Dspico&&Dspico.setSection&&Dspico.setSection('settings'),50)">Definições do launcher</button>
          </div>`;
        return;
      }
      const res = await api.list_pico_themes(path || "");
      if (!res || !res.success) {
        el.innerHTML = `<p class="text-[12px] text-danger">${escapeHtml((res && res.error) || "Erro")}</p>`;
        return;
      }
      const themes = res.themes || [];
      const active = res.active || res.active_theme || "";
      let html = `<p class="text-[12px] text-fg-mute mb-2">Activo: <strong>${escapeHtml(active || "—")}</strong></p>`;
      html += '<div class="space-y-2">';
      for (const t of themes) {
        const folder = escapeHtml(t.folder || "");
        const name = escapeHtml(t.name || folder);
        const meta = escapeHtml(`${t.type || "?"} · ${t.author || "?"}`);
        html += `<div class="flex items-center justify-between gap-2 p-2 rounded border border-line">
          <div><div class="text-[13px] font-medium">${name}</div><div class="text-[11px] text-fg-mute">${meta}</div></div>
          <button type="button" class="btn-ghost !text-[11px]" onclick="R1K.utilidades.setTheme('${folder}')">Activar</button>
        </div>`;
      }
      html += "</div>";
      html += `<div class="mt-4 flex flex-wrap gap-2">
        <button type="button" class="btn-primary" onclick="R1K.utilidades.importTheme()">Importar tema</button>
        <button type="button" class="btn-ghost" onclick="R1K.utilidades.createMaterial()">Criar material</button>
      </div>`;
      el.innerHTML = html;
    } catch (e) {
      el.innerHTML = `<p class="text-[12px] text-danger">${escapeHtml(e.message || e)}</p>`;
    }
  }

  async function setTheme(folder) {
    const path = drivePath();
    if (!path) return alert("Seleccione um cartão.");
    const api = await waitForApi();
    const res = await api.set_pico_theme(path, folder);
    if (res && res.success) open("themes");
    else alert((res && res.error) || "Falha");
  }

  async function importTheme() {
    const path = drivePath();
    if (!path) return alert("Seleccione um cartão.");
    const api = await waitForApi();
    const pick = await api.pick_folder();
    if (!pick || pick.cancelled || !pick.path) return;
    const res = await api.import_pico_theme(path, pick.path);
    alert((res && (res.message || res.error)) || "Concluído");
    open("themes");
  }

  async function createMaterial() {
    const path = drivePath();
    if (!path) return alert("Seleccione um cartão.");
    const name = prompt("Nome do tema material:", "Route1");
    if (!name) return;
    const api = await waitForApi();
    const res = await api.create_pico_material_theme(path, name, 109, 139, 255, true);
    alert((res && (res.message || res.error)) || "Concluído");
    open("themes");
  }

  function renderUtilMissing(missing, flow) {
    const el = document.getElementById("util-art-missing");
    if (!el) return;
    const list = Array.isArray(missing) ? missing : [];
    if (!list.length) {
      el.classList.add("hidden");
      el.innerHTML = "";
      return;
    }
    el.classList.remove("hidden");
    const isDspico = flow === "dspico";
    const rows = list
      .slice(0, 40)
      .map((item) => {
        const name = escapeHtml(item.display_name || item.rel_path || "?");
        const bits = [];
        if (item.missing_cover) bits.push("capa");
        if (item.missing_icon) bits.push("ícone");
        return `<li class="text-[12px]"><strong>${name}</strong> — ${escapeHtml(
          bits.join(" + ") || "arte"
        )}</li>`;
      })
      .join("");
    const go = isDspico
      ? `R1K.shell.navigate('dspico'); setTimeout(()=>Dspico&&Dspico.setSection&&Dspico.setSection('games'),50)`
      : `R1K.shell.navigate('cartao')`;
    el.innerHTML = `
      <div class="rounded-lg border border-line p-3 space-y-2">
        <p class="text-[12px] font-semibold">${
          isDspico ? "Falhas DSPico" : "Falhas TWiLight"
        } (${list.length})</p>
        <ul class="list-disc pl-5 space-y-1 max-h-40 overflow-y-auto">${rows}</ul>
        <button type="button" class="btn-secondary !text-[11px]" onclick="${go}">Abrir e corrigir manualmente</button>
      </div>`;
  }

  async function batchDspicoArt() {
    const path = drivePath();
    if (!path) return alert("Seleccione um cartão.");
    const msg = document.getElementById("util-art-result");
    try {
      const api = await waitForApi();
      const fn =
        api.generate_dspico_artwork_batch || api.generate_dspico_covers_batch;
      if (!fn) {
        if (msg) msg.textContent = "API de lote DSPico indisponível.";
        return;
      }
      setBusy &&
        setBusy(true, null, {
          op: "generate_dspico_artwork_batch",
          label: "A buscar capas e ícones…",
        });
      if (msg) msg.textContent = "A buscar capas e ícones DSPico…";
      const res = await fn.call(api, path);
      if (msg) msg.textContent = (res && (res.message || res.error)) || "";
      renderUtilMissing((res && res.missing) || [], "dspico");
    } catch (e) {
      if (msg) msg.textContent = String(e.message || e);
    } finally {
      setBusy && setBusy(false);
    }
  }

  async function batchTwilightArt() {
    const path = drivePath();
    if (!path) return alert("Seleccione um cartão.");
    const msg = document.getElementById("util-art-result");
    try {
      const api = await waitForApi();
      if (!api.generate_twilight_artwork_batch) {
        if (msg) msg.textContent = "API de lote TWiLight indisponível.";
        return;
      }
      setBusy &&
        setBusy(true, null, {
          op: "generate_twilight_artwork_batch",
          label: "A buscar capas e ícones…",
        });
      if (msg) msg.textContent = "A buscar capas e ícones TWiLight…";
      const res = await api.generate_twilight_artwork_batch(path);
      if (msg) msg.textContent = (res && (res.message || res.error)) || "";
      renderUtilMissing((res && res.missing) || [], "twilight");
    } catch (e) {
      if (msg) msg.textContent = String(e.message || e);
    } finally {
      setBusy && setBusy(false);
    }
  }

  /** @deprecated use batchDspicoArt */
  async function batchCovers() {
    return batchDspicoArt();
  }

  window.R1K = window.R1K || {};
  window.R1K.utilidades = {
    open,
    ensure,
    setTheme,
    importTheme,
    createMaterial,
    batchCovers,
    batchDspicoArt,
    batchTwilightArt,
  };
})();
