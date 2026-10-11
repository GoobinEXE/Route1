/**
 * Verificar Atualizações — ecossistema DSPico.
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
    return document.getElementById("updates-panel");
  }

  function drivePath() {
    if (typeof selectedDrive !== "undefined" && selectedDrive && selectedDrive.mount_path) {
      return selectedDrive.mount_path;
    }
    const sel = document.getElementById("dspico-drive-select");
    if (sel && sel.value) return sel.value;
    return "";
  }

  async function check() {
    const el = panel();
    if (!el) return;
    el.classList.remove("hidden");
    el.innerHTML = '<p class="text-[12px] text-fg-mute">A verificar versões (cartão, pins da app, GitHub LNH)…</p>';
    R1K.shell && R1K.shell.toggleActivity(true);

    try {
      const api = typeof waitForApi === "function" ? await waitForApi() : window.pywebview && pywebview.api;
      if (!api || typeof api.check_dspico_updates !== "function") {
        el.innerHTML =
          '<p class="text-[12px] text-fg-mute">API de actualizações indisponível nesta build. Use Preparar SD com os pins oficiais.</p>';
        return;
      }
      const path = drivePath();
      const res = await api.check_dspico_updates(path || "");
      render(res);
    } catch (e) {
      el.innerHTML = `<p class="text-[12px] text-danger">Falha ao verificar: ${escapeHtml(e.message || e)}</p>`;
    }
  }

  function render(res) {
    const el = panel();
    if (!el) return;
    if (!res || res.success === false) {
      el.innerHTML = `<p class="text-[12px] text-danger">${escapeHtml((res && res.error) || "Sem resposta")}</p>`;
      return;
    }
    const comps = res.components || [];
    if (!comps.length) {
      el.innerHTML = '<p class="text-[12px] text-fg-mute">Nenhum componente reportado.</p>';
      return;
    }
    const head =
      '<div class="updates-row text-fg-mute font-medium">' +
      "<span>Componente</span><span>No cartão</span><span>Na app</span><span>Mais recente</span><span></span></div>";
    const rows = comps
      .map((c) => {
        const id = escapeHtml(c.id || c.name || "");
        const name = escapeHtml(c.label || c.name || c.id || "");
        const installed = escapeHtml(c.installed_version || "desconhecida");
        const pinned = escapeHtml(c.pinned_version || "—");
        const latest = escapeHtml(c.latest_version || "—");
        const actions = [];
        if (c.can_install_pinned) {
          actions.push(
            `<button type="button" class="btn-ghost !text-[11px]" onclick="R1K.updates.install('${id}','pinned')">Instalar incluída</button>`
          );
        }
        if (c.can_install_latest) {
          actions.push(
            `<button type="button" class="btn-primary !text-[11px] !px-2 !py-1" onclick="R1K.updates.install('${id}','latest')">Mais recente</button>`
          );
        }
        if (c.release_url) {
          actions.push(
            `<button type="button" class="btn-ghost !text-[11px]" onclick="R1K.updates.openUrl('${escapeHtml(c.release_url)}')">Abrir</button>`
          );
        }
        return (
          `<div class="updates-row"><span>${name}</span><span>${installed}</span><span>${pinned}</span><span>${latest}</span>` +
          `<span class="flex flex-wrap gap-1 justify-end">${actions.join("")}</span></div>`
        );
      })
      .join("");
    el.innerHTML = head + rows;
  }

  async function install(component, channel) {
    const path = drivePath();
    if (!path) {
      alert("Seleccione o microSD do DSPico.");
      return;
    }
    if (channel === "latest") {
      const ok = confirm(
        `Instalar a versão mais recente de ${component} a partir de github.com/LNH-team?\n\n` +
          "O ficheiro será verificado pelo digest SHA-256 do release. Continuar?"
      );
      if (!ok) return;
    }
    try {
      const api = typeof waitForApi === "function" ? await waitForApi() : window.pywebview && pywebview.api;
      if (!api || typeof api.install_dspico_component !== "function") {
        alert("Instalação de componentes indisponível.");
        return;
      }
      if (typeof setBusy === "function") setBusy(true);
      const res = await api.install_dspico_component(path, component, channel);
      if (res && res.success) {
        if (typeof appendLog === "function") appendLog(res.message || "Componente instalado.", "ok");
        await check();
      } else {
        alert((res && res.error) || "Falha na instalação.");
      }
    } catch (e) {
      alert(String(e.message || e));
    } finally {
      if (typeof setBusy === "function") setBusy(false);
    }
  }

  async function openUrl(url) {
    try {
      const api = typeof waitForApi === "function" ? await waitForApi() : window.pywebview && pywebview.api;
      if (api && typeof api.open_external_url === "function") {
        await api.open_external_url(url);
      }
    } catch (e) {
      /* ignore */
    }
  }

  window.R1K = window.R1K || {};
  window.R1K.updates = { check, install, openUrl, render };
})();
