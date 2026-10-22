function escHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
/* ==========================================================================
   CivicFlow AI — Interactions
   1. Sticky navbar shadow   2. Mobile menu   3. Scroll reveal
   4. Animated counters      5. FAQ accordion  6. Live activity feed ticker
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {

  /* ---------- 1. Sticky navbar shadow ---------- */
  const navbar = document.getElementById('navbar');
  const onScroll = () => {
    navbar.classList.toggle('is-scrolled', window.scrollY > 12);
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  /* ---------- 2. Mobile menu ---------- */
  const navToggle = document.getElementById('navToggle');
  const navLinks = document.getElementById('navLinks');

  navToggle.addEventListener('click', () => {
    const isOpen = navLinks.classList.toggle('is-open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
  });

  navLinks.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      navLinks.classList.remove('is-open');
      navToggle.setAttribute('aria-expanded', 'false');
    });
  });

  /* ---------- 3. Scroll reveal ---------- */
  const revealTargets = document.querySelectorAll(
    '.stat-card, .feature-card, .dept-row, .why-card, .timeline__item, .accordion__item'
  );
  revealTargets.forEach(el => el.setAttribute('data-reveal', ''));

  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });

  revealTargets.forEach(el => revealObserver.observe(el));

  /* ---------- 4. Animated counters ---------- */
  const counters = document.querySelectorAll('[data-count]');

  const animateCounter = (el) => {
    const target = parseFloat(el.getAttribute('data-count'));
    const decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);
    const suffix = el.getAttribute('data-suffix') || '';
    const duration = 1600;
    const start = performance.now();

    const step = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = target * eased;
      el.textContent = value.toLocaleString('en-IN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
      }) + suffix;
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        counterObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.4 });

  counters.forEach(el => counterObserver.observe(el));

  /* ---------- 5. FAQ accordion ---------- */
  const accordionItems = document.querySelectorAll('.accordion__item');

  accordionItems.forEach(item => {
    const trigger = item.querySelector('.accordion__trigger');
    const panel = item.querySelector('.accordion__panel');

    trigger.addEventListener('click', () => {
      const isOpen = item.classList.contains('is-open');

      accordionItems.forEach(other => {
        other.classList.remove('is-open');
        other.querySelector('.accordion__trigger').setAttribute('aria-expanded', 'false');
        other.querySelector('.accordion__panel').style.maxHeight = null;
      });

      if (!isOpen) {
        item.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');
        panel.style.maxHeight = panel.scrollHeight + 'px';
      }
    });
  });
  // Let the static hero render before starting API traffic and map downloads.
  const loadPublicContent = () => {
    loadDashboardStats();
    loadRecentComplaints();
    loadTopStates();
    loadDepartmentPerformance();
    loadPublicServiceLevels();
  };
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(loadPublicContent, { timeout: 1800 });
  } else {
    window.setTimeout(loadPublicContent, 700);
  }
  loadMap();

});

async function loadPublicServiceLevels() {
    const meta = document.getElementById("publicSlaMeta");
    const tbody = document.getElementById("publicSlaRows");
    if (!meta || !tbody) return;
    try {
        const response = await fetch(`${API_BASE}/dashboard/public-service-levels`);
        if (!response.ok) throw new Error("Service-level data unavailable");
        const data = await response.json();
        const groups = Array.isArray(data.groups) ? data.groups : [];
        meta.textContent = `Last ${Number(data.period_days) || 90} days · Updated ${new Date(data.generated_at).toLocaleString()}`;
        if (!groups.length) {
            tbody.innerHTML = '<tr><td colspan="7">No district and department groups currently meet the privacy threshold.</td></tr>';
            return;
        }
        tbody.innerHTML = groups.map(row => {
            const median = row.median_resolution_hours == null ? "Not enough recorded resolutions" : `${Number(row.median_resolution_hours).toLocaleString(undefined, { maximumFractionDigits: 1 })} hours`;
            const sla = row.sla_met_rate == null ? "Not enough recorded timestamps" : `${Number(row.sla_met_rate).toLocaleString()}%`;
            return `<tr><td>${escHtml(row.district)}, ${escHtml(row.state)}</td><td>${escHtml(row.department)}</td><td>${Number(row.complaints) || 0}</td><td>${Number(row.resolved) || 0} (${Number(row.resolution_rate) || 0}%)</td><td>${escHtml(median)}</td><td>${Number(row.overdue_open) || 0}</td><td>${escHtml(sla)}</td></tr>`;
        }).join("");
    } catch (error) {
        meta.textContent = "Public service-level summaries are temporarily unavailable.";
        tbody.innerHTML = '<tr><td colspan="7">Please try again later.</td></tr>';
        console.warn("Public service-level report unavailable", error);
    }
}
  


async function loadDashboardStats() {
  // console.log("loadDashbiardStats claleed")

    try {

        const response = await fetch(`${API_BASE}/dashboard/public-stats`);
        // console.log(response.status);

        const data = await response.json();
        
        // console.log(data);

        document.getElementById("totalComplaints").textContent = data.total_complaints;
        document.getElementById("resolvedComplaints").textContent = data.resolved;
        document.getElementById("pendingComplaints").textContent = data.pending;
        document.getElementById("departmentCount").textContent = data.departments;

    } catch (error) {

        console.error(error);

    }

}



async function loadRecentComplaints() {

    try {

        const response = await fetch(`${API_BASE}/dashboard/public-recent-complaints`);

        const complaints = await response.json();

        const feed = document.getElementById("activityFeed");

        feed.innerHTML = "";

        complaints.forEach(c => {

            let tagClass = "activity-feed__tag--medium";

            if (c.priority.toLowerCase() === "high")
                tagClass = "activity-feed__tag--critical";

            if (c.status.toLowerCase() === "resolved")
                tagClass = "activity-feed__tag--resolved";

            feed.innerHTML += `
                <li>
                    <span class="activity-feed__tag ${tagClass}">
                        ${c.priority}
                    </span>

                    ${escHtml(c.title)} — ${escHtml(c.district)}, ${escHtml(c.state)}

                    <time>${escHtml(c.status)}</time>

                </li>
            `;

        });

    }

    catch (error) {

        console.log(error);

    }

}
async function loadTopStates(){
    try{
        const response = await fetch(`${API_BASE}/dashboard/top-states`);
        const states = await response.json();
        const container = document.getElementById("topStates");
        if (!container) return;
        container.innerHTML = `<div class="top-states__head"><h3>Top States by Complaints</h3><span>Current database</span></div><div class="state-ranking"></div>`;
        const list = container.querySelector(".state-ranking");
        if (!states.length){
            list.innerHTML = `<p class="state-empty">No state complaint data yet.</p>`;
            return;
        }
        const maxCount = Math.max(...states.map(s => Number(s.count)||0), 1);
        const palette = ["#ef4444", "#f59e0b", "#eab308", "#22c55e", "#14b8a6"];
        states.forEach((state, index) => {
            const count = Number(state.count)||0;
            const width = Math.max(8, Math.round((count/maxCount)*100));
            const color = palette[Math.min(index,palette.length-1)];
            list.insertAdjacentHTML("beforeend", `
              <div class="state-rank-row">
                <div class="state-rank-meta"><span>${escHtml(state.state || "Unknown")}</span><strong>${count}</strong></div>
                <div class="state-rank-track"><i style="width:${width}%;background:${color}"></i></div>
              </div>`);
        });
    }catch(error){
        console.log(error);
    }
}

// Display real department complaint counts inside the reportable-issue tiles.
// A department contributes to at most one category; these are configured-name matches,
// not verified issue-level categories or resolution rates.
async function loadDepartmentPerformance() {
    const cards = Array.from(document.querySelectorAll('.issue-performance-card[data-department]'));
    if (!cards.length) return;
    try {
        const response = await fetch(`${API_BASE}/dashboard/department-performance`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const departments = await response.json();
        if (!Array.isArray(departments)) throw new Error('Invalid department list');
        const totals = new Map(departments.map(item => [String(item.department || '').trim().toLowerCase(), Number(item.complaints) || 0]));
        const grandTotal = [...totals.values()].reduce((sum, value) => sum + value, 0);
        cards.forEach(card => {
            const name = card.dataset.department;
            const count = totals.get(name.toLowerCase());
            card.querySelector('.issue-performance-count').textContent = count === undefined
                ? 'No department data yet' : `${count.toLocaleString()} recorded complaint${count === 1 ? '' : 's'}`;
            card.querySelector('.issue-performance-departments').textContent = `Department: ${name}`;
            const share = card.querySelector('.department-back-share');
            if (share) share.textContent = count === undefined || !grandTotal ? 'Share of listed department reports: unavailable' : `Share of listed department reports: ${(count / grandTotal * 100).toFixed(1)}%`;
        });
    } catch (error) {
        console.warn('Department counts unavailable', error);
        cards.forEach(card => {
            card.querySelector('.issue-performance-count').textContent = 'Counts unavailable';
            card.querySelector('.issue-performance-departments').textContent = 'Please try again later';
            const share = card.querySelector('.department-back-share');
            if (share) share.textContent = 'Share unavailable';
        });
    }
    const setFlipped = (card, active) => {
        card.classList.toggle('show-performance', active);
        card.setAttribute('aria-pressed', String(active));
    };
    cards.forEach(card => {
        card.addEventListener('click', () => setFlipped(card, !card.classList.contains('show-performance')));
        card.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                setFlipped(card, !card.classList.contains('show-performance'));
            }
            if (event.key === 'Escape') setFlipped(card, false);
        });
    });
}

async function loadMap() {
    const mapElement = document.getElementById("indiaMap");
    if (!mapElement) return;

    // The public map is below the hero. Do not download Leaflet until a
    // visitor scrolls near it; this keeps its JS, CSS and tile requests out
    // of the initial page render.
    await new Promise(resolve => {
        if (!("IntersectionObserver" in window)) return resolve();
        const observer = new IntersectionObserver(entries => {
            if (entries.some(entry => entry.isIntersecting)) {
                observer.disconnect();
                resolve();
            }
        }, { rootMargin: "500px 0px" });
        observer.observe(mapElement);
    });
    if (typeof L === "undefined") {
        await new Promise((resolve, reject) => {
            const css = document.createElement("link");
            css.rel = "stylesheet";
            css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
            document.head.appendChild(css);
            const script = document.createElement("script");
            script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
            script.onload = resolve;
            script.onerror = () => reject(new Error("Map library could not be loaded"));
            document.body.appendChild(script);
        }).catch(error => console.warn("Public incident map unavailable", error));
    }
    if (typeof L === "undefined") return;

    const map = L.map("indiaMap").setView([22.8, 79], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "? OpenStreetMap" }).addTo(map);

    try {
        const response = await fetch(`${API_BASE}/dashboard/map-data`);
        if (!response.ok) throw new Error("Map data is temporarily unavailable");
        const complaints = await response.json();
        const points = [];
        const validPoint = c => Number.isFinite(Number(c.latitude)) && Number.isFinite(Number(c.longitude)) &&
            Number(c.latitude) >= -90 && Number(c.latitude) <= 90 && Number(c.longitude) >= -180 && Number(c.longitude) <= 180;
        (Array.isArray(complaints) ? complaints : []).filter(validPoint).forEach(c => {
            const priority = c.priority || "Low";
            const status = c.status || "Submitted";
            const color = status === "Resolved" ? "#22c55e" : priority === "Critical" ? "#ef4444" : priority === "High" ? "#f97316" : priority === "Medium" ? "#eab308" : "#06b6d4";
            L.circleMarker([c.latitude, c.longitude], {
                radius: 6, color: "#ffffff", weight: 1.5, fillColor: color, fillOpacity: 0.92
            }).addTo(map).bindPopup(`
                <b>${escHtml(c.department || "Unassigned")}</b><br>
                Priority: ${escHtml(priority)}<br>
                Status: ${escHtml(status)}<br>
                ${escHtml(c.district || "")}${c.district && c.state ? ", " : ""}${escHtml(c.state || "")}<br>
                Approximate complaint location; citizen details are private.
            `);
            points.push([Number(c.latitude), Number(c.longitude)]);
        });
        if (points.length) map.fitBounds(L.latLngBounds(points).pad(0.15), { maxZoom: 10 });
    } catch (error) {
        console.warn("Public incident map unavailable", error);
    }
}

function createFeedbackCard(feedback) {
    let stars = "";
    const rating = Math.max(1, Math.min(5, Number(feedback.rating) || 4));
    for (let i = 1; i <= 5; i++) {
        stars += i <= rating ? `<i class="fa-solid fa-star"></i>` : `<i class="fa-regular fa-star"></i>`;
    }
    return `
        <div class="user-feedback-card">
            <div class="feedback-stars">${stars}</div>
            <p class="feedback-message">"${escHtml(feedback.message)}"</p>
            <div class="feedback-user">
                <div class="feedback-avatar">${escHtml((feedback.user_name || 'U').charAt(0).toUpperCase())}</div>
                <div>
                    <h4>${escHtml(feedback.user_name || 'CivicFlow User')}</h4>
                    <span>CivicFlow User</span>
                </div>
            </div>
        </div>`;
}

async function loadRecentFeedback() {
    const container = document.getElementById("recentFeedbackContainer");
    if (!container) return;
    try {
        const response = await fetch(`${API_BASE}/feedback/recent`);
        if (!response.ok) throw new Error("Unable to load feedback");
        const feedbackList = await response.json();
        const cleaned = (feedbackList || [])
            .filter(item => item && item.message)
            .map(item => ({
                user_name: item.user_name || 'Citizen',
                rating: Number(item.rating) || 4,
                message: String(item.message).trim()
            }))
            .filter(item => item.message.length >= 12);

        const merged = cleaned;

        if (!merged.length) {
            container.innerHTML = `<p class="no-feedback">No feedback yet. Be the first CivicFlow user to share your experience!</p>`;
            return;
        }

        container.innerHTML = merged.slice(0, 12).map(createFeedbackCard).join('');
    } catch (error) {
        console.error("Feedback loading error:", error);
        container.innerHTML = `<p class="no-feedback">Reviews are temporarily unavailable. Please try again later.</p>`;
    }
}

document.addEventListener(
    "DOMContentLoaded",
    loadRecentFeedback
);





