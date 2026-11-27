const loginForm = document.getElementById("loginForm");

function completeLogin(data) {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("role", data.role);
    localStorage.setItem("actual_role", data.actual_role || data.role);

    if (data.name) {
        localStorage.setItem("name", data.name);
    }

    if (data.role === "department" && data.department) {
        localStorage.setItem("department", data.department);
    }

    if (data.role === "admin") {
        window.location.href = "admin_dashboard.html";
        return;
    }

    if (data.role === "department") {
        window.location.href = "department_dashboard.html";
        return;
    }

    const params = new URLSearchParams(window.location.search);
    const next = params.get("next");

    // Offer an unfinished complaint as soon as a citizen signs in.
    let hasSavedComplaint = false;
    try {
        const encoded = data.access_token.split(".")[1];
        const base64 = encoded.replace(/-/g, "+").replace(/_/g, "/");
        const tokenPayload = JSON.parse(atob(base64 + "=".repeat((4 - base64.length % 4) % 4)));
        const identity = String(tokenPayload.sub || "").trim().toLowerCase();
        if (identity) {
            let hash = 2166136261;
            for (let i = 0; i < identity.length; i++) hash = Math.imul(hash ^ identity.charCodeAt(i), 16777619);
            const draftKey = `civicflow:complaint-draft:${(hash >>> 0).toString(36)}`;
            hasSavedComplaint = Boolean(JSON.parse(localStorage.getItem(draftKey) || "null")?.values);
        }
    } catch (error) {
        console.warn("Could not check for an unfinished complaint after login.", error);
    }

    if (hasSavedComplaint) {
        window.location.href = `dashboard.html?showComplaintDraft=1${next === "lodge" ? "&next=lodge" : ""}`;
    } else if (next === "lodge") {
        window.location.href = "complaint.html";
    } else if (next === "track") {
        window.location.href = "my_complaints.html";
    } else {
        window.location.href = "dashboard.html";
    }
}

loginForm.addEventListener("submit", async function (e) {
    e.preventDefault();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", password);

    const submitBtn = this.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = "Signing in...";

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);

    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: formData,
            signal: controller.signal
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.detail || "Login failed.");
            return;
        }

        completeLogin(data);

    } catch (error) {
        console.error(error);
        alert(
            error.name === "AbortError"
                ? "Login request timed out. Check that the backend is running."
                : "Unable to reach the server."
        );
    } finally {
        clearTimeout(timeout);
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
});
