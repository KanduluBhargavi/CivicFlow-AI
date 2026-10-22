(function () {
  const token = localStorage.getItem("access_token");
  const role = (localStorage.getItem("actual_role") || localStorage.getItem("role") || "").toLowerCase();
  if (!token || (role && role !== "citizen")) return;

  const navRight = document.querySelector(".nav-right, .navbar__actions, .nav-actions");
  if (!navRight) return;

  const wrap = document.createElement("div");
  wrap.className = "citizen-notification-wrap";
  wrap.innerHTML = `
    <button class="citizen-notification-bell" id="citizenNotificationBell" type="button"
      aria-label="Citizen notifications" title="Notifications">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"></path>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
      </svg>
      <span class="citizen-notification-badge" id="citizenNotificationBadge">0</span>
    </button>
    <div class="citizen-notification-menu" id="citizenNotificationMenu">
      <div class="citizen-notification-head">
        <div>
          <strong>Complaint Updates</strong>
          <span>Officer assignment, status and resolution updates</span>
        </div>
        <button type="button" class="citizen-notification-mark" id="citizenMarkRead">Mark read</button>
      </div>
      <div class="citizen-notification-list" id="citizenNotificationList">
        <div class="citizen-notification-empty">Loading updates...</div>
      </div>
    </div>
  `;

  const logoutBtn = navRight.querySelector("#logoutBtn");
  if (logoutBtn) navRight.insertBefore(wrap, logoutBtn);
  else navRight.prepend(wrap);

  const bell = wrap.querySelector("#citizenNotificationBell");
  const menu = wrap.querySelector("#citizenNotificationMenu");
  const badge = wrap.querySelector("#citizenNotificationBadge");
  const list = wrap.querySelector("#citizenNotificationList");
  const markRead = wrap.querySelector("#citizenMarkRead");

  const READ_KEY = "civicflow_citizen_notifications_last_read";
  let currentNotifications = [];

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
    }[ch]));
  }

  function timeAgo(value) {
    const t = new Date(value).getTime();
    if (!Number.isFinite(t)) return "";
    const mins = Math.max(0, Math.floor((Date.now() - t) / 60000));
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  function lastReadTime() {
    const raw = localStorage.getItem(READ_KEY);
    const t = raw ? new Date(raw).getTime() : 0;
    return Number.isFinite(t) ? t : 0;
  }

  function render() {
    const readAt = lastReadTime();
    const unread = currentNotifications.filter(n => new Date(n.created_at).getTime() > readAt);
    badge.textContent = unread.length > 99 ? "99+" : String(unread.length);
    badge.style.display = unread.length ? "inline-flex" : "none";

    if (!currentNotifications.length) {
      list.innerHTML = `<div class="citizen-notification-empty">No complaint updates yet.</div>`;
      return;
    }

    list.innerHTML = currentNotifications.map(n => {
      const isUnread = new Date(n.created_at).getTime() > readAt;
      const href = `complaint_details.html?id=${encodeURIComponent(n.complaint_id)}`;
      return `
        <a class="citizen-notification-item ${isUnread ? "unread" : ""}" href="${href}">
          <strong>Complaint #${escapeHtml(n.complaint_id)} · ${escapeHtml(n.title)}</strong>
          ${n.detail ? `<p>${escapeHtml(n.detail)}</p>` : ""}
          <div class="citizen-notification-meta">
            <span>${escapeHtml(n.complaint_title || "Complaint")}</span>
            <span>${timeAgo(n.created_at)}</span>
          </div>
        </a>`;
    }).join("");
  }

  async function loadNotifications() {
    try {
      const response = await fetch(`${API_BASE}/dashboard/notifications`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) return;
      const data = await response.json();
      currentNotifications = Array.isArray(data.notifications) ? data.notifications : [];
      render();
    } catch (err) {
      console.debug("Citizen notification load skipped:", err);
    }
  }

  function markAllRead() {
    localStorage.setItem(READ_KEY, new Date().toISOString());
    render();
  }

  bell.addEventListener("click", (event) => {
    event.stopPropagation();
    menu.classList.toggle("open");
    if (menu.classList.contains("open")) markAllRead();
  });

  markRead.addEventListener("click", (event) => {
    event.stopPropagation();
    markAllRead();
  });

  document.addEventListener("click", (event) => {
    if (!wrap.contains(event.target)) menu.classList.remove("open");
  });

  loadNotifications();
  setInterval(loadNotifications, 30000);
})();
