document.getElementById("loginForm").addEventListener("submit", async function (e) {

    e.preventDefault();

    const email = document.getElementById("email").value;

    const password = document.getElementById("password").value;

    const formData = new URLSearchParams();

    formData.append("username", email);
    formData.append("password", password);

    try {

        const response = await fetch(`${API_BASE}/login`, {

            method: "POST",

            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },

            body: formData

        });

        const data = await response.json();

        if (!response.ok) {

            alert(data.detail || "Login Failed");

            return;

        }

        localStorage.setItem("access_token", data.access_token);

        localStorage.setItem("role", data.role);

        if (data.role === "department") {

        localStorage.setItem("department", data.department);

        }
        else {
        localStorage.setItem("name", data.name);}

        alert("Login Successful!");

      if (data.role === "admin") {

    window.location.href = "admin_dashboard.html";

}
      else if (data.role === "department") {

    window.location.href = "department_dashboard.html";

        }
      else {

    window.location.href = "dashboard.html";

}

    }

    catch (error) {

        console.log(error);

        alert("Server Error");

    }

});