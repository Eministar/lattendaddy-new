window.requireModule = function requireModule() {
  if (!state.moduleKey) {
    toast("Bitte erst ein Modul wählen");
    throw new Error("module_missing");
  }
  return state.moduleKey;
};

window.normalizeModuleSetting = function normalizeModuleSetting(setting) {
  if (!setting || typeof setting !== "object") return null;
  return {
    ...setting,
    label: setting.label || setting.leaf_name || setting.relative_path || "Setting",
    selector_type: setting.selector_type || setting.reference_kind || null,
    has_override: Boolean(setting.has_override ?? setting.override),
    current_display: setting.current_display ?? text(setting.current_value, "–"),
    global_display: setting.global_display ?? text(setting.global_value, "–"),
  };
};

window.normalizeModuleSummary = function normalizeModuleSummary(module) {
  if (!module || typeof module !== "object") return null;
  const source = module.module && typeof module.module === "object" ? module.module : module;
  return {
    key: source.key || source.module_key || null,
    label: source.label || source.name || source.key || "Modul",
    emoji: source.emoji || "⚙️",
    aliases: Array.isArray(source.aliases) ? source.aliases : [],
    settings_total: source.settings_total ?? source.setting_count ?? (Array.isArray(source.settings) ? source.settings.length : Array.isArray(module.fields) ? module.fields.length : 0),
    override_total: source.override_total ?? source.override_count ?? 0,
  };
};

window.normalizeModuleList = function normalizeModuleList(payload) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.modules)
      ? payload.modules
      : Array.isArray(payload?.items)
        ? payload.items
        : [];
  return list
    .map((item) => normalizeModuleSummary(item))
    .filter((item) => item && item.key);
};

window.normalizeModuleDetail = function normalizeModuleDetail(payload) {
  if (!payload || typeof payload !== "object") return null;
  const base = normalizeModuleSummary(payload);
  if (!base) return null;
  const rawSettings = Array.isArray(payload.settings)
    ? payload.settings
    : Array.isArray(payload.fields)
      ? payload.fields
      : [];
  return {
    ...base,
    settings: rawSettings.map((item) => normalizeModuleSetting(item)).filter(Boolean),
  };
};

window.fetchModulesPayload = async function fetchModulesPayload(gid) {
  try {
    return await api(`/api/guilds/${gid}/modules`);
  } catch (_err) {
    return api(`/api/guilds/${gid}/setup/modules`);
  }
};

window.fetchModuleDetailPayload = async function fetchModuleDetailPayload(gid, moduleKey) {
  try {
    return await api(`/api/guilds/${gid}/modules/${encodeURIComponent(moduleKey)}`);
  } catch (_err) {
    return api(`/api/guilds/${gid}/setup/modules/${encodeURIComponent(moduleKey)}`);
  }
};

window.renderModuleSidebar = function renderModuleSidebar() {
  const root = $("moduleList");
  root.innerHTML = "";
  if (state.moduleError) {
    root.innerHTML = `<div class="muted">${escapeHtml(state.moduleError)}</div>`;
    return;
  }
  const query = $("moduleSearch").value.trim().toLowerCase();
  const modules = state.modules.filter((module) => {
    if (!query) return true;
    const haystack = [module.key, module.label, ...(module.aliases || [])].join(" ").toLowerCase();
    return haystack.includes(query);
  });
  if (!modules.length) {
    root.innerHTML = '<div class="muted">Keine Module gefunden</div>';
    return;
  }
  modules.forEach((module) => {
    const button = createElement("button", `module-nav-btn${state.moduleKey === module.key ? " active" : ""}`);
    button.type = "button";
    button.innerHTML = `
      <span class="module-nav-main">
        <span class="module-emoji">${escapeHtml(module.emoji || "⚙️")}</span>
        <span class="module-name">${escapeHtml(module.label)}</span>
      </span>
      <span class="module-nav-meta"><span class="module-count">${escapeHtml(module.override_total || 0)}</span></span>
    `;
    button.onclick = () => selectModule(module.key);
    root.appendChild(button);
  });
};

window.renderQuickModules = function renderQuickModules() {
  const root = $("moduleQuickGrid");
  root.innerHTML = "";
  if (state.moduleError) {
    root.innerHTML = `<div class="empty-state">${escapeHtml(state.moduleError)}</div>`;
    return;
  }
  if (!state.modules.length) {
    root.innerHTML = '<div class="empty-state">Noch keine Module geladen.</div>';
    return;
  }
  state.modules.slice(0, 10).forEach((module) => {
    const tile = createElement("button", "module-tile");
    tile.type = "button";
    tile.innerHTML = `
      <div class="module-tile-label">${escapeHtml(`${module.emoji || "⚙️"} ${module.label}`)}</div>
      <div class="module-tile-sub">${escapeHtml(`${module.override_total || 0} Overrides · ${module.settings_total || 0} Settings`)}</div>
    `;
    tile.onclick = () => selectModule(module.key);
    root.appendChild(tile);
  });
};

window.renderApplicationsHint = function renderApplicationsHint() {
  const hint = $("applicationsModuleHint");
  if (!hint) return;
  const module = state.modules.find((entry) => entry.key === "applications") || null;
  hint.textContent = module
    ? `${module.override_total || 0} Guild-Overrides bei ${module.settings_total || 0} Settings.`
    : "Applications-Modul noch nicht geladen.";
};

window.selectorItems = function selectorItems(setting) {
  if (!state.resources) return [];
  const selectorType = setting.selector_type || setting.reference_kind;
  if (selectorType === "channel") return state.resources.channels || [];
  if (selectorType === "thread") return state.resources.threads || [];
  if (selectorType === "role") return state.resources.roles || [];
  if (selectorType === "user") return state.resources.members || [];
  return [];
};

window.settingNeedsTextarea = function settingNeedsTextarea(setting) {
  const path = String(setting.relative_path || "").toLowerCase();
  if (setting.kind === "dict") return true;
  if (setting.kind === "list" && ["dict", "list"].includes(setting.element_kind)) return true;
  if (setting.kind === "str" && (path.includes("prompt") || path.includes("text") || path.includes("template") || path.includes("message") || path.includes("body") || path.includes("description"))) return true;
  return typeof setting.current_value === "string" && setting.current_value.length > 120;
};

window.buildSelectForSetting = function buildSelectForSetting(setting, currentValue) {
  const select = createElement("select");
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = setting.example ? `Leer / ${setting.example}` : "Wert wählen";
  select.appendChild(empty);
  const items = selectorItems(setting);
  const current = currentValue === undefined || currentValue === null ? "" : String(currentValue);
  let found = false;
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = String(item.id);
    option.textContent = optionLabel(item);
    if (String(item.id) === current) {
      option.selected = true;
      found = true;
    }
    select.appendChild(option);
  });
  if (current && !found) {
    const fallback = document.createElement("option");
    fallback.value = current;
    fallback.textContent = `Aktueller Wert · ${current}`;
    fallback.selected = true;
    select.appendChild(fallback);
  }
  return select;
};

window.buildValueControl = function buildValueControl(setting) {
  const currentValue = setting.current_value ?? setting.global_value ?? "";
  if (setting.kind === "bool") {
    const select = createElement("select");
    [["true", "Aktiviert"], ["false", "Deaktiviert"]].forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      if (String(currentValue) === value) option.selected = true;
      select.appendChild(option);
    });
    return { node: select, getValue: () => select.value === "true" };
  }
  if (setting.selector_type && setting.kind !== "list") {
    const select = buildSelectForSetting(setting, currentValue);
    return { node: select, getValue: () => select.value.trim() };
  }
  if (setting.kind === "dict" || (setting.kind === "list" && ["dict", "list"].includes(setting.element_kind))) {
    const area = createElement("textarea");
    area.value = currentValue && typeof currentValue === "object" ? JSON.stringify(currentValue, null, 2) : (currentValue || "");
    return {
      node: area,
      getValue: () => {
        const raw = area.value.trim();
        if (!raw) return setting.kind === "dict" ? {} : [];
        return JSON.parse(raw);
      },
    };
  }
  if (setting.kind === "list") {
    const area = createElement("textarea");
    area.value = Array.isArray(currentValue) ? currentValue.join(", ") : (currentValue || "");
    area.placeholder = setting.example || "eins,zwei,drei";
    return { node: area, getValue: () => area.value.trim() };
  }
  if (settingNeedsTextarea(setting)) {
    const area = createElement("textarea");
    area.value = setting.sensitive ? "" : String(currentValue || "");
    area.placeholder = setting.sensitive ? "Neuen Wert setzen" : (setting.example || "Textwert");
    return { node: area, getValue: () => area.value };
  }
  const input = createElement("input");
  if (setting.kind === "int" || setting.kind === "float") input.type = "number";
  input.value = setting.sensitive ? "" : String(currentValue || "");
  input.placeholder = setting.sensitive ? "Neuen Wert setzen" : (setting.example || "Wert");
  return { node: input, getValue: () => input.value.trim() };
};

window.createListChip = function createListChip(setting, value) {
  const chip = createElement("div", "chip");
  chip.innerHTML = `<span>${escapeHtml(String(value))}</span>`;
  const button = createElement("button", null, "Entfernen");
  button.type = "button";
  button.onclick = async () => {
    try {
      await moduleAction("remove", setting.relative_path, value);
    } catch (_err) {
      /* toast already handled */
    }
  };
  chip.appendChild(button);
  return chip;
};

window.buildSettingCard = function buildSettingCard(setting) {
  const card = createElement("div", "setting-card");
  const sourceClass = setting.has_override ? "setting-source override" : "setting-source";
  card.innerHTML = `
    <div class="setting-head">
      <div>
        <div class="setting-path">${escapeHtml(setting.label || setting.relative_path)}</div>
        <div class="setting-type">${escapeHtml(setting.relative_path)} · ${escapeHtml(setting.type_label)}${setting.selector_type ? ` · ${escapeHtml(setting.selector_type)}` : ""}</div>
      </div>
      <div class="${sourceClass}">${setting.has_override ? "Guild-Override" : "Global"}</div>
    </div>
    <div class="setting-values">
      <div class="setting-value-box">
        <div class="setting-value-label">Aktuell</div>
        <div class="setting-value-text">${escapeHtml(setting.current_display)}</div>
      </div>
      <div class="setting-value-box">
        <div class="setting-value-label">Global</div>
        <div class="setting-value-text">${escapeHtml(setting.global_display)}</div>
      </div>
    </div>
  `;
  const editor = createElement("div", "setting-editor");

  if (setting.kind === "list" && setting.selector_type) {
    const chips = createElement("div", "chips");
    const values = Array.isArray(setting.current_value) ? setting.current_value : [];
    if (values.length) values.forEach((value) => chips.appendChild(createListChip(setting, value)));
    else chips.appendChild(createElement("div", "empty-state", "Noch keine Werte gesetzt."));
    editor.appendChild(chips);

    const inline = createElement("div", "row-inline");
    const select = buildSelectForSetting({ ...setting, kind: "str" }, "");
    const addBtn = createElement("button", "primary", "Hinzufügen");
    addBtn.type = "button";
    addBtn.onclick = async () => {
      if (!select.value) return toast("Bitte erst einen Wert wählen");
      try {
        await moduleAction("add", setting.relative_path, select.value);
      } catch (_err) {
        /* toast already handled */
      }
    };
    inline.appendChild(select);
    inline.appendChild(addBtn);
    editor.appendChild(inline);

    const actions = createElement("div", "setting-actions");
    const resetBtn = createElement("button", "ghost", "Reset");
    resetBtn.type = "button";
    resetBtn.onclick = async () => {
      try {
        await moduleAction("reset", setting.relative_path);
      } catch (_err) {
        /* toast already handled */
      }
    };
    actions.appendChild(resetBtn);
    editor.appendChild(actions);
  } else {
    const control = buildValueControl(setting);
    editor.appendChild(control.node);
    if (setting.example) editor.appendChild(createElement("div", "setting-hint", `Beispiel: ${setting.example}`));
    const actions = createElement("div", "setting-actions");
    const saveBtn = createElement("button", "primary", "Speichern");
    saveBtn.type = "button";
    saveBtn.onclick = async () => {
      try {
        await moduleAction("set", setting.relative_path, control.getValue());
      } catch (err) {
        toast(err.message || "Wert konnte nicht gespeichert werden");
      }
    };
    const resetBtn = createElement("button", "ghost", "Reset");
    resetBtn.type = "button";
    resetBtn.onclick = async () => {
      try {
        await moduleAction("reset", setting.relative_path);
      } catch (_err) {
        /* toast already handled */
      }
    };
    actions.appendChild(saveBtn);
    actions.appendChild(resetBtn);
    editor.appendChild(actions);
  }

  card.appendChild(editor);
  return card;
};

window.renderModuleMetrics = function renderModuleMetrics(detail) {
  const root = $("moduleStats");
  root.innerHTML = "";
  [
    { label: "Settings", value: detail.settings_total || 0 },
    { label: "Overrides", value: detail.override_total || 0 },
    { label: "Aliase", value: (detail.aliases || []).length || 0 },
  ].forEach((metric) => {
    const node = createElement("div", "metric");
    node.innerHTML = `<div class="label">${escapeHtml(metric.label)}</div><div class="value">${escapeHtml(metric.value)}</div>`;
    root.appendChild(node);
  });
};

window.renderModuleEditor = function renderModuleEditor() {
  const detail = state.moduleDetail;
  const settingsRoot = $("moduleSettings");
  settingsRoot.innerHTML = "";
  if (!detail) {
    $("moduleTitle").textContent = "Kein Modul gewählt";
    $("moduleSubtitle").textContent = state.moduleError || "Wähle links ein Modul aus.";
    $("moduleSelectedBadge").textContent = "Kein Modul gewählt";
    $("moduleStats").innerHTML = "";
    settingsRoot.innerHTML = `<div class="empty-state">${escapeHtml(state.moduleError || "Wähle links ein Modul aus, um alle Einstellungen zu sehen.")}</div>`;
    return;
  }
  $("moduleTitle").textContent = `${detail.emoji || "⚙️"} ${detail.label}`;
  $("moduleSubtitle").textContent = `${detail.key} · ${(detail.aliases || []).join(", ") || "keine Aliase"}`;
  $("moduleSelectedBadge").textContent = `${detail.emoji || "⚙️"} ${detail.label}`;
  renderModuleMetrics(detail);
  const query = $("moduleSettingSearch").value.trim().toLowerCase();
  const settings = (detail.settings || []).filter((setting) => {
    if (!query) return true;
    const haystack = [setting.label, setting.relative_path, setting.full_path, setting.leaf_name, setting.type_label].join(" ").toLowerCase();
    return haystack.includes(query);
  });
  if (!settings.length) {
    settingsRoot.innerHTML = '<div class="empty-state">Keine Settings für diese Suche gefunden.</div>';
    return;
  }
  settings.forEach((setting) => settingsRoot.appendChild(buildSettingCard(setting)));
};

window.loadModules = async function loadModules() {
  const gid = requireGuild();
  try {
    const payload = await fetchModulesPayload(gid);
    state.modules = normalizeModuleList(payload);
    state.moduleError = state.modules.length ? null : "Es wurden keine Module vom Server geliefert.";
  } catch (err) {
    state.modules = [];
    state.moduleDetail = null;
    state.moduleError = err.message || "Module konnten nicht geladen werden.";
    renderModuleSidebar();
    renderQuickModules();
    renderApplicationsHint();
    renderModuleEditor();
    throw err;
  }
  renderModuleSidebar();
  renderQuickModules();
  renderApplicationsHint();
  const remembered = localStorage.getItem("starry_module");
  const validCurrent = state.modules.find((module) => module.key === state.moduleKey);
  if (!validCurrent) {
    state.moduleKey = state.modules.find((module) => module.key === remembered)?.key || (state.modules[0]?.key || null);
  }
  if (state.moduleKey) {
    await loadModuleDetail(state.moduleKey, true);
  } else {
    state.moduleDetail = null;
    renderModuleEditor();
  }
};

window.loadModuleDetail = async function loadModuleDetail(moduleKey, silent = false) {
  const gid = requireGuild();
  state.moduleKey = moduleKey;
  localStorage.setItem("starry_module", moduleKey);
  const payload = await fetchModuleDetailPayload(gid, moduleKey);
  state.moduleDetail = normalizeModuleDetail(payload);
  if (!state.moduleDetail) {
    throw new Error("Modul-Details konnten nicht gelesen werden");
  }
  renderModuleSidebar();
  renderQuickModules();
  renderApplicationsHint();
  renderModuleEditor();
  if (!silent) setView("settings");
};

window.selectModule = async function selectModule(moduleKey) {
  try {
    await loadModuleDetail(moduleKey);
  } catch (err) {
    toast(err.message || "Modul konnte nicht geladen werden");
  }
};

window.moduleAction = async function moduleAction(action, setting, value = null) {
  const gid = requireGuild();
  const moduleKey = requireModule();
  const payload = { setting };
  if (value !== null && value !== undefined) payload.value = value;
  let response;
  try {
    response = await postJson(`/api/guilds/${gid}/modules/${encodeURIComponent(moduleKey)}/${action}`, payload);
  } catch (_err) {
    response = await postJson(`/api/guilds/${gid}/setup/action`, {
      module: moduleKey,
      action,
      setting,
      value,
    });
  }
  toast(response.message || "Gespeichert");
  await loadModules();
  return response;
};
