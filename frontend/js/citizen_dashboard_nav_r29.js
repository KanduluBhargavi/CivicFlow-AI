// Citizen navbar display and logout on subpages; dashboard's original logic stays untouched.
(() => {
 const name = document.querySelector('.citizen-dashboard-nav #userName');
 if(name) name.textContent = localStorage.getItem('name') || 'Citizen';
 const logout = document.querySelector('.citizen-dashboard-nav #logoutBtn');
 // feedback.js and incident_details.js already wire logout; don't double bind.
 if(logout && !['feedback.html','incident_details.html'].includes(location.pathname.split('/').pop())) {
   logout.addEventListener('click', () => { localStorage.clear(); location.href='login.html'; });
 }
})();
