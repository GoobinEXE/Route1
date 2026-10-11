/**
 * Grelha/lista virtualizada simples (>200 itens).
 */
(function () {
  function createVirtualList(container, items, opts) {
    const rowHeight = (opts && opts.rowHeight) || 52;
    const renderRow = (opts && opts.renderRow) || (() => document.createElement("div"));
    const overscan = (opts && opts.overscan) || 6;

    container.classList.add("vgrid");
    container.innerHTML = "";
    const spacer = document.createElement("div");
    spacer.className = "vgrid-spacer";
    const windowEl = document.createElement("div");
    windowEl.className = "vgrid-window";
    container.appendChild(spacer);
    container.appendChild(windowEl);

    let list = Array.isArray(items) ? items : [];

    function paint() {
      const total = list.length;
      spacer.style.height = total * rowHeight + "px";
      const scrollTop = container.scrollTop;
      const viewH = container.clientHeight || 400;
      let start = Math.floor(scrollTop / rowHeight) - overscan;
      if (start < 0) start = 0;
      let end = Math.ceil((scrollTop + viewH) / rowHeight) + overscan;
      if (end > total) end = total;
      windowEl.style.transform = `translateY(${start * rowHeight}px)`;
      windowEl.innerHTML = "";
      const frag = document.createDocumentFragment();
      for (let i = start; i < end; i++) {
        const row = renderRow(list[i], i);
        if (!row) continue;
        row.classList.add("vgrid-item");
        row.style.height = rowHeight + "px";
        frag.appendChild(row);
      }
      windowEl.appendChild(frag);
    }

    container.addEventListener("scroll", paint, { passive: true });

    return {
      setItems(next) {
        list = Array.isArray(next) ? next : [];
        paint();
      },
      refresh: paint,
      destroy() {
        container.removeEventListener("scroll", paint);
        container.innerHTML = "";
      },
    };
  }

  window.R1K = window.R1K || {};
  window.R1K.virtual = { createVirtualList };
})();
