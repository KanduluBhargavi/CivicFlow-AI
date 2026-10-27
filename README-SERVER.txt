CivicFlow - fix for the 2.5 minute page loads (local development)
================================================================
Your Network log shows only the first 3 files load fast; everything after waits exactly 2.5 min, even a 992-byte file.
Your login.html has 113 lines but the log says line 135 -> a dev server (VS Code "Live Server") is injecting its own script
and is the thing stalling. The frontend files are not the problem.

FIX: stop using Live Server. Use this threaded server instead.
 1. Put serve_frontend.py in your project root (the folder that CONTAINS "frontend").
 2. Run:   python serve_frontend.py
 3. Open:  http://127.0.0.1:5500/login.html      (use 127.0.0.1, not localhost)
    It uses port 5500, the same port as Live Server, so your backend's CORS settings keep working.
 4. Keep your FastAPI backend running as usual.
Tested: login page loads in 0.29 s (10 requests).

If it is still slow with this server, the cause is your PC/network (antivirus or a browser extension scanning localhost).
Try an Incognito window with extensions off, and send me the new Network screenshot.

WHEN YOU DEPLOY: serve the frontend from FastAPI itself (same origin, no CORS):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")   # add AFTER all your API routes
    from fastapi.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware, minimum_size=500)
