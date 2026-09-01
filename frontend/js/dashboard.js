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

        document.getElementById("rejectedComplaints").textContent =
            data.rejected ?? 0;

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
                <tr>
                    <td colspan="5">
                        No complaints yet.
                    </td>
                </tr>
            `;

            return;

        }


       complaints.forEach(c => {

    tbody.innerHTML += `

        <tr>

            <td>${c.complaint_id}</td>

            <td>${c.title}</td>

            <td>${c.department}</td>

            <td>${c.status}</td>

            <td>${c.priority}</td>

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

getHelpBtn.addEventListener("click", () => {

    helpModal.classList.add("active");

    helpMainMenu.classList.remove("hidden");

    chatSupportSection.classList.add("hidden");

    contactSupportSection.classList.add("hidden");

});


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

        chatSupportSection.classList.add("hidden");

        helpMainMenu.classList.remove("hidden");

    });


// ================= BACK FROM CONTACT =================

document
    .getElementById("backFromContact")
    .addEventListener("click", () => {

        contactSupportSection.classList.add("hidden");

        helpMainMenu.classList.remove("hidden");

    });


// ================= SEND CHAT MESSAGE =================

const chatInput =
    document.getElementById("chatInput");

const sendChatBtn =
    document.getElementById("sendChatBtn");

const chatMessages =
    document.getElementById("chatMessages");

async function getBotResponse(message) {

    try {

        const token = localStorage.getItem("access_token");

        const response = await fetch(
            `${API_BASE}/support/chat`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json",

                    "Authorization": `Bearer ${token}`
                },

                body: JSON.stringify({
                    message: message
                })
            }
        );


        const data = await response.json();


        if (!response.ok) {

            console.error("Server error:", data);

            throw new Error(
                data.detail || "Failed to get bot response"
            );
        }


        // IMPORTANT: Backend returns "reply"

        return data.reply;


    }

    catch (error) {

        console.error("Bot error:", error);

        return "Sorry, CivicFlow AI Support is currently unavailable. Please try again later.";

    }

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

