// Browser-side settings: theme, terminal zoom, available commands.
// Stored in localStorage. Provides a shared modal accessible via a cog button
// that any page can drop into its header.
(function () {
  const STORAGE_KEY = "agentbox.settings.v1";
  const DEFAULTS = Object.freeze({
    theme: "dark",
    zoom: 13,
    commands: [
      "claude --dangerously-skip-permissions",
      "bash -l",
    ],
  });

  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { ...DEFAULTS };
      const parsed = JSON.parse(raw);
      return {
        theme: parsed.theme === "light" ? "light" : "dark",
        zoom: clampZoom(parsed.zoom ?? DEFAULTS.zoom),
        commands: Array.isArray(parsed.commands) && parsed.commands.length
          ? parsed.commands.filter((c) => typeof c === "string")
          : [...DEFAULTS.commands],
      };
    } catch {
      return { ...DEFAULTS };
    }
  }

  function clampZoom(n) {
    n = Number(n) || DEFAULTS.zoom;
    return Math.max(8, Math.min(32, Math.round(n)));
  }

  let state = load();
  const listeners = new Set();

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch {}
  }

  function update(patch) {
    state = { ...state, ...patch };
    if (patch.zoom !== undefined) state.zoom = clampZoom(state.zoom);
    save();
    applyTheme();
    for (const fn of listeners) {
      try { fn(state); } catch (e) { console.error(e); }
    }
  }

  function applyTheme() {
    document.documentElement.dataset.theme = state.theme;
  }

  // xterm.js theme objects per UI theme.
  const TERM_THEMES = {
    dark: {
      background: "#000000",
      foreground: "#e7e7e9",
      cursor: "#7ec8ff",
      cursorAccent: "#000000",
      selectionBackground: "#3a3f4b",
      black: "#1e2127",       red: "#e06c75",         green: "#98c379",         yellow: "#e5c07b",
      blue: "#61afef",        magenta: "#c678dd",     cyan: "#56b6c2",          white: "#abb2bf",
      brightBlack: "#5c6370", brightRed: "#e06c75",   brightGreen: "#98c379",   brightYellow: "#e5c07b",
      brightBlue: "#61afef",  brightMagenta: "#c678dd", brightCyan: "#56b6c2",  brightWhite: "#ffffff",
    },
    light: {
      background: "#ffffff",
      foreground: "#383a42",
      cursor: "#1e40af",
      cursorAccent: "#ffffff",
      selectionBackground: "#cfd6e6",
      black: "#383a42",       red: "#e45649",         green: "#50a14f",         yellow: "#c18401",
      blue: "#0184bc",        magenta: "#a626a4",     cyan: "#0997b3",          white: "#a0a1a7",
      brightBlack: "#696c77", brightRed: "#e45649",   brightGreen: "#50a14f",   brightYellow: "#c18401",
      brightBlue: "#0184bc",  brightMagenta: "#a626a4", brightCyan: "#0997b3",  brightWhite: "#1e2127",
    },
  };

  const COG_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>';
  const TRASH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6"/></svg>';

  let modalEl = null;

  function open() {
    if (modalEl) return;
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = '\
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">\
        <div class="modal-head">\
          <h2 id="settings-title">Settings</h2>\
          <button class="icon-btn" data-act="close" aria-label="close">\
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>\
          </button>\
        </div>\
        <div class="modal-body">\
          <div class="settings-section">\
            <div class="label">Theme</div>\
            <div class="theme-toggle">\
              <button data-theme="dark">Dark</button>\
              <button data-theme="light">Light</button>\
            </div>\
          </div>\
          <div class="settings-section">\
            <div class="label">Terminal zoom</div>\
            <div class="zoom-control">\
              <button data-zoom="-1" aria-label="zoom out">−</button>\
              <span class="value"></span>\
              <button data-zoom="1" aria-label="zoom in">+</button>\
            </div>\
          </div>\
          <div class="settings-section">\
            <div class="label">Commands</div>\
            <div class="commands-list"></div>\
            <button class="add-cmd" type="button">+ Add command</button>\
          </div>\
        </div>\
      </div>';
    document.body.appendChild(backdrop);
    modalEl = backdrop;

    function close() {
      if (!modalEl) return;
      modalEl.remove();
      modalEl = null;
      document.removeEventListener("keydown", onKey);
    }
    function onKey(e) { if (e.key === "Escape") close(); }
    document.addEventListener("keydown", onKey);
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
    backdrop.querySelector('[data-act="close"]').addEventListener("click", close);

    const themeBtns = backdrop.querySelectorAll(".theme-toggle button");
    function refreshTheme() {
      themeBtns.forEach((b) => b.classList.toggle("active", b.dataset.theme === state.theme));
    }
    themeBtns.forEach((b) => b.addEventListener("click", () => {
      update({ theme: b.dataset.theme });
      refreshTheme();
    }));
    refreshTheme();

    const zoomValue = backdrop.querySelector(".zoom-control .value");
    function refreshZoom() { zoomValue.textContent = state.zoom + "px"; }
    backdrop.querySelectorAll(".zoom-control button").forEach((b) => {
      b.addEventListener("click", () => {
        update({ zoom: state.zoom + parseInt(b.dataset.zoom, 10) });
        refreshZoom();
      });
    });
    refreshZoom();

    const list = backdrop.querySelector(".commands-list");
    function refreshCommands() {
      list.innerHTML = "";
      state.commands.forEach((cmd, i) => {
        const row = document.createElement("div");
        row.className = "command-row";
        const input = document.createElement("input");
        input.type = "text";
        input.value = cmd;
        input.placeholder = "e.g. claude --dangerously-skip-permissions";
        input.addEventListener("change", () => {
          const next = [...state.commands];
          next[i] = input.value;
          update({ commands: next });
        });
        const del = document.createElement("button");
        del.className = "icon-btn danger";
        del.setAttribute("aria-label", "remove command");
        del.innerHTML = TRASH_SVG;
        del.addEventListener("click", () => {
          update({ commands: state.commands.filter((_, j) => j !== i) });
          refreshCommands();
        });
        row.appendChild(input);
        row.appendChild(del);
        list.appendChild(row);
      });
    }
    backdrop.querySelector(".add-cmd").addEventListener("click", () => {
      update({ commands: [...state.commands, ""] });
      refreshCommands();
      const last = list.querySelector(".command-row:last-child input");
      if (last) last.focus();
    });
    refreshCommands();
  }

  function createCog() {
    const btn = document.createElement("button");
    btn.className = "icon-btn bordered";
    btn.title = "Settings";
    btn.setAttribute("aria-label", "Settings");
    btn.innerHTML = COG_SVG;
    btn.addEventListener("click", open);
    return btn;
  }

  applyTheme();

  window.Settings = {
    get: () => ({ ...state, commands: [...state.commands] }),
    onChange: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
    createCog,
    open,
    terminalTheme: () => TERM_THEMES[state.theme],
  };
})();
