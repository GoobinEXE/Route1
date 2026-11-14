/**
 * Janelas portadas da PicoDex (rasalopa, MIT) para o Route Pico:
 * capa e ícone de um jogo (CoverPicker), banner de pasta (BannerEditor),
 * estatísticas de um jogo (StatsEditor) e compatibilidade com o loader (CompatSheet).
 *
 * A composição da imagem é feita aqui num canvas, como na PicoDex: a capa é
 * esticada para 106×96 (convenção das capas da comunidade) e o ícone é
 * encaixado em 32×32 sem esticar. O Python codifica no formato do launcher e
 * devolve a prévia do próprio arquivo: o que aparece é o que vai para o cartão.
 * Todas as imagens chegam como data URLs; a UI não acessa a rede.
 */
(() => {
  const esc = (s) => escapeHtml(String(s == null ? "" : s));
  const ICON_SOURCES_LABEL = { rom: "Do jogo", steamgriddb: "SteamGridDB", logos: "Logo libretro", cover: "Da capa", file: "Do computador" };

  async function api() {
    return getApi() || (await waitForApi());
  }
  function hardBusy() {
    return typeof isHardBusy === "function" ? isHardBusy() : !!(typeof busy !== "undefined" && busy);
  }

  /** Escrita no cartão com a UI bloqueada (mesmo padrão do RouteDex). */
  async function write(method, args, label) {
    if (hardBusy()) {
      alert("Aguarde a operação em andamento terminar.");
      return null;
    }
    try {
      setBusy(true, null, { op: method, label: label || "Gravando no cartão…" });
      const a = await api();
      const res = await a[method](...args);
      if (!(res && res.success)) alert((res && res.error) || "A operação falhou.");
      return res || null;
    } catch (e) {
      alert(e.message || String(e));
      return null;
    } finally {
      setBusy(false);
    }
  }

  function fmtMinutes(min) {
    const m = Math.max(0, Math.round(Number(min) || 0));
    return `${Math.floor(m / 60)}h ${m % 60}m`;
  }
  function fmtBytes(n) {
    const v = Number(n) || 0;
    if (v >= 1024 * 1024) return `${+(v / (1024 * 1024)).toFixed(v % (1024 * 1024) ? 1 : 0)} MB`;
    if (v >= 1024) return `${+(v / 1024).toFixed(v % 1024 ? 1 : 0)} KB`;
    return `${v} bytes`;
  }
  function isPng(u) {
    return typeof u === "string" && u.startsWith("data:image/");
  }

  // ------------------------------------------------------------------ janela modal

  let openCount = 0;
  function modal({ title, kicker, meta, wide, onClose }) {
    const opener = document.activeElement;
    const id = `pdx-title-${++openCount}`;
    const ov = document.createElement("div");
    ov.className = "pdx-overlay";
    ov.innerHTML = `
      <div class="pdx-dialog${wide ? " pdx-dialog--wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="${id}">
        <header class="pdx-head">
          <div class="min-w-0">
            ${kicker ? `<div class="pdx-kicker">${esc(kicker)}</div>` : ""}
            <h2 class="pdx-title" id="${id}">${esc(title)}</h2>
            ${meta ? `<div class="pdx-meta">${esc(meta)}</div>` : ""}
          </div>
          <button type="button" class="btn-ghost !px-2 !py-1 pdx-close" aria-label="Fechar"><svg class="ico" aria-hidden="true"><use href="#i-close"/></svg></button>
        </header>
        <div class="pdx-body"></div>
      </div>`;
    document.body.appendChild(ov);
    let closed = false;
    const close = () => {
      if (closed || hardBusy()) return;
      closed = true;
      document.removeEventListener("keydown", onKey, true);
      ov.remove();
      if (opener && typeof opener.focus === "function") opener.focus();
      if (onClose) onClose();
    };
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        e.preventDefault();
        close();
      }
    };
    document.addEventListener("keydown", onKey, true);
    ov.addEventListener("mousedown", (e) => {
      if (e.target === ov) close();
    });
    ov.querySelector(".pdx-close").onclick = close;
    setTimeout(() => {
      const f = ov.querySelector("input, button:not(.pdx-close)") || ov.querySelector(".pdx-close");
      if (f) f.focus();
    }, 0);
    return { el: ov, body: ov.querySelector(".pdx-body"), close };
  }

  // ------------------------------------------------------------------ composição (canvas)

  /** onload/onerror com prazo: img.decode() pode ficar parado com a janela em segundo plano. */
  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const timer = setTimeout(() => reject(new Error("A imagem demorou demais para abrir.")), 15000);
      img.onload = () => {
        clearTimeout(timer);
        if (!img.naturalWidth || !img.naturalHeight) reject(new Error("Não foi possível ler esta imagem."));
        else resolve(img);
      };
      img.onerror = () => {
        clearTimeout(timer);
        reject(new Error("Não foi possível ler esta imagem."));
      };
      img.src = url;
    });
  }
  function makeCanvas(w, h) {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    return [c, ctx];
  }
  function toB64(data) {
    let s = "";
    const CH = 0x8000;
    for (let i = 0; i < data.length; i += CH) s += String.fromCharCode.apply(null, data.subarray(i, i + CH));
    return btoa(s);
  }
  /** Capa 128×96: arte esticada em 106×96 sobre preto (PicoDex composeCoverRgba). */
  function coverRgba(img) {
    const [, ctx] = makeCanvas(128, 96);
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, 128, 96);
    ctx.drawImage(img, 0, 0, 106, 96);
    return ctx.getImageData(0, 0, 128, 96).data;
  }
  /** Ícone 32×32: encaixado sem esticar, margens transparentes (composeIconRgba). */
  function iconRgba(img, square) {
    let sx = 0;
    let sy = 0;
    let sw = img.naturalWidth;
    let sh = img.naturalHeight;
    if (square) {
      // "Da capa": o maior quadrado central da arte, depois encaixado.
      const s = Math.min(sw, sh);
      sx = Math.floor((sw - s) / 2);
      sy = Math.floor((sh - s) / 2);
      sw = sh = s;
    }
    const [, ctx] = makeCanvas(32, 32);
    const scale = Math.min(32 / sw, 32 / sh);
    const w = Math.max(1, Math.round(sw * scale));
    const h = Math.max(1, Math.round(sh * scale));
    ctx.drawImage(img, sx, sy, sw, sh, Math.floor((32 - w) / 2), Math.floor((32 - h) / 2), w, h);
    return ctx.getImageData(0, 0, 32, 32).data;
  }
  async function encode(kind, dataUrl, square) {
    const img = await loadImage(dataUrl);
    const rgba = kind === "cover" ? coverRgba(img) : iconRgba(img, square);
    const a = await api();
    const r = await a.encode_art(kind, toB64(rgba));
    if (!(r && r.success)) throw new Error((r && r.error) || "Não foi possível preparar esta imagem.");
    return r;
  }

  // ------------------------------------------------------------------ capa e ícone de um jogo

  async function openCoverPicker(mount, rel, opts) {
    const o = opts || {};
    const a = await api();
    const ctx = await a.get_art_picker_context(mount, rel);
    if (!(ctx && ctx.success)) {
      alert((ctx && ctx.error) || "Não foi possível ler o jogo.");
      return;
    }
    const sys = ctx.system || { label: "", repo: "", id: "" };
    const m = modal({
      title: `Capa e ícone — ${ctx.title}`,
      meta: [sys.label, ctx.game_code].filter(Boolean).join(" · "),
      wide: true,
    });
    const st = {
      tab: "catalog",
      query: ctx.title,
      cover: null, // {token, preview, source}
      icon: null, // {token, preview, label}
      coverSrc: null, // data URL da origem escolhida (para "ícone da capa")
      results: null,
      catalogError: null,
      iconSources: null,
      iconQuery: "",
      saving: false,
      searchTimer: null,
      searchGen: 0,
    };
    const iconBlocked = ctx.icon && ctx.icon.kind === "banner";

    function notes() {
      const out = [];
      if (iconBlocked)
        out.push(
          `Este jogo tem um banner próprio em <code>${esc(ctx.icon.rel || "_pico/banners")}</code> e o launcher tira o ícone de lá. Um ícone salvo aqui não apareceria; para usar o seu, tire esse banner de <code>_pico/banners</code> primeiro.`
        );
      if (ctx.launcher && ctx.launcher.custom_icons_ignored)
        out.push("Ícones próprios precisam de um Pico Launcher mais novo que a v1.3.0. Com a v1.3.0 o ícone é salvo no cartão, mas o console continua mostrando o do jogo.");
      if (ctx.icon && ctx.icon.kind === "invalid")
        out.push("O ícone que está no cartão não está no formato que o launcher lê, então o console mostra um ícone em branco. Salvar um novo substitui esse arquivo.");
      if (ctx.cover && ctx.cover.invalid)
        out.push(`A capa que está no cartão não está no formato que o launcher lê (${esc(ctx.cover.invalid)}). Salvar uma nova corrige.`);
      return out.map((n) => `<p class="pdx-note">${n}</p>`).join("");
    }

    function currentIcon() {
      if (st.icon) return `<img class="pdx-row-icon" src="${st.icon.preview}" alt="Ícone novo de ${esc(ctx.title)}">`;
      const ic = ctx.icon || {};
      if (isPng(ic.preview)) return `<img class="pdx-row-icon" src="${ic.preview}" alt="Ícone atual de ${esc(ctx.title)}">`;
      if (ic.kind === "invalid") return `<span class="pdx-row-icon pdx-row-icon--bad" title="Ícone inválido no cartão">!</span>`;
      return `<span class="pdx-row-icon pdx-row-icon--empty" title="Sem ícone próprio">?</span>`;
    }

    function screens() {
      const cur = ctx.cover && isPng(ctx.cover.preview) ? ctx.cover.preview : null;
      const top = st.cover
        ? `<img class="pdx-top-cover" src="${st.cover.preview}" width="106" height="96" alt="Capa nova de ${esc(ctx.title)}">`
        : cur
          ? `<img class="pdx-top-cover" src="${cur}" width="106" height="96" alt="Capa atual de ${esc(ctx.title)}">`
          : `<span class="pdx-top-cover pdx-top-cover--empty">?</span>`;
      const nb = ctx.neighbours || { before: [], after: [] };
      const dim = (n) => `<div class="pdx-row pdx-row--dim"><span class="pdx-row-icon pdx-row-icon--empty"></span><span class="pdx-row-name">${esc(n)}</span></div>`;
      return `
        <div class="pdx-screens">
          <section class="pdx-screen" aria-label="Tela de cima">
            <div class="pdx-panel pdx-panel--top">
              ${top}
              <span class="pdx-chip">${esc(ctx.title)}</span>
              ${st.cover ? `<span class="pdx-pill">Nova</span>` : ""}
              ${st.cover && cur ? `<span class="pdx-before"><img src="${cur}" width="53" height="48" alt="">Atual</span>` : ""}
            </div>
          </section>
          <section class="pdx-screen" aria-label="Tela de baixo">
            <div class="pdx-panel pdx-list">
              ${nb.before.map(dim).join("")}
              <div class="pdx-row pdx-row--sel">${currentIcon()}<span class="pdx-row-name">${esc(ctx.title)}</span>${st.icon ? `<span class="pdx-pill">Novo</span>` : ""}</div>
              ${nb.after.map(dim).join("")}
            </div>
          </section>
        </div>`;
    }

    function tabs() {
      const t = (id, label, dot) =>
        `<button type="button" role="tab" class="pdx-tab${st.tab === id ? " pdx-tab--on" : ""}" aria-selected="${st.tab === id}" data-tab="${id}">${label}${dot ? `<span class="pdx-dot" aria-hidden="true"></span>` : ""}</button>`;
      return `<div class="pdx-tabs" role="tablist">
        ${t("catalog", "Capas do catálogo", st.cover && st.cover.source === "catalog")}
        ${t("more", "Outras fontes", st.cover && st.cover.source === "more")}
        ${t("file", "Capa do computador", st.cover && st.cover.source === "file")}
        ${t("icon", "Ícone", !!st.icon)}
      </div>`;
    }

    function catalogPanel() {
      let list;
      if (st.catalogError) list = `<div class="pdx-error" role="alert">Não deu para baixar a lista de capas. ${esc(st.catalogError)} <button type="button" class="btn-ghost btn-sm" data-act="retry">Tentar de novo</button></div>`;
      else if (st.results === null) list = `<p class="pdx-status" role="status">Carregando o catálogo de capas…</p>`;
      else if (!st.results.length) list = `<p class="pdx-status">Nenhuma capa corresponde a “${esc(st.query)}”.</p>`;
      else
        list = `<ul class="pdx-results">${st.results
          .map(
            (r) => `<li><button type="button" class="pdx-cand${st.cover && st.cover.name === r.name ? " pdx-cand--on" : ""}" data-name="${esc(r.name)}" aria-pressed="${!!(st.cover && st.cover.name === r.name)}">
              <span class="pdx-thumb" data-thumb="${esc(r.name)}"></span><span class="pdx-cand-text"><span class="pdx-cand-name">${esc(r.label)}</span>${r.suggested ? `<span class="pdx-pill pdx-pill--soft">Sugerida</span>` : ""}</span></button></li>`
          )
          .join("")}</ul>`;
      return `<input type="search" class="field-select w-full pdx-search" id="pdx-q" value="${esc(st.query)}" placeholder="Procurar capas de ${esc(sys.label)}…" aria-label="Procurar capa">${list}
        <p class="pdx-hint">Capas do catálogo libretro-thumbnails, escolhidas pela região do jogo. A lista fica guardada por 7 dias.</p>`;
    }

    function morePanel() {
      return `<p class="pdx-hint">SteamGridDB (com a chave de Configurações) e GameTDB, as fontes de capas que o Route Pico já usava.</p>
        <div class="flex gap-2"><input type="search" class="field-select flex-1" id="pdx-more-q" value="${esc(st.query)}" aria-label="Procurar em outras fontes"><button type="button" class="btn-secondary" data-act="more-search">Procurar</button></div>
        <div id="pdx-more-list" class="pdx-icon-grid pdx-icon-grid--covers"></div>`;
    }

    function filePanel() {
      return `<p class="pdx-hint">Qualquer PNG, JPG, WebP ou GIF serve. A imagem é esticada para preencher a capa, como as capas baixadas.</p>
        <button type="button" class="btn-secondary" data-act="cover-file">Escolher imagem…</button>`;
    }

    function iconPanel() {
      if (iconBlocked) return `<p class="pdx-hint">Ícone bloqueado pelo banner deste jogo (veja o aviso acima).</p>`;
      const srcs = st.iconSources;
      const tiles = [];
      const cur = st.coverSrc || (ctx.cover && isPng(ctx.cover.preview) ? ctx.cover.preview : null);
      if (cur) tiles.push({ source: "cover", label: "Da capa", image: cur, square: true });
      (srcs || []).forEach((s) => tiles.push(s));
      const grid = tiles
        .map(
          (s, i) => `<button type="button" class="pdx-icon-cand${st.icon && st.icon.idx === i ? " pdx-cand--on" : ""}" data-icon="${i}" title="${esc(s.label)}">
            <img src="${s.image}" alt="" class="pdx-icon-src${s.source === "rom" ? " pdx-pixel" : ""}"><span>${esc(ICON_SOURCES_LABEL[s.source] || s.source)}</span></button>`
        )
        .join("");
      st.iconTiles = tiles;
      return `<p class="pdx-hint">A figurinha ao lado do nome na lista do launcher. Jogos de DS já trazem uma, e esta a substitui; outros sistemas não têm, e esta adiciona uma. A imagem é encaixada em 32×32 sem esticar.</p>
        <div class="flex gap-2"><input type="search" class="field-select flex-1" id="pdx-icon-q" value="${esc(st.iconQuery || ctx.title)}" aria-label="Procurar ícones"><button type="button" class="btn-secondary" data-act="icon-search">Procurar ícones</button><button type="button" class="btn-ghost" data-act="icon-file">Do computador…</button></div>
        ${srcs === null ? `<p class="pdx-status" role="status">Procurando ícones…</p>` : ""}
        <div class="pdx-icon-grid">${grid || `<p class="pdx-status">Nenhum ícone encontrado. Escolha uma capa primeiro (para gerar o ícone a partir dela) ou use uma imagem do computador.</p>`}</div>
        ${st.iconKeyMissing ? `<p class="pdx-hint">Para incluir ícones do SteamGridDB, salve a chave da API em Configurações.</p>` : ""}`;
    }

    function footer() {
      const can = (st.cover || st.icon) && !st.saving;
      const writes = [st.cover ? ctx.targets.cover : null, st.icon ? ctx.targets.icon : null].filter(Boolean);
      return `<footer class="pdx-foot">
        <span class="pdx-writes">${writes.length ? `Grava em ${writes.map((w) => `<code>/${esc(w)}</code>`).join(" e ")}` : "Escolha uma capa ou um ícone."}</span>
        <button type="button" class="btn-primary" data-act="save" ${can ? "" : "disabled"}>${st.saving ? "Gravando…" : "Salvar"}</button>
      </footer>`;
    }

    function render() {
      const panel = st.tab === "catalog" ? catalogPanel() : st.tab === "more" ? morePanel() : st.tab === "file" ? filePanel() : iconPanel();
      m.body.innerHTML = `${screens()}${notes()}${tabs()}<div class="pdx-tabpanel" role="tabpanel">${panel}</div><div class="pdx-msg" role="status" aria-live="polite"></div>${footer()}`;
      bind();
      if (st.tab === "catalog" && st.results && st.results.length) loadThumbs();
    }

    function say(msg, bad) {
      const el = m.body.querySelector(".pdx-msg");
      if (el) {
        el.textContent = msg || "";
        el.classList.toggle("text-danger", !!bad);
      }
    }

    async function search() {
      const my = ++st.searchGen;
      st.results = null;
      st.catalogError = null;
      render();
      const r = await a.search_art_catalog(sys.repo, st.query, "boxarts", ctx.title, ctx.game_code || "", sys.id);
      if (my !== st.searchGen) return;
      if (!(r && r.success)) {
        st.catalogError = (r && r.error) || "";
        st.results = [];
      } else {
        st.results = (r.results || []).map((x) => ({ ...x, suggested: x.name === r.suggested }));
      }
      if (st.tab === "catalog") render();
    }

    async function loadThumbs() {
      const holders = [...m.body.querySelectorAll("[data-thumb]")].filter((h) => !h.dataset.loaded);
      if (!holders.length) return;
      holders.forEach((h) => (h.dataset.loaded = "1"));
      const names = holders.map((h) => h.getAttribute("data-thumb"));
      for (let i = 0; i < names.length; i += 12) {
        const part = names.slice(i, i + 12);
        const r = await a.get_art_catalog_thumbs(sys.repo, part, "boxarts");
        const thumbs = (r && r.thumbs) || {};
        part.forEach((n) => {
          const h = m.body.querySelector(`[data-thumb="${CSS.escape(n)}"]`);
          if (h && isPng(thumbs[n])) h.innerHTML = `<img src="${thumbs[n]}" alt="" loading="lazy">`;
        });
      }
    }

    async function setCover(dataUrl, source, name) {
      say("Preparando a prévia…");
      try {
        const r = await encode("cover", dataUrl);
        st.cover = { token: r.token, preview: r.preview, source, name };
        st.coverSrc = dataUrl;
        say("");
        render();
      } catch (e) {
        say(`Não foi possível preparar esta imagem. ${e.message || e}`, true);
      }
    }

    async function setIcon(dataUrl, square, idx, label) {
      say("Preparando o ícone…");
      try {
        const r = await encode("icon", dataUrl, square);
        st.icon = { token: r.token, preview: r.preview, idx, label };
        say("");
        render();
      } catch (e) {
        say(`Não foi possível preparar este ícone. ${e.message || e}`, true);
      }
    }

    async function loadIconSources(query) {
      st.iconSources = null;
      st.iconQuery = query || "";
      render();
      const r = await a.get_icon_sources(mount, rel, query || "");
      st.iconSources = r && r.success ? r.sources || [] : [];
      st.iconKeyMissing = !!(r && r.success && !r.steamgriddb_key);
      if (!(r && r.success)) say((r && r.error) || "Não deu para procurar ícones.", true);
      if (st.tab === "icon") render();
    }

    function bind() {
      m.body.querySelectorAll("[data-tab]").forEach((b) => {
        b.onclick = () => {
          st.tab = b.getAttribute("data-tab");
          if (st.tab === "icon" && st.iconSources === undefined) loadIconSources("");
          render();
        };
      });
      const q = m.body.querySelector("#pdx-q");
      if (q) {
        q.oninput = () => {
          st.query = q.value;
          clearTimeout(st.searchTimer);
          st.searchTimer = setTimeout(() => {
            search().then(() => {
              const nq = m.body.querySelector("#pdx-q");
              if (nq) {
                nq.focus();
                nq.setSelectionRange(nq.value.length, nq.value.length);
              }
            });
          }, 280);
        };
      }
      m.body.querySelectorAll("[data-name]").forEach((b) => {
        b.onclick = async () => {
          const name = b.getAttribute("data-name");
          say("Baixando a capa…");
          const r = await a.get_art_catalog_image(sys.repo, name, "boxarts");
          if (!(r && r.success)) {
            say((r && r.error) || "A capa não pôde ser baixada.", true);
            return;
          }
          await setCover(r.image, "catalog", name);
        };
      });
      m.body.querySelectorAll("[data-icon]").forEach((b) => {
        b.onclick = () => {
          const i = Number(b.getAttribute("data-icon"));
          const s = (st.iconTiles || [])[i];
          if (s) setIcon(s.image, !!s.square, i, s.label);
        };
      });
      const act = (name, fn) => {
        const el = m.body.querySelector(`[data-act="${name}"]`);
        if (el) el.onclick = fn;
      };
      act("retry", () => search());
      act("cover-file", async () => {
        const r = await a.pick_art_image();
        if (r && r.success && !r.cancelled) await setCover(r.image, "file");
        else if (r && !r.success) say(r.error, true);
      });
      act("icon-file", async () => {
        const r = await a.pick_art_image();
        if (r && r.success && !r.cancelled) await setIcon(r.image, false, -1, "Do computador");
        else if (r && !r.success) say(r.error, true);
      });
      act("icon-search", () => {
        const v = (m.body.querySelector("#pdx-icon-q") || {}).value || "";
        loadIconSources(v.trim());
      });
      act("more-search", () => moreSearch());
      act("save", save);
    }

    async function moreSearch() {
      const box = m.body.querySelector("#pdx-more-list");
      const q = ((m.body.querySelector("#pdx-more-q") || {}).value || "").trim();
      if (!box) return;
      box.innerHTML = `<p class="pdx-status" role="status">Procurando…</p>`;
      const r = await a.search_dspico_artwork(mount, rel, "cover", q);
      const cands = ((r && r.candidates) || []).slice(0, 12);
      if (!(r && r.success) || !cands.length) {
        box.innerHTML = `<p class="pdx-status">${esc((r && r.error) || "Nada encontrado nessas fontes.")}</p>`;
        return;
      }
      const shown = cands.slice(0, 12);
      box.innerHTML = shown
        .map(
          (c, i) => `<button type="button" class="pdx-icon-cand pdx-icon-cand--cover" data-more="${i}" title="${esc(c.label || c.source || "")}">
            <span class="pdx-thumb" data-more-thumb="${i}"></span><span>${esc(c.source_label || c.source || "")}</span></button>`
        )
        .join("");
      // Miniaturas pelo Python (data URL): a UI não acessa a rede.
      shown.forEach(async (c, i) => {
        const img = await a.get_art_remote_image(c.preview || c.url);
        const h = box.querySelector(`[data-more-thumb="${i}"]`);
        if (h && img && img.success) h.innerHTML = `<img src="${img.image}" alt="">`;
      });
      box.querySelectorAll("[data-more]").forEach((b) => {
        b.onclick = async () => {
          const c = cands[Number(b.getAttribute("data-more"))];
          say("Baixando a imagem…");
          const img = await a.get_art_remote_image(c.url);
          if (!(img && img.success)) {
            say((img && img.error) || "A imagem não pôde ser baixada.", true);
            return;
          }
          await setCover(img.image, "more", c.url);
        };
      });
    }

    async function save() {
      if (st.saving || !(st.cover || st.icon)) return;
      st.saving = true;
      render();
      const res = await write("save_game_art", [mount, rel, st.cover ? st.cover.token : null, st.icon ? st.icon.token : null], "Gravando capa e ícone…");
      st.saving = false;
      if (res && res.success) {
        appendLog(`Arte salva: ${ctx.title}`, "ok");
        m.close();
        if (o.onSaved) o.onSaved();
        return;
      }
      render();
    }

    st.iconSources = undefined;
    render();
    search();
  }

  // ------------------------------------------------------------------ banner de pasta

  async function openBannerEditor(mount, folder, opts) {
    const o = opts || {};
    const a = await api();
    const ctx = await a.get_banner_context(mount, folder);
    if (!(ctx && ctx.success)) {
      alert((ctx && ctx.error) || "Não foi possível ler a pasta.");
      return;
    }
    const m = modal({ title: `Banner da pasta — ${ctx.folder}/`, kicker: "Ícone e nome mostrados no launcher" });
    const st = {
      title: ctx.default_title || ctx.name,
      mode: ctx.current && isPng(ctx.current.icon) ? "keep" : "search",
      icon: null,
      sources: undefined,
      game: "",
      saving: false,
      query: ctx.default_query || ctx.name,
    };

    function preview() {
      const icon = st.icon ? st.icon.preview : st.mode === "keep" && ctx.current ? ctx.current.icon : null;
      return `<div class="pdx-banner-prev" aria-label="Prévia do banner">
        ${isPng(icon) ? `<img class="pdx-row-icon pdx-pixel" src="${icon}" alt="">` : `<span class="pdx-row-icon pdx-row-icon--empty">?</span>`}
        <span class="pdx-banner-title">${esc(st.title || ctx.name)}</span>
      </div>`;
    }

    function sourcesPanel() {
      if (st.mode === "keep") return `<p class="pdx-hint">Mantém o ícone que já está no banner; só o nome muda.</p>`;
      if (st.mode === "game") {
        return `<label class="pdx-label" for="pdx-bn-game">Jogo de onde tirar o ícone</label>
          <select id="pdx-bn-game" class="field-select w-full"><option value="">Escolha um jogo…</option>${(ctx.games || [])
            .map((g) => `<option value="${esc(g)}"${g === st.game ? " selected" : ""}>${esc(g)}</option>`)
            .join("")}</select>${(ctx.games || []).length ? "" : `<p class="pdx-hint">Esta pasta não tem jogos de DS com ícone.</p>`}`;
      }
      if (st.mode === "file") return `<p class="pdx-hint">A imagem é encaixada em 32×32 e reduzida a 15 cores. A prévia acima mostra como fica no DS.</p><button type="button" class="btn-secondary" data-act="bn-file">Escolher imagem…</button>`;
      const tiles = (st.sources || [])
        .map(
          (s, i) => `<button type="button" class="pdx-icon-cand${st.icon && st.icon.idx === i ? " pdx-cand--on" : ""}" data-bsrc="${i}" title="${esc(s.label)}"><img src="${s.image}" alt="" class="pdx-icon-src"><span>${esc(ICON_SOURCES_LABEL[s.source] || s.source)}</span></button>`
        )
        .join("");
      return `<div class="flex gap-2"><input type="search" class="field-select flex-1" id="pdx-bn-q" value="${esc(st.query)}" aria-label="Procurar ícones"><button type="button" class="btn-secondary" data-act="bn-search">Procurar ícones</button></div>
        ${st.sources === null ? `<p class="pdx-status" role="status">Procurando ícones…</p>` : ""}
        <div class="pdx-icon-grid">${tiles || (st.sources ? `<p class="pdx-status">Nada encontrado. Tente outro nome, um jogo da pasta ou uma imagem do computador.</p>` : "")}</div>
        ${st.keyMissing ? `<p class="pdx-hint">Para incluir ícones do SteamGridDB, salve a chave da API em Configurações.</p>` : ""}`;
    }

    function render() {
      const notes = [];
      if ((ctx.shared_systems || []).length > 1) {
        const s = ctx.shared_systems;
        notes.push(`Esta pasta guarda ${esc(s.slice(0, -1).join(", "))} e ${esc(s[s.length - 1])}. Eles dividem um só banner: salvar aqui muda o ícone e o nome de todos.`);
      }
      if (ctx.launcher && ctx.launcher.custom_icons_ignored) notes.push("Banners de pasta precisam de um Pico Launcher mais novo que a v1.3.0. Com a v1.3.0 o console mantém o nome e o ícone padrão da pasta.");
      if (ctx.current && ctx.current.error) notes.push(`Não deu para ler o banner atual: ${esc(ctx.current.error)}`);
      const opt = (v, label, disabled) => `<label class="pdx-radio"><input type="radio" name="pdx-bn-mode" value="${v}"${st.mode === v ? " checked" : ""}${disabled ? " disabled" : ""}> ${label}</label>`;
      const can = !st.saving && (st.title || "").trim() && (st.mode === "keep" ? !!(ctx.current && isPng(ctx.current.icon)) : !!st.icon);
      m.body.innerHTML = `
        ${preview()}
        ${notes.map((n) => `<p class="pdx-note">${n}</p>`).join("")}
        <label class="pdx-label" for="pdx-bn-title">Título</label>
        <input id="pdx-bn-title" class="field-select w-full" maxlength="127" value="${esc(st.title)}" placeholder="Nome da pasta mostrado pelo launcher">
        <fieldset class="pdx-fieldset"><legend class="pdx-label">Ícone</legend>
          <div class="pdx-radios">
            ${opt("keep", "Manter o atual", !(ctx.current && isPng(ctx.current.icon)))}
            ${opt("search", "Procurar")}
            ${opt("game", "De um jogo da pasta")}
            ${opt("file", "Do computador")}
          </div>
          <div class="pdx-tabpanel">${sourcesPanel()}</div>
        </fieldset>
        <div class="pdx-msg" role="status" aria-live="polite"></div>
        <footer class="pdx-foot">
          <span class="pdx-writes">Grava <code>/${esc(ctx.folder)}/banner.bnr</code></span>
          <div class="flex gap-2">
            ${ctx.current ? `<button type="button" class="btn-ghost btn-ghost--muted" data-act="bn-remove">Remover banner</button>` : ""}
            <button type="button" class="btn-primary" data-act="bn-save" ${can ? "" : "disabled"}>${st.saving ? "Gravando…" : "Salvar banner"}</button>
          </div>
        </footer>`;
      bind();
    }

    function say(msg, bad) {
      const el = m.body.querySelector(".pdx-msg");
      if (el) {
        el.textContent = msg || "";
        el.classList.toggle("text-danger", !!bad);
      }
    }

    async function useImage(dataUrl, idx, exact) {
      say("Preparando o ícone…");
      try {
        const r = await encode("icon", dataUrl, false);
        st.icon = { token: r.token, preview: r.preview, idx };
        say(exact ? "" : "");
        render();
      } catch (e) {
        say(`Não foi possível ler a imagem. ${e.message || e}`, true);
      }
    }

    async function searchIcons() {
      st.sources = null;
      render();
      const r = await a.get_banner_icon_sources(mount, ctx.folder, st.query, "");
      st.sources = r && r.success ? r.sources || [] : [];
      st.keyMissing = !!(r && r.success && !r.steamgriddb_key);
      render();
    }

    function bind() {
      const t = m.body.querySelector("#pdx-bn-title");
      if (t)
        t.oninput = () => {
          st.title = t.value;
          const p = m.body.querySelector(".pdx-banner-title");
          if (p) p.textContent = st.title || ctx.name;
          const sb = m.body.querySelector('[data-act="bn-save"]');
          if (sb) sb.disabled = !st.title.trim() || (st.mode === "keep" ? !(ctx.current && isPng(ctx.current.icon)) : !st.icon);
        };
      m.body.querySelectorAll('input[name="pdx-bn-mode"]').forEach((r) => {
        r.onchange = () => {
          st.mode = r.value;
          st.icon = null;
          if (st.mode === "search" && st.sources === undefined) searchIcons();
          else render();
        };
      });
      const g = m.body.querySelector("#pdx-bn-game");
      if (g)
        g.onchange = async () => {
          st.game = g.value;
          if (!st.game) return;
          say("Lendo o ícone do jogo…");
          const r = await a.get_banner_icon_sources(mount, ctx.folder, "", st.game);
          if (!(r && r.success && r.sources && r.sources[0])) {
            say((r && r.error) || "Este jogo não tem ícone.", true);
            return;
          }
          await useImage(r.sources[0].image, -1, true);
        };
      const q = m.body.querySelector("#pdx-bn-q");
      if (q) q.onchange = () => (st.query = q.value.trim());
      m.body.querySelectorAll("[data-bsrc]").forEach((b) => {
        b.onclick = () => {
          const s = (st.sources || [])[Number(b.getAttribute("data-bsrc"))];
          if (s) useImage(s.image, Number(b.getAttribute("data-bsrc")));
        };
      });
      const act = (name, fn) => {
        const el = m.body.querySelector(`[data-act="${name}"]`);
        if (el) el.onclick = fn;
      };
      act("bn-search", () => {
        st.query = ((m.body.querySelector("#pdx-bn-q") || {}).value || "").trim() || ctx.name;
        searchIcons();
      });
      act("bn-file", async () => {
        const r = await a.pick_art_image();
        if (r && r.success && !r.cancelled) await useImage(r.image, -1);
      });
      act("bn-remove", async () => {
        if (!confirm(`Remover ${ctx.folder}/banner.bnr?\n\nFica uma cópia no computador.`)) return;
        const res = await write("remove_routedex_folder_art", [mount, ctx.folder, "banner"], "Removendo o banner…");
        if (res && res.success) {
          appendLog(`Banner removido de ${ctx.folder}.`, "ok");
          m.close();
          if (o.onSaved) o.onSaved();
        }
      });
      act("bn-save", async () => {
        st.saving = true;
        render();
        const res = await write(
          "save_folder_banner",
          [mount, ctx.folder, st.title.trim(), st.icon ? st.icon.token : null, st.mode === "keep"],
          "Gravando o banner…"
        );
        st.saving = false;
        if (res && res.success) {
          appendLog(`Banner salvo em ${ctx.folder}.`, "ok");
          m.close();
          if (o.onSaved) o.onSaved();
          return;
        }
        render();
      });
    }

    render();
    if (st.mode === "search") searchIcons();
  }

  // ------------------------------------------------------------------ estatísticas de um jogo

  function openStatsEditor(mount, game, opts) {
    const o = opts || {};
    const mins = Math.max(0, Number(game.playMinutes) || 0);
    const m = modal({ title: `Estatísticas — ${game.title || game.name}`, kicker: "Corrigir partidas e tempo de jogo" });
    m.body.innerHTML = `
      <div class="pdx-stats-form">
        <label class="pdx-label" for="pdx-st-l">Partidas</label>
        <input id="pdx-st-l" class="field-select" type="number" min="0" max="999999" value="${Number(game.launchCount) || 0}">
        <span class="pdx-label">Tempo de jogo</span>
        <div class="flex gap-2 items-center">
          <input id="pdx-st-h" class="field-select w-24" type="number" min="0" max="99999" value="${Math.floor(mins / 60)}" aria-label="Horas"> <span class="pdx-hint">h</span>
          <input id="pdx-st-m" class="field-select w-24" type="number" min="0" max="59" value="${mins % 60}" aria-label="Minutos"> <span class="pdx-hint">min</span>
        </div>
      </div>
      <footer class="pdx-foot"><span></span><div class="flex gap-2"><button type="button" class="btn-ghost" data-act="cancel">Cancelar</button><button type="button" class="btn-primary" data-act="save">Salvar</button></div></footer>`;
    m.body.querySelector('[data-act="cancel"]').onclick = m.close;
    m.body.querySelector('[data-act="save"]').onclick = async () => {
      const l = Math.max(0, parseInt(m.body.querySelector("#pdx-st-l").value, 10) || 0);
      const h = Math.max(0, parseInt(m.body.querySelector("#pdx-st-h").value, 10) || 0);
      const mm = Math.min(59, Math.max(0, parseInt(m.body.querySelector("#pdx-st-m").value, 10) || 0));
      const res = await write("set_routedex_stats", [mount, game.rel, String(l), String(h * 60 + mm)], "Salvando estatísticas…");
      if (res && res.success) {
        m.close();
        if (o.onSaved) o.onSaved(res.entry || { launchCount: l, playMinutes: h * 60 + mm });
      }
    };
  }

  // ------------------------------------------------------------------ compatibilidade com o loader

  const SAVE_TYPES = { none: "Nenhum", eeprom: "EEPROM", flash: "Flash", nand: "NAND", unknown: "Desconhecido" };
  const HINTS = {
    ap: {
      retail: "Alguns jogos travam de propósito quando percebem um flashcard. O loader evita isso ao abrir o jogo, usando o aplist.bin e algumas correções embutidas no próprio loader. O Route Pico só consegue conferir o aplist.bin.",
      dsiware: "A proteção anti-pirataria é coisa de cartucho. Jogos DSiWare nunca estiveram num cartucho, então o loader nem roda esse passo para eles.",
      homebrew: "Proteção anti-pirataria é coisa de jogo comercial. O loader não roda nada disso para homebrew, então não há o que conferir.",
    },
    save: {
      retail: "Os cartuchos originais têm um chip de save. O loader troca esse chip por um arquivo de save no seu cartão.",
      dsiware: "Jogos DSiWare salvam em arquivos, não num chip. O loader cria esses arquivos ao lado do jogo, nos tamanhos que o jogo pede.",
      homebrew: "Homebrew cuida dos próprios arquivos no cartão, então o loader não cria save para ele.",
    },
    patch: {
      retail: "Alguns jogos precisam de um pequeno ajuste para rodar a partir de um flashcard. O loader aplica ao abrir o jogo, a partir do patchlist.bin ou de ajustes embutidos no loader. O Route Pico só consegue conferir o patchlist.bin.",
      dsiware: "Alguns jogos precisam de um pequeno ajuste para rodar a partir de um flashcard, e jogos DSiWare também podem receber um. O Route Pico só consegue conferir o patchlist.bin.",
      homebrew: "Esses ajustes são para jogos comerciais. O loader não aplica nenhum deles em homebrew.",
    },
  };

  function mismatch(kind, versions, romVersion) {
    const thing = kind === "fix" ? "uma correção" : "um patch";
    const noun = versions.length === 1 ? "a revisão" : "as revisões";
    const rom = romVersion === null || romVersion === undefined ? "não deu para ler a revisão da sua cópia (o loader então considera a revisão 0)" : `a sua cópia é a revisão ${romVersion}`;
    return `O loader tem ${thing} para ${noun} ${versions.join(", ")} deste jogo, mas ${rom}, então não usa. Se o jogo travar ou se comportar mal, pode ser isso.`;
  }

  async function openCompat(mount, rel, title) {
    const a = await api();
    const r = await a.get_routedex_compat(mount, rel);
    const m = modal({ title: title || rel.split("/").pop(), kicker: "Compatibilidade com o loader" });
    if (!(r && r.success)) {
      m.body.innerHTML = `<p class="pdx-note">${esc(
        (r && r.error) ||
          "O Route Pico não conseguiu ler este arquivo de jogo, então não dá para mostrar o que o loader faz com ele. O arquivo pode estar danificado ou copiado pela metade."
      )}</p>`;
      return;
    }
    const c = r.compat;
    const kind = c.kind;
    const lists = r.lists || {};
    if (!lists.ap && !lists.save && !lists.patch) {
      m.body.innerHTML = `<p class="pdx-note">Os arquivos do loader que esta verificação usa (aplist.bin, savelist.bin, patchlist.bin) não estão em /_pico. A Saúde do cartão mostra quais arquivos do loader faltam.</p>`;
      return;
    }
    const rev = r.rom_version === null || r.rom_version === undefined ? "revisão desconhecida (o loader considera a revisão 0)" : `revisão ${r.rom_version}`;
    let ap;
    if (c.ap.status === "not-applicable") ap = "Não é preciso. O loader pula este passo para homebrew e DSiWare.";
    else if (c.ap.status === "applies") ap = `Corrigido pelo loader ao abrir o jogo (DS Protect ${esc(c.ap.ds_protect_version || "desconhecido")}).`;
    else if (c.ap.status === "version-mismatch") ap = mismatch("fix", c.ap.entry_versions, r.rom_version);
    else if (c.ap.status === "list-unavailable") ap = "O aplist.bin falta em /_pico ou não pode ser lido, então isto não dá para conferir. O loader precisa deste arquivo: veja a Saúde do cartão.";
    else ap = "Não está no aplist.bin. A maioria dos jogos não precisa desta correção.";
    const s = c.save;
    let save;
    if (s.source === "homebrew-none") save = "O loader não cria arquivo de save para homebrew.";
    else if (s.source === "dsiware-header") save = s.size_bytes ? `Salva num .pub de ${fmtBytes(s.size_bytes)}${s.private_size_bytes ? ` e num .prv de ${fmtBytes(s.private_size_bytes)}` : ""} ao lado do jogo.` : "Este jogo DSiWare não salva.";
    else if (s.source === "nand-header") save = `NAND, ${fmtBytes(s.size_bytes)}`;
    else if (s.source === "default") save = "Não está no savelist.bin, então o loader cria um save de 512 KB.";
    else if (s.save_type === "none" || !s.size_bytes) save = "Nenhum: este jogo não salva.";
    else save = `${SAVE_TYPES[s.save_type] || s.save_type}, ${fmtBytes(s.size_bytes)}`;
    let patch;
    if (c.patch.status === "not-applicable") patch = "Não é preciso. O loader não aplica patches em homebrew.";
    else if (c.patch.status === "applies") patch = c.patch.patch_count === 1 ? "1 patch aplicado ao abrir o jogo." : `${c.patch.patch_count} patches aplicados ao abrir o jogo.`;
    else if (c.patch.status === "version-mismatch") patch = mismatch("patch", c.patch.entry_versions, r.rom_version);
    else if (c.patch.status === "list-unavailable") patch = "O patchlist.bin falta em /_pico ou não pode ser lido, então isto não dá para conferir. Versões antigas do Pico Loader não têm este arquivo; atualizar o loader adiciona.";
    else patch = "Não está no patchlist.bin. A maioria dos jogos não precisa de patch.";
    const warn = (st) => (st === "version-mismatch" ? " pdx-compat-row--warn" : "");
    const row = (label, text, hint, cls) => `<div class="pdx-compat-row${cls || ""}"><dt>${label}</dt><dd>${text}<p class="pdx-hint">${hint}</p></dd></div>`;
    m.body.innerHTML = `
      <p class="pdx-meta">${esc(r.game_code)} · ${esc(rev)}${kind !== "retail" ? ` · ${kind === "homebrew" ? "homebrew" : "DSiWare"}` : ""}</p>
      <dl class="pdx-compat">
        ${row("Correção anti-pirataria", ap, HINTS.ap[kind], warn(c.ap.status))}
        ${row("Save", save, HINTS.save[kind])}
        ${row("Patch específico do jogo", patch, HINTS.patch[kind], warn(c.patch.status))}
      </dl>`;
  }

  // ------------------------------------------------------------------ associações de arquivo

  /** Editor de fileAssociations do settings.json (PicoDex AssociationsView). */
  async function renderAssociations(el, mount) {
    if (!el) return;
    const card = (inner) => `<section class="panel p-5 space-y-3"><h3 class="section-label">Associações de arquivo</h3>${inner}</section>`;
    el.innerHTML = card(`<p class="text-[12px] text-fg-mute">Lendo o settings.json…</p>`);
    const a = await api();
    let r;
    try {
      r = await a.get_file_associations(mount);
    } catch (e) {
      r = { success: false, error: e.message || String(e) };
    }
    if (!(r && r.success)) {
      el.innerHTML = card(`<p class="text-[12px] text-danger">${esc((r && r.error) || "Não foi possível ler o cartão.")}</p>`);
      return;
    }
    if (r.problem) {
      el.innerHTML = card(`<div class="note note--warn">${esc(r.problem.message)}${r.problem.detail ? `<p class="pdx-hint">Detalhes: ${esc(r.problem.detail)}</p>` : ""}</div>`);
      return;
    }
    if (!r.exists) {
      el.innerHTML = card(`<div class="note">Não há <code>${esc(r.path)}</code> no cartão. Abra o Pico Launcher uma vez no console para ele criar o arquivo, depois volte aqui.</div>`);
      return;
    }
    const original = r.associations.map((x) => ({ ...x }));
    let draft = r.associations.map((x) => ({ ...x }));
    const dirty = () => JSON.stringify(draft) !== JSON.stringify(original);

    function draw(msg, bad) {
      const rows = draft
        .map(
          (x, i) => `<tr>
            <td><code>.${esc(x.ext)}</code></td>
            <td><input class="field-select w-full" list="pdx-assoc-ex" data-i="${i}" value="${esc(x.app_path)}" aria-label="Aplicativo para arquivos .${esc(x.ext)}"></td>
            <td class="text-right"><button type="button" class="btn-ghost btn-sm" data-rm="${i}" aria-label="Remover a associação .${esc(x.ext)}">Remover</button></td>
          </tr>`
        )
        .join("");
      el.innerHTML = card(`
        <p class="text-[12px] text-fg-mute">Escolha qual aplicativo o launcher abre para cada extensão de arquivo. Fica em <code>${esc(r.path)}</code>; as outras configurações do arquivo não mudam.</p>
        <datalist id="pdx-assoc-ex">${(r.examples || []).map((x) => `<option value="${esc(x)}">`).join("")}</datalist>
        ${
          draft.length
            ? `<table class="pdx-table pdx-assoc"><thead><tr><th>Extensão</th><th>Caminho do aplicativo</th><th></th></tr></thead><tbody>${rows}</tbody></table>`
            : `<p class="text-[12px] text-fg-mute">Nenhuma associação ainda. Adicione uma abaixo.</p>`
        }
        <div class="flex gap-2 flex-wrap items-center">
          <input id="pdx-assoc-ext" class="field-select w-24" placeholder="nes" aria-label="Extensão nova">
          <input id="pdx-assoc-path" class="field-select flex-1 min-w-[14rem]" list="pdx-assoc-ex" placeholder="/_pico/emulators/nesDS.nds" aria-label="Caminho do aplicativo novo">
          <button type="button" class="btn-secondary" id="pdx-assoc-add">Adicionar</button>
        </div>
        <p class="pdx-hint">Digite a extensão sem o ponto. Os caminhos sugeridos vêm dos emuladores do cartão e do guia de emuladores do Pico Launcher.</p>
        <p class="text-[12px] ${bad ? "text-danger" : "text-fg-mute"}" role="status" aria-live="polite">${esc(msg || (dirty() ? "Depois de salvar, as mudanças valem na próxima vez que o Pico Launcher abrir no DS." : ""))}</p>
        <div class="flex gap-2">
          <button type="button" class="btn-primary" id="pdx-assoc-save" ${dirty() ? "" : "disabled"}>Salvar no cartão</button>
          <button type="button" class="btn-ghost" id="pdx-assoc-discard" ${dirty() ? "" : "disabled"}>Descartar mudanças</button>
        </div>`);
      el.querySelectorAll("[data-i]").forEach((inp) => {
        inp.onchange = () => {
          draft[Number(inp.dataset.i)].app_path = inp.value;
          draw();
        };
      });
      el.querySelectorAll("[data-rm]").forEach((b) => {
        b.onclick = () => {
          draft.splice(Number(b.dataset.rm), 1);
          draw();
        };
      });
      el.querySelector("#pdx-assoc-add").onclick = () => {
        const ext = el.querySelector("#pdx-assoc-ext").value.trim().toLowerCase().replace(/^\.+/, "");
        const path = el.querySelector("#pdx-assoc-path").value.trim();
        if (!/^[a-z0-9]{1,8}$/.test(ext)) return draw("Digite as letras da extensão, por exemplo nes.", true);
        if (!path) return draw("Preencha o caminho do aplicativo.", true);
        const i = draft.findIndex((x) => x.ext === ext);
        if (i >= 0) draft[i].app_path = path;
        else draft.push({ ext, app_path: path });
        draft.sort((x, y) => x.ext.localeCompare(y.ext));
        draw();
      };
      el.querySelector("#pdx-assoc-discard").onclick = () => {
        draft = original.map((x) => ({ ...x }));
        draw();
      };
      el.querySelector("#pdx-assoc-save").onclick = async () => {
        if (draft.some((x) => !String(x.app_path || "").trim())) return draw("Os caminhos não podem ficar vazios. Preencha ou remova as linhas em branco.", true);
        const res = await write("set_file_associations", [mount, draft], "Salvando associações…");
        if (res && res.success) {
          appendLog("Associações de arquivo salvas.", "ok");
          renderAssociations(el, mount);
        }
      };
    }
    draw();
  }

  window.R1K = window.R1K || {};
  window.R1K.picodex = { openCoverPicker, openBannerEditor, openStatsEditor, openCompat, renderAssociations, fmtMinutes, modal };
})();
