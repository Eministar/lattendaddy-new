Array.from(document.querySelectorAll(".nav-btn")).forEach((btn) => {
  btn.addEventListener("click", () => {
    const view = btn.dataset.view;
    setView(view);
    if (view === "birthdays") {
      loadBirthdaySummary().catch((err) => toast(err.message));
    }
    if (view === "logs") loadLogs().catch((err) => toast(err.message));
    if (view === "settings" && state.moduleKey) renderModuleEditor();
  });
});

$("loginBtn").onclick = () => (window.location.href = "/login");
$("loginHero").onclick = () => (window.location.href = "/login");
$("logoutBtn").onclick = () => (window.location.href = "/logout");

$("refreshGlobal").onclick = () => loadGlobalSummary().then(() => toast("Global aktualisiert")).catch((err) => toast(err.message));
$("refreshGuild").onclick = () => loadGuildSummary().then(() => toast("Guild aktualisiert")).catch((err) => toast(err.message));

$("ticketsReload").onclick = () => loadTickets().then(() => toast("Tickets geladen")).catch((err) => toast(err.message));
$("ticketSearch").addEventListener("input", renderTickets);
$("ticketThreadId").addEventListener("change", () => {
  const ticket = ticketCache.find((entry) => String(entry.thread_id) === String($("ticketThreadId").value));
  if (ticket) selectTicket(ticket.id);
});
$("ticketActionBtn").onclick = () => {
  const gid = requireGuild();
  postJson(`/api/guilds/${gid}/tickets/action`, {
    thread_id: $("ticketThreadId").value.trim(),
    actor_id: $("ticketActorId").value.trim(),
    user_id: $("ticketUserId").value.trim(),
    action: $("ticketAction").value,
    reason: $("ticketReason").value.trim(),
  }).then(async () => {
    await loadTickets();
    toast("Ticket Aktion ausgeführt");
  }).catch((err) => toast(err.message));
};

$("sendMessage").onclick = () => {
  const gid = requireGuild();
  postJson(`/api/guilds/${gid}/discord/message`, {
    channel_id: $("msgChannelSelect").value,
    content: $("msgContent").value.trim(),
  }).then(() => toast("Nachricht gesendet")).catch((err) => toast(err.message));
};

["embedTitle", "embedDesc", "embedFields", "embedThumbnail", "embedImage", "embedFooter", "embedColor"].forEach((id) => {
  $(id).addEventListener("input", renderEmbedPreview);
});

$("sendEmbed").onclick = () => {
  const gid = requireGuild();
  const payload = currentEmbedPayload();
  postJson(`/api/guilds/${gid}/discord/embed`, {
    channel_id: $("embedChannelSelect").value,
    title: payload.title,
    description: payload.description,
    fields: payload.fields,
    thumbnail: payload.thumbnail,
    image: payload.image,
    footer: payload.footer,
    color: payload.color,
  }).then(() => toast("Embed gesendet")).catch((err) => toast(err.message));
};

$("timeoutBtn").onclick = () => {
  const gid = requireGuild();
  postJson(`/api/guilds/${gid}/moderation/timeout`, {
    user_id: $("timeoutUserId").value.trim(),
    moderator_id: $("timeoutModeratorId").value.trim(),
    minutes: $("timeoutMinutes").value.trim(),
    reason: $("timeoutReason").value.trim(),
  }).then(() => toast("Timeout gesetzt")).catch((err) => toast(err.message));
};

$("kickBtn").onclick = () => {
  const gid = requireGuild();
  postJson(`/api/guilds/${gid}/moderation/kick`, {
    user_id: $("kickUserId").value.trim(),
    moderator_id: $("kickModeratorId").value.trim(),
    reason: $("kickReason").value.trim(),
  }).then(() => toast("User gekickt")).catch((err) => toast(err.message));
};

$("banBtn").onclick = () => {
  const gid = requireGuild();
  postJson(`/api/guilds/${gid}/moderation/ban`, {
    user_id: $("banUserId").value.trim(),
    moderator_id: $("banModeratorId").value.trim(),
    delete_days: $("banDays").value.trim(),
    reason: $("banReason").value.trim(),
  }).then(() => toast("User gebannt")).catch((err) => toast(err.message));
};

$("purgeBtn").onclick = () => {
  const gid = requireGuild();
  postJson(`/api/guilds/${gid}/moderation/purge`, {
    channel_id: $("purgeChannelId").value.trim(),
    moderator_id: $("purgeModeratorId").value.trim(),
    amount: $("purgeAmount").value.trim(),
    user_id: $("purgeUserId").value.trim(),
  }).then((res) => toast(`Purge: ${res.deleted}`)).catch((err) => toast(err.message));
};

$("roleAddBtn").onclick = () => {
  const gid = requireGuild();
  postJson(`/api/guilds/${gid}/roles/add`, {
    user_id: $("roleAddUserId").value.trim(),
    role_id: $("roleAddRoleId").value.trim(),
  }).then(() => toast("Rolle hinzugefügt")).catch((err) => toast(err.message));
};

$("roleRemoveBtn").onclick = () => {
  const gid = requireGuild();
  postJson(`/api/guilds/${gid}/roles/remove`, {
    user_id: $("roleRemoveUserId").value.trim(),
    role_id: $("roleRemoveRoleId").value.trim(),
  }).then(() => toast("Rolle entfernt")).catch((err) => toast(err.message));
};

$("userSearchBtn").onclick = () => searchUsers().catch((err) => toast(err.message));
$("userLiveReload").onclick = () => loadLiveUsers().then(() => toast("Live User geladen")).catch((err) => toast(err.message));

$("appsListReload").onclick = () => loadApplicationsList().then(() => toast("Bewerbungen aktualisiert")).catch((err) => toast(err.message));
$("openApplicationsModule").onclick = () => selectModule("applications");

$("logsReload").onclick = () => loadLogs().then(() => toast("Logs geladen")).catch((err) => toast(err.message));
$("logsLive").onclick = () => connectLogs();

$("moduleSearch").addEventListener("input", renderModuleSidebar);
$("moduleSettingSearch").addEventListener("input", renderModuleEditor);
$("moduleReload").onclick = async () => {
  try {
    await loadModules();
    toast("Module neu geladen");
  } catch (err) {
    toast(err.message || "Module konnten nicht geladen werden");
  }
};

$("birthdaysReload").onclick = () => loadBirthdaySummary()
  .then(() => toast("Birthdays geladen"))
  .catch((err) => toast(err.message));

initDashboard();
