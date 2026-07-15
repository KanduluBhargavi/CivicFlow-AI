

document.getElementById("registerForm").addEventListener("submit", async function(e){

    e.preventDefault();

    const user={

        full_name:document.getElementById("full_name").value,

        email:document.getElementById("email").value,

        phone:document.getElementById("phone").value,

        password:document.getElementById("password").value,

        department_id:null,

        state:document.getElementById("state").value,

        district:document.getElementById("district").value,

        address:document.getElementById("address").value,
        area: document.getElementById("area").value,
        landmark: document.getElementById("landmark").value,
        pincode: document.getElementById("pincode").value,
       latitude: document.getElementById("latitude").value
    ? parseFloat(document.getElementById("latitude").value)
    : null,

longitude: document.getElementById("longitude").value
    ? parseFloat(document.getElementById("longitude").value)
    : null,

    };

    const response=await fetch(`${API_BASE}/register`,{

        method:"POST",

        headers:{

            "Content-Type":"application/json"

        },

        body:JSON.stringify(user)

    });

    const data = await response.json();

console.log(data);

if(response.ok){

    alert("Registration Successful!");
    window.location.href = "login.html";

}
else{

    console.log(data);
    alert(JSON.stringify(data, null, 2));

}

});