function escHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
// ================= USER =================

const userName = localStorage.getItem("name");

document.getElementById("userName").textContent = userName || "Citizen";
document.getElementById("welcomeName").textContent = userName || "Citizen";


// ================= LOGOUT =================

function logout() {

    localStorage.clear();

    window.location.href = "login.html";

}

document.getElementById("logoutBtn").addEventListener("click", logout);
document.getElementById("logoutSide").addEventListener("click", logout);


// ================= DASHBOARD STATS =================

async function loadDashboardStats() {

    try {

        const token = localStorage.getItem("access_token");

        const response = await fetch(
            `${API_BASE}/dashboard/stats`,
            {
                headers: {
                    Authorization: `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {
            console.error("Failed to load dashboard stats");
            return;
        }

        const data = await response.json();

        document.getElementById("totalComplaints").textContent =
            data.total_complaints ?? 0;

        document.getElementById("pendingComplaints").textContent =
            data.pending ?? 0;

        document.getElementById("resolvedComplaints").textContent =
            data.resolved ?? 0;

    }

    catch (error) {

        console.error("Dashboard stats error:", error);

    }

}


// ================= RECENT COMPLAINTS =================

async function loadComplaints() {

    try {

        const token = localStorage.getItem("access_token");

        const response = await fetch(
            `${API_BASE}/dashboard/recent-complaints`,
            {
                headers: {
                    Authorization: `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {

            console.error("Failed to load recent complaints");

            return;

        }

        const complaints = await response.json();

        const tbody = document.getElementById("recentComplaints");

        tbody.innerHTML = "";

        if (!Array.isArray(complaints) || complaints.length === 0) {

            tbody.innerHTML = `
                <tr class="dashboard-empty-row">
                    <td colspan="6">
                        <div class="dashboard-empty">
                            <div class="dashboard-empty-icon">✓</div>
                            <div>
                                <strong>No complaints yet</strong>
                                <span>Your submitted grievances will appear here with live status and tracking.</span>
                            </div>
                            <a href="complaint.html">Lodge your first complaint</a>
                        </div>
                    </td>
                </tr>
            `;

            return;

        }


       complaints.forEach(c => {

    tbody.innerHTML += `

        <tr>

            <td>${c.complaint_id}</td>

            <td>${escHtml(c.title)}</td>

            <td>${escHtml(c.department)}</td>

            <td>${escHtml(c.display_status || c.status)}</td>

            <td>${c.priority}</td>

            <td class="recent-actions">
                <button type="button" class="recent-action-btn recent-action-view" onclick="location.href='complaint_details.html?id=${c.complaint_id}'">View</button>
                <button type="button" class="recent-action-btn recent-action-track" onclick="location.href='track.html?id=${c.complaint_id}'">Track</button>
            </td>

        </tr>

    `;

});

    }

    catch (error) {

        console.error("Recent complaints error:", error);

    }

}
// ================= HELP & SUPPORT =================

const getHelpBtn = document.getElementById("getHelpBtn");

const helpModal = document.getElementById("helpModal");

const closeHelpModal = document.getElementById("closeHelpModal");


const helpMainMenu = document.getElementById("helpMainMenu");

const chatSupportSection =
    document.getElementById("chatSupportSection");

const contactSupportSection =
    document.getElementById("contactSupportSection");


// ================= OPEN HELP =================

function openSupportPanel(type) {
    helpModal.classList.add("active");
    helpModal.setAttribute("aria-hidden", "false");
    helpMainMenu.classList.add("hidden");
    chatSupportSection.classList.toggle("hidden", type !== "chat");
    contactSupportSection.classList.toggle("hidden", type !== "contact");
    if (type === "chat") document.getElementById("chatInput")?.focus();
    else closeHelpModal.focus();
}

const floatingChatSupport = document.getElementById("floatingChatSupport");
const navContactSupport = document.getElementById("navContactSupport");
floatingChatSupport?.addEventListener("click", () => openSupportPanel("chat"));
navContactSupport?.addEventListener("click", () => openSupportPanel("contact"));

// ================= CLOSE HELP =================

closeHelpModal.addEventListener("click", () => {

    helpModal.classList.remove("active");

});


// Close when clicking outside

helpModal.addEventListener("click", (e) => {

    if (e.target === helpModal) {

        helpModal.classList.remove("active");

    }

});


// ================= CHAT =================

document
    .getElementById("chatSupportBtn")
    .addEventListener("click", () => {

        helpMainMenu.classList.add("hidden");

        chatSupportSection.classList.remove("hidden");

    });


// ================= CONTACT =================

document
    .getElementById("contactSupportBtn")
    .addEventListener("click", () => {

        helpMainMenu.classList.add("hidden");

        contactSupportSection.classList.remove("hidden");

    });


// ================= BACK FROM CHAT =================

document
    .getElementById("backFromChat")
    .addEventListener("click", () => {

        helpModal.classList.remove("active");

    });


// ================= BACK FROM CONTACT =================

document
    .getElementById("backFromContact")
    .addEventListener("click", () => {

        helpModal.classList.remove("active");

    });


// ================= SEND CHAT MESSAGE =================

const chatInput =
    document.getElementById("chatInput");

const sendChatBtn =
    document.getElementById("sendChatBtn");

const chatMessages =
    document.getElementById("chatMessages");

// Instant, verified navigation/help responses. Other questions use Gemini.
function civicflowQuickAnswer(message) {
    const q = String(message || "").toLocaleLowerCase().trim().replace(/[!?.,]+/g, " ").replace(/\s+/g, " ").trim();
    // Recognize casual self-description questions before the general rules.
    // Handles chat shorthand and common typos without making a Gemini request.
    const normalized = q
        .replace(/\b(ur|youre|you r)\b/g, "you are")
        .replace(/\b(u)\b/g, "you")
        .replace(/\b(r)\b/g, "are")
        .replace(/\b(doin|doingg|diung|doign|diong|dng)\b/g, "doing")
        .replace(/\b(wat|wht|whats)\b/g, "what")
        .replace(/\b(yr)\b/g, "your")
        .replace(/\s+/g, " ").trim();
    const identityQuestion = /^(?:(?:so|hey|hi|hello|tell me|i asked|please|can you tell me)\s+)*(?:what(?:\s+are|\s+is|\s+do|\s+can|\s+does|\s+you|\s+your|\s+u)?\s*)?(?:you\s+)?(?:are\s+)?(?:you\s+)?(?:doing|do|work|purpose|job|role|help)(?:\s+(?:here|for me|in civicflow|on civicflow|exactly|today|now|me|with|about|this|you))*$/i.test(normalized)
        || /^(?:who (?:are|is) you|what (?:do|can) you do|what (?:are|is) you doing|how (?:can|do) you help(?: me)?|what is your (?:purpose|job|role)|what does civicflow do|what is civicflow)(?:\s+(?:exactly|here|today|now))?$/i.test(normalized);
    if (identityQuestion) {
        return "I'm CivicFlow's help assistant. I can guide you through lodging civic complaints, tracking progress, understanding department assignments, checking incident reports, and requesting a resolution review. I can't submit or resolve complaints for you. What would you like help with?";
    }
    const rules = [
        [/^(hi|hello|hey|good morning|good evening|good afternoon)$/, "Hello! I'm CivicFlow's support assistant. I can explain how to file a complaint, track it, understand departments, and request further review. What would you like help with?"],
        [/^(what (do|can) (you|u) do|what (are|is) your (job|purpose)|who are you|tell me about yourself|what is civicflow|what does civicflow do|i asked what r u doing|what r u doing|what are you doing|how can you help( me)?)$/, "I'm CivicFlow's help assistant. I can guide you through lodging civic complaints, tracking progress, understanding which department handles your issue, checking incident reports, and reviewing a resolution. I can't submit or resolve complaints for you. What would you like to do?"],
        [/how.*(lodge|file|submit)|create.*complaint/, "Select Lodge Complaint, describe the issue, enter its location, attach relevant evidence if available, and submit. You will receive a complaint ID."],
        [/track|status.*complaint|where.*complaint/, "Open My Complaints and choose Track. You can follow the status, the assigned officer when available, and recorded actions."],
        [/incident|affected|similar complaint/, "Incident reports group related complaints within an area. If you've already submitted a complaint linked to an incident, you are counted as affected automatically."],
        [/sla|escalat|deadline/, "An SLA is a target timeframe for responding to a complaint. At-risk or overdue cases can appear in the department head's Escalation Queue."],
        [/language|translate|odia|telugu|hindi/, "You can submit a written complaint in your preferred language. CivicFlow keeps the original and attempts an English processing translation. Voice recognition depends on browser and language support."],
        [/not satisfied|reopen|resolved/, "If your complaint is marked Resolved but the problem remains, you can choose Not Satisfied to request another review, subject to the allowed limit."],
        [/password|forgot|login|sign in/, "Use the login page or Forgot Password for account issues. Never share your password or OTP with support."],
        [/contact|call support|phone number|human support/, "Use the Support icon in the dashboard navigation bar to see the available contact details."],
    ];
    const rule = rules.find(([pattern]) => pattern.test(q));
    return rule ? rule[1] : null;
}

const CHAT_FALLBACK = "I can still help with CivicFlow basics while the AI service is busy. You can ask me how to lodge or track a complaint, check incidents, understand department assignments, or request a resolution review. For a more specific question, please try again shortly.";
const waitForChatRetry = ms => new Promise(resolve => setTimeout(resolve, ms));

async function getBotResponse(message) {
    const quick = civicflowQuickAnswer(message);
    if (quick) return quick;

    const token = localStorage.getItem("access_token");
    // One retry for temporary server failures, never for invalid credentials or requests.
    for (let attempt = 0; attempt < 2; attempt++) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 9000);
        try {
            const response = await fetch(`${API_BASE}/support/chat`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({ message }),
                signal: controller.signal
            });
            const data = await response.json().catch(() => ({}));
            if (response.ok && typeof data.reply === "string" && data.reply.trim()) {
                return data.reply.trim();
            }
            if ((response.status === 503 || response.status === 429 || response.status >= 500) && attempt === 0) {
                await waitForChatRetry(500);
                continue;
            }
            console.warn("CivicFlow support chat request unavailable", response.status);
            break;
        } catch (error) {
            console.warn("CivicFlow support chat connection issue", error?.name || "network error");
            if (attempt === 0 && error?.name !== "AbortError") {
                await waitForChatRetry(500);
                continue;
            }
            break;
        } finally {
            clearTimeout(timeout);
        }
    }
    return CHAT_FALLBACK;
}

async function sendChatMessage() {

    const message = chatInput.value.trim();

    if (!message) return;


    // Disable button while AI responds

    sendChatBtn.disabled = true;


    // ================= USER MESSAGE =================

    const userMessage = document.createElement("div");

    userMessage.classList.add(
        "chat-message",
        "user-message"
    );

    userMessage.textContent = message;

    chatMessages.appendChild(userMessage);


    // Clear input

    chatInput.value = "";


    // Scroll

    chatMessages.scrollTop = chatMessages.scrollHeight;


    // ================= TYPING MESSAGE =================

    const typingMessage = document.createElement("div");

    typingMessage.classList.add(
        "chat-message",
        "support-message",
        "typing-message"
    );

    typingMessage.textContent =
        "🤖 CivicFlow Assistant is typing...";

    chatMessages.appendChild(typingMessage);

    chatMessages.scrollTop = chatMessages.scrollHeight;


    try {

        // ================= GET AI RESPONSE =================

        const botResponse =
            await getBotResponse(message);


        // Remove typing message

        typingMessage.remove();


        // ================= BOT MESSAGE =================

        const supportMessage =
            document.createElement("div");

        supportMessage.classList.add(
            "chat-message",
            "support-message"
        );


        supportMessage.textContent =
            botResponse || "Sorry, I couldn't generate a response.";


        chatMessages.appendChild(supportMessage);


        chatMessages.scrollTop =
            chatMessages.scrollHeight;


    }

    catch (error) {

        console.error("Chat error:", error);

        typingMessage.remove();


        const errorMessage =
            document.createElement("div");

        errorMessage.classList.add(
            "chat-message",
            "support-message"
        );

        errorMessage.textContent =
            "Sorry, something went wrong. Please try again.";

        chatMessages.appendChild(errorMessage);

    }


    // Enable button again

    sendChatBtn.disabled = false;

    chatInput.focus();

}


// Send button

sendChatBtn.addEventListener(
    "click",
    sendChatMessage
);


// Enter key

chatInput.addEventListener(
    "keypress",
    (e) => {

        if (e.key === "Enter") {

            sendChatMessage();

        }

    }
);

// ================= START =================

loadDashboardStats();

loadComplaints();


// ================= COMMUNITY INCIDENTS / I'M AFFECTED TOO =================
async function loadCommunityIncidents() {
    const token = localStorage.getItem("access_token");
    const box = document.getElementById("communityIncidents");
    if (!box) return;
    try {
        const response = await fetch(`${API_BASE}/community/incidents`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        const incidents = await response.json();
        if (!response.ok || !Array.isArray(incidents)) throw new Error("Unable to load incidents");
        if (!incidents.length) {
            box.innerHTML = `<p class="community-empty">No unresolved incidents found in your district.</p>`;
            return;
        }
        box.innerHTML = incidents.map(i => `
            <article class="incident-card" data-cluster="${i.incident_cluster_id}">
                <div class="incident-card__top">
                    <span class="incident-dept">${escHtml(i.department || "Civic issue")}</span>
                    <span class="incident-priority">${i.priority || "-"}</span>
                </div>
                <h3>${i.title || `Incident #${i.incident_cluster_id}`}</h3>
                <p class="incident-location">${escHtml(i.area || "-")}, ${escHtml(i.district || "-")}${i.pincode ? ` · ${i.pincode}` : ""}</p>
                <div class="incident-meta">
                    <span><b>${i.report_count}</b> total reports</span>
                    <span><b>${i.unresolved_count ?? 0}</b> active</span>
                    <span class="affected-count"><b>${i.affected_count}</b> citizens affected</span>
                    <span><b>${i.impact?.level || "Local"}</b> impact</span>
                </div>
                <div class="incident-actions">
                    <button class="incident-view-action" onclick="location.href='incident_details.html?id=${i.incident_cluster_id}'">View Incident</button>
                    ${i.already_reported
                        ? `<button class="support-btn is-reported" disabled>✓ Your complaint is part of this incident</button>`
                        : `<button class="support-btn ${i.supported ? "is-supported" : ""}" ${i.supported ? "disabled" : ""} onclick="supportIncident(${i.incident_cluster_id}, this)">${i.supported ? "✓ You're marked as affected" : "I'm affected too"}</button>`}
                </div>
            </article>
        `).join("");
    } catch (error) {
        console.error(error);
        box.innerHTML = `<p class="community-empty">Community incidents are temporarily unavailable.</p>`;
    }
}

async function supportIncident(clusterId, button) {
    const token = localStorage.getItem("access_token");
    button.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/incidents/${clusterId}/support`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` }
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not support incident");
        button.textContent = data.already_reported ? "✓ Your complaint is part of this incident" : "✓ You're marked as affected";
        button.classList.add(data.already_reported ? "is-reported" : "is-supported");
        const card = button.closest(".incident-card");
        if (card) {
            const count = card.querySelector(".affected-count b");
            if (count && typeof data.affected_count === "number") count.textContent = data.affected_count;
        }
    } catch (error) {
        alert(error.message);
        button.disabled = false;
    }
}

loadCommunityIncidents();
