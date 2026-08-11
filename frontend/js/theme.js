(function () {

    const savedTheme = localStorage.getItem("theme");

    if (savedTheme === "dark") {
        document.documentElement.classList.add("dark");
    }

    document.addEventListener("DOMContentLoaded", () => {

        const themeToggle = document.getElementById("themeToggle");

        if (!themeToggle) {
            return;
        }

        function updateIcon() {

            if (document.documentElement.classList.contains("dark")) {
                themeToggle.textContent = "☀️";
                themeToggle.setAttribute(
                    "aria-label",
                    "Switch to light mode"
                );
            } else {
                themeToggle.textContent = "🌙";
                themeToggle.setAttribute(
                    "aria-label",
                    "Switch to dark mode"
                );
            }

        }

        updateIcon();

        themeToggle.addEventListener("click", () => {

            const isDark =
                document.documentElement.classList.toggle("dark");

            if (isDark) {

                localStorage.setItem("theme", "dark");

            } else {

                localStorage.setItem("theme", "light");

            }

            updateIcon();

        });

    });

})();