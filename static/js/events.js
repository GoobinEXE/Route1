/**
 * Canal de eventos Python → UI (web_events / evaluate_js).
 * Fallback: polling de logs nos primeiros segundos.
 */
(function () {
  const listeners = Object.create(null);

  function on(type, fn) {
    if (typeof type !== "string" || typeof fn !== "function") return () => {};
    if (!listeners[type]) listeners[type] = new Set();
    listeners[type].add(fn);
    return () => {
      listeners[type] && listeners[type].delete(fn);
    };
  }

  function dispatch(raw) {
    let evt = raw;
    if (typeof raw === "string") {
      try {
        evt = JSON.parse(raw);
      } catch (e) {
        return;
      }
    }
    if (!evt || typeof evt !== "object") return;
    const type = evt.type || evt.event;
    if (!type || !listeners[type]) return;
    const payload = evt.payload != null ? evt.payload : evt;
    for (const fn of Array.from(listeners[type])) {
      try {
        fn(payload);
      } catch (e) {
        /* listener isolado */
      }
    }
  }

  window.R1K = window.R1K || {};
  window.R1K.events = { on, dispatch };
})();
