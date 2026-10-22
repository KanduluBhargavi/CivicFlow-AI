const forgotPasswordForm = document.getElementById("forgotPasswordForm");
const resetPasswordForm = document.getElementById("resetPasswordForm");
const resetEmail = document.getElementById("resetEmail");
const resetEmailHint = document.getElementById("resetEmailHint");
const resetOtp = document.getElementById("resetOtp");
const newPassword = document.getElementById("newPassword");
const confirmNewPassword = document.getElementById("confirmNewPassword");
const resetMessage = document.getElementById("resetMessage");
const resendResetOtpBtn = document.getElementById("resendResetOtpBtn");
const changeResetEmailBtn = document.getElementById("changeResetEmailBtn");

let resetChallengeId = null;
let resetResendTimer = null;

function setResetMessage(message, isError = false) {
    resetMessage.textContent = message || "";
    resetMessage.classList.toggle("error", Boolean(isError));
}

function startResetResendTimer(seconds = 60) {
    clearInterval(resetResendTimer);
    let remaining = Number(seconds) || 60;

    const render = () => {
        if (remaining > 0) {
            resendResetOtpBtn.disabled = true;
            resendResetOtpBtn.textContent = `Resend OTP in ${remaining}s`;
            remaining -= 1;
        } else {
            clearInterval(resetResendTimer);
            resendResetOtpBtn.disabled = false;
            resendResetOtpBtn.textContent = "Resend OTP";
        }
    };

    render();
    resetResendTimer = setInterval(render, 1000);
}

forgotPasswordForm.addEventListener("submit", async function(e) {
    e.preventDefault();

    const email = resetEmail.value.trim();
    const btn = document.getElementById("sendResetOtpBtn");
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Sending OTP...";

    try {
        const response = await fetch(`${API_BASE}/forgot-password`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({email})
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.detail || "Could not start password reset.");
            return;
        }

        resetChallengeId = data.challenge_id;
        resetEmailHint.textContent = data.masked_email || email;
        document.getElementById("resetExpiry").textContent =
            `Code expires in ${Math.max(1, Math.round((data.expires_in || 300) / 60))} minutes.`;

        forgotPasswordForm.style.display = "none";
        resetPasswordForm.style.display = "block";

        setResetMessage(
            data.dev_otp
                ? `Development OTP: ${data.dev_otp}`
                : "Check your email for the password reset code."
        );

        startResetResendTimer(data.resend_after || 60);
        resetOtp.focus();

    } catch (error) {
        console.error(error);
        alert("Unable to reach the server.");
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
});

resetOtp.addEventListener("input", function() {
    this.value = this.value.replace(/\D/g, "").slice(0, 6);
});

resetPasswordForm.addEventListener("submit", async function(e) {
    e.preventDefault();

    const otp = resetOtp.value.trim();
    const password = newPassword.value;
    const confirmPassword = confirmNewPassword.value;

    if (!/^\d{6}$/.test(otp)) {
        setResetMessage("Enter the complete 6-digit OTP.", true);
        return;
    }

    if (password.length < 8) {
        setResetMessage("New password must be at least 8 characters long.", true);
        return;
    }

    if (password !== confirmPassword) {
        setResetMessage("Passwords do not match.", true);
        return;
    }

    const btn = document.getElementById("resetPasswordBtn");
    btn.disabled = true;
    btn.textContent = "Resetting password...";

    try {
        const response = await fetch(`${API_BASE}/reset-password`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                challenge_id: resetChallengeId,
                otp,
                new_password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            setResetMessage(data.detail || "Password reset failed.", true);
            return;
        }

        alert("Password reset successful. Please login with your new password.");
        window.location.href = "login.html";

    } catch (error) {
        console.error(error);
        setResetMessage("Unable to reset password. Please try again.", true);
    } finally {
        btn.disabled = false;
        btn.textContent = "Verify OTP & Reset Password";
    }
});

resendResetOtpBtn.addEventListener("click", async function() {
    if (!resetChallengeId || this.disabled) return;

    try {
        const response = await fetch(`${API_BASE}/forgot-password/resend-otp`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({challenge_id: resetChallengeId})
        });

        const data = await response.json();

        if (!response.ok) {
            setResetMessage(data.detail || "Could not resend OTP.", true);
            return;
        }

        resetOtp.value = "";
        setResetMessage(
            data.dev_otp
                ? `New development OTP: ${data.dev_otp}`
                : "A new password reset code has been sent."
        );
        startResetResendTimer(data.resend_after || 60);
        resetOtp.focus();

    } catch (error) {
        console.error(error);
        setResetMessage("Unable to resend OTP.", true);
    }
});

changeResetEmailBtn.addEventListener("click", function() {
    clearInterval(resetResendTimer);
    resetChallengeId = null;
    resetOtp.value = "";
    newPassword.value = "";
    confirmNewPassword.value = "";
    resetPasswordForm.style.display = "none";
    forgotPasswordForm.style.display = "block";
    resetEmail.focus();
});
