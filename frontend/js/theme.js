/* CivicFlow theme + small UI helpers.
   Loaded in <head> on every page so the saved theme applies before first paint. */
(function () {
    var KEY = "theme";
    var saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) {}
    var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (saved === "dark" || (!saved && prefersDark)) {
        document.documentElement.classList.add("dark");
    }

    var SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4"/></svg>';
    var MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"/></svg>';

    /* ---- status / priority marks for plain table cells ---- */
    var STATUS = {
        "submitted": "submitted", "pending": "pending", "new": "submitted",
        "classified": "classified", "assigned": "assigned",
        "in progress": "progress", "in-progress": "progress", "under review": "review", "review": "review",
        "resolved": "resolved", "closed": "closed", "completed": "resolved",
        "rejected": "rejected", "escalated": "escalated", "overdue": "overdue"
    };
    var PRIORITY = { "critical": "critical", "high": "high", "medium": "medium", "low": "low" };

    function decorateCell(td) {
        if (td.dataset.cfDone || td.children.length) return;
        var raw = (td.textContent || "").trim();
        if (!raw || raw.length > 20) return;
        var key = raw.toLowerCase();
        var cls = null, attr = null, val = null;
        if (STATUS[key]) { cls = "cf-status"; attr = "data-s"; val = STATUS[key]; }
        else if (PRIORITY[key]) { cls = "cf-priority"; attr = "data-p"; val = PRIORITY[key]; }
        if (!cls) return;
        td.dataset.cfDone = "1";
        var span = document.createElement("span");
        span.className = cls;
        span.setAttribute(attr, val);
        span.textContent = raw;
        td.textContent = "";
        td.appendChild(span);
    }

    function decorate(root) {
        if (!root || !root.querySelectorAll) return;
        var cells = root.tagName === "TD" ? [root] : root.querySelectorAll("td");
        for (var i = 0; i < cells.length; i++) decorateCell(cells[i]);
    }

    document.addEventListener("DOMContentLoaded", function () {
        var themeToggle = document.getElementById("themeToggle");

        function updateIcon() {
            if (!themeToggle) return;
            var dark = document.documentElement.classList.contains("dark");
            themeToggle.innerHTML = dark ? SUN : MOON;
            themeToggle.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
            themeToggle.setAttribute("title", dark ? "Light mode" : "Dark mode");
        }

        if (themeToggle) {
            updateIcon();
            themeToggle.addEventListener("click", function () {
                var isDark = document.documentElement.classList.toggle("dark");
                try { localStorage.setItem(KEY, isDark ? "dark" : "light"); } catch (e) {}
                updateIcon();
            });
        }

        decorate(document.body);
        new MutationObserver(function (muts) {
            for (var i = 0; i < muts.length; i++) {
                var added = muts[i].addedNodes;
                for (var j = 0; j < added.length; j++) {
                    if (added[j].nodeType === 1) decorate(added[j]);
                }
            }
        }).observe(document.body, { childList: true, subtree: true });
    });
})();
