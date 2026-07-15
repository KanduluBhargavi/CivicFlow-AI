// complaint.js

document.getElementById("complaintForm").addEventListener("submit", async function (e) {

    e.preventDefault();

    const token = localStorage.getItem("access_token");

    if (!token) {
        alert("Please login first.");
        window.location.href = "login.html";
        return;
    }

    const formData = new FormData();

    formData.append("title", document.getElementById("title").value);
    formData.append("description", document.getElementById("description").value);
    formData.append("state", document.getElementById("state").value);
    formData.append("district", document.getElementById("district").value);
    formData.append("area", document.getElementById("area").value);
    formData.append("address", document.getElementById("address").value);
    formData.append("landmark", document.getElementById("landmark").value);
    formData.append("pincode", document.getElementById("pincode").value);

    formData.append(
        "latitude",
        document.getElementById("latitude").value || 0
    );

    formData.append(
        "longitude",
        document.getElementById("longitude").value || 0
    );

    const file = document.getElementById("media").files[0];

    if (file) {
        formData.append("file", file);
    }

    try {

        const response = await fetch(`${API_BASE}/complaints`, {

            method: "POST",

            headers: {
                Authorization: `Bearer ${token}`
            },

            body: formData

        });

        const data = await response.json();

        if (response.ok) {

            alert("Complaint Submitted Successfully!");

            document.getElementById("complaintForm").reset();

            window.location.href = "dashboard.html";

        } else {

            alert(data.detail || data.message || "Submission Failed");

        }

    } catch (err) {

        console.log(err);

        alert("Server Error");

    }

});