/* Single-page app: hash-based router. Sections: #login #events #event/<id> #dashboard #notifications */
const state = { user: null };

function h(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstChild; }
function fmtDate(d) { return new Date(d + "T00:00:00").toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" }); }
function toast(msg) { const el = h(`<div class="toast">${msg}</div>`); document.body.appendChild(el); setTimeout(() => el.remove(), 2500); }
function statusBadge(s) { return `<span class="badge b-${s.toLowerCase()}">${s}</span>`; }

async function refreshMe() {
  if (!API.token) { state.user = null; return; }
  try { state.user = await API.get("/api/me"); } catch (_) { API.setToken(null); state.user = null; }
}

function renderNav() {
  const nav = document.getElementById("nav");
  nav.innerHTML = "";
  const links = [["#/events", "Events"]];
  if (state.user) {
    if (state.user.role !== "attendee") links.push(["#/dashboard", "Organizer Dashboard"]);
    links.push(["#/my-rsvps", "My RSVPs"], ["#/notifications", "Notifications"]);
  }
  links.forEach(([href, label]) => nav.appendChild(h(`<a href="${href}">${label}</a>`)));
  if (state.user) {
    nav.appendChild(h(`<a href="#" id="logoutLink">Logout (${state.user.name})</a>`));
  } else {
    nav.appendChild(h(`<a href="#/login">Login / Register</a>`));
  }
  const lo = document.getElementById("logoutLink");
  if (lo) lo.onclick = async (e) => { e.preventDefault(); await API.post("/api/logout", {}).catch(() => {}); API.setToken(null); state.user = null; location.hash = "#/login"; render(); };
}

const main = () => document.getElementById("main");

async function render() {
  await refreshMe();
  renderNav();
  const [route, ...rest] = (location.hash.slice(2) || "events").split("/");
  const map = { login: viewLogin, events: viewEvents, event: () => viewEventDetail(rest[0]), dashboard: viewDashboard, "my-rsvps": viewMyRSVPs, notifications: viewNotifications };
  main().innerHTML = "";
  try { await (map[route] || viewEvents)(); } catch (e) { main().appendChild(h(`<div class="card error">${e.message}</div>`)); }
}
window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", render);

/* ---------------- Auth ---------------- */
function viewLogin() {
  main().appendChild(h(`
    <div class="card" style="max-width:420px;margin:0 auto">
      <div class="row" style="margin-bottom:12px">
        <button id="tabLogin">Login</button><button id="tabReg" class="secondary">Register</button>
      </div>
      <div id="loginForm">
        <label>Email</label><input id="lEmail" type="email" style="width:100%">
        <label style="margin-top:8px">Password</label><input id="lPass" type="password" style="width:100%">
        <button id="doLogin" style="margin-top:12px;width:100%">Login</button>
        <div class="error" id="lErr"></div>
      </div>
      <div id="regForm" class="hidden">
        <label>Name</label><input id="rName" style="width:100%">
        <label style="margin-top:8px">Email</label><input id="rEmail" type="email" style="width:100%">
        <label style="margin-top:8px">Password (min 8 chars)</label><input id="rPass" type="password" style="width:100%">
        <label style="margin-top:8px">Role</label>
        <select id="rRole" style="width:100%"><option value="attendee">Attendee</option><option value="organizer">Organizer</option></select>
        <button id="doReg" style="margin-top:12px;width:100%">Create account</button>
        <div class="error" id="rErr"></div>
      </div>
    </div>`));
  document.getElementById("tabLogin").onclick = () => { loginForm.classList.remove("hidden"); regForm.classList.add("hidden"); };
  document.getElementById("tabReg").onclick = () => { regForm.classList.remove("hidden"); loginForm.classList.add("hidden"); };
  document.getElementById("doLogin").onclick = async () => {
    try { const r = await API.post("/api/login", { email: lEmail.value, password: lPass.value }); API.setToken(r.token); location.hash = "#/events"; render(); }
    catch (e) { lErr.textContent = e.message; }
  };
  document.getElementById("doReg").onclick = async () => {
    try { const r = await API.post("/api/register", { name: rName.value, email: rEmail.value, password: rPass.value, role: rRole.value }); API.setToken(r.token); toast("Account created"); location.hash = "#/events"; render(); }
    catch (e) { rErr.textContent = e.message; }
  };
}

/* ---------------- Event list & create ---------------- */
async function viewEvents() {
  const wrap = h(`<div></div>`);
  main().appendChild(wrap);
  if (state.user && state.user.role !== "attendee") {
    const form = h(`
      <div class="card">
        <h3>Create Event</h3>
        <div class="grid">
          <div><label>Name</label><input id="cName" style="width:100%"></div>
          <div><label>Type</label><input id="cType" value="workshop" style="width:100%"></div>
          <div><label>Date</label><input id="cDate" type="date" style="width:100%"></div>
          <div><label>Start</label><input id="cStart" type="time" value="10:00" style="width:100%"></div>
          <div><label>End</label><input id="cEnd" type="time" value="12:00" style="width:100%"></div>
          <div><label>Capacity</label><input id="cCap" type="number" value="50" style="width:100%"></div>
          <div><label>Venue</label><input id="cVenue" style="width:100%" placeholder="Room / Hall"></div>
          <div><label>Online link (optional)</label><input id="cLink" style="width:100%" placeholder="https://..."></div>
        </div>
        <label style="margin-top:8px">Description</label><textarea id="cDesc" style="width:100%" rows="2"></textarea>
        <button id="cCreate" style="margin-top:10px">Create & Publish</button>
        <div class="error" id="cErr"></div>
      </div>`);
    wrap.appendChild(form);
    document.getElementById("cCreate").onclick = async () => {
      try {
        await API.post("/api/events", {
          event_name: cName.value, event_type: cType.value, event_date: cDate.value,
          start_time: cStart.value, end_time: cEnd.value, maximum_capacity: Number(cCap.value),
          venue: cVenue.value || null, online_link: cLink.value || null, description: cDesc.value, publish: true,
        });
        toast("Event published"); render();
      } catch (e) { cErr.textContent = e.message; }
    };
  }
  const list = h(`<div class="grid" id="eventList"><p class="muted">Loading events...</p></div>`);
  wrap.appendChild(list);
  const data = state.user ? await API.get("/api/events?scope=upcoming") : { events: [] };
  list.innerHTML = "";
  if (!state.user) { list.appendChild(h(`<p class="muted">Log in to browse and RSVP to events.</p>`)); return; }
  if (!data.events.length) { list.appendChild(h(`<p class="muted">No upcoming events yet.</p>`)); }
  data.events.forEach((e) => {
    list.appendChild(h(`
      <div class="card">
        <div class="row" style="justify-content:space-between"><b>${e.event_name}</b>${statusBadge(e.status)}</div>
        <div class="muted">${fmtDate(e.event_date)} - ${e.start_time} to ${e.end_time}</div>
        <div class="muted">${e.venue || e.online_link || ""}</div>
        <div style="margin-top:6px">${e.going_count}/${e.maximum_capacity} going ${e.my_rsvp ? "- your RSVP: <b>" + e.my_rsvp + "</b>" : ""}</div>
        <a class="link" href="#/event/${e.event_id}">View details -></a>
      </div>`));
  });
}

/* ---------------- Event detail (real-time) ---------------- */
async function viewEventDetail(id) {
  const box = h(`<div class="card"><p class="muted">Loading...</p></div>`);
  main().appendChild(box);
  const data = await API.get(`/api/events/${id}`);
  box.innerHTML = `
    <div class="row" style="justify-content:space-between">
      <h2 style="margin:0">${data.event_name}</h2>
      <div>${statusBadge(data.status)}</div>
    </div>
    <p class="muted">${fmtDate(data.event_date)} - ${data.start_time} to ${data.end_time} - ${data.venue || ""} ${data.online_link ? `<a class="link" href="${data.online_link}" target="_blank">join link</a>` : ""}</p>
    <p>${data.description || ""}</p>
    <div><span class="dot live"></span><span class="muted">Live counts</span></div>
    <div class="counts" id="counts"></div>
    <div id="rsvpArea"></div>
    ${data.organizer_id === state.user.user_id || state.user.role === "admin" ? `<div style="margin-top:10px"><a class="link" href="#/dashboard">Manage this event in the dashboard -></a></div>` : ""}
    <h4>Announcements</h4><div id="annList" class="muted">Loading...</div>`;

  function paintCounts(c, cap) {
    document.getElementById("counts").innerHTML = `
      <div class="count"><div class="n">${c.GOING}</div><div class="l">GOING</div></div>
      <div class="count"><div class="n">${c.MAYBE}</div><div class="l">MAYBE</div></div>
      <div class="count"><div class="n">${c.NOT_GOING}</div><div class="l">NOT GOING</div></div>
      <div class="count"><div class="n">${c.WAITLISTED}</div><div class="l">WAITLIST</div></div>
      <div class="count"><div class="n">${cap}</div><div class="l">CAPACITY</div></div>`;
  }
  paintCounts(data.counts, data.maximum_capacity);

  function paintRSVP(myStatus, eventStatus) {
    const area = document.getElementById("rsvpArea");
    const btn = (s, label) => `<button data-s="${s}" class="${myStatus === s ? "" : "secondary"}">${label}</button>`;
    area.innerHTML = `<div class="row">${btn("GOING", "Going")}${btn("MAYBE", "Maybe")}${btn("NOT_GOING", "Not going")}
      ${myStatus ? `<button class="danger" id="cancelRsvp">Cancel RSVP</button>` : ""}</div>
      ${eventStatus === "FULL" && !myStatus ? `<p class="muted">Event is full - selecting Going will join the waitlist.</p>` : ""}`;
    area.querySelectorAll("button[data-s]").forEach((b) => b.onclick = async () => {
      try {
        const method = myStatus ? "put" : "post";
        const r = await API[method](`/api/events/${id}/rsvp?join_waitlist=true`, { status: b.dataset.s });
        toast(r.message); myStatus = b.dataset.s; paintRSVP(myStatus, r.event_status);
      } catch (e) { toast(e.message); }
    });
    const cancel = document.getElementById("cancelRsvp");
    if (cancel) cancel.onclick = async () => { const r = await API.del(`/api/events/${id}/rsvp`); toast(r.message); myStatus = null; paintRSVP(null, r.event_status); };
  }
  paintRSVP(data.my_rsvp, data.status);

  API.get(`/api/events/${id}/announcements`).then((a) => {
    document.getElementById("annList").innerHTML = a.announcements.length
      ? a.announcements.map((x) => `<div class="card"><b>${x.title}</b><div class="muted">${new Date(x.created_at).toLocaleString()}</div><div>${x.message}</div></div>`).join("")
      : `<p class="muted">No announcements yet.</p>`;
  }).catch(() => {});

  const stop = connectEventRealtime(id, (msg) => { if (msg.counts) { paintCounts(msg.counts, msg.capacity ?? data.maximum_capacity); } });
  window.addEventListener("hashchange", stop, { once: true });
}

/* ---------------- My RSVPs ---------------- */
async function viewMyRSVPs() {
  const data = await API.get("/api/rsvps/me");
  const wrap = h(`<div><h2>My RSVPs</h2></div>`);
  main().appendChild(wrap);
  if (!data.rsvps.length) wrap.appendChild(h(`<p class="muted">You haven't RSVP'd to anything yet.</p>`));
  data.rsvps.forEach((e) => wrap.appendChild(h(`
    <div class="card"><div class="row" style="justify-content:space-between"><b>${e.event_name}</b>${statusBadge(e.my_rsvp)}</div>
    <div class="muted">${fmtDate(e.event_date)}</div><a class="link" href="#/event/${e.event_id}">View -></a></div>`)));
}

/* ---------------- Notifications ---------------- */
async function viewNotifications() {
  const data = await API.get("/api/notifications");
  const wrap = h(`<div><div class="row" style="justify-content:space-between"><h2>Notifications</h2><button id="markAll" class="secondary">Mark all read</button></div></div>`);
  main().appendChild(wrap);
  document.getElementById("markAll").onclick = async () => { await API.put("/api/notifications/read-all"); render(); };
  if (!data.notifications.length) wrap.appendChild(h(`<p class="muted">No notifications.</p>`));
  data.notifications.forEach((n) => wrap.appendChild(h(`
    <div class="card" style="${n.read ? "opacity:.6" : ""}"><b>${n.type.replace(/_/g, " ")}</b>
    <div class="muted">${new Date(n.created_at).toLocaleString()}</div><div>${n.message}</div></div>`)));
}

/* ---------------- Organizer dashboard ---------------- */
async function viewDashboard() {
  const summary = await API.get("/api/organizer/summary");
  const wrap = h(`<div><h2>Organizer Dashboard</h2></div>`);
  main().appendChild(wrap);
  wrap.appendChild(h(`
    <div class="counts">
      <div class="count"><div class="n">${summary.total_events}</div><div class="l">TOTAL EVENTS</div></div>
      <div class="count"><div class="n">${summary.upcoming_events}</div><div class="l">UPCOMING</div></div>
      <div class="count"><div class="n">${summary.going}</div><div class="l">GOING</div></div>
      <div class="count"><div class="n">${summary.maybe}</div><div class="l">MAYBE</div></div>
      <div class="count"><div class="n">${summary.waitlist_size}</div><div class="l">WAITLISTED</div></div>
      <div class="count"><div class="n">${summary.response_rate ?? "-"}%</div><div class="l">RESPONSE RATE</div></div>
    </div>`));
  summary.events.forEach((e) => {
    const card = h(`
      <div class="card">
        <div class="row" style="justify-content:space-between"><b>${e.event_name}</b>${statusBadge(e.status)}</div>
        <div class="muted">${fmtDate(e.event_date)} - capacity ${e.going}/${e.capacity} (${e.capacity_utilization ?? 0}%)</div>
        <div class="row" style="margin-top:8px">
          <a class="link" href="#/event/${e.event_id}">View</a>
          <button data-a="attendees" data-id="${e.event_id}" class="secondary">Attendees</button>
          <button data-a="announce" data-id="${e.event_id}" class="secondary">Announce</button>
          ${e.status !== "CANCELLED" && e.status !== "COMPLETED" ? `<button data-a="cancel" data-id="${e.event_id}" class="danger">Cancel</button>` : ""}
        </div>
        <div class="details hidden" id="details-${e.event_id}"></div>
      </div>`);
    wrap.appendChild(card);
  });
  wrap.querySelectorAll("button[data-a]").forEach((b) => b.onclick = () => handleDashAction(b.dataset.a, b.dataset.id));
}

async function handleDashAction(action, id) {
  const box = document.getElementById(`details-${id}`);
  box.classList.remove("hidden");
  if (action === "cancel") {
    if (!confirm("Cancel this event? All attendees will be notified.")) return;
    await API.post(`/api/events/${id}/cancel`); toast("Event cancelled"); return render();
  }
  if (action === "attendees") {
    const r = await API.get(`/api/events/${id}/rsvps`);
    box.innerHTML = `<table><tr><th>Name</th><th>Email</th><th>Status</th></tr>${r.rsvps.map(x => `<tr><td>${x.user_name}</td><td>${x.user_email}</td><td>${statusBadge(x.status)}</td></tr>`).join("")}</table>`;
  }
  if (action === "announce") {
    box.innerHTML = `<div class="row"><input id="annTitle-${id}" placeholder="Title"><input id="annMsg-${id}" placeholder="Message" style="flex:1"><button id="annSend-${id}">Send</button></div>`;
    document.getElementById(`annSend-${id}`).onclick = async () => {
      await API.post(`/api/events/${id}/announcements`, { title: document.getElementById(`annTitle-${id}`).value, message: document.getElementById(`annMsg-${id}`).value });
      toast("Announcement sent");
    };
  }
}
