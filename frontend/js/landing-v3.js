const menuBtn = document.getElementById("menuBtn");
const mainNav = document.getElementById("mainNav");

menuBtn?.addEventListener("click", () => {
  const open = mainNav.classList.toggle("open");
  menuBtn.setAttribute("aria-expanded", String(open));
});

mainNav?.querySelectorAll("a").forEach(link => {
  link.addEventListener("click", () => {
    mainNav.classList.remove("open");
    menuBtn?.setAttribute("aria-expanded", "false");
  });
});

const sections = [...document.querySelectorAll("section[id]")];
const navAnchors = [...document.querySelectorAll('.main-nav a[href^="#"]')];

window.addEventListener("scroll", () => {
  const y = window.scrollY + 130;
  let active = "top";
  for (const section of sections) {
    if (section.offsetTop <= y) active = section.id;
  }
  navAnchors.forEach(a => {
    a.classList.toggle("active", a.getAttribute("href") === `#${active}`);
  });
}, { passive: true });
