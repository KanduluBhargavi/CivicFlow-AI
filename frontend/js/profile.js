const token = localStorage.getItem("access_token");

// Load Profile

async function loadProfile(){

const response = await fetch(

`${API_BASE}/profile`,

{

headers:{

Authorization:`Bearer ${token}`

}

}

);

const data = await response.json();

document.getElementById("full_name").value=data.name;

document.getElementById("email").value=data.email;

document.getElementById("phone").value=data.phone;

document.getElementById("state").value=data.state;

document.getElementById("district").value=data.district;

document.getElementById("area").value=data.area;

document.getElementById("address").value=data.address;

document.getElementById("pincode").value=data.pincode;

}

// Update Profile

document.getElementById("profileForm")

.addEventListener("submit",async(e)=>{

e.preventDefault();

const response=await fetch(

`${API_BASE}/profile`,

{

method:"PUT",

headers:{

Authorization:`Bearer ${token}`,

"Content-Type":"application/json"

},

body:JSON.stringify({

name:document.getElementById("full_name").value,

phone:document.getElementById("phone").value,

state:document.getElementById("state").value,

district:document.getElementById("district").value,

city:document.getElementById("area").value,

address:document.getElementById("address").value,

pincode:document.getElementById("pincode").value

})

}

);

const data=await response.json();

alert(data.message || data.detail);

});

// Change Password

document.getElementById("passwordForm")

.addEventListener("submit",async(e)=>{

e.preventDefault();

const response=await fetch(

`${API_BASE}/change-password`,

{

method:"PUT",

headers:{

Authorization:`Bearer ${token}`,

"Content-Type":"application/json"

},

body:JSON.stringify({

old_password:document.getElementById("oldPassword").value,

new_password:document.getElementById("newPassword").value

})

}

);

const data=await response.json();

alert(data.message || data.detail);

document.getElementById("passwordForm").reset();

});

loadProfile();