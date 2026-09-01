function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("userName");

    window.location.href = "login.html";
}