const registerForm = document.getElementById("registerForm");
const registrationOtpForm = document.getElementById("registrationOtpForm");
const registrationOtpInput = document.getElementById("registrationOtp");
const registrationOtpEmail = document.getElementById("registrationOtpEmail");
const registrationOtpMessage = document.getElementById("registrationOtpMessage");
const resendRegistrationOtpBtn = document.getElementById("resendRegistrationOtpBtn");
const editRegistrationBtn = document.getElementById("editRegistrationBtn");

let registrationChallengeId = null;
let registrationResendTimer = null;
window.registrationVerificationInProgress = false;

function setRegistrationMessage(message, isError = false) {
    registrationOtpMessage.textContent = message || "";
    registrationOtpMessage.classList.toggle("error", Boolean(isError));
}

function startRegistrationResendTimer(seconds = 60) {
    clearInterval(registrationResendTimer);
    let remaining = Number(seconds) || 60;

    const render = () => {
        if (remaining > 0) {
            resendRegistrationOtpBtn.disabled = true;
            resendRegistrationOtpBtn.textContent = `Resend OTP in ${remaining}s`;
            remaining -= 1;
        } else {
            clearInterval(registrationResendTimer);
            resendRegistrationOtpBtn.disabled = false;
            resendRegistrationOtpBtn.textContent = "Resend OTP";
        }
    };

    render();
    registrationResendTimer = setInterval(render, 1000);
}

registerForm.addEventListener("submit", async function(e) {
    e.preventDefault();

    const user = {
        full_name: document.getElementById("full_name").value,
        email: document.getElementById("email").value,
        phone: document.getElementById("phone").value,
        password: document.getElementById("password").value,
        department_id: null,
        state: document.getElementById("state").value,
        district: document.getElementById("district").value,
        address: document.getElementById("address").value,
        area: document.getElementById("area").value,
        landmark: document.getElementById("landmark").value,
        pincode: document.getElementById("pincode").value,
        latitude: document.getElementById("latitude").value
            ? parseFloat(document.getElementById("latitude").value)
            : null,
        longitude: document.getElementById("longitude").value
            ? parseFloat(document.getElementById("longitude").value)
            : null
    };

    if (user.password.length < 8) {
        alert("Password must be at least 8 characters long.");
        return;
    }

    const submitBtn = e.currentTarget.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = "Sending verification code...";

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);

    try {
        const response = await fetch(`${API_BASE}/register`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(user),
            signal: controller.signal
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.detail || data.message || "Registration failed.");
            return;
        }

        registrationChallengeId = data.challenge_id;
        window.registrationVerificationInProgress = true;

        registrationOtpEmail.textContent = data.masked_email || user.email;
        document.getElementById("registrationOtpExpiry").textContent =
            `Code expires in ${Math.max(1, Math.round((data.expires_in || 300) / 60))} minutes.`;

        registerForm.style.display = "none";
        registrationOtpForm.style.display = "block";

        setRegistrationMessage(
            data.dev_otp
                ? `Development OTP: ${data.dev_otp}`
                : "Check your email for the verification code."
        );

        startRegistrationResendTimer(data.resend_after || 60);
        registrationOtpInput.focus();

    } catch (error) {
        console.error(error);
        alert(
            error.name === "AbortError"
                ? "Registration request timed out."
                : "Unable to reach the server."
        );
    } finally {
        clearTimeout(timeout);
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
});

registrationOtpInput.addEventListener("input", function() {
    this.value = this.value.replace(/\D/g, "").slice(0, 6);
});

registrationOtpForm.addEventListener("submit", async function(e) {
    e.preventDefault();

    const otp = registrationOtpInput.value.trim();

    if (!registrationChallengeId || !/^\d{6}$/.test(otp)) {
        setRegistrationMessage("Enter the complete 6-digit OTP.", true);
        return;
    }

    const btn = document.getElementById("verifyRegistrationOtpBtn");
    btn.disabled = true;
    btn.textContent = "Verifying...";

    try {
        const response = await fetch(`${API_BASE}/register/verify-otp`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                challenge_id: registrationChallengeId,
                otp
            })
        });

        const data = await response.json();

        if (!response.ok) {
            setRegistrationMessage(data.detail || "Verification failed.", true);
            return;
        }

        window.registrationVerificationInProgress = false;
        setRegistrationMessage("Email verified. Account created successfully.");
        alert("Email verified. Registration successful!");
        window.location.href = "login.html";

    } catch (error) {
        console.error(error);
        setRegistrationMessage("Unable to verify OTP. Please try again.", true);
    } finally {
        btn.disabled = false;
        btn.textContent = "Verify Email & Create Account";
    }
});

resendRegistrationOtpBtn.addEventListener("click", async function() {
    if (!registrationChallengeId || this.disabled) return;

    try {
        const response = await fetch(`${API_BASE}/register/resend-otp`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({challenge_id: registrationChallengeId})
        });

        const data = await response.json();

        if (!response.ok) {
            setRegistrationMessage(data.detail || "Unable to resend OTP.", true);
            return;
        }

        registrationOtpInput.value = "";
        registrationOtpInput.focus();
        setRegistrationMessage(
            data.dev_otp
                ? `New development OTP: ${data.dev_otp}`
                : "A new verification code has been sent."
        );
        startRegistrationResendTimer(data.resend_after || 60);

    } catch (error) {
        console.error(error);
        setRegistrationMessage("Unable to resend OTP.", true);
    }
});

editRegistrationBtn.addEventListener("click", function() {
    clearInterval(registrationResendTimer);
    registrationChallengeId = null;
    window.registrationVerificationInProgress = false;
    registrationOtpInput.value = "";
    registrationOtpForm.style.display = "none";
    registerForm.style.display = "block";
    document.getElementById("email").focus();
});
