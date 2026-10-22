// Reuse the citizen dashboard support workflow on other citizen pages.
(() => {
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


})();
