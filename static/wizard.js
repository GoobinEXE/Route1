/**
 * Assistente passo a passo — máquina de estados + percursos.
 * Depende de app.js (selectedDrive, fetchDrives, runMountOp, getApi, waitForApi).
 */
const Wizard = (() => {
  const state = {
    goal: null, // flash-update | flash-new | sd-new | sd-update
    brand: null, // gei | r4
    stepIndex: 0,
    hasFacebook: null,
    r4Source: null,
    skipNandRisk: false,
    lastError: null,
    inspect: null,
    kernels: null,
  };

  let steps = [];
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
    // Re-render só se estamos num CTA que muda estado visual
    const root = document.getElementById("wizard-root");
    if (root && !root.classList.contains("hidden")) {
      // botões já são desabilitados por setBusy
    }
  }

  function onDrivesUpdated() {
    const driveBox = document.getElementById("wizard-drive-panel");
    if (driveBox && !driveBox.classList.contains("hidden")) {
      // badge já atualizado por app.js
    }
  }

  function onDriveSelected() {
    // noop — gates reavaliados no próximo render/CTA
  }

  function goalTitle(goal) {
    return (
      {
        "flash-update": "Atualizar flashcard",
        "flash-new": "Criar flashcard do zero",
        "sd-new": "Instalar SD-direct",
        "sd-update": "Atualizar SD-direct",
      }[goal] || "Assistente"
    );
  }

  function buildSteps() {
    if (state.goal === "flash-update") return buildFlashSteps(false);
    if (state.goal === "flash-new") return buildFlashSteps(true);
    if (state.goal === "sd-new") return buildSdNewSteps();
    if (state.goal === "sd-update") return buildSdUpdateSteps();
    return [];
  }

  function buildFlashSteps(fromScratch) {
    const brandLabel = state.brand === "gei" ? "GEi" : "R4";
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
      title: `Preparar kernel ${brandLabel}`,
      where: "PC",
      render: renderKernelPrep,
    });
    list.push({
      id: "kernel-install",
      title: `Instalar kernel ${brandLabel}`,
      where: "PC",
      render: renderKernelInstall,
    });
    list.push({
      id: "roms-opt",
      title: "Organizar jogos (opcional)",
      where: "PC",
      render: renderRomsOptional,
    });
    list.push({
      id: "done-flash",
      title: "Pronto",
      where: "PC",
      render: renderDone({
        lines: [
          "Ejete o MicroSD com segurança no sistema operativo.",
          `Coloque-o no cartucho ${brandLabel} e ligue o DSi/DS.`,
          "Se o menu não abrir, confirme que o kernel é do clone exato do cartucho.",
        ],
      }),
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
        title: "Câmera: com ou sem Facebook?",
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
        title: "Passo 1 no PC — Memory Pit e dumpTool",
        where: "PC",
        render: renderStage1,
      },
      {
        id: "exploit",
        title: "No DSi — abrir o Memory Pit",
        where: "DSi",
        render: renderExploitDsi,
      },
      {
        id: "nand-dump",
        title: "No DSi — backup da NAND (dumpTool)",
        where: "DSi",
        render: renderNandDumpDsi,
      },
      {
        id: "reinsert-nand",
        title: "Voltar o SD ao PC e verificar o dump",
        where: "PC",
        render: renderNandVerify,
      },
      {
        id: "stage2",
        title: "Passo 2 no PC — TWiLight e Unlaunch",
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
        title: "Configurar boot no TWiLight",
        where: "DSi",
        render: renderUnlaunchOpts,
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
            "Insira-o no slot lateral do DSi e ligue a console.",
            "Deve arrancar diretamente no TWiLight Menu++.",
            "Se aparecer o Filemenu do Unlaunch, volte um passo e configure NO BUTTON → TWiLight.",
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
            "Não é necessário reinstalar o Unlaunch se a console já arranca no menu.",
          ],
        }),
      },
    ];
  }

  /* ---------- navigation ---------- */

  function startGoal(goal) {
    resetFlow();
    state.goal = goal;
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
    const root = document.getElementById("wizard-root");
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
          <button type="button" class="btn-ghost" onclick="Wizard.goBack()">Voltar</button>
        </div>
        <section class="panel overflow-hidden mt-2">
          <div class="flex items-center justify-between px-4 py-2 panel-header">
            <h3 class="section-label !normal-case tracking-normal text-fg-soft">Atividade</h3>
            <button type="button" onclick="clearLogs()" class="text-[11px] font-medium text-fg-mute hover:text-fg transition">Limpar</button>
          </div>
          <div id="wizard-log" class="h-28 overflow-y-auto px-4 py-2 space-y-1 log-view">
            <div class="text-fg-mute">Atividade do assistente.</div>
          </div>
        </section>
      </div>
    `;

    const body = document.getElementById("wizard-step-body");
    step.render(body);
  }

  function renderGoalPicker() {
    return `
      <div class="space-y-5">
        <div>
          <h2 class="text-[17px] font-semibold text-fg">O que você quer fazer?</h2>
          <p class="text-[12px] text-fg-mute mt-1.5 leading-relaxed max-w-2xl">
            O assistente guia cada etapa com calma — no PC e no DSi — para evitar erros comuns de quem está a começar.
          </p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          ${goalCard(
            "flash-update",
            "Atualizar flashcard",
            "O MicroSD do cartucho Slot-1 (GEi ou R4) já tem kernel e quer atualizar.",
            "Não formata o cartão."
          )}
          ${goalCard(
            "flash-new",
            "Instalar / criar flashcard do zero",
            "MicroSD vazio ou a limpar + kernel do cartucho GEi ou R4.",
            "Formata em FAT32 (apaga tudo)."
          )}
          ${goalCard(
            "sd-new",
            "Instalar e usar só o cartão SD",
            "Slot lateral do DSi com TWiLight Menu++ e Unlaunch — jogos sem flashcard.",
            "Inclui backup da NAND e instalação no consol."
          )}
          ${goalCard(
            "sd-update",
            "Atualizar o SD-direct",
            "Já tem Unlaunch/TWiLight e quer atualizar o menu ou organizar jogos.",
            "Não reinstala o Unlaunch."
          )}
        </div>
        <p class="text-[11px] text-fg-mute leading-relaxed">
          Flashcard (Slot-1) ≠ SD lateral do DSi.
          DS / DS Lite / 3DS <strong>não</strong> usam este softmod.
          Preferir o <button type="button" class="text-accent-fg font-medium" onclick="setAppMode('advanced')">Modo avançado</button> se já souber o que fazer.
        </p>
      </div>
    `;
  }

  function goalCard(id, title, when, not) {
    return `
      <button type="button" class="wizard-goal text-left" onclick="Wizard.startGoal('${id}')">
        <h3 class="text-[14px] font-semibold text-fg">${title}</h3>
        <p class="text-[12px] text-fg-mute mt-2 leading-relaxed">${when}</p>
        <p class="text-[11px] text-fg-soft mt-2"><span class="font-medium">Nota:</span> ${not}</p>
      </button>
    `;
  }

  /* ---------- step renderers ---------- */

  function renderBrandPick(el) {
    el.innerHTML = `
      <p class="text-[12px] text-fg-mute leading-relaxed">
        Confirme o nome no plástico ou na PCB do cartucho. Clones “R4” exigem o kernel <strong>daquele</strong> clone — o kernel errado não inicia.
      </p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button type="button" class="wizard-goal" onclick="Wizard.chooseBrand('gei')">
          <h3 class="text-[14px] font-semibold">Galaxy Eagle i (GEi)</h3>
          <p class="text-[11px] text-fg-mute mt-1">Escrito Galaxy Eagle i / GEi. Kernel v4.2 EN.</p>
        </button>
        <button type="button" class="wizard-goal" onclick="Wizard.chooseBrand('r4')">
          <h3 class="text-[14px] font-semibold">R4 / clone R4</h3>
          <p class="text-[11px] text-fg-mute mt-1">Nome no cartucho (R4, R4i, etc.). Extraia o firmware oficial do modelo exato para Downloads.</p>
        </button>
      </div>
      <div class="note note--warn">
        AceKard e outros cartuchos não suportados neste assistente — use o Modo avançado ou o firmware do fabricante.
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

  function drivePanelHtml() {
    return `
      <section class="panel p-4 drive-panel" id="wizard-drive-panel">
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div class="flex-1 space-y-2">
            <div class="flex items-center gap-2">
              <span id="wizard-drive-status-dot" class="status-dot status-dot--idle" aria-hidden="true"></span>
              <h3 class="section-label">Cartão SD</h3>
            </div>
            <select id="wizard-drive-select" onchange="onDriveSelected(true)" class="field-select w-full md:max-w-lg">
              <option value="">Procurando unidades…</option>
            </select>
          </div>
          <div class="flex items-center gap-2">
            <button type="button" class="btn-ghost" onclick="fetchDrives()">Atualizar</button>
            <div id="wizard-drive-badge" class="hidden stats-row">
              <div>
                <span class="stat-label">Formato</span>
                <span id="wizard-info-fs" class="stat-value">—</span>
              </div>
              <div class="stat-divider"></div>
              <div>
                <span class="stat-label">Capacidade</span>
                <span id="wizard-info-size" class="stat-value">—</span>
              </div>
              <div class="stat-divider"></div>
              <div>
                <span class="stat-label">Livre</span>
                <span id="wizard-info-free" class="stat-value text-accent-fg">—</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    `;
  }

  function bindDrivePanel() {
    syncDriveSelects();
    updateDriveBadge();
    setDriveStatus(!!selectedDrive);
  }

  function renderFormatWarn(el) {
    el.innerHTML = `
      <div class="note note--warn">
        <strong>Atenção:</strong> formatar apaga <em>todos</em> os dados do MicroSD.
        No Windows pode ser necessário executar o app como Administrador.
      </div>
      ${drivePanelHtml()}
      <ol class="guide-list list-decimal">
        <li>Confirme que selecionou o MicroSD do cartucho (não o disco do sistema).</li>
        <li>Clique em Formatar FAT32 e confirme o diálogo.</li>
        <li>Aguarde terminar — a seguir terá de re-selecionar a unidade.</li>
      </ol>
      <button type="button" class="btn-primary wizard-cta btn-primary--ok" id="wiz-format">Formatar FAT32</button>
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
      <p class="text-[12px] text-fg-mute leading-relaxed">
        Recomendamos um backup do cartão para o Ambiente de Trabalho antes de gravar.
        Pode saltar se o cartão estiver vazio ou se já tiver cópia.
      </p>
      ${drivePanelHtml()}
      <div class="flex flex-col sm:flex-row gap-2">
        <button type="button" class="btn-primary wizard-cta" id="wiz-backup">Fazer backup</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-backup-skip">Saltar</button>
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
    el.innerHTML = `
      <div class="note">
        O app <strong>não descarrega</strong> o kernel automaticamente (risco de firmware errado).
        Extraia o zip oficial do seu modelo para a pasta <code>Downloads</code>.
      </div>
      ${
        isGei
          ? `<ol class="guide-list list-decimal">
              <li>Extraia a pasta <code>GEiv4.2_EN</code> para Downloads (deve conter <code>_DS_MENU.DAT</code> e <code>_DS_MSHL.NDS</code>).</li>
              <li>Clique em Procurar.</li>
            </ol>`
          : `<ol class="guide-list list-decimal">
              <li>Extraia o firmware <strong>exato</strong> do seu clone R4 para Downloads.</li>
              <li>A pasta deve ter arquivos como <code>_DS_MENU.DAT</code>, <code>R4.dat</code> ou semelhantes — sem jogos.</li>
              <li>Clique em Procurar e escolha a pasta correcta se houver várias.</li>
            </ol>`
      }
      <div id="wiz-kernel-status" class="text-[12px] text-fg-mute">Ainda não procurado.</div>
      <div class="flex flex-col sm:flex-row gap-2">
        <button type="button" class="btn-secondary wizard-cta" id="wiz-probe">Procurar em Downloads</button>
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
          status.innerHTML = `<span class="text-ok">GEi encontrado: ${escapeHtml(res.gei.path)}</span>`;
          next.disabled = false;
        } else {
          status.innerHTML =
            '<span class="text-warn">Pasta GEiv4.2_EN não encontrada em Downloads.</span>';
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
    el.innerHTML = `
      <p class="text-[12px] text-fg-mute leading-relaxed">
        Vai copiar e verificar os arquivos do kernel para o MicroSD selecionado.
      </p>
      ${drivePanelHtml()}
      ${
        !isGei
          ? `<div class="note">Origem: <code>${escapeHtml(state.r4Source || "—")}</code></div>`
          : ""
      }
      <button type="button" class="btn-primary wizard-cta" id="wiz-install-k">Instalar kernel</button>
    `;
    bindDrivePanel();
    document.getElementById("wiz-install-k").onclick = async () => {
      let res;
      if (isGei) {
        res = await runMountOp({ method: "setup_gei" });
      } else {
        res = await runMountOp({ method: "setup_r4", sourceDir: state.r4Source });
      }
      if (res.success) {
        alert("Kernel instalado. Ejetar o cartão com segurança quando terminar as etapas seguintes.");
        goNext();
      } else {
        state.lastError = res.error || "Falha na instalação.";
        render();
      }
    };
  }

  function renderRomsOptional(el) {
    el.innerHTML = `
      <p class="text-[12px] text-fg-mute leading-relaxed">
        Se já copiou jogos para o cartão, pode organizá-los agora: jogos em
        <code>/roms/nds/</code> (lista flat) e apps em <code>/roms/apps/</code>.
        Caso contrário, salte e copie os jogos depois.
      </p>
      ${drivePanelHtml()}
      <div class="flex flex-col sm:flex-row gap-2">
        <button type="button" class="btn-primary wizard-cta" id="wiz-roms">Organizar jogos</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-roms-skip">Saltar</button>
      </div>
    `;
    bindDrivePanel();
    document.getElementById("wiz-roms").onclick = async () => {
      const res = await runMountOp({ method: "organize_roms" });
      if (res.success || res.error === "cancelled") {
        if (res.success) goNext();
      }
    };
    document.getElementById("wiz-roms-skip").onclick = () => goNext();
  }

  function renderRomsAndCleanOptional(el) {
    el.innerHTML = `
      <p class="text-[12px] text-fg-mute leading-relaxed">Opcional: organizar ROMs ou limpar metadados do sistema.</p>
      ${drivePanelHtml()}
      <div class="flex flex-col sm:flex-row gap-2 flex-wrap">
        <button type="button" class="btn-primary wizard-cta" id="wiz-roms">Organizar jogos</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-clean">Limpar metadados</button>
        <button type="button" class="btn-ghost wizard-cta" id="wiz-roms-skip">Continuar</button>
      </div>
    `;
    bindDrivePanel();
    document.getElementById("wiz-roms").onclick = async () => {
      await runMountOp({ method: "organize_roms" });
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
      <p class="text-[12px] text-fg-mute leading-relaxed">
        Este softmod (Memory Pit + Unlaunch) só funciona em <strong>Nintendo DSi</strong> ou <strong>DSi XL / LL</strong>
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
      <p class="text-[12px] text-fg-mute leading-relaxed">
        No DSi, abra a <strong>Câmera Nintendo DSi</strong> e veja se aparece o ícone do Facebook na barra inferior.
        O Memory Pit errado impede o exploit de abrir.
      </p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
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
      <button type="button" class="btn-primary wizard-cta mt-2" id="wiz-cam-next">Continuar</button>
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
      <p class="text-[12px] text-fg-mute leading-relaxed">
        A Câmera do DSi precisa de <strong>FAT32</strong>. A pasta <code>DCIM</code> na raiz impede o Memory Pit —
        o assistente pode renomeá-la (as fotos não são apagadas).
      </p>
      ${drivePanelHtml()}
      <div id="wiz-dcim-status" class="text-[12px] text-fg-mute">Clique em Verificar.</div>
      <div class="flex flex-col sm:flex-row gap-2 flex-wrap">
        <button type="button" class="btn-secondary wizard-cta" id="wiz-check">Verificar cartão</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-dcim" disabled>Mover DCIM</button>
        <button type="button" class="btn-secondary wizard-cta" id="wiz-fmt" disabled>Formatar FAT32</button>
        <button type="button" class="btn-primary wizard-cta" id="wiz-dcim-next" disabled>Continuar</button>
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
      <div class="note">
        Vai descarregar (1ª vez, precisa de Internet) e gravar Memory Pit (${fb}), dumpTool como <code>boot.nds</code>
        e o instalador Unlaunch. Não avance se a rede falhar.
      </div>
      ${drivePanelHtml()}
      <button type="button" class="btn-primary wizard-cta" id="wiz-s1">Configurar Passo 1 no SD</button>
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
        <li>Insira o SD no <strong>slot lateral</strong> do DSi e ligue a console.</li>
        <li>Abra a <strong>Câmera Nintendo DSi</strong>.</li>
        <li>Toque no ícone do <strong>cartão SD</strong> (canto superior direito).</li>
        <li>Abra o <strong>Álbum</strong> com o botão grande à direita.</li>
      </ol>
      <div class="space-y-2">
        <div class="note note--ok"><strong>Tela magenta</strong> — Memory Pit correto; deve aparecer o dumpTool.</div>
        <div class="note note--warn"><strong>Tela verde</strong> — falta <code>boot.nds</code>. Volte ao PC e refaça o Passo 1.</div>
        <div class="note"><strong>Álbum normal</strong> — pit errado (Facebook) ou ainda existe pasta <code>DCIM</code>.</div>
      </div>
      <button type="button" class="btn-primary wizard-cta" id="wiz-exploit-next">Já abriu o dumpTool</button>
    `;
    document.getElementById("wiz-exploit-next").onclick = () => goNext();
  }

  function renderNandDumpDsi(el) {
    el.innerHTML = `
      <ol class="guide-list list-decimal">
        <li>No dumpTool, carregue em <strong>A</strong> para iniciar o backup (~7 minutos).</li>
        <li><strong>Não desligue</strong> a console nem retire o SD.</li>
        <li>Quando terminar, carregue em <strong>START</strong> e desligue o DSi.</li>
        <li>O dump fica numa pasta <code>DT…</code> na raiz do SD (com <code>nand.bin</code>).</li>
      </ol>
      <div class="note note--warn">Guarde depois a pasta DT… noutro sítio (Desktop). É a sua rede de segurança se algo correr mal com o Unlaunch.</div>
      <button type="button" class="btn-primary wizard-cta" id="wiz-nand-next">Já terminei o dump — vou ao PC</button>
    `;
    document.getElementById("wiz-nand-next").onclick = () => goNext();
  }

  function renderNandVerify(el) {
    el.innerHTML = `
      <p class="text-[12px] text-fg-mute leading-relaxed">
        Volte a inserir o SD no PC, atualize a lista e verifique se existe <code>DT…/nand.bin</code> (~240 MB).
      </p>
      ${drivePanelHtml()}
      <div id="wiz-nand-status" class="text-[12px] text-fg-mute">Ainda não verificado.</div>
      <label class="choice mt-2">
        <input type="checkbox" id="wiz-nand-risk">
        <span>
          <span class="choice-title text-warn">Avançar sem dump neste cartão (risco)</span>
          <span class="choice-sub">Só se já tiver nand.bin noutro sítio. Desaconselhado.</span>
        </span>
      </label>
      <div class="flex flex-col sm:flex-row gap-2 mt-2">
        <button type="button" class="btn-secondary wizard-cta" id="wiz-nand-check">Verificar dump</button>
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
      <div class="note">
        Instala/restaura o TWiLight Menu++ e coloca <code>unlaunch-installer.dsi</code> na raiz.
        Precisa de Internet na primeira vez (download pinado).
      </div>
      <div class="note note--warn">
        Se o firmware do DSi for exactamente <strong>1.4.2</strong>, o guia oficial recomenda atualizar o sistema nas Definições antes do Unlaunch. Não automatizamos esse passo.
      </div>
      ${drivePanelHtml()}
      <button type="button" class="btn-primary wizard-cta btn-primary--ok" id="wiz-s2">Configurar Passo 2 no SD</button>
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
      <div class="note note--warn">
        <strong>Atenção:</strong> o Unlaunch grava na NAND da console. Há um risco pequeno de brick.
        Só continue se tiver o backup da NAND. Use o instalador seguro v2.6 preparado pelo app.
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
      <p class="text-[12px] text-fg-mute leading-relaxed">
        Se ao ligar aparecer o Filemenu do Unlaunch (lista de arquivos), configure o arranque automático no TWiLight.
        Sem isto, parece que “o menu não instalou”.
      </p>
      <ol class="guide-list list-decimal">
        <li>Ligue o DSi mantendo <strong>A + B</strong> premidos.</li>
        <li>Abra <strong>OPTIONS</strong>.</li>
        <li>Em <strong>NO BUTTON</strong>, escolha TWiLight Menu++ (<code>sdmc:/BOOT.NDS</code>).</li>
        <li><strong>SAVE &amp; EXIT</strong> e desligue.</li>
      </ol>
      <div class="note note--ok">No próximo arranque (sem botões) deve ir direto ao TWiLight.</div>
      <button type="button" class="btn-primary wizard-cta" id="wiz-opts-next">Já configurei / já arranca no TWiLight</button>
    `;
    document.getElementById("wiz-opts-next").onclick = () => goNext();
  }

  function renderUpdateTwilight(el) {
    el.innerHTML = `
      <div class="note note--warn">
        Isto actualiza o TWiLight Menu++ no cartão.
        <strong>Não</strong> abra o instalador Unlaunch no DSi se a console já arranca no menu ou no Filemenu.
      </div>
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
    render,
    startGoal,
    chooseBrand,
    goHome,
    goBack,
    goNext,
    onBusyChange,
    onDrivesUpdated,
    onDriveSelected,
  };
})();
