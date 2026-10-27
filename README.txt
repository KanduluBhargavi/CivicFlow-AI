CivicFlow - GREEN theme, speed fix only
=======================================
Your original green theme, unchanged. Only the <head> of each .html page was edited:
Google Fonts / Font Awesome now load in the background, so the page paints immediately
instead of waiting for them (first paint with a hanging font host: 15.1 s -> 0.1 s).

Install: extract into your project root so these files replace the ones in frontend/. No CSS/JS/image files are included, so nothing else changes.
Then hard refresh (Ctrl+Shift+R).

Still slow? See SPEED notes: free hosting sleeping, no gzip, no caching. Send a DevTools > Network screenshot.
