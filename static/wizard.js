/**
 * Assistente passo a passo — máquina de estados + percursos.
 * Depende de app.js (selectedDrive, fetchDrives, runMountOp, getApi, waitForApi).
 */
const Wizard = (() => {
  const state = {
    goal: null, // flash-update | flash-new | sd-new | sd-update
    brand: null, // gei | r4 | dspico
    stepIndex: 0,
    hasFacebook: null,
    r4Source: null,
    skipNandRisk: false,
    lastError: null,
    inspect: null,
    kernels: null,
  };

  let steps = [];
  // Cada tela monta o assistente no seu host: Softmod (SD do DSi) ou Flashcards (cartucho).
  let hostId = "wizard-root";
  let scope = "dsi";
  // dspico: só «começar do zero» do DSPico, montado dentro da tela Cartão.
  const SCOPE_GOALS = { dsi: ["sd-new", "sd-update"], flash: ["flash-update", "flash-new"], dspico: ["flash-new"] };
  /** Incrementado a cada render(); async helpers abandonam resultados stale. */
  let renderGen = 0;

  function resetFlow() {
    state.goal = null;
    state.brand = null;
    state.stepIndex = 0;
    state.hasFacebook = null;
    state.r4Source = null;
    state.skipNandRisk = false;
    state.lastError = null;
    state.inspect = null;
    state.kernels = null;
    steps = [];
  }

  function init() {
    render();
  }

  function onBusyChange() {
    // Re-render só se estamos em um CTA que muda estado visual
    const root = document.getElementById(hostId);
    if (root && !root.classList.contains("hidden")) {
      // botões já são desabilitados por setBusy
    }
  }

  function onDrivesUpdated() {
    bindDrivePanel();
  }

  function onDriveSelected() {
    bindDrivePanel();
  }

  function goalTitle(goal) {
    return (
      {
        "flash-update": "Atualizar flashcard",
        "flash-new": "Criar flashcard do zero",
        "sd-new": "Instalar softmod no SD do DSi",
        "sd-update": "Atualizar SD do DSi",
      }[goal] || "Assistente"
    );
  }

  function pathBadge(kind) {
    if (kind === "dsi") {
      return `<span class="path-badge path-badge--dsi">SD do DSi</span>`;
    }
    return `<span class="path-badge path-badge--flash">MicroSD do cartucho</span>`;
  }

  function glossBlock(term, body) {
    return `
      <details class="gloss">
        <summary>O que é ${term}?</summary>
        <div class="gloss-body">${body}</div>
      </details>`;
  }

  function writesList(items) {
    return `
      <div>
        <span class="opt-writes-label">Vai escrever no cartão</span>
        <ul class="opt-writes">
          ${items.map((i) => `<li>${i}</li>`).join("")}
        </ul>
      </div>`;
  }

  function buildSteps() {
    if (state.goal === "flash-update") return buildFlashSteps(false);
    if (state.goal === "flash-new") return buildFlashSteps(true);
    if (state.goal === "sd-new") return buildSdNewSteps();
    if (state.goal === "sd-update") return buildSdUpdateSteps();
    return [];
  }

  function buildFlashSteps(fromScratch) {
    const brandLabel =
      state.brand === "gei" ? "GEi" : state.brand === "dspico" ? "DSPico" : "R4";
    const list = [
      {
        id: "brand",
        title: "Qual é o seu flashcard?",
        where: "PC",
        render: renderBrandPick,
      },
      {
        id: "select-card",
        title: "Selecione o MicroSD do cartucho",
        where: "PC",
        render: renderDriveStep({
          warning:
            "Use o MicroSD que fica <strong>dentro do cartucho Slot-1</strong> (não o SD lateral do DSi).",
          nextLabel: "Continuar",
        }),
      },
    ];

    if (fromScratch) {
      list.push({
        id: "format-warn",
        title: "Formatar em FAT32",
        where: "PC",
        render: renderFormatWarn,
      });
      list.push({
        id: "reinsert-format",
        title: "Reinserir o cartão após formatar",
        where: "PC",
        render: renderReinsert({
          text: "Após formatar, o sistema pode mudar o nome/letra do volume. Atualize a lista e selecione o MicroSD de novo.",
        }),
      });
    } else {
      list.push({
        id: "backup",
        title: "Backup recomendado",
        where: "PC",
        render: renderBackupOptional,
      });
    }

    list.push({
      id: "kernel-prep",
      title:
        state.brand === "dspico"
          ? "Preparar pacote DSPico"
          : `Preparar kernel ${brandLabel}`,
      where: "PC",
      render: renderKernelPrep,
    });
    list.push({
      id: "kernel-install",
      title:
        state.brand === "dspico"
          ? "Instalar pacote DSPico"
          : `Instalar kernel ${brandLabel}`,
      where: "PC",
      render: renderKernelInstall,
    });
    list.push({
      id: "roms-opt",
      title:
        state.brand === "dspico"
          ? "Adicionar jogos a Games/ (opcional)"
          : "Organizar jogos (opcional)",
      where: "PC",
      render:
        state.brand === "dspico" ? renderDspicoGamesOptional : renderRomsOptional,
    });
    const doneLines =
      state.brand === "dspico"
        ? [
            "Ejete o MicroSD com segurança no sistema operativo.",
            "Insira-o no cartucho DSPico e o cartucho no DSi/DS.",
            "O microSD já tem Pico Launcher + Loader oficiais LNH.",
            "Depois, copie os jogos na tela <strong>Jogos</strong>; firmware e emunand ficam em <strong>Avançado</strong>.",
          ]
        : [
            "Ejete o MicroSD com segurança no sistema operativo.",
            `Coloque-o no cartucho ${brandLabel} e ligue o DSi/DS.`,
            "Se o menu não abrir, confirme que o kernel é do clone exato do cartucho.",
          ];
    list.push({
      id: "done-flash",
      title: "Pronto",
      where: "PC",
      render: renderDone({ lines: doneLines }),
    });
    return list;
  }

  function buildSdNewSteps() {
    return [
      {
        id: "model",
        title: "É um Nintendo DSi?",
        where: "PC",
        render: renderModelCheck,
      },
      {
        id: "camera",
        title: "Qual versão do app Câmera?",
        where: "PC",
        render: renderCameraPick,
      },
      {
        id: "select-lateral",
        title: "Selecione o SD do slot lateral",
        where: "PC",
        render: renderDriveStep({
          warning:
            "Use o cartão do <strong>slot lateral</strong> do DSi — não o MicroSD de um flashcard Slot-1.",
          nextLabel: "Continuar",
        }),
      },
      {
        id: "dcim-fat",
        title: "Preparar o cartão (DCIM e FAT32)",
        where: "PC",
        render: renderDcimFat,
      },
      {
        id: "stage1",
        title: "Passo 1 — preparar exploit e dumpTool",
        where: "PC",
        render: renderStage1,
      },
      {
        id: "exploit",
        title: "No DSi — abrir o exploit da Câmera",
        where: "DSi",
        render: renderExploitDsi,
      },
      {
        id: "nand-dump",
        title: "No DSi — salvar cópia da memória interna",
        where: "DSi",
        render: renderNandDumpDsi,
      },
      {
        id: "reinsert-nand",
        title: "No PC — verificar a cópia (nand.bin)",
        where: "PC",
        render: renderNandVerify,
      },
      {
        id: "stage2",
        title: "Passo 2 — menu e instalador Unlaunch",
        where: "PC",
        render: renderStage2,
      },
      {
        id: "unlaunch-dsi",
        title: "No DSi — instalar Unlaunch",
        where: "DSi",
        render: renderUnlaunchDsi,
      },
      {
        id: "unlaunch-opts",
        title: "No DSi — inicialização automática no menu",
        where: "DSi",
        render: renderUnlaunchOpts,
      },
      {
        id: "hiya-install",
        title: "hiyaCFW — sistema no cartão (recomendado)",
        where: "PC",
        render: renderHiyaInstall,
      },
      {
        id: "roms-opt",
        title: "Organizar jogos (opcional)",
        where: "PC",
        render: renderRomsOptional,
      },
      {
        id: "done-sd",
        title: "Instalação concluída",
        where: "PC",
        render: renderDone({
          lines: [
            "Ejete o SD com segurança.",
            "Insira-o no slot lateral do DSi e ligue o console.",
            "Se instalou hiyaCFW: Unlaunch A+B → OPTIONS → NO BUTTON → hiyaCFW. Não faça system update.",
            "Sem hiya: deve iniciar no TWiLight (NO BUTTON → BOOT.NDS).",
          ],
        }),
      },
    ];
  }

  function buildSdUpdateSteps() {
    return [
      {
        id: "select-lateral",
        title: "Selecione o SD do slot lateral",
        where: "PC",
        render: renderDriveStep({
          warning:
            "Cartão do <strong>slot lateral</strong> com Unlaunch/TWiLight já instalados.",
          nextLabel: "Inspecionar cartão",
          onNext: async () => {
            const ok = await refreshInspect();
            if (!ok) return false;
            if (!state.inspect?.has_twilight) {
              alert(
                "Não foi encontrado TWiLight Menu++ neste cartão. O assistente vai redirecioná-lo para a instalação completa."
              );
              startGoal("sd-new");
              return false;
            }
            return true;
          },
        }),
      },
      {
        id: "backup",
        title: "Backup recomendado",
        where: "PC",
        render: renderBackupOptional,
      },
      {
        id: "update-twl",
        title: "Atualizar TWiLight Menu++",
        where: "PC",
        render: renderUpdateTwilight,
      },
      {
        id: "hiya-install",
        title: "hiyaCFW (instalar ou atualizar)",
        where: "PC",
        render: renderHiyaInstall,
      },
      {
        id: "roms-opt",
        title: "Organizar jogos / limpar (opcional)",
        where: "PC",
        render: renderRomsAndCleanOptional,
      },
      {
        id: "done-upd",
        title: "Atualização concluída",
        where: "PC",
        render: renderDone({
          lines: [
            "Ejete o SD com segurança e volte a colocá-lo no DSi.",
            "Não é necessário reinstalar o Unlaunch se o console já inicia no menu.",
            "Se instalou/atualizou hiyaCFW: NO BUTTON → hiyaCFW; não faça system update.",
          ],
        }),
      },
    ];
  }

  /* ---------- navigation ---------- */

  function mount(id, sc) {
    if (hostId !== id) {
      const old = document.getElementById(hostId);
      if (old) old.innerHTML = "";
    }
    hostId = id;
    scope = SCOPE_GOALS[sc] ? sc : "dsi";
    if (state.goal && !SCOPE_GOALS[scope].includes(state.goal)) resetFlow();
    render();
  }

  function startGoal(goal) {
    resetFlow();
    state.goal = goal;
    if (scope === "dspico" && goal === "flash-new") {
      state.brand = "dspico";
      steps = buildSteps();
      state.stepIndex = 1; // sem a escolha de marca
      render();
      return;
    }
    if (goal === "flash-update" || goal === "flash-new") {
      steps = [{ id: "brand", title: "Qual é o seu flashcard?", where: "PC", render: renderBrandPick }];
      // brand pick rebuilds full steps when chosen
    } else {
      steps = buildSteps();
    }
    state.stepIndex = 0;
    render();
  }

  function chooseBrand(brand) {
    state.brand = brand;
    steps = buildSteps();
    state.stepIndex = 1; // after brand
    render();
  }

  function goHome() {
    resetFlow();
    render();
  }

  function goBack() {
    if (scope === "dspico" && state.stepIndex <= 1) {
      goHome();
      return;
    }
    if (state.stepIndex <= 0) {
      goHome();
      return;
    }
    state.lastError = null;
    state.stepIndex -= 1;
    render();
  }

  async function goNext() {
    state.lastError = null;
    if (state.stepIndex < steps.length - 1) {
      state.stepIndex += 1;
      render();
    }
  }

  /* ---------- API helpers ---------- */

  async function refreshInspect() {
    if (!selectedDrive) {
      alert("Selecione um cartão SD primeiro.");
      return false;
    }
    const gen = renderGen;
    try {
      const api = getApi() || (await waitForApi());
      if (gen !== renderGen) return false;
      const res = await api.inspect_sd(selectedDrive.mount_path);
      if (gen !== renderGen) return false;
      if (!res.success) {
        state.lastError = res.error || "Falha ao inspecionar.";
        render();
        return false;
      }
      state.inspect = res;
      return true;
    } catch (e) {
      if (gen !== renderGen) return false;
      state.lastError = e.message;
      render();
      return false;
    }
  }

  async function refreshKernels() {
    const gen = renderGen;
    try {
      const api = getApi() || (await waitForApi());
      if (gen !== renderGen) return null;
      const res = await api.probe_kernels();
      if (gen !== renderGen) return null;
      state.kernels = res;
      return res;
    } catch (e) {
      if (gen !== renderGen) return null;
      state.kernels = { success: false, error: e.message, gei: null, r4: [] };
      return state.kernels;
    }
  }

  /* ---------- chrome / render ---------- */

  function render() {
    const root = document.getElementById(hostId);
    if (!root) return;
    renderGen += 1;

    if (!state.goal) {
      root.innerHTML = renderGoalPicker();
      return;
    }

    if (!steps.length) steps = buildSteps();
    const step = steps[state.stepIndex];
    if (!step) {
      goHome();
      return;
    }

    const total = steps.length;
    const idx = state.stepIndex + 1;
    const whereChip =
      step.where === "DSi"
        ? '<span class="chip chip--warn">No DSi</span>'
        : '<span class="chip chip--accent">No PC</span>';

    root.innerHTML = `
      <div class="wizard-chrome space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="text-[11px] font-medium text-fg-mute">
              Etapa ${idx} de ${total} · ${escapeHtml(goalTitle(state.goal))}
            </p>
            <div class="wizard-progress mt-2" aria-hidden="true">
              <div class="wizard-progress-bar" style="width:${(idx / total) * 100}%"></div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            ${whereChip}
            <button type="button" class="btn-ghost !text-[11px]" onclick="Wizard.goHome()">Sair</button>
          </div>
        </div>
        <h2 class="text-[17px] font-semibold text-fg leading-snug">${escapeHtml(step.title)}</h2>
        ${state.lastError ? `<div class="note note--warn"><strong>Erro:</strong> ${escapeHtml(state.lastError)}</div>` : ""}
        <div id="wizard-step-body" class="space-y-4"></div>
        <div class="flex flex-wrap gap-2 pt-1">
          <button type="button" class="btn-ghost" onclick="Wizard.goBack()">Etapa anterior</button>
        </div>
      </div>
    `;

    const body = document.getElementById("wizard-step-body");
    step.render(body);
  }

  function renderGoalPicker() {
    if (scope === "dspico") {
      return `
      <div class="space-y-3">
        <p class="text-[13px] text-fg-soft leading-relaxed max-w-2xl">
          Formata o microSD em FAT32 e instala o pacote oficial do DSPico, passo a passo.
          <strong>Apaga tudo</strong> no cartão; use quando o cartão estiver vazio, corrompido ou cheio de outros sistemas.
        </p>
        <button type="button" class="btn-ghost" onclick="Wizard.startGoal('flash-new')">Começar do zero</button>
      </div>`;
    }
    if (scope === "flash") {
      return `
      <div class="space-y-5">
        <div>
          <h2 class="wizard-title">O que você quer fazer no flashcard?</h2>
          <p class="text-[12px] text-fg-mute mt-1.5 leading-relaxed max-w-2xl">
            Cartucho Slot-1 GEi ou R4. O microSD fica <em>dentro</em> do cartucho, não é o SD lateral do DSi.
            O assistente pergunta a marca e guia cada etapa.
          </p>
        </div>
        <div class="wizard-goal-list">
          ${goalCard(
            "flash-update",
            "Atualizar kernel ou pacote",
            "O microSD já tem o kernel e quer atualizar o GEi ou o R4.",
            "Não formata o cartão."
          )}
          ${goalCard(
            "flash-new",
            "Criar flashcard do zero",
            "MicroSD vazio ou para limpar: formata em FAT32 e instala o kernel/pacote do cartucho.",
            "Formata o cartão (apaga tudo)."
          )}
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <p class="text-[12px] text-fg-mute leading-relaxed">Cartucho DSPico? Ele tem a sua própria tela.</p>
          <button type="button" class="btn-ghost btn-sm" onclick="R1K.shell.go('dspico','cartao')">Abrir Cartão do DSPico</button>
        </div>
      </div>
    `;
    }
    return `
      <div class="space-y-5">
        <div>
          <h2 class="wizard-title">O que você quer fazer no DSi?</h2>
          <p class="text-[12px] text-fg-mute mt-1.5 leading-relaxed max-w-2xl">
            Softmod no cartão do slot lateral: exploit da Câmera, backup, menu TWiLight e Unlaunch.
            DS / DS Lite / 3DS não usam este caminho; para cartuchos, use Flashcards R4/GEi.
          </p>
        </div>
        <div class="wizard-goal-list">
          ${goalCard(
            "sd-new",
            "Instalar softmod completo",
            "Primeira vez: Memory Pit → cópia da memória interna → Unlaunch → hiyaCFW (opcional) → TWiLight.",
            "Inclui escrita na memória interna do console (Unlaunch)."
          )}
          ${goalCard(
            "sd-update",
            "Atualizar menu / hiyaCFW",
            "Já tem Unlaunch e TWiLight: atualizar o menu, hiyaCFW ou organizar jogos.",
            "Não reinstala o Unlaunch."
          )}
        </div>
        <p class="text-[11px] text-fg-mute leading-relaxed">
          Se já souber exatamente o que gravar, use os
          <button type="button" class="text-accent-fg font-medium" onclick="Wizard.openManualSteps()">passos manuais</button>
          abaixo.
        </p>
      </div>
    `;
  }

  function goalCard(id, title, does, note) {
    const risk =
      id === "flash-new" || id === "sd-new"
        ? `<span class="risk-chip">${id === "flash-new" ? "Apaga o cartão" : "Risco Unlaunch"}</span>`
        : "";
    return `
      <button type="button" class="wizard-goal" onclick="Wizard.startGoal('${id}')">
        <span class="wizard-goal-text">
          <span class="wizard-goal-title">${title}${risk}</span>
          <span class="opt-does">${does}</span>
          <span class="opt-when">${note}</span>
        </span>
        <svg class="wizard-goal-chev" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3.5L10.5 8 6 12.5"/></svg>
      </button>
    `;
  }

  /* ---------- step renderers ---------- */

  function renderBrandPick(el) {
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-3">
        ${pathBadge("flash")}
        <p class="text-[12px] text-fg-mute leading-relaxed flex-1 min-w-[12rem]">
          Confirme o nome no plástico ou na PCB. Clones “R4” exigem o kernel <strong>daquele</strong> clone — o errado não inicia.
        </p>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button type="button" class="wizard-goal" onclick="Wizard.chooseBrand('gei')">
          <h3 class="text-[14px] font-semibold">Galaxy Eagle i (GEi)</h3>
          <p class="opt-does">Kernel oficial v4.2 EN (<code>_DS_MENU.DAT</code> + <code>_DS_MSHL.NDS</code>).</p>
          <p class="opt-when">Quando usar: está escrito Galaxy Eagle i / GEi no cartucho.</p>
        </button>
        <button type="button" class="wizard-goal" onclick="Wizard.chooseBrand('r4')">
          <h3 class="text-[14px] font-semibold">R4 / clone R4</h3>
          <p class="opt-does">Copia o firmware do modelo exato a partir de uma pasta em Downloads.</p>
          <p class="opt-when">Quando usar: R4, R4i, etc. Extraia o zip oficial do clone para Downloads.</p>
        </button>
        <button type="button" class="wizard-goal sm:col-span-2${scope === "flash" ? " hidden" : ""}" onclick="Wizard.chooseBrand('dspico')">
          <h3 class="text-[14px] font-semibold">DSPico</h3>
          <p class="opt-does">Pico Launcher + Loader oficiais no microSD (<code>_picoboot.nds</code>, <code>_pico/</code>).</p>
          <p class="opt-when">Quando usar: cartucho RP2040 (LNH Team). O <code>.uf2</code> do cartucho deve <strong>já</strong> estar gravado fora deste app.</p>
        </button>
      </div>
      <div class="note note--warn mt-3">
        AceKard e outros cartuchos não suportados neste assistente — use o firmware do fabricante.
      </div>
    `;
  }

  function renderDriveStep({ warning, nextLabel, onNext }) {
    return (el) => {
      el.innerHTML = `
        <div class="note note--warn">${warning}</div>
        ${drivePanelHtml()}
        <button type="button" class="btn-primary wizard-cta" id="wiz-drive-next">${nextLabel || "Continuar"}</button>
      `;
      bindDrivePanel();
      document.getElementById("wiz-drive-next").onclick = async () => {
        if (!selectedDrive) {
          alert("Selecione um cartão SD primeiro.");
          return;
        }
        if (onNext) {
          const ok = await onNext();
          if (!ok) return;
        }
        goNext();
      };
    };
  }

  function driveSummaryText() {
    if (typeof selectedDrive === "undefined" || !selectedDrive) {
      return "Nenhum cartão escolhido. Conecte o SD e escolha-o na barra de cima.";
    }
    const d = selectedDrive;
    return `${d.name || d.mount_path} · ${d.fs_type || "?"} · ${d.total_size_gb} GB (livre ${d.free_size_gb} GB)`;
  }

  function drivePanelHtml() {
    return `
      <section class="panel p-4 drive-panel" id="wizard-drive-panel">
        <h3 class="section-label">Cartão SD</h3>
        <p id="wizard-drive-summary" class="text-[13px] text-fg mt-1">${escapeHtml(driveSummaryText())}</p>
        <p class="text-[11px] text-fg-mute mt-1">Para trocar de cartão, use o seletor na barra de cima.</p>
      </section>
    `;
  }

  function bindDrivePanel() {
    const el = document.getElementById("wizard-drive-summary");
    if (el) el.textContent = driveSummaryText();
  }

  function renderFormatWarn(el) {
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">
        ${pathBadge("flash")}
        <span class="risk-chip">Apaga tudo</span>
      </div>
      <p class="opt-does">
        Formata o MicroSD em <strong>FAT32</strong> (MBR, cluster 32&nbsp;KB), o formato esperado por flashcards e pela Câmera do DSi.
      </p>
      ${glossBlock(
        "FAT32",
        "Sistema de arquivos do cartão. A Câmera do DSi e a maioria dos flashcards só funcionam bem em FAT32 (não exFAT)."
      )}
      <div class="note note--warn mt-3">
        <strong>Atenção:</strong> formatar apaga <em>todos</em> os dados do volume selecionado.
        Confirme que é o MicroSD do cartucho — não o disco do sistema. No Windows pode ser necessário Administrador.
      </div>
      ${drivePanelHtml()}
      <ol class="guide-list list-decimal">
        <li>Confirme o volume selecionado abaixo.</li>
        <li>Clique em Formatar FAT32 e confirme o diálogo.</li>
        <li>Aguarde terminar — depois será preciso selecionar a unidade de novo.</li>
      </ol>
      <button type="button" class="btn-primary wizard-cta btn-primary--ok" id="wiz-format">Formatar FAT32 (apaga o cartão)</button>
    `;
    bindDrivePanel();
    document.getElementById("wiz-format").onclick = async () => {
      const res = await confirmFormat();
      if (res && res.success) goNext();
    };
  }

  function renderReinsert({ text }) {
    return (el) => {
      el.innerHTML = `
        <p class="text-[12px] text-fg-mute leading-relaxed">${text}</p>
        ${drivePanelHtml()}
        <button type="button" class="btn-primary wizard-cta" id="wiz-reinsert-next">Cartão selecionado — continuar</button>
      `;
      bindDrivePanel();
      document.getElementById("wiz-reinsert-next").onclick = () => {
        if (!selectedDrive) {
          alert("Atualize a lista e selecione o cartão.");
          return;
        }
        goNext();
      };
    };
  }

  function renderBackupOptional(el) {
    el.innerHTML = `
      <p class="opt-does">
        Copia o conteúdo do cartão para a Área de Trabalho antes de gravar. Recomendado se já tiver jogos ou saves.
      </p>
      <p class="opt-when">Pode pular se o cartão estiver vazio ou se já tiver cópia em outro lugar.</p>
      ${drivePanelHtml()}
      <div class="flex flex-col sm:flex-row gap-2">
        <button type="button" class="btn-primary wizard-cta" id="wiz-backup">Fazer backup para o Desktop</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-backup-skip">Pular backup</button>
      </div>
    `;
    bindDrivePanel();
    document.getElementById("wiz-backup").onclick = async () => {
      const res = await runMountOp({ method: "backup" });
      if (res.success) goNext();
    };
    document.getElementById("wiz-backup-skip").onclick = () => goNext();
  }

  function renderKernelPrep(el) {
    const isGei = state.brand === "gei";
    const isDspico = state.brand === "dspico";

    if (isDspico) {
      el.innerHTML = `
        <div class="flex items-center gap-2 flex-wrap mb-2">${pathBadge("flash")}</div>
        <p class="opt-does">
          O app baixa automaticamente o <strong>Pico Launcher</strong> e o <strong>Pico Loader DSPICO</strong>
          oficiais (SHA-256 pinado) e monta <code>_picoboot.nds</code> + <code>_pico/</code> no microSD.
        </p>
        <div class="note note--warn">
          O firmware <code>.uf2</code> do cartucho deve já estar gravado (fora deste assistente). Este passo só prepara o microSD.
        </div>
        <ol class="guide-list list-decimal">
          <li>Confirme que selecionou o MicroSD do cartucho DSPico.</li>
          <li>Continue para escrever o pacote no cartão.</li>
        </ol>
        <button type="button" class="btn-primary wizard-cta" id="wiz-kernel-next">Continuar para instalar</button>
      `;
      document.getElementById("wiz-kernel-next").onclick = () => goNext();
      return;
    }

    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">${pathBadge("flash")}</div>
      ${
        isGei
          ? `<div class="note">
              O kernel <strong>GEi v4.2 EN</strong> é do fabricante do cartucho e não vem com o Route Pico.
              Baixe o pacote oficial no site do fabricante, extraia e deixe a pasta <code>GEiv4.2_EN</code> em Downloads; o app usa os arquivos de lá.
            </div>
            <ol class="guide-list list-decimal">
              <li>Confirme que o cartucho é Galaxy Eagle i / GEi.</li>
              <li>Clique em Verificar pacote.</li>
            </ol>`
          : `<div class="note">
              O app <strong>não baixa</strong> o kernel R4 automaticamente (risco de firmware errado).
              Extraia o zip oficial do seu clone para a pasta <code>Downloads</code>.
            </div>
            <ol class="guide-list list-decimal">
              <li>Extraia o firmware <strong>exato</strong> do seu clone R4 para Downloads.</li>
              <li>A pasta deve ter arquivos como <code>_DS_MENU.DAT</code>, <code>R4.dat</code> ou semelhantes — sem jogos.</li>
              <li>Clique em Procurar e escolha a pasta correta se houver várias.</li>
            </ol>`
      }
      <div id="wiz-kernel-status" class="text-[12px] text-fg-mute">Ainda não procurado.</div>
      <div class="flex flex-col sm:flex-row gap-2">
        <button type="button" class="btn-secondary wizard-cta" id="wiz-probe">${
          isGei ? "Verificar pacote GEi" : "Procurar em Downloads"
        }</button>
        <button type="button" class="btn-primary wizard-cta" id="wiz-kernel-next" disabled>Continuar</button>
      </div>
    `;
    const next = document.getElementById("wiz-kernel-next");
    const status = document.getElementById("wiz-kernel-status");

    async function probe() {
      const gen = renderGen;
      const res = await refreshKernels();
      if (gen !== renderGen || !res || !status.isConnected) return;
      if (isGei) {
        if (res.gei) {
          const where = res.gei.bundled
            ? "incluído no app"
            : escapeHtml(res.gei.path || "");
          status.innerHTML = `<span class="text-ok">GEi pronto (${where}).</span>`;
          next.disabled = false;
        } else {
          status.innerHTML =
            '<span class="text-warn">Pacote GEi incompleto (faltam <code>_DS_MENU.DAT</code> / <code>_DS_MSHL.NDS</code>).</span>';
          next.disabled = true;
        }
      } else {
        const list = res.r4 || [];
        if (!list.length) {
          status.innerHTML =
            '<span class="text-warn">Nenhuma pasta R4 candidata em Downloads.</span>';
          next.disabled = true;
          return;
        }
        status.innerHTML =
          `<p class="mb-2">Pastas encontradas:</p>` +
          list
            .map(
              (k, i) => `
            <label class="choice mb-2">
              <input type="radio" name="r4-src" value="${escapeHtml(k.path)}" ${i === 0 ? "checked" : ""}>
              <span>
                <span class="choice-title">${escapeHtml(k.name)}</span>
                <span class="choice-sub">${escapeHtml(k.path)} · ${(k.files || []).length} arquivos, ${(k.dirs || []).length} pastas</span>
              </span>
            </label>`
            )
            .join("");
        state.r4Source = list[0].path;
        status.querySelectorAll('input[name="r4-src"]').forEach((inp) => {
          inp.addEventListener("change", () => {
            state.r4Source = inp.value;
          });
        });
        next.disabled = false;
      }
    }

    document.getElementById("wiz-probe").onclick = probe;
    next.onclick = () => {
      if (!isGei) {
        const sel = document.querySelector('input[name="r4-src"]:checked');
        state.r4Source = sel ? sel.value : state.r4Source;
        if (!state.r4Source) {
          alert("Escolha a pasta do kernel R4.");
          return;
        }
      }
      goNext();
    };
    probe();
  }

  function renderKernelInstall(el) {
    const isGei = state.brand === "gei";
    const isDspico = state.brand === "dspico";
    const writes = isDspico
      ? [
          "<code>_picoboot.nds</code> e pasta <code>_pico/</code> (Pico Launcher + Loader)",
          "Pasta <code>Games/</code> para ROMs (se ainda não existir)",
        ]
      : isGei
        ? [
            "<code>_DS_MENU.DAT</code> e <code>_DS_MSHL.NDS</code> (kernel GEi v4.2 EN)",
            "Arquivos auxiliares do pacote oficial na raiz do microSD",
          ]
        : [
            "Arquivos do kernel R4 da pasta escolhida (marcadores do clone)",
            "Não copia pastas <code>roms/</code> da origem",
          ];
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">${pathBadge("flash")}</div>
      <p class="opt-does">
        ${
          isDspico
            ? "Baixa (se necessário), verifica e copia o pacote DSPico oficial para o MicroSD do cartucho."
            : "Copia e verifica os arquivos do kernel para o MicroSD selecionado."
        }
      </p>
      ${writesList(writes)}
      ${
        isDspico
          ? `<div class="note note--warn">O firmware <code>.uf2</code> do cartucho não é gravado aqui — só o conteúdo do microSD.</div>`
          : ""
      }
      ${drivePanelHtml()}
      ${
        !isGei && !isDspico
          ? `<div class="note">Origem: <code>${escapeHtml(state.r4Source || "—")}</code></div>`
          : ""
      }
      <button type="button" class="btn-primary wizard-cta" id="wiz-install-k">
        ${
          isDspico
            ? "Escrever pacote DSPico no microSD"
            : isGei
              ? "Escrever kernel GEi no microSD"
              : "Escrever kernel R4 no microSD"
        }
      </button>
    `;
    bindDrivePanel();
    document.getElementById("wiz-install-k").onclick = async () => {
      let res;
      if (isDspico) {
        res = await runMountOp({ method: "setup_dspico" });
      } else if (isGei) {
        res = await runMountOp({ method: "setup_gei" });
      } else {
        res = await runMountOp({ method: "setup_r4", sourceDir: state.r4Source });
      }
      if (res.success) {
        alert(
          isDspico
            ? "MicroSD DSPico pronto. Ejete com segurança e coloque-o no cartucho."
            : "Kernel instalado. Ejetar o cartão com segurança quando terminar as etapas seguintes."
        );
        goNext();
      } else {
        state.lastError = res.error || "Falha na instalação.";
        render();
      }
    };
  }

  function renderHiyaInstall(el) {
    el.innerHTML = `
      <div class="note">Inspecionando o cartão…</div>
    `;
    (async () => {
      const gen = renderGen;
      await refreshInspect();
      if (gen !== renderGen || !el.isConnected) return;

      const hasHiya = !!(state.inspect && state.inspect.has_hiya);
      const dumps = (state.inspect && state.inspect.nand_dumps) || [];
      const plausible = dumps.filter((d) => d && d.plausible);
      const nandHint = plausible.length
        ? `Cópia no cartão: <code>${escapeHtml(plausible[0].rel_path)}</code> (${escapeHtml(String(plausible[0].size_mb))} MiB)`
        : "Sem <code>DT*/nand.bin</code> no cartão — copie o dump para o SD ou volte a fazer o dump no DSi.";

      el.innerHTML = `
        <div class="flex items-center gap-2 flex-wrap mb-2">
          ${pathBadge("dsi")}
          <span class="opt-tech">hiyaCFW · SDNAND</span>
        </div>
        <p class="opt-does">
          Monta uma cópia do sistema do DSi <strong>no cartão</strong> a partir do <code>nand.bin</code>.
          O app <strong>não</strong> grava na memória interna do console.
        </p>
        <p class="opt-when">Quando usar: depois do Unlaunch, com dump válido e ~512&nbsp;MB livres. Pode demorar vários minutos.</p>
        ${glossBlock(
          "hiyaCFW",
          "Permite rodar o menu do sistema a partir do SD (SDNAND), em vez de só da memória interna. Requer Unlaunch e o dump que fez com o dumpTool."
        )}
        ${glossBlock(
          "NAND",
          "Memória interna do DSi. O arquivo <code>nand.bin</code> é a backup (~240&nbsp;MiB) feita pelo dumpTool."
        )}
        ${writesList([
          "Árvore SDNAND e <code>hiya.dsi</code> (pipeline TWLMagician pinado)",
          "Não altera a SysNAND / Unlaunch já instalado",
        ])}
        <p class="text-[12px] text-fg-mute leading-relaxed">${nandHint}</p>
        ${drivePanelHtml()}
        <div class="flex flex-col sm:flex-row gap-2 flex-wrap">
          <button type="button" class="btn-primary wizard-cta btn-primary--ok" id="wiz-hiya" ${
            plausible.length || hasHiya ? "" : "disabled"
          }>
            ${hasHiya && !plausible.length ? "Atualizar hiyaCFW no SD" : "Escrever hiyaCFW no SD"}
          </button>
          <button type="button" class="btn-secondary wizard-cta" id="wiz-hiya-skip">Pular hiyaCFW</button>
        </div>
        <div class="note note--ok mt-3">
          Depois no DSi: Unlaunch <strong>A+B</strong> → OPTIONS → <strong>NO BUTTON</strong> → hiyaCFW.
          Não faça system update.
        </div>
      `;
      bindDrivePanel();
      document.getElementById("wiz-hiya-skip").onclick = () => goNext();
      document.getElementById("wiz-hiya").onclick = async () => {
        const nandRel = plausible.length ? plausible[0].rel_path : "";
        const res = await runMountOp({
          method: "setup_hiya",
          nandRelPath: nandRel,
          updateOnly: hasHiya && !plausible.length,
        });
        if (res && res.success) {
          alert(
            "hiyaCFW no SD. Configure Unlaunch: NO BUTTON → hiyaCFW. Não atualize o sistema."
          );
          goNext();
        } else if (res && res.error !== "cancelled") {
          state.lastError = (res && res.error) || "Falha na instalação hiyaCFW.";
          render();
        }
      };
    })();
  }

  function organizeLayoutChoicesHtml(namePrefix) {
    const name = namePrefix || "wiz-organize-layout";
    return `
      <p class="text-[11px] font-medium text-fg-soft mb-2">Como organizar</p>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
        <label class="choice">
          <input type="radio" name="${name}" value="console" checked>
          <span>
            <span class="choice-title">Por console</span>
            <span class="choice-sub"><code>/roms/nds/</code></span>
          </span>
        </label>
        <label class="choice">
          <input type="radio" name="${name}" value="franchise">
          <span>
            <span class="choice-title">Por franquia</span>
            <span class="choice-sub"><code>/roms/Pokemon/</code>…</span>
          </span>
        </label>
        <label class="choice">
          <input type="radio" name="${name}" value="both">
          <span>
            <span class="choice-title">Console + franquia</span>
            <span class="choice-sub"><code>/roms/nds/Pokemon/</code></span>
          </span>
        </label>
      </div>`;
  }

  function selectedOrganizeLayout(namePrefix) {
    const name = namePrefix || "wiz-organize-layout";
    return (
      document.querySelector(`input[name="${name}"]:checked`)?.value || "console"
    );
  }

  function renderRomsOptional(el) {
    el.innerHTML = `
      <p class="opt-does">
        Se já copiou jogos para o cartão, organiza-os conforme a opção abaixo (cria pastas e remove as vazias). Saves e estados GameYob vão com o jogo. Apps em <code>/roms/apps/</code>.
      </p>
      <p class="opt-when">Pode pular e copiar os jogos depois — esta etapa é opcional.</p>
      ${drivePanelHtml()}
      ${organizeLayoutChoicesHtml("wiz-organize-layout")}
      <div class="flex flex-col sm:flex-row gap-2">
        <button type="button" class="btn-primary wizard-cta" id="wiz-roms">Organizar jogos no cartão</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-roms-skip">Pular</button>
      </div>
    `;
    bindDrivePanel();
    document.getElementById("wiz-roms").onclick = async () => {
      const res = await runMountOp({
        method: "organize_roms",
        layout: selectedOrganizeLayout("wiz-organize-layout"),
      });
      if (res.success || res.error === "cancelled") {
        if (res.success) goNext();
      }
    };
    document.getElementById("wiz-roms-skip").onclick = () => goNext();
  }

  function renderDspicoGamesOptional(el) {
    el.innerHTML = `
      <p class="opt-does">
        O Pico Launcher navega o cartão como browser de arquivos. O kit usa a pasta
        <code>Games/</code> na raiz do microSD (recomendado pelo GUIDE LNH).
      </p>
      <p class="opt-when">Opcional: pode pular e adicionar os jogos depois na tela <strong>Jogos</strong>.</p>
      ${drivePanelHtml()}
      <div class="flex flex-col sm:flex-row gap-2 flex-wrap">
        <button type="button" class="btn-primary wizard-cta" id="wiz-dspico-games">Adicionar jogos a Games/</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-roms-skip">Pular</button>
        <button type="button" class="btn-ghost wizard-cta" id="wiz-open-dspico">Abrir Jogos</button>
      </div>
    `;
    bindDrivePanel();
    document.getElementById("wiz-dspico-games").onclick = async () => {
      try {
        const api = getApi() || (await waitForApi());
        const picked = await api.pick_dspico_rom_files();
        if (!(picked && picked.success) || picked.cancelled) return;
        const paths = picked.paths || [];
        if (!paths.length) return;
        setBusy(true);
        try {
          const mount =
            (typeof selectedDrive !== "undefined" &&
              selectedDrive &&
              selectedDrive.mount_path) ||
            null;
          if (!mount) {
            alert("Selecione o microSD primeiro.");
            return;
          }
          const res = await api.import_dspico_games(mount, paths, "");
          if (res && res.success) {
            appendLog(res.message || "Jogos importados.", "success");
            goNext();
          } else {
            appendLog((res && res.error) || "Falha ao importar.", "error");
          }
        } finally {
          setBusy(false);
        }
      } catch (e) {
        appendLog(e.message || String(e), "error");
      }
    };
    document.getElementById("wiz-roms-skip").onclick = () => goNext();
    document.getElementById("wiz-open-dspico").onclick = () => {
      if (window.R1K && R1K.shell) R1K.shell.go("dspico", "games");
    };
  }

  function renderRomsAndCleanOptional(el) {
    el.innerHTML = `
      <p class="opt-does">Opcional: organizar ROMs ou limpar arquivos lixo do macOS (<code>._*</code>, <code>.DS_Store</code>).</p>
      ${drivePanelHtml()}
      ${organizeLayoutChoicesHtml("wiz-organize-layout-clean")}
      <div class="flex flex-col sm:flex-row gap-2 flex-wrap">
        <button type="button" class="btn-primary wizard-cta" id="wiz-roms">Organizar jogos</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-clean">Limpar metadados</button>
        <button type="button" class="btn-ghost wizard-cta" id="wiz-roms-skip">Continuar sem alterar</button>
      </div>
    `;
    bindDrivePanel();
    document.getElementById("wiz-roms").onclick = async () => {
      await runMountOp({
        method: "organize_roms",
        layout: selectedOrganizeLayout("wiz-organize-layout-clean"),
      });
    };
    document.getElementById("wiz-clean").onclick = async () => {
      await runMountOp({ method: "clean_sd" });
    };
    document.getElementById("wiz-roms-skip").onclick = () => goNext();
  }

  function renderDone({ lines }) {
    return (el) => {
      el.innerHTML = `
        <div class="note note--ok">
          <strong>Concluído.</strong>
        </div>
        <ol class="guide-list list-decimal">
          ${lines.map((l) => `<li>${l}</li>`).join("")}
        </ol>
        <button type="button" class="btn-primary wizard-cta" onclick="Wizard.goHome()">Voltar ao início</button>
      `;
    };
  }

  function renderModelCheck(el) {
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">${pathBadge("dsi")}</div>
      <p class="opt-does">
        Este softmod (exploit da Câmera + Unlaunch) só funciona em <strong>Nintendo DSi</strong> ou <strong>DSi XL / LL</strong>
        (etiqueta <code>TWL-001</code> ou <code>UTL-001</code>).
      </p>
      <div class="note note--warn">
        DS, DS Lite, 3DS e DSi de desenvolvimento <strong>não</strong> são suportados aqui.
        Nas etapas longas, mantenha a bateria carregada (LED não vermelho).
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <button type="button" class="btn-primary wizard-cta" id="wiz-dsi-yes">Sim — é um DSi / DSi XL</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-dsi-no">Não — outro modelo</button>
      </div>
    `;
    document.getElementById("wiz-dsi-yes").onclick = () => goNext();
    document.getElementById("wiz-dsi-no").onclick = () => {
      alert(
        "Este assistente não se aplica ao seu modelo. Consulte guias específicos para DS Lite / 3DS."
      );
      goHome();
    };
  }

  function renderCameraPick(el) {
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">${pathBadge("dsi")}</div>
      <p class="opt-does">
        Isto escolhe o arquivo do exploit (<strong>Memory Pit</strong>) — <em>não</em> é sobre rede social.
        No DSi, abra a Câmera e veja se aparece o ícone do Facebook na barra inferior.
      </p>
      ${glossBlock(
        "Memory Pit",
        "Exploit que abre ao ver o Álbum da Câmera com o cartão SD. O arquivo <code>pit.bin</code> precisa corresponder à versão do app Câmera (com ou sem Facebook)."
      )}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3">
        <label class="choice">
          <input type="radio" name="wiz-cam" value="facebook">
          <span>
            <span class="choice-title">Com Facebook</span>
            <span class="choice-sub">Típico 1.4+ EUA / Europa</span>
          </span>
        </label>
        <label class="choice">
          <input type="radio" name="wiz-cam" value="no-facebook">
          <span>
            <span class="choice-title">Sem Facebook</span>
            <span class="choice-sub">1.0–1.3 / maioria JP</span>
          </span>
        </label>
      </div>
      <button type="button" class="btn-primary wizard-cta mt-2" id="wiz-cam-next">Continuar com esta versão</button>
    `;
    document.getElementById("wiz-cam-next").onclick = () => {
      const v = document.querySelector('input[name="wiz-cam"]:checked')?.value;
      if (!v) {
        alert("Escolha se a câmera tem ou não Facebook.");
        return;
      }
      state.hasFacebook = v === "facebook";
      goNext();
    };
  }

  function renderDcimFat(el) {
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">${pathBadge("dsi")}</div>
      <p class="opt-does">
        A Câmera precisa de <strong>FAT32</strong>. A pasta <code>DCIM</code> na raiz bloqueia o exploit —
        o assistente pode renomeá-la (as fotos <strong>não</strong> são apagadas).
      </p>
      ${drivePanelHtml()}
      <div id="wiz-dcim-status" class="text-[12px] text-fg-mute">Clique em Verificar.</div>
      <div class="flex flex-col sm:flex-row gap-2 flex-wrap">
        <button type="button" class="btn-secondary wizard-cta" id="wiz-check">Verificar cartão</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-dcim" disabled>Mover pasta DCIM</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-fmt" disabled>Formatar FAT32</button>
        <button type="button" class="btn-primary wizard-cta" id="wiz-dcim-next" disabled>Cartão pronto — continuar</button>
      </div>
    `;
    bindDrivePanel();
    const status = document.getElementById("wiz-dcim-status");
    const btnDcim = document.getElementById("wiz-dcim");
    const btnFmt = document.getElementById("wiz-fmt");
    const btnNext = document.getElementById("wiz-dcim-next");

    async function check() {
      const gen = renderGen;
      const ok = await refreshInspect();
      if (gen !== renderGen || !ok || !status.isConnected) return;
      const i = state.inspect;
      let msgs = [];
      msgs.push(`Sistema: ${i.fs_type} ${i.is_fat32 ? "(FAT32 OK)" : "(precisa FAT32)"}`);
      if (i.over_32gb) {
        msgs.push(
          "Aviso: cartão &gt;32 GB — a Câmera/Unlaunch podem falhar; preferir SDHC até 32 GB."
        );
      }
      if (i.has_dcim) {
        msgs.push("Pasta DCIM na raiz — deve ser movida antes do Passo 1.");
        btnDcim.disabled = false;
      } else {
        btnDcim.disabled = true;
      }
      btnFmt.disabled = !!i.is_fat32;
      const ready = i.is_fat32 && !i.has_dcim;
      btnNext.disabled = !ready;
      status.innerHTML = msgs.map((m) => `<div>${m}</div>`).join("");
    }

    document.getElementById("wiz-check").onclick = check;
    btnDcim.onclick = async () => {
      const res = await runMountOp({ method: "quarantine_dcim" });
      if (res.success) await check();
    };
    btnFmt.onclick = async () => {
      const res = await confirmFormat();
      if (res && res.success) {
        alert("Cartão formatado. Atualize a lista, selecione de novo e Verifique.");
        await fetchDrives();
        await check();
      }
    };
    btnNext.onclick = () => goNext();
    check();
  }

  function renderStage1(el) {
    const fb =
      state.hasFacebook === true
        ? "Com Facebook"
        : state.hasFacebook === false
          ? "Sem Facebook"
          : "?";
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">
        ${pathBadge("dsi")}
        <span class="chip chip--accent">Passo 1</span>
      </div>
      <p class="opt-does">
        Prepara o SD para o exploit da Câmera e o programa que guarda a cópia da memória interna (dumpTool).
        Na 1ª vez precisa de Internet (downloads pinados).
      </p>
      ${glossBlock(
        "Memory Pit",
        "O arquivo <code>pit.bin</code> escolhido pela versão da Câmera (${fb}). Pit errado = Álbum normal, sem exploit."
      )}
      ${writesList([
        `<code>pit.bin</code> do Memory Pit (${fb})`,
        "<code>boot.nds</code> — dumpTool",
        "<code>unlaunch-installer.dsi</code> (preparado para o Passo 2)",
      ])}
      ${drivePanelHtml()}
      <button type="button" class="btn-primary wizard-cta" id="wiz-s1">Escrever Passo 1 no SD</button>
    `;
    bindDrivePanel();
    document.getElementById("wiz-s1").onclick = async () => {
      if (state.hasFacebook === null) {
        alert("Volte e escolha a versão da câmera.");
        return;
      }
      const res = await runMountOp({
        method: "setup_nand_dump",
        hasFacebook: state.hasFacebook,
      });
      if (res.success) {
        alert(
          "Passo 1 concluído. Ejete o SD com segurança e coloque-o no slot lateral do DSi."
        );
        goNext();
      } else {
        state.lastError = res.error || "Falha no Passo 1.";
        render();
      }
    };
  }

  function renderExploitDsi(el) {
    el.innerHTML = `
      <ol class="guide-list list-decimal">
        <li>Insira o SD no <strong>slot lateral</strong> do DSi e ligue o console.</li>
        <li>Abra a <strong>Câmera Nintendo DSi</strong>.</li>
        <li>Toque no ícone do <strong>cartão SD</strong> (canto superior direito).</li>
        <li>Abra o <strong>Álbum</strong> com o botão grande à direita.</li>
      </ol>
      <div class="space-y-2">
        <div class="note note--ok"><strong>Tela magenta</strong> — exploit correto; deve aparecer o dumpTool.</div>
        <div class="note note--warn"><strong>Tela verde</strong> — falta <code>boot.nds</code>. Volte ao PC e refaça o Passo 1.</div>
        <div class="note"><strong>Álbum normal</strong> — pit errado (Facebook) ou ainda existe pasta <code>DCIM</code>.</div>
      </div>
      <button type="button" class="btn-primary wizard-cta" id="wiz-exploit-next">Já abriu o dumpTool</button>
    `;
    document.getElementById("wiz-exploit-next").onclick = () => goNext();
  }

  function renderNandDumpDsi(el) {
    el.innerHTML = `
      <p class="opt-does">
        O dumpTool grava uma cópia da memória interna (~240&nbsp;MiB) em uma pasta <code>DT…</code> no SD.
        Salve-a depois em outro lugar — é a sua rede de segurança antes do Unlaunch.
      </p>
      ${glossBlock(
        "NAND",
        "Memória interna do DSi. O Unlaunch grava nesta memória; o dump (<code>nand.bin</code>) permite recuperar ou instalar hiyaCFW."
      )}
      <ol class="guide-list list-decimal">
        <li>No dumpTool, pressione <strong>A</strong> para iniciar o backup (~7 minutos).</li>
        <li><strong>Não desligue</strong> o console nem retire o SD.</li>
        <li>Quando terminar, pressione <strong>START</strong> e desligue o DSi.</li>
      </ol>
      <div class="note note--warn">Copie a pasta DT… para o Desktop no próximo passo, se ainda não o fez.</div>
      <button type="button" class="btn-primary wizard-cta" id="wiz-nand-next">Já terminei o dump — vou ao PC</button>
    `;
    document.getElementById("wiz-nand-next").onclick = () => goNext();
  }

  function renderNandVerify(el) {
    el.innerHTML = `
      <p class="opt-does">
        Volte a inserir o SD no PC e confirme que existe <code>DT…/nand.bin</code> (~240&nbsp;MB) antes de continuar.
      </p>
      ${drivePanelHtml()}
      <div id="wiz-nand-status" class="text-[12px] text-fg-mute">Ainda não verificado.</div>
      <label class="choice mt-2">
        <input type="checkbox" id="wiz-nand-risk">
        <span>
          <span class="choice-title text-warn">Avançar sem dump neste cartão (risco)</span>
          <span class="choice-sub">Só se já tiver nand.bin em outro lugar. Não recomendado.</span>
        </span>
      </label>
      <div class="flex flex-col sm:flex-row gap-2 mt-2">
        <button type="button" class="btn-secondary wizard-cta" id="wiz-nand-check">Verificar dump no SD</button>
        <button type="button" class="btn-primary wizard-cta" id="wiz-nand-go" disabled>Continuar</button>
      </div>
    `;
    bindDrivePanel();
    const status = document.getElementById("wiz-nand-status");
    const go = document.getElementById("wiz-nand-go");
    const risk = document.getElementById("wiz-nand-risk");

    function updateGate() {
      const has = state.inspect?.has_nand_dump;
      go.disabled = !(has || risk.checked);
    }

    document.getElementById("wiz-nand-check").onclick = async () => {
      const gen = renderGen;
      const ok = await refreshInspect();
      if (gen !== renderGen || !ok || !status.isConnected) return;
      const dumps = state.inspect.nand_dumps || [];
      if (state.inspect.has_nand_dump) {
        status.innerHTML = dumps
          .map(
            (d) =>
              `<div class="text-ok">Encontrado ${escapeHtml(d.folder)}/nand.bin (${d.size_mb} MB)${d.has_sha1 ? " + sha1" : ""}</div>`
          )
          .join("");
        status.innerHTML +=
          '<p class="mt-1 text-fg-mute">Copie a pasta DT… para o Desktop antes de continuar, se ainda não o fez.</p>';
      } else if (dumps.length) {
        status.innerHTML =
          '<span class="text-warn">Pasta DT encontrada mas nand.bin parece incompleto.</span>';
      } else {
        status.innerHTML =
          '<span class="text-warn">Nenhum DT…/nand.bin encontrado. Repita o dump no DSi.</span>';
      }
      updateGate();
    };
    risk.onchange = updateGate;
    go.onclick = () => {
      state.skipNandRisk = risk.checked && !state.inspect?.has_nand_dump;
      goNext();
    };
  }

  function renderStage2(el) {
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">
        ${pathBadge("dsi")}
        <span class="chip chip--ok">Passo 2</span>
      </div>
      <p class="opt-does">
        Coloca o menu de jogos (TWiLight Menu++) e o instalador seguro do Unlaunch no SD.
        Na 1ª vez precisa de Internet.
      </p>
      ${glossBlock(
        "Unlaunch",
        "Bootloader permanente na memória interna do DSi. É a <strong>única</strong> etapa deste kit que grava no console — há um risco pequeno de brick; só avance com o dump feito."
      )}
      ${writesList([
        "TWiLight Menu++ (<code>BOOT.NDS</code>, pasta <code>_nds/</code>, …)",
        "<code>unlaunch-installer.dsi</code> na raiz",
        "dumpTool movido para <code>dumptool.nds</code> (se existir)",
      ])}
      <div class="note note--warn">
        Se o firmware do DSi for exatamente <strong>1.4.2</strong>, o guia oficial recomenda atualizar o sistema nas Configurações antes do Unlaunch. Não automatizamos esse passo.
      </div>
      ${drivePanelHtml()}
      <button type="button" class="btn-primary wizard-cta btn-primary--ok" id="wiz-s2">Escrever Passo 2 no SD</button>
    `;
    bindDrivePanel();
    document.getElementById("wiz-s2").onclick = async () => {
      const res = await runMountOp({ method: "setup_unlaunch" });
      if (res.success) {
        alert("Passo 2 concluído. Ejete o SD e coloque-o no DSi.");
        goNext();
      } else {
        state.lastError = res.error || "Falha no Passo 2.";
        render();
      }
    };
  }

  function renderUnlaunchDsi(el) {
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">
        <span class="risk-chip">Memória interna</span>
      </div>
      <div class="note note--warn">
        <strong>Atenção:</strong> o Unlaunch grava na NAND do console — é a <strong>única escrita na memória interna</strong> deste fluxo.
        Há um risco pequeno de brick. Só continue se tiver o backup da NAND. Use o instalador seguro v2.6 preparado pelo app.
      </div>
      <ol class="guide-list list-decimal">
        <li>No DSi: Câmera → ícone SD → Álbum (agora deve abrir o TWiLight Menu++).</li>
        <li>Abra <code>unlaunch-installer.dsi</code> (Safe Unlaunch installer).</li>
        <li>Carregue em <strong>A</strong> após a mensagem WARNING.</li>
        <li>Se o LED da bateria estiver vermelho, ligue à corrente e continue.</li>
        <li><strong>Não</strong> escolha Uninstall / Restore launcher tmd.</li>
        <li>Escolha <strong>Install unlaunch</strong> → A; A no fim; POWER para reiniciar.</li>
      </ol>
      <button type="button" class="btn-primary wizard-cta" id="wiz-unl-next">Já instalei o Unlaunch</button>
    `;
    document.getElementById("wiz-unl-next").onclick = () => goNext();
  }

  function renderUnlaunchOpts(el) {
    el.innerHTML = `
      <p class="opt-does">
        Se ao ligar aparecer o Filemenu do Unlaunch (lista de arquivos), configure a inicialização automática no TWiLight.
        Sem isto, parece que “o menu não instalou”.
      </p>
      <ol class="guide-list list-decimal">
        <li>Ligue o DSi mantendo <strong>A + B</strong> premidos.</li>
        <li>Abra <strong>OPTIONS</strong>.</li>
        <li>Em <strong>NO BUTTON</strong>, escolha TWiLight Menu++ (<code>sdmc:/BOOT.NDS</code>).</li>
        <li><strong>SAVE &amp; EXIT</strong> e desligue.</li>
      </ol>
      <div class="note note--ok">Na próxima inicialização (sem botões) deve ir direto ao TWiLight.</div>
      <button type="button" class="btn-primary wizard-cta" id="wiz-opts-next">Já configurei / já inicia no TWiLight</button>
    `;
    document.getElementById("wiz-opts-next").onclick = () => goNext();
  }

  function renderUpdateTwilight(el) {
    el.innerHTML = `
      <div class="flex items-center gap-2 flex-wrap mb-2">${pathBadge("dsi")}</div>
      <p class="opt-does">
        Atualiza o TWiLight Menu++ no cartão. <strong>Não</strong> reinstala o Unlaunch no console.
      </p>
      <div class="note note--warn">
        <strong>Não</strong> abra o instalador Unlaunch no DSi se o console já inicia no menu ou no Filemenu.
      </div>
      ${writesList([
        "Arquivos do TWiLight Menu++ atualizados",
        "Pode colocar de novo <code>unlaunch-installer.dsi</code> — ignore-o no DSi",
      ])}
      ${drivePanelHtml()}
      <button type="button" class="btn-primary wizard-cta btn-primary--ok" id="wiz-upd">Atualizar TWiLight no SD</button>
    `;
    bindDrivePanel();
    document.getElementById("wiz-upd").onclick = async () => {
      const res = await runMountOp({ method: "setup_unlaunch" });
      if (res.success) goNext();
      else {
        state.lastError = res.error || "Falha ao atualizar.";
        render();
      }
    };
  }

  return {
    init,
    mount,
    render,
    startGoal,
    chooseBrand,
    goHome,
    goBack,
    goNext,
    onBusyChange,
    onDrivesUpdated,
    onDriveSelected,
    openManualSteps() {
      const d = document.querySelector("#tools-pane-softmod details.manual-steps");
      if (d) {
        d.open = true;
        d.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    },
  };
})();
