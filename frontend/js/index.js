/* ==========================================================================
   CivicFlow AI — Interactions
   1. Sticky navbar shadow   2. Mobile menu   3. Scroll reveal
   4. Animated counters      5. FAQ accordion  6. Live activity feed ticker
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {

  /* ---------- 1. Sticky navbar shadow ---------- */
  const navbar = document.getElementById('navbar');
  const onScroll = () => {
    navbar.classList.toggle('is-scrolled', window.scrollY > 12);
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  /* ---------- 2. Mobile menu ---------- */
  const navToggle = document.getElementById('navToggle');
  const navLinks = document.getElementById('navLinks');

  navToggle.addEventListener('click', () => {
    const isOpen = navLinks.classList.toggle('is-open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
  });

  navLinks.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      navLinks.classList.remove('is-open');
      navToggle.setAttribute('aria-expanded', 'false');
    });
  });

  /* ---------- 3. Scroll reveal ---------- */
  const revealTargets = document.querySelectorAll(
    '.stat-card, .feature-card, .dept-row, .why-card, .timeline__item, .accordion__item'
  );
  revealTargets.forEach(el => el.setAttribute('data-reveal', ''));

  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });

  revealTargets.forEach(el => revealObserver.observe(el));

  /* ---------- 4. Animated counters ---------- */
  const counters = document.querySelectorAll('[data-count]');

  const animateCounter = (el) => {
    const target = parseFloat(el.getAttribute('data-count'));
    const decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);
    const suffix = el.getAttribute('data-suffix') || '';
    const duration = 1600;
    const start = performance.now();

    const step = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = target * eased;
      el.textContent = value.toLocaleString('en-IN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
      }) + suffix;
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        counterObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.4 });

  counters.forEach(el => counterObserver.observe(el));

  /* ---------- 5. FAQ accordion ---------- */
  const accordionItems = document.querySelectorAll('.accordion__item');

  accordionItems.forEach(item => {
    const trigger = item.querySelector('.accordion__trigger');
    const panel = item.querySelector('.accordion__panel');

    trigger.addEventListener('click', () => {
      const isOpen = item.classList.contains('is-open');

      accordionItems.forEach(other => {
        other.classList.remove('is-open');
        other.querySelector('.accordion__trigger').setAttribute('aria-expanded', 'false');
        other.querySelector('.accordion__panel').style.maxHeight = null;
      });

      if (!isOpen) {
        item.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');
        panel.style.maxHeight = panel.scrollHeight + 'px';
      }
    });
  });
loadDashboardStats();
loadRecentComplaints();
loadTopStates();
loadDepartmentPerformance();

});
  


async function loadDashboardStats() {

    try {

        const response = await fetch("http://127.0.0.1:8000/dashboard/stats");

        const data = await response.json();

        document.getElementById("totalComplaints").textContent = data.total_complaints;
        document.getElementById("resolvedComplaints").textContent = data.resolved;
        document.getElementById("pendingComplaints").textContent = data.pending;
        document.getElementById("departmentCount").textContent = data.departments;

    } catch (error) {

        console.error(error);

    }

}



async function loadRecentComplaints() {

    try {

        const response = await fetch("http://127.0.0.1:8000/dashboard/recent-complaints");

        const complaints = await response.json();

        const feed = document.getElementById("activityFeed");

        feed.innerHTML = "";

        complaints.forEach(c => {

            let tagClass = "activity-feed__tag--medium";

            if (c.priority.toLowerCase() === "high")
                tagClass = "activity-feed__tag--critical";

            if (c.status.toLowerCase() === "resolved")
                tagClass = "activity-feed__tag--resolved";

            feed.innerHTML += `
                <li>
                    <span class="activity-feed__tag ${tagClass}">
                        ${c.priority}
                    </span>

                    ${c.title} — ${c.district}, ${c.state}

                    <time>${c.status}</time>

                </li>
            `;

        });

    }

    catch (error) {

        console.log(error);

    }

}
async function loadTopStates(){

    try{

        const response = await fetch("http://127.0.0.1:8000/dashboard/top-states");

        const states = await response.json();

        const container = document.getElementById("topStates");

        container.innerHTML = "";

        states.forEach(state =>{

            container.innerHTML +=`

                <div class="state-item">

                    <span>${state.state}</span>

                    <strong>${state.count}</strong>

                </div>

            `;

        });

    }

    catch(error){

        console.log(error);

    }

}

async function loadDepartmentPerformance() {

    try {

        const response = await fetch("http://127.0.0.1:8000/dashboard/department-performance");

        const departments = await response.json();

        const container = document.getElementById("departmentPerformance");

        container.innerHTML = "";

        let maxComplaints = 1;

        departments.forEach(d => {
            if (d.complaints > maxComplaints)
                maxComplaints = d.complaints;
        });

        departments.forEach(d => {

            const percentage = (d.complaints / maxComplaints) * 100;

            container.innerHTML += `

                <div class="dept-card">

                    <div class="dept-header">
                        <span>${d.department}</span>
                        <strong>${d.complaints}</strong>
                    </div>

                    <div class="dept-bar">
                        <div class="dept-progress" style="width:${percentage}%"></div>
                    </div>

                </div>

            `;

        });

    }

    catch(error){

        console.log(error);

    }

}



