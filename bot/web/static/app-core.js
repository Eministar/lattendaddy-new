const $ = window.$ = (id) => document.getElementById(id);

const state = window.state = {
  user: null,
  guilds: [],
  guildId: null,
  resources: null,
  modules: [],
  moduleKey: null,
  moduleDetail: null,
  moduleError: null,
  selectedTicketId: null,
};

let ticketCache = window.ticketCache = [];
let applicationCache = window.applicationCache = [];
let logSocket = window.logSocket = null;

window.escapeHtml = function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
};

window.text = function text(value, fallback = "–") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
};

window.createElement = function createElement(tag, className, textContent) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (textContent !== undefined) node.textContent = textContent;
  return node;
};

window.toast = function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2400);
};

window.api = async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: "include",
    headers: Object.assign({ "Content-Type": "application/json" }, opts.headers || {}),
    ...opts,
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`${res.status} ${txt}`);
  }
  if (res.status === 204) return null;
  return res.json();
};

window.postJson = async function postJson(path, payload) {
  return api(path, { method: "POST", body: JSON.stringify(payload) });
};

window.prettyJson = function prettyJson(value) {
  if (value === undefined || value === null || value === "") return "–";
  if (typeof value === "string") {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch (_err) {
      return value;
    }
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch (_err) {
    return String(value);
  }
};

window.formatDate = function formatDate(value) {
  if (!value) return "–";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("de-DE");
};

window.setView = function setView(view) {
  document.querySelectorAll(".view").forEach((node) => node.classList.add("hidden"));
  const active = document.getElementById(`view-${view}`);
  if (active) active.classList.remove("hidden");
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
};

window.setAuthState = function setAuthState(loggedIn) {
  $("authPanel").classList.toggle("hidden", loggedIn);
  $("userPanel").classList.toggle("hidden", !loggedIn);
  setView(loggedIn ? "overview" : "login");
};

window.selectedGuild = function selectedGuild() {
  return state.guilds.find((guild) => String(guild.id) === String(state.guildId)) || null;
};

window.requireGuild = function requireGuild() {
  if (!state.guildId) {
    toast("Bitte erst eine Guild wählen");
    throw new Error("guild_missing");
  }
  return state.guildId;
};

window.defaultAvatarUrlForUser = function defaultAvatarUrlForUser(user) {
  try {
    const rawId = BigInt(String(user?.id || 0));
    const index = Number((rawId >> 22n) % 6n);
    return `https://cdn.discordapp.com/embed/avatars/${index}.png`;
  } catch (_err) {
    return "https://cdn.discordapp.com/embed/avatars/0.png";
  }
};

window.avatarUrlForUser = function avatarUrlForUser(user) {
  if (!user) return defaultAvatarUrlForUser(null);
  if (user.avatar_url) return String(user.avatar_url);
  if (user.avatar) {
    const ext = String(user.avatar).startsWith("a_") ? "gif" : "webp";
    return `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.${ext}?size=128`;
  }
  return defaultAvatarUrlForUser(user);
};

window.guildIconUrl = function guildIconUrl(guild) {
  if (!guild) return "";
  if (guild.icon_url) return String(guild.icon_url);
  if (guild.icon) return `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.webp?size=128`;
  return "";
};

window.initials = function initials(value, fallback = "★") {
  const parts = String(value || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);
  if (!parts.length) return fallback;
  return parts.map((part) => part[0]).join("").toUpperCase();
};

window.updateGuildLabels = function updateGuildLabels() {
  const guild = selectedGuild();
  const label = guild ? `Guild: ${guild.name}` : "Keine Guild gewählt";
  $("selectedGuildLabel").textContent = label;
  $("birthdayGuildLabel").textContent = label;
};

window.renderGuilds = function renderGuilds() {
  const root = $("guildList");
  root.innerHTML = "";
  if (!state.guilds.length) {
    root.innerHTML = '<div class="muted">Keine Guilds verfügbar</div>';
    return;
  }
  for (const guild of state.guilds) {
    const item = createElement("div", `guild-item${String(state.guildId) === String(guild.id) ? " active" : ""}`);
    const icon = createElement("div", "guild-icon");
    const iconUrl = guildIconUrl(guild);
    if (iconUrl) {
      icon.style.backgroundImage = `url(${iconUrl})`;
      icon.classList.add("has-image");
    } else {
      icon.textContent = initials(guild.name, "★");
      icon.classList.add("is-fallback");
    }
    item.appendChild(icon);
    item.appendChild(createElement("div", "guild-name", guild.name));
    item.onclick = () => selectGuild(String(guild.id));
    root.appendChild(item);
  }
};

window.resolveResource = function resolveResource(listKey, id) {
  if (!state.resources || id === undefined || id === null || id === "") return null;
  const list = state.resources[listKey] || [];
  return list.find((item) => String(item.id) === String(id)) || null;
};

window.memberLabel = function memberLabel(userId) {
  const member = resolveResource("members", userId);
  if (!member) return "Unbekannter Nutzer";
  return String(member.display_name || member.name || "Unbekannter Nutzer");
};

window.channelLabel = function channelLabel(channelId) {
  const channel = resolveResource("channels", channelId) || resolveResource("threads", channelId);
  if (!channel) return "Unbekannter Kanal";
  const parent = channel.parent_name ? `${channel.parent_name} / ` : "";
  return `${parent}${channel.name}`;
};

window.roleLabel = function roleLabel(roleId) {
  const role = resolveResource("roles", roleId);
  if (!role) return "Unbekannte Rolle";
  return String(role.name || "Unbekannte Rolle");
};

window.resourceOptionLabel = function resourceOptionLabel(item, kind = "") {
  if (!item) return "Unbekannter Eintrag";
  if (kind === "user") {
    if (item.display_name && item.name && item.display_name !== item.name) {
      return `${item.display_name} · @${item.name}`;
    }
    return item.display_name || item.name || "Unbekannter Nutzer";
  }
  if (kind === "role") {
    return item.name || "Unbekannte Rolle";
  }
  if (kind === "thread") {
    const parent = item.parent_name ? `${item.parent_name} / ` : "";
    return `${parent}${item.name || "Thread"}`;
  }
  if (kind === "channel") {
    const parent = item.parent_name || item.category_name ? `${item.parent_name || item.category_name} / ` : "";
    const type = item.type ? ` · ${item.type}` : "";
    return `${parent}${item.name || "Kanal"}${type}`;
  }
  if (item.display_name || item.name) {
    return item.display_name && item.name && item.display_name !== item.name
      ? `${item.display_name} · @${item.name}`
      : (item.display_name || item.name);
  }
  return String(item.id || "Eintrag");
};

window.parseFields = function parseFields(raw) {
  const lines = String(raw || "").split("\n").map((line) => line.trim()).filter(Boolean);
  const out = [];
  for (const line of lines) {
    const parts = line.split("|");
    const name = (parts[0] || "").trim();
    const value = (parts[1] || "").trim();
    const inline = ((parts[2] || "").trim().toLowerCase() === "true");
    if (!name || !value) continue;
    out.push({ name, value, inline });
  }
  return out;
};

window.statusBadge = function statusBadge(status) {
  if (status === "closed") return { text: "geschlossen" };
  if (status === "claimed") return { text: "geclaimed" };
  return { text: "offen" };
};

window.currentTicket = function currentTicket() {
  return ticketCache.find((ticket) => String(ticket.id) === String(state.selectedTicketId)) || null;
};

window.selectTicket = function selectTicket(ticketId) {
  state.selectedTicketId = ticketId ? String(ticketId) : null;
  renderTickets();
  renderTicketDetail();
  populateOperationalSelectors();
};

window.renderTicketDetail = function renderTicketDetail() {
  const ticket = currentTicket();
  const root = $("ticketDetail");
  const badge = $("ticketSelectedBadge");
  if (!root || !badge) return;
  if (!ticket) {
    badge.textContent = "Kein Ticket gewählt";
    root.className = "empty-state";
    root.textContent = "Wähle links ein Ticket aus, um Status, Besitzer und Aktionen zu sehen.";
    return;
  }
  const status = statusBadge(ticket.status);
  badge.textContent = `#${ticket.id} · ${status.text}`;
  root.className = "ticket-focus";
  root.innerHTML = `
    <div class="ticket-focus-head">
      <div class="ticket-focus-user">${escapeHtml(memberLabel(ticket.user_id))}</div>
      <div class="ticket-focus-status">${escapeHtml(status.text)}</div>
    </div>
    <div class="ticket-focus-grid">
      <div class="ticket-focus-item">
        <span>Thread</span>
        <strong>${escapeHtml(channelLabel(ticket.thread_id))}</strong>
      </div>
      <div class="ticket-focus-item">
        <span>Claimed by</span>
        <strong>${escapeHtml(ticket.claimed_by ? memberLabel(ticket.claimed_by) : "Niemand")}</strong>
      </div>
      <div class="ticket-focus-item">
        <span>Erstellt</span>
        <strong>${escapeHtml(formatDate(ticket.created_at))}</strong>
      </div>
      <div class="ticket-focus-item">
        <span>Bewertung</span>
        <strong>${escapeHtml(text(ticket.rating, "Keine"))}</strong>
      </div>
    </div>
  `;
};

window.populateOperationalSelectors = function populateOperationalSelectors() {
  if (!state.resources) return;
  const members = state.resources.members || [];
  const roles = state.resources.roles || [];
  const channels = channelCandidates(true);
  const threads = ticketCache.map((ticket) => ({
    id: ticket.thread_id,
    name: channelLabel(ticket.thread_id),
    parent_name: "",
    type: "ticket",
  }));
  const uniqueThreads = [];
  const seenThreads = new Set();
  threads.forEach((thread) => {
    const key = String(thread.id);
    if (seenThreads.has(key)) return;
    seenThreads.add(key);
    uniqueThreads.push(thread);
  });

  fillTypedSelect("ticketThreadId", uniqueThreads, "Ticket-Thread wählen", "thread", currentTicket()?.thread_id || "");
  fillTypedSelect("ticketActorId", members, "Staff-Mitglied wählen", "user", $("ticketActorId")?.value || state.user?.id || "");
  fillTypedSelect("ticketUserId", members, "Teilnehmer wählen", "user", "");

  fillTypedSelect("timeoutUserId", members, "User wählen", "user", $("timeoutUserId")?.value || "");
  fillTypedSelect("timeoutModeratorId", members, "Moderator wählen", "user", $("timeoutModeratorId")?.value || state.user?.id || "");
  fillTypedSelect("kickUserId", members, "User wählen", "user", $("kickUserId")?.value || "");
  fillTypedSelect("kickModeratorId", members, "Moderator wählen", "user", $("kickModeratorId")?.value || state.user?.id || "");
  fillTypedSelect("banUserId", members, "User wählen", "user", $("banUserId")?.value || "");
  fillTypedSelect("banModeratorId", members, "Moderator wählen", "user", $("banModeratorId")?.value || state.user?.id || "");
  fillTypedSelect("purgeChannelId", channels, "Kanal wählen", "channel", $("purgeChannelId")?.value || "");
  fillTypedSelect("purgeModeratorId", members, "Moderator wählen", "user", $("purgeModeratorId")?.value || state.user?.id || "");
  fillTypedSelect("purgeUserId", members, "Optional: nur diesen User", "user", $("purgeUserId")?.value || "");
  fillTypedSelect("roleAddUserId", members, "User wählen", "user", $("roleAddUserId")?.value || "");
  fillTypedSelect("roleAddRoleId", roles, "Rolle wählen", "role", $("roleAddRoleId")?.value || "");
  fillTypedSelect("roleRemoveUserId", members, "User wählen", "user", $("roleRemoveUserId")?.value || "");
  fillTypedSelect("roleRemoveRoleId", roles, "Rolle wählen", "role", $("roleRemoveRoleId")?.value || "");
};

window.renderTickets = function renderTickets() {
  const root = $("tickets");
  const query = $("ticketSearch").value.trim().toLowerCase();
  root.innerHTML = "";
  const rows = ticketCache.filter((ticket) => {
    if (!query) return true;
    const haystack = [ticket.id, ticket.user_id, ticket.thread_id, ticket.claimed_by, memberLabel(ticket.user_id), channelLabel(ticket.thread_id)].join(" ").toLowerCase();
    return haystack.includes(query);
  });
  if (!rows.length) {
    root.innerHTML = '<div class="list-item">Keine Tickets.</div>';
    return;
  }
  rows.forEach((ticket) => {
    const badge = statusBadge(ticket.status);
    const selectedClass = String(ticket.id) === String(state.selectedTicketId) ? " selected" : "";
    const div = createElement("div", `ticket${selectedClass}`);
    div.innerHTML = `
      <div class="ticket-row">
        <span class="badge-status">${escapeHtml(badge.text)} · #${escapeHtml(ticket.id)}</span>
        <small class="ticket-meta">${escapeHtml(formatDate(ticket.created_at))}</small>
      </div>
      <div><strong>User:</strong> ${escapeHtml(memberLabel(ticket.user_id))}</div>
      <div><strong>Thread:</strong> ${escapeHtml(channelLabel(ticket.thread_id))}</div>
      <div><strong>Claimed by:</strong> ${escapeHtml(ticket.claimed_by ? memberLabel(ticket.claimed_by) : "Niemand")}</div>
      <div><strong>Rating:</strong> <code>${escapeHtml(text(ticket.rating, "-"))}</code></div>
    `;
    div.onclick = () => selectTicket(ticket.id);
    root.appendChild(div);
  });
};

window.renderApplicationsList = function renderApplicationsList() {
  const root = $("applicationsList");
  root.innerHTML = "";
  if (!applicationCache.length) {
    root.innerHTML = '<div class="list-item">Keine Bewerbungen.</div>';
    return;
  }
  applicationCache.forEach((row) => {
    const member = resolveResource("members", row.user_id);
    const avatar = member?.avatar_url || defaultAvatarUrlForUser({ id: row.user_id });
    const div = createElement("div", "list-item");
    div.innerHTML = `
      <div class="entity-row">
        <img class="avatar-chip" src="${escapeHtml(avatar)}" alt="Avatar">
        <div class="entity-copy">
          <div class="entity-title">${escapeHtml(memberLabel(row.user_id))}</div>
          <div class="entity-sub">Bewerbung #${escapeHtml(row.id)} · ${escapeHtml(channelLabel(row.thread_id))}</div>
        </div>
        <span class="status-pill">${escapeHtml(row.status)}</span>
      </div>
      <div class="list-meta">Erstellt ${escapeHtml(formatDate(row.created_at))}</div>
    `;
    root.appendChild(div);
  });
};

window.parsePayloadObject = function parsePayloadObject(payload) {
  if (payload && typeof payload === "object") return payload;
  if (typeof payload === "string") {
    try {
      return JSON.parse(payload);
    } catch (_err) {
      return { text: payload };
    }
  }
  return {};
};

window.looksLikeEmbedObject = function looksLikeEmbedObject(value) {
  return Boolean(
    value
    && typeof value === "object"
    && !Array.isArray(value)
    && (
      value.title
      || value.description
      || value.fields
      || value.thumbnail
      || value.image
      || value.footer
      || value.author
    )
  );
};

window.collectEmbedObjects = function collectEmbedObjects(value, out = [], depth = 0) {
  if (!value || depth > 3) return out;
  if (Array.isArray(value)) {
    value.forEach((item) => collectEmbedObjects(item, out, depth + 1));
    return out;
  }
  if (looksLikeEmbedObject(value)) out.push(value);
  if (typeof value === "object") {
    Object.entries(value).forEach(([key, item]) => {
      if (["embed", "embeds", "message", "messages", "data", "payload"].includes(String(key))) {
        collectEmbedObjects(item, out, depth + 1);
      }
    });
  }
  return out;
};

window.renderEmbedCardHtml = function renderEmbedCardHtml(embed) {
  const fields = Array.isArray(embed.fields) ? embed.fields : [];
  const author = embed.author?.name || "";
  const footer = typeof embed.footer === "object" ? embed.footer.text : embed.footer;
  const thumb = typeof embed.thumbnail === "object" ? embed.thumbnail.url : embed.thumbnail;
  const image = typeof embed.image === "object" ? embed.image.url : embed.image;
  return `
    <div class="log-embed">
      <div class="embed-shell">
        ${thumb ? `<img class="embed-thumb" src="${escapeHtml(thumb)}" alt="Thumbnail">` : ""}
        <div class="embed-body">
          ${author ? `<div class="embed-author">${escapeHtml(author)}</div>` : ""}
          ${embed.title ? `<div class="embed-title">${escapeHtml(embed.title)}</div>` : ""}
          ${embed.description ? `<div class="embed-desc">${escapeHtml(embed.description)}</div>` : ""}
          ${fields.length ? `<div class="embed-fields">${fields.map((field) => `<div class="embed-field"><strong>${escapeHtml(field.name || "")}</strong><div>${escapeHtml(field.value || "")}</div></div>`).join("")}</div>` : ""}
          ${image ? `<img class="embed-image" src="${escapeHtml(image)}" alt="Embed Bild">` : ""}
          ${footer ? `<div class="embed-footer">${escapeHtml(footer)}</div>` : ""}
        </div>
      </div>
    </div>
  `;
};

window.renderLogs = function renderLogs(list, prepend = false) {
  const root = $("logs");
  if (!prepend) root.innerHTML = "";
  if (!list.length && !prepend) {
    root.innerHTML = '<div class="list-item">Keine Logs.</div>';
    return;
  }
  list.forEach((row) => {
    const payload = parsePayloadObject(row.payload);
    const embeds = collectEmbedObjects(payload);
    const factEntries = Object.entries(payload || {})
      .filter(([key, value]) => !["embed", "embeds", "message", "messages", "data", "payload"].includes(String(key)) && (typeof value !== "object" || value === null))
      .slice(0, 6);
    const div = createElement("div", "list-item log-card");
    div.innerHTML = `
      <div class="log-head">
        <strong class="log-title">${escapeHtml(row.event)}</strong>
        <span class="status-pill subtle">${escapeHtml(formatDate(row.created_at))}</span>
      </div>
      ${factEntries.length ? `<div class="log-facts">${factEntries.map(([key, value]) => `<div class="log-fact"><span>${escapeHtml(key)}</span><strong>${escapeHtml(String(value))}</strong></div>`).join("")}</div>` : ""}
      ${embeds.length ? `<div class="log-embed-stack">${embeds.slice(0, 3).map((embed) => renderEmbedCardHtml(embed)).join("")}</div>` : ""}
      <details class="log-json">
        <summary>Rohdaten</summary>
        <pre class="json-block pretty-json">${escapeHtml(prettyJson(payload))}</pre>
      </details>
    `;
    if (prepend) root.prepend(div); else root.appendChild(div);
  });
};

window.channelCandidates = function channelCandidates(forMessaging = false) {
  if (!state.resources) return [];
  const channels = [...(state.resources.channels || [])];
  const threads = [...(state.resources.threads || [])].map((thread) => ({ ...thread, type: "thread" }));
  const all = [...channels, ...threads];
  if (!forMessaging) return all;
  return all.filter((item) => !["category", "voice", "stage_voice", "forum"].includes(String(item.type || "")));
};

window.optionLabel = function optionLabel(item) {
  if (!item) return "Eintrag";
  if (item.display_name || item.name) {
    if ("parent_name" in item || "category_name" in item || item.type) {
      return resourceOptionLabel(item, item.type === "thread" ? "thread" : "channel");
    }
    if ("position" in item && !("display_name" in item)) {
      return resourceOptionLabel(item, "role");
    }
    return resourceOptionLabel(item, "user");
  }
  return String(item.id || "Eintrag");
};

window.fillSelect = function fillSelect(selectId, items, placeholder, currentValue = "") {
  const select = $(selectId);
  if (!select) return;
  select.dataset.kind = "";
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = placeholder;
  select.appendChild(empty);
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = String(item.id);
    option.textContent = optionLabel(item);
    if (String(item.id) === String(currentValue || "")) option.selected = true;
    select.appendChild(option);
  });
};

window.fillTypedSelect = function fillTypedSelect(selectId, items, placeholder, kind, currentValue = "") {
  const select = $(selectId);
  if (!select) return;
  select.dataset.kind = String(kind || "");
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = placeholder;
  select.appendChild(empty);
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = String(item.id);
    option.textContent = resourceOptionLabel(item, kind);
    if (String(item.id) === String(currentValue || "")) option.selected = true;
    select.appendChild(option);
  });
};

window.resourceLookupByKind = function resourceLookupByKind(kind, id) {
  if (!state.resources || !id) return null;
  const value = String(id);
  if (kind === "user") return (state.resources.members || []).find((item) => String(item.id) === value) || null;
  if (kind === "role") return (state.resources.roles || []).find((item) => String(item.id) === value) || null;
  if (kind === "thread") return (state.resources.threads || []).find((item) => String(item.id) === value) || null;
  if (kind === "channel") {
    return [...(state.resources.channels || []), ...(state.resources.threads || [])].find((item) => String(item.id) === value) || null;
  }
  return null;
};

window.pickerOptionMarkup = function pickerOptionMarkup(select, option, selected = false) {
  const value = String(option.value || "");
  const label = option.textContent || option.label || "";
  const kind = String(select.dataset.kind || "");
  const item = resourceLookupByKind(kind, value);
  const checked = selected ? '<span class="picker-check">✓</span>' : '<span class="picker-check empty"></span>';
  if (!value) {
    return `<span class="picker-option-copy"><strong>${escapeHtml(label)}</strong></span>${checked}`;
  }
  if (kind === "user") {
    const avatar = item?.avatar_url || defaultAvatarUrlForUser({ id: value });
    const handle = item?.name ? `@${item.name}` : "";
    return `
      <span class="picker-option-main">
        <img class="picker-avatar" src="${escapeHtml(avatar)}" alt="Avatar">
        <span class="picker-option-copy">
          <strong>${escapeHtml(item?.display_name || label)}</strong>
          <small>${escapeHtml(handle || label)}</small>
        </span>
      </span>
      ${checked}
    `;
  }
  if (kind === "role") {
    const swatch = item?.color && item.color !== "#000000"
      ? `<span class="picker-swatch" style="background:${escapeHtml(item.color)}"></span>`
      : '<span class="picker-swatch neutral"></span>';
    return `
      <span class="picker-option-main">
        ${swatch}
        <span class="picker-option-copy">
          <strong>${escapeHtml(item?.name || label)}</strong>
          <small>Rolle</small>
        </span>
      </span>
      ${checked}
    `;
  }
  if (kind === "channel" || kind === "thread") {
    const icon = kind === "thread" ? "🧵" : "#";
    return `
      <span class="picker-option-main">
        <span class="picker-channel-icon">${icon}</span>
        <span class="picker-option-copy">
          <strong>${escapeHtml(item ? resourceOptionLabel(item, kind) : label)}</strong>
          <small>${escapeHtml(kind === "thread" ? "Thread" : "Kanal")}</small>
        </span>
      </span>
      ${checked}
    `;
  }
  return `
    <span class="picker-option-copy">
      <strong>${escapeHtml(label)}</strong>
    </span>
    ${checked}
  `;
};

window.closePickers = function closePickers(exceptId = "") {
  document.querySelectorAll(".picker.open").forEach((picker) => {
    if (exceptId && picker.dataset.selectId === exceptId) return;
    picker.classList.remove("open");
  });
};

window.refreshPicker = function refreshPicker(selectId) {
  const select = typeof selectId === "string" ? $(selectId) : selectId;
  if (!select || select.tagName !== "SELECT") return;
  if (!select.id) return;

  let picker = select.nextElementSibling;
  if (!picker || !picker.classList.contains("picker")) {
    picker = document.createElement("div");
    picker.className = "picker";
    picker.dataset.selectId = select.id;
    picker.innerHTML = `
      <button type="button" class="picker-trigger"></button>
      <div class="picker-menu">
        <div class="picker-search-wrap">
          <input type="text" class="picker-search" placeholder="Suchen…">
        </div>
        <div class="picker-options"></div>
      </div>
    `;
    select.classList.add("picker-native");
    select.after(picker);
    const trigger = picker.querySelector(".picker-trigger");
    const search = picker.querySelector(".picker-search");
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      const shouldOpen = !picker.classList.contains("open");
      closePickers(shouldOpen ? select.id : "");
      picker.classList.toggle("open", shouldOpen);
      if (shouldOpen) {
        search.value = "";
        refreshPicker(select);
        search.focus();
      }
    });
    search.addEventListener("input", () => refreshPicker(select));
    select.addEventListener("change", () => refreshPicker(select));
  }

  const trigger = picker.querySelector(".picker-trigger");
  const optionsRoot = picker.querySelector(".picker-options");
  const search = picker.querySelector(".picker-search");
  const query = String(search.value || "").trim().toLowerCase();
  const selectedOption = select.options[select.selectedIndex] || select.options[0];
  trigger.innerHTML = `
    <span class="picker-trigger-copy">${pickerOptionMarkup(select, selectedOption || { value: "", textContent: "Wählen" })}</span>
    <span class="picker-caret">▾</span>
  `;

  optionsRoot.innerHTML = "";
  Array.from(select.options).forEach((option) => {
    const label = String(option.textContent || option.label || "").toLowerCase();
    if (query && !label.includes(query)) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `picker-option${option.selected ? " active" : ""}`;
    button.innerHTML = pickerOptionMarkup(select, option, option.selected);
    button.addEventListener("click", () => {
      select.value = option.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      select.dispatchEvent(new Event("input", { bubbles: true }));
      picker.classList.remove("open");
    });
    optionsRoot.appendChild(button);
  });

  if (!optionsRoot.childNodes.length) {
    optionsRoot.innerHTML = '<div class="picker-empty">Keine Treffer</div>';
  }
};

window.enhanceSelects = function enhanceSelects(root = document) {
  root.querySelectorAll("select").forEach((select) => refreshPicker(select));
};

window.populateMessagingSelectors = function populateMessagingSelectors() {
  const items = channelCandidates(true);
  fillTypedSelect("msgChannelSelect", items, "Channel wählen", "channel");
  fillTypedSelect("embedChannelSelect", items, "Channel wählen", "channel");
};

window.currentEmbedPayload = function currentEmbedPayload() {
  return {
    title: $("embedTitle").value.trim(),
    description: $("embedDesc").value.trim(),
    fields: parseFields($("embedFields").value),
    thumbnail: $("embedThumbnail").value.trim(),
    image: $("embedImage").value.trim(),
    footer: $("embedFooter").value.trim(),
    color: $("embedColor").value.trim() || "#f8d66f",
  };
};

window.renderEmbedPreview = function renderEmbedPreview() {
  const payload = currentEmbedPayload();
  const root = $("embedPreview");
  if (!payload.title && !payload.description && !payload.image && !payload.thumbnail && !payload.fields.length) {
    root.className = "embed-preview empty-state";
    root.textContent = "Fülle rechts Titel, Beschreibung oder Bilder aus.";
    return;
  }
  root.className = "embed-preview";
  root.innerHTML = "";
  if (payload.title) root.appendChild(createElement("div", "embed-preview-title", payload.title));
  if (payload.description) root.appendChild(createElement("div", "embed-preview-desc", payload.description));
  if (payload.fields.length) {
    const fields = createElement("div", "embed-preview-fields");
    payload.fields.forEach((field) => {
      const item = createElement("div", "embed-preview-field");
      item.innerHTML = `<strong>${escapeHtml(field.name)}</strong><div>${escapeHtml(field.value)}</div>`;
      fields.appendChild(item);
    });
    root.appendChild(fields);
  }
  const media = createElement("div", "embed-preview-media");
  if (payload.thumbnail) {
    const thumb = document.createElement("img");
    thumb.className = "embed-preview-thumb";
    thumb.src = payload.thumbnail;
    thumb.alt = "Thumbnail";
    media.appendChild(thumb);
  }
  if (payload.image) {
    const image = document.createElement("img");
    image.src = payload.image;
    image.alt = "Embed Bild";
    media.appendChild(image);
  }
  if (media.childNodes.length) root.appendChild(media);
  if (payload.footer) root.appendChild(createElement("div", "embed-preview-footer", payload.footer));
};

window.loadGlobalSummary = async function loadGlobalSummary() {
  const data = await api("/api/global/summary");
  const tickets = data.tickets || {};
  $("globalTickets").textContent = tickets.total ?? 0;
  $("globalGiveaways").textContent = data.giveaways ?? 0;
  $("globalPolls").textContent = data.polls ?? 0;
  $("globalApps").textContent = data.applications ?? 0;
  $("globalBirthdays").textContent = data.birthdays ?? 0;
};

window.loadGuildSummary = async function loadGuildSummary() {
  const gid = requireGuild();
  const data = await api(`/api/guilds/${gid}/summary`);
  const tickets = data.tickets || {};
  $("guildTicketsOpen").textContent = tickets.open ?? 0;
  $("guildTicketsTotal").textContent = tickets.total ?? 0;
  $("guildGiveaways").textContent = data.giveaways ?? 0;
  $("guildPolls").textContent = data.polls ?? 0;
  $("guildApps").textContent = data.applications ?? 0;
};

window.loadResources = async function loadResources() {
  const gid = requireGuild();
  state.resources = await api(`/api/guilds/${gid}/resources`);
  populateMessagingSelectors();
  populateOperationalSelectors();
  enhanceSelects();
  renderTickets();
  renderTicketDetail();
  renderApplicationsList();
  if (window.renderModuleEditor) renderModuleEditor();
};

window.loadTickets = async function loadTickets() {
  const gid = requireGuild();
  ticketCache = window.ticketCache = await api(`/api/guilds/${gid}/tickets?limit=200`);
  if (!currentTicket() && ticketCache.length) {
    state.selectedTicketId = String(ticketCache[0].id);
  }
  renderTickets();
  renderTicketDetail();
  populateOperationalSelectors();
  enhanceSelects();
};

window.loadApplicationsList = async function loadApplicationsList() {
  const gid = requireGuild();
  applicationCache = window.applicationCache = await api(`/api/guilds/${gid}/applications/list?limit=100`);
  renderApplicationsList();
};

window.loadLogs = async function loadLogs() {
  renderLogs(await api("/api/logs?limit=200"));
};

window.connectLogs = function connectLogs() {
  if (logSocket && logSocket.readyState === 1) return;
  const status = $("logsLiveStatus");
  status.textContent = "Verbinde…";
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  logSocket = window.logSocket = new WebSocket(`${protocol}://${location.host}/ws/logs`);
  logSocket.onopen = () => { status.textContent = "Verbunden"; };
  logSocket.onclose = () => { status.textContent = "Getrennt"; };
  logSocket.onerror = () => { status.textContent = "Fehler"; };
  logSocket.onmessage = (event) => {
    try {
      renderLogs([JSON.parse(event.data)], true);
    } catch (_err) {
      /* ignore */
    }
  };
};

window.searchUsers = async function searchUsers() {
  const gid = requireGuild();
  const query = $("userSearchInput").value.trim();
  if (!query) return;
  const list = await api(`/api/guilds/${gid}/users/search?query=${encodeURIComponent(query)}`);
  const root = $("userSearchResults");
  root.innerHTML = "";
  if (!list.length) {
    root.innerHTML = '<div class="list-item">Keine Treffer.</div>';
    return;
  }
  list.forEach((row) => {
    const member = resolveResource("members", row.id);
    const avatar = member?.avatar_url || defaultAvatarUrlForUser({ id: row.id });
    const div = createElement("div", "list-item");
    div.innerHTML = `
      <div class="entity-row">
        <img class="avatar-chip" src="${escapeHtml(avatar)}" alt="Avatar">
        <div class="entity-copy">
          <div class="entity-title">${escapeHtml(row.display_name)}</div>
          <div class="entity-sub">@${escapeHtml(row.name || row.display_name)}</div>
        </div>
      </div>
    `;
    root.appendChild(div);
  });
};

window.loadLiveUsers = async function loadLiveUsers() {
  const gid = requireGuild();
  const list = await api(`/api/guilds/${gid}/users/live?limit=50`);
  const root = $("userLive");
  root.innerHTML = "";
  if (!list.length) {
    root.innerHTML = '<div class="list-item">Keine aktiven User.</div>';
    return;
  }
  list.forEach((row) => {
    const member = resolveResource("members", row.id);
    const avatar = member?.avatar_url || defaultAvatarUrlForUser({ id: row.id });
    const div = createElement("div", "list-item");
    div.innerHTML = `
      <div class="entity-row">
        <div class="avatar-stack">
          <img class="avatar-chip" src="${escapeHtml(avatar)}" alt="Avatar">
          <span class="presence-dot ${escapeHtml(String(row.status || "offline"))}"></span>
        </div>
        <div class="entity-copy">
          <div class="entity-title">${escapeHtml(row.display_name)}</div>
          <div class="entity-sub">${escapeHtml(String(row.status || "offline"))}</div>
        </div>
      </div>
    `;
    root.appendChild(div);
  });
};

window.loadBirthdays = async function loadBirthdays() {
  const data = await api("/api/global/birthdays?limit=50&offset=0");
  const root = $("birthdays");
  root.innerHTML = "";
  if (!(data.items || []).length) {
    root.innerHTML = '<div class="list-item">Keine Geburtstage.</div>';
    return;
  }
  data.items.forEach((row) => {
    const div = createElement("div", "list-item");
    const label = row.display_name || row.username || memberLabel(row.user_id);
    div.innerHTML = `
      <div class="entity-row">
        <img class="avatar-chip" src="${escapeHtml(row.avatar_url || defaultAvatarUrlForUser({ id: row.user_id }))}" alt="Avatar">
        <div class="entity-copy">
          <div class="entity-title">${escapeHtml(label)}</div>
          <div class="entity-sub">${escapeHtml(`${row.day}.${row.month}.${row.year}`)}</div>
        </div>
      </div>
    `;
    root.appendChild(div);
  });
};

window.loadBirthdaySummary = async function loadBirthdaySummary() {
  const gid = requireGuild();
  const data = await api(`/api/guilds/${gid}/birthdays/summary`);
  $("birthdayTodayCount").textContent = data.total_today ?? 0;
  $("birthdayNextCount").textContent = data.total_next ?? 0;
  $("birthdayBoosterCount").textContent = data.total_boosters ?? 0;
  $("birthdayTotalCount").textContent = data.total_birthdays ?? 0;
  $("birthdayTodayBadge").textContent = data.date ? formatDate(data.date) : (data.total_today ?? 0);
  $("birthdayNextBadge").textContent = data.total_next ?? 0;
  $("birthdayBoosterBadge").textContent = data.total_boosters ?? 0;

  const renderList = (rootId, items, mapper, emptyText) => {
    const root = $(rootId);
    root.innerHTML = "";
    if (!items.length) {
      root.innerHTML = `<div class="list-item">${escapeHtml(emptyText)}</div>`;
      return;
    }
    items.forEach((item) => {
      const div = createElement("div", "list-item");
      div.innerHTML = mapper(item);
      root.appendChild(div);
    });
  };

  renderList("birthdaysToday", data.today || [], (row) => `<strong>${escapeHtml(row.display_name)}</strong><div class="list-meta">${escapeHtml(row.age ? `wird ${row.age}` : "Alter unbekannt")}</div>`, "Heute hat niemand Geburtstag.");
  renderList("birthdaysNext", data.next || [], (row) => `<strong>${escapeHtml(row.display_name)}</strong><div class="list-meta">${escapeHtml(`${row.day}.${row.month} · in ${row.days_until} Tagen${row.turns ? ` · wird ${row.turns}` : ""}`)}</div>`, "Keine anstehenden Termine.");
  renderList("boosters", data.boosters || [], (row) => `<strong>${escapeHtml(row.display_name)}</strong><div class="list-meta">Booster seit ${escapeHtml(formatDate(row.premium_since))}</div>`, "Keine Booster gespeichert.");
};

window.refreshGuildData = async function refreshGuildData() {
  const tasks = [
    loadGuildSummary(),
    loadResources(),
    loadTickets(),
    loadApplicationsList(),
    loadBirthdaySummary(),
    window.loadModules ? loadModules() : Promise.resolve(),
  ];
  const results = await Promise.allSettled(tasks);
  const failed = results.filter((result) => result.status === "rejected");
  if (failed.length) {
    const first = failed[0];
    throw new Error(first.reason?.message || "Ein Teil der Guild-Daten konnte nicht geladen werden");
  }
};

window.selectGuild = async function selectGuild(guildId) {
  state.guildId = String(guildId);
  state.resources = null;
  localStorage.setItem("starry_guild", state.guildId);
  renderGuilds();
  updateGuildLabels();
  try {
    await refreshGuildData();
  } catch (err) {
    toast(err.message || "Guild-Daten konnten nicht geladen werden");
  }
};

window.initDashboard = async function initDashboard() {
  try {
    if (!window.__starryPickerBound) {
      document.addEventListener("click", (event) => {
        if (event.target.closest(".picker")) return;
        closePickers();
      });
      window.__starryPickerBound = true;
    }
    const me = await api("/api/me");
    state.user = me.user ? { ...me.user, id: String(me.user.id || "") } : null;
    state.guilds = (me.guilds || []).map((guild) => ({ ...guild, id: String(guild.id || "") }));
    setAuthState(true);
    $("userName").textContent = state.user.display_name || state.user.username;
    const avatar = avatarUrlForUser(state.user);
    $("userAvatar").src = avatar;
    $("userAvatar").alt = `${state.user.display_name || state.user.username} Avatar`;
    $("userAvatar").onerror = () => {
      $("userAvatar").src = defaultAvatarUrlForUser(state.user);
    };
    renderGuilds();
    if (window.renderModuleSidebar) renderModuleSidebar();
    if (window.renderQuickModules) renderQuickModules();
    enhanceSelects();
    const rememberedGuild = String(localStorage.getItem("starry_guild") || "").trim();
    if (rememberedGuild && state.guilds.find((guild) => String(guild.id) === rememberedGuild)) {
      await selectGuild(rememberedGuild);
    } else if (state.guilds.length) {
      await selectGuild(String(state.guilds[0].id));
    }
    await loadGlobalSummary();
    renderEmbedPreview();
  } catch (_err) {
    setAuthState(false);
  }
};
