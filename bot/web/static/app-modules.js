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
    description: setting.description || "",
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
      <span class="module-nav-head">
        <span class="module-nav-icon">${escapeHtml(module.emoji || "⚙️")}</span>
        <span class="module-nav-copy">
          <strong>${escapeHtml(module.label)}</strong>
          <small>${escapeHtml(module.key)} · ${escapeHtml(module.settings_total || 0)} Settings · ${escapeHtml((module.aliases || []).length || 0)} Aliase</small>
        </span>
        <span class="module-nav-count">${escapeHtml(module.override_total || 0)}</span>
      </span>
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
      <div class="module-tile-sub">${escapeHtml(module.key)}</div>
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

window.humanizeSettingToken = function humanizeSettingToken(value) {
  const text = String(value || "").replace(/[_\-.]+/g, " ").trim();
  if (!text) return "Allgemein";
  return text.replace(/\b\w/g, (char) => char.toUpperCase());
};

window.settingGroupLabel = function settingGroupLabel(setting) {
  const raw = String(setting.parent_path || "allgemein").trim();
  if (!raw) return "Allgemein";
  return raw
    .split(".")
    .map((part) => humanizeSettingToken(part))
    .join(" / ");
};

window.selectorTypeLabel = function selectorTypeLabel(value) {
  const key = String(value || "").toLowerCase();
  if (key === "channel") return "Kanal";
  if (key === "thread") return "Thread";
  if (key === "role") return "Rolle";
  if (key === "user") return "Nutzer";
  return humanizeSettingToken(value);
};

window.isUnsetReferenceValue = function isUnsetReferenceValue(setting, value) {
  if (!(setting.selector_type || setting.reference_kind)) return false;
  const raw = String(value ?? "").trim();
  return raw === "" || raw === "0" || raw === "null" || raw === "None";
};

window.moduleControlId = function moduleControlId(setting, token = "field") {
  const raw = `${state.moduleKey || "module"}-${setting.relative_path || setting.leaf_name || token}-${token}`;
  return `module-${raw.replace(/[^a-zA-Z0-9_-]+/g, "-")}`;
};

window.isMessagePointerSetting = function isMessagePointerSetting(setting) {
  const leaf = String(setting.leaf_name || "").toLowerCase();
  return leaf.endsWith("_message_id") || leaf === "message_id";
};

window.resolveSelectorItem = function resolveSelectorItem(setting, value) {
  const selectorType = setting.selector_type || setting.reference_kind;
  if (!selectorType || value === undefined || value === null || value === "") return null;
  return selectorItems(setting).find((item) => String(item.id) === String(value)) || null;
};

window.formatSettingValue = function formatSettingValue(setting, value) {
  if (value === undefined || value === null || value === "" || (Array.isArray(value) && !value.length) || isUnsetReferenceValue(setting, value)) {
    return "Nicht gesetzt";
  }
  if (isMessagePointerSetting(setting)) {
    return "Nachricht verknüpft";
  }
  if ((setting.selector_type || setting.reference_kind) && setting.kind !== "list") {
    const item = resolveSelectorItem(setting, value);
    return item ? resourceOptionLabel(item, setting.selector_type || setting.reference_kind) : "Nicht gefunden";
  }
  if ((setting.selector_type || setting.reference_kind) && setting.kind === "list") {
    const values = Array.isArray(value) ? value : [];
    if (!values.length) return "Nicht gesetzt";
    return values
      .map((entry) => {
        const item = resolveSelectorItem(setting, entry);
        return item ? resourceOptionLabel(item, setting.selector_type || setting.reference_kind) : null;
      })
      .filter(Boolean)
      .slice(0, 4)
      .join(", ") + (values.length > 4 ? ` +${values.length - 4}` : "");
  }
  if (setting.kind === "bool") return value ? "Aktiviert" : "Deaktiviert";
  if (setting.kind === "list") return Array.isArray(value) && value.length ? `${value.length} Einträge` : "Keine Einträge";
  if (setting.kind === "dict") return value && typeof value === "object" ? `${Object.keys(value).length} Felder` : "Leeres Objekt";
  const textValue = String(value);
  return textValue.length > 140 ? `${textValue.slice(0, 140)}…` : textValue;
};

window.sliderSpecForSetting = function sliderSpecForSetting(setting) {
  if (!["int", "float"].includes(setting.kind) || setting.selector_type) return null;
  const path = String(setting.relative_path || "").toLowerCase();
  if (path.endsWith("_id") || path.endsWith("_ids")) return null;
  const current = Number(setting.current_value ?? setting.global_value ?? setting.default_value ?? 0);
  if (!Number.isFinite(current)) return null;

  if (path.includes("priority")) return { min: 1, max: 5, step: 1 };
  if (path.includes("percent") || path.includes("chance")) return { min: 0, max: 100, step: setting.kind === "float" ? 0.1 : 1 };
  if (path.includes("minute")) return { min: 0, max: Math.max(240, Math.ceil(current / 10) * 10 || 60), step: 1 };
  if (path.includes("hour")) return { min: 0, max: Math.max(72, Math.ceil(current / 5) * 5 || 24), step: 1 };
  if (path.includes("day")) return { min: 0, max: Math.max(365, Math.ceil(current / 10) * 10 || 30), step: 1 };
  if (path.includes("limit") || path.includes("count") || path.includes("max") || path.includes("min")) {
    return { min: 0, max: Math.max(100, Math.ceil(current / 10) * 10 || 25), step: 1 };
  }
  if (Math.abs(current) <= 100) return { min: 0, max: 100, step: setting.kind === "float" ? 0.1 : 1 };
  if (Math.abs(current) <= 500) return { min: 0, max: 500, step: setting.kind === "float" ? 0.5 : 1 };
  return null;
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
  select.id = moduleControlId(setting, "select");
  select.dataset.kind = String(setting.selector_type || setting.reference_kind || "");
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = setting.example ? `Leer / ${setting.example}` : "Wert wählen";
  select.appendChild(empty);
  const items = selectorItems(setting);
  const current = isUnsetReferenceValue(setting, currentValue) ? "" : (currentValue === undefined || currentValue === null ? "" : String(currentValue));
  let found = false;
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = String(item.id);
    option.textContent = resourceOptionLabel(item, setting.selector_type || setting.reference_kind || "");
    if (String(item.id) === current) {
      option.selected = true;
      found = true;
    }
    select.appendChild(option);
  });
  if (current && !found) {
    const fallback = document.createElement("option");
    fallback.value = current;
    fallback.textContent = `${selectorTypeLabel(setting.selector_type || setting.reference_kind)} nicht gefunden`;
    fallback.selected = true;
    select.appendChild(fallback);
  }
  return select;
};

window.shouldShowExample = function shouldShowExample(setting) {
  if (!setting || !setting.example) return false;
  if (setting.selector_type) return false;
  const example = String(setting.example).trim();
  if (!example || ["123", "123456789012345678", "true", "eins,zwei,drei"].includes(example)) return false;
  return true;
};

window.buildValueControl = function buildValueControl(setting) {
  const currentValue = setting.current_value ?? setting.global_value ?? "";
  if (setting.kind === "bool") {
    const wrapper = createElement("label", "switch");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(currentValue);
    const slider = createElement("span", "switch-slider");
    const copy = createElement("span", "switch-copy", input.checked ? "Aktiviert" : "Deaktiviert");
    input.addEventListener("change", () => {
      copy.textContent = input.checked ? "Aktiviert" : "Deaktiviert";
    });
    wrapper.appendChild(input);
    wrapper.appendChild(slider);
    wrapper.appendChild(copy);
    return { node: wrapper, getValue: () => input.checked, control: input };
  }
  if (setting.selector_type && setting.kind !== "list") {
    const select = buildSelectForSetting(setting, isUnsetReferenceValue(setting, currentValue) ? "" : currentValue);
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
  const sliderSpec = sliderSpecForSetting(setting);
  if (sliderSpec) {
    const wrap = createElement("div", "field-editor");
    const input = createElement("input");
    input.type = "range";
    input.min = String(sliderSpec.min);
    input.max = String(sliderSpec.max);
    input.step = String(sliderSpec.step);
    input.value = String(currentValue || 0);
    const number = createElement("input");
    number.type = "number";
    number.min = String(sliderSpec.min);
    number.max = String(sliderSpec.max);
    number.step = String(sliderSpec.step);
    number.value = String(currentValue || 0);
    const live = createElement("div", "setting-hint", `Bereich: ${sliderSpec.min} bis ${sliderSpec.max}`);
    input.addEventListener("input", () => {
      number.value = input.value;
      live.textContent = `Aktueller Wert: ${input.value}`;
    });
    number.addEventListener("input", () => {
      input.value = number.value || "0";
      live.textContent = `Aktueller Wert: ${number.value || "0"}`;
    });
    wrap.appendChild(input);
    wrap.appendChild(number);
    wrap.appendChild(live);
    return { node: wrap, getValue: () => number.value.trim() };
  }
  const input = createElement("input");
  if (setting.kind === "int" || setting.kind === "float") input.type = "number";
  input.value = setting.sensitive ? "" : String(currentValue || "");
  input.placeholder = setting.sensitive ? "Neuen Wert setzen" : (setting.example || "Wert");
  return { node: input, getValue: () => input.value.trim() };
};

window.createListChip = function createListChip(setting, value) {
  const chip = createElement("div", "chip");
  const item = resolveSelectorItem(setting, value);
  chip.innerHTML = `<span>${escapeHtml(item ? resourceOptionLabel(item, setting.selector_type || setting.reference_kind || "") : String(value))}</span>`;
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
  const selectorPill = setting.selector_type ? `<span class="setting-pill">${escapeHtml(selectorTypeLabel(setting.selector_type))}</span>` : "";
  card.innerHTML = `
    <div class="setting-head">
      <div class="setting-copy">
        <div class="setting-path">${escapeHtml(setting.label || setting.relative_path)}</div>
        ${setting.description ? `<div class="setting-description">${escapeHtml(setting.description)}</div>` : ""}
        <div class="setting-meta-row">
          <span class="setting-pill">${escapeHtml(setting.type_label)}</span>
          ${selectorPill}
        </div>
        <div class="setting-config-key">Konfig-Schlüssel: <code>${escapeHtml(setting.relative_path)}</code></div>
      </div>
      <div class="${sourceClass}">${setting.has_override ? "Guild-Override" : "Global"}</div>
    </div>
  `;
  const values = createElement("div", "setting-values");
  const currentBox = createElement("div", "setting-value-box");
  currentBox.innerHTML = `
    <div class="setting-value-label">Aktuell</div>
    <div class="setting-value-text">${escapeHtml(formatSettingValue(setting, setting.current_value))}</div>
  `;
  const globalBox = createElement("div", "setting-value-box");
  globalBox.innerHTML = `
    <div class="setting-value-label">Basis</div>
    <div class="setting-value-text">${escapeHtml(formatSettingValue(setting, setting.global_value))}</div>
  `;
  values.appendChild(currentBox);
  values.appendChild(globalBox);
  card.appendChild(values);
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
    if (shouldShowExample(setting)) editor.appendChild(createElement("div", "setting-hint", `Beispiel: ${setting.example}`));
    const actions = createElement("div", "setting-actions");
    const saveBtn = createElement("button", "primary", setting.kind === "bool" ? "Übernehmen" : "Speichern");
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
  settingsRoot.className = "module-settings-shell";
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
  const groups = new Map();
  settings.forEach((setting) => {
    const key = String(setting.parent_path || "allgemein");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(setting);
  });
  for (const [groupKey, groupSettings] of groups.entries()) {
    const section = createElement("section", "setting-group");
    section.appendChild(createElement("div", "setting-group-title", settingGroupLabel({ parent_path: groupKey })));
    const grid = createElement("div", "settings-grid");
    groupSettings.forEach((setting) => grid.appendChild(buildSettingCard(setting)));
    section.appendChild(grid);
    settingsRoot.appendChild(section);
  }
  if (window.enhanceSelects) enhanceSelects(settingsRoot);
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
