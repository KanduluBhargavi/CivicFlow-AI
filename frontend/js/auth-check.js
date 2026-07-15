const token = localStorage.getItem("access_token");

if(!token){

    alert("Please login first.");

    window.location.href="login.html";

}