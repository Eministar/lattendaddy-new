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
  if (!member) return `User ${userId}`;
  return `${member.display_name} (${member.id})`;
};

window.channelLabel = function channelLabel(channelId) {
  const channel = resolveResource("channels", channelId) || resolveResource("threads", channelId);
  if (!channel) return `Channel ${channelId}`;
  const parent = channel.parent_name ? `${channel.parent_name} / ` : "";
  return `${parent}${channel.name} (${channel.id})`;
};

window.roleLabel = function roleLabel(roleId) {
  const role = resolveResource("roles", roleId);
  if (!role) return `Rolle ${roleId}`;
  return `${role.name} (${role.id})`;
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
    const div = createElement("div", "ticket");
    div.innerHTML = `
      <div class="ticket-row">
        <span class="badge-status">${escapeHtml(badge.text)} · #${escapeHtml(ticket.id)}</span>
        <small class="ticket-meta">${escapeHtml(formatDate(ticket.created_at))}</small>
      </div>
      <div><strong>User:</strong> ${escapeHtml(memberLabel(ticket.user_id))}</div>
      <div><strong>Thread:</strong> ${escapeHtml(channelLabel(ticket.thread_id))}</div>
      <div><strong>Claimed by:</strong> ${escapeHtml(ticket.claimed_by ? memberLabel(ticket.claimed_by) : "-")}</div>
      <div><strong>Rating:</strong> <code>${escapeHtml(text(ticket.rating, "-"))}</code></div>
    `;
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
    const div = createElement("div", "list-item");
    div.innerHTML = `
      <strong>#${escapeHtml(row.id)}</strong>
      <div>${escapeHtml(memberLabel(row.user_id))}</div>
      <div class="list-meta">${escapeHtml(channelLabel(row.thread_id))}</div>
      <div class="list-meta">${escapeHtml(row.status)} · ${escapeHtml(formatDate(row.created_at))}</div>
    `;
    root.appendChild(div);
  });
};

window.renderLogs = function renderLogs(list, prepend = false) {
  const root = $("logs");
  if (!prepend) root.innerHTML = "";
  if (!list.length && !prepend) {
    root.innerHTML = '<div class="list-item">Keine Logs.</div>';
    return;
  }
  list.forEach((row) => {
    const div = createElement("div", "list-item");
    div.innerHTML = `
      <strong>${escapeHtml(row.event)}</strong>
      <div class="list-meta">${escapeHtml(formatDate(row.created_at))}</div>
      <pre class="json-block">${escapeHtml(prettyJson(row.payload))}</pre>
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
  const parent = item.parent_name ? `${item.parent_name} / ` : "";
  const type = item.type ? ` · ${item.type}` : "";
  return `${parent}${item.name}${type}`;
};

window.fillSelect = function fillSelect(selectId, items, placeholder, currentValue = "") {
  const select = $(selectId);
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

window.populateMessagingSelectors = function populateMessagingSelectors() {
  const items = channelCandidates(true);
  fillSelect("msgChannelSelect", items, "Channel wählen");
  fillSelect("embedChannelSelect", items, "Channel wählen");
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
  renderTickets();
  renderApplicationsList();
  if (window.renderModuleEditor) renderModuleEditor();
};

window.loadTickets = async function loadTickets() {
  const gid = requireGuild();
  ticketCache = window.ticketCache = await api(`/api/guilds/${gid}/tickets?limit=200`);
  renderTickets();
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
    const div = createElement("div", "list-item");
    div.innerHTML = `
      <div class="inline-identity">
        ${member && member.avatar_url ? `<img class="avatar-chip" src="${escapeHtml(member.avatar_url)}" alt="Avatar">` : ""}
        <strong>${escapeHtml(row.display_name)}</strong>
      </div>
      <div class="list-meta">${escapeHtml(row.id)}</div>
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
    const div = createElement("div", "list-item");
    div.innerHTML = `
      <div class="inline-identity">
        ${member && member.avatar_url ? `<img class="avatar-chip" src="${escapeHtml(member.avatar_url)}" alt="Avatar">` : ""}
        <strong>${escapeHtml(row.display_name)}</strong>
      </div>
      <div class="list-meta">${escapeHtml(row.id)} · ${escapeHtml(row.status)}</div>
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
      <div class="inline-identity">
        <img class="avatar-chip" src="${escapeHtml(row.avatar_url || defaultAvatarUrlForUser({ id: row.user_id }))}" alt="Avatar">
        <strong>${escapeHtml(label)}</strong>
      </div>
      <div class="list-meta">${escapeHtml(`${row.day}.${row.month}.${row.year}`)} · ${escapeHtml(String(row.user_id))}</div>
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

  renderList("birthdaysToday", data.today || [], (row) => `<strong>${escapeHtml(row.display_name)}</strong><div class="list-meta">${escapeHtml(row.user_id)} · ${escapeHtml(row.age ? `wird ${row.age}` : "–")}</div>`, "Heute hat niemand Geburtstag.");
  renderList("birthdaysNext", data.next || [], (row) => `<strong>${escapeHtml(row.display_name)}</strong><div class="list-meta">${escapeHtml(`${row.day}.${row.month} · in ${row.days_until} Tagen${row.turns ? ` · wird ${row.turns}` : ""}`)}</div>`, "Keine anstehenden Termine.");
  renderList("boosters", data.boosters || [], (row) => `<strong>${escapeHtml(row.display_name)}</strong><div class="list-meta">${escapeHtml(row.user_id)} · seit ${escapeHtml(formatDate(row.premium_since))}</div>`, "Keine Booster gespeichert.");
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
