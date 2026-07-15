const token = localStorage.getItem("access_token");

async function loadComplaints(){

    const response = await fetch(`${API_BASE}/my-complaints`,{

        headers:{
            Authorization:`Bearer ${token}`
        }

    });

    const data = await response.json();

    const table = document.getElementById("complaintsTable");

    table.innerHTML="";

    data.forEach(c=>{

table.innerHTML += `

<tr>

<td>${c.complaint_id}</td>

<td>${c.title}</td>

<td>${c.department}</td>

<td>${c.status}</td>

<td>${c.priority}</td>

<td>
<button class="view-btn" onclick="viewComplaint(${c.complaint_id})">
<i class="fa-solid fa-eye"></i> View
</button>
</td>

<td>
<button class="track-btn" onclick="trackComplaint(${c.complaint_id})">
<i class="fa-solid fa-location-dot"></i> Track
</button>
</td>

</tr>

`;

});

}

function viewComplaint(id){

    window.location.href=`complaint_details.html?id=${id}`;

}

loadComplaints();

function trackComplaint(id){

window.location.href=`track.html?id=${id}`;

}