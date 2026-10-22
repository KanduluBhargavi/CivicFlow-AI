function escHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}

const token = localStorage.getItem("access_token");

function viewComplaint(id) {
    window.location.href = `complaint_details.html?id=${id}`;
}

function trackComplaint(id) {
    window.location.href = `track.html?id=${id}`;
}

function renderEmptyState(title = "No complaints yet", message = "You have not submitted any complaints yet. Once you lodge a complaint, it will appear here with quick View and Track options.") {
    const tableWrap = document.getElementById("complaintsTableWrap");
    const emptyState = document.getElementById("complaintsEmptyState");
    tableWrap.style.display = "none";
    emptyState.style.display = "flex";
    emptyState.innerHTML = `
        <svg class="empty-state-illustration" viewBox="0 0 220 180" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <rect x="30" y="28" width="160" height="116" rx="18" fill="#EFF6FF"/>
            <rect x="52" y="48" width="116" height="12" rx="6" fill="#93C5FD"/>
            <rect x="52" y="72" width="88" height="10" rx="5" fill="#BFDBFE"/>
            <rect x="52" y="92" width="102" height="10" rx="5" fill="#DBEAFE"/>
            <rect x="52" y="112" width="74" height="10" rx="5" fill="#DBEAFE"/>
            <circle cx="168" cy="132" r="26" fill="#DCFCE7"/>
            <path d="M156 132l8 8 16-18" stroke="#10B981" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M89 18c8 0 14 6 14 14s-6 14-14 14-14-6-14-14 6-14 14-14z" fill="#2563EB" opacity=".12"/>
            <path d="M129 148c0 8-6 14-14 14s-14-6-14-14 6-14 14-14 14 6 14 14z" fill="#2563EB" opacity=".1"/>
        </svg>
        <h3>${title}</h3>
        <p>${message}</p>
        <div class="empty-state-actions">
            <a class="empty-link-btn" href="complaint.html">Lodge a complaint</a>
            <a class="empty-link-btn empty-secondary-btn" href="dashboard.html">Back to dashboard</a>
        </div>
    `;
}

async function loadComplaints() {
    const table = document.getElementById("complaintsTable");
    table.innerHTML = `<tr><td colspan="7" style="padding:24px; color:#64748b;">Loading your complaints...</td></tr>`;

    try {
        const response = await fetch(`${API_BASE}/my-complaints`, {
            headers: {
                Authorization: `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error("Unable to load complaints");
        }

        const data = await response.json();
        table.innerHTML = "";

        if (!Array.isArray(data) || data.length === 0) {
            renderEmptyState();
            return;
        }

        document.getElementById("complaintsTableWrap").style.display = "block";
        document.getElementById("complaintsEmptyState").style.display = "none";

        data.forEach(c => {
            table.innerHTML += `
                <tr>
                    <td>${c.complaint_id}</td>
                    <td>${escHtml(c.title)}</td>
                    <td>${escHtml(c.department)}</td>
                    <td>${escHtml(c.display_status || c.status)}</td>
                    <td>${c.priority}</td>
                    <td>
                        <button class="view-btn" onclick="viewComplaint(${c.complaint_id})">View</button>
                    </td>
                    <td>
                        <button class="track-btn" onclick="trackComplaint(${c.complaint_id})">Track</button>
                    </td>
                </tr>
            `;
        });
    } catch (error) {
        console.error(error);
        renderEmptyState(
            "Unable to load complaints",
            "We could not fetch your complaints right now. Please refresh the page or try again after a moment."
        );
    }
}

loadComplaints();
