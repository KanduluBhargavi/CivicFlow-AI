
const locationBtn = document.getElementById("locationBtn");
const locationBtnText = document.querySelector(".location-btn-text") || locationBtn;
const defaultLocationBtnText = locationBtnText ? locationBtnText.textContent : "Use My Current Location";

if (locationBtn) {
    locationBtn.addEventListener("click", () => {
        if (!navigator.geolocation) {
            alert("Geolocation is not supported in this browser.");
            return;
        }

        locationBtn.classList.add("loading");
        if (locationBtnText) locationBtnText.textContent = "Detecting your location...";
        locationBtn.disabled = true;

        navigator.geolocation.getCurrentPosition(success, error, {
            enableHighAccuracy: true,
            timeout: 12000,
            maximumAge: 0
        });
    });
}

function resetLocationBtn(message) {
    if (!locationBtn) return;
    locationBtn.classList.remove("loading");
    locationBtn.disabled = false;
    if (locationBtnText) locationBtnText.textContent = message || defaultLocationBtnText;
}

function success(position) {
    document.getElementById("latitude").value = position.coords.latitude;
    document.getElementById("longitude").value = position.coords.longitude;
    const sourceField = document.getElementById("locationSource");
    if (sourceField) sourceField.value = "gps";
    if (locationBtnText) locationBtnText.textContent = "Fetching address...";
    reverseGeocode(position.coords.latitude, position.coords.longitude);
}

function error(err) {
    resetLocationBtn();
    if (err && err.code === 1) {
        alert("Location permission was denied. Please allow access and try again.");
    } else {
        alert("Unable to get your location right now. Please enter the location manually.");
    }
}

async function reverseGeocode(lat, lon) {
    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}`
        );
        const data = await response.json();
        const address = data.address || {};

        document.getElementById("latitude").value = lat;
        document.getElementById("longitude").value = lon;

        if (address.state) {
            stateSelect.value = address.state;
            stateSelect.dispatchEvent(new Event("change"));
        }

        let district =
            address.state_district ||
            address.county ||
            address.city_district ||
            address.district ||
            "";

        setTimeout(() => {
            if (district) {
                const optionValues = districtOptions
                    ? [...districtOptions.options].map(o => o.value)
                    : [];
                const matched = optionValues.find(option =>
                    option.toLowerCase().includes(district.toLowerCase()) ||
                    district.toLowerCase().includes(option.toLowerCase())
                );
                // If the district is newer/missing from local suggestions, keep
                // the geocoder's district text instead of dropping it.
                districtSelect.value = matched || district;
            }
        }, 300);

        document.getElementById("area").value =
            address.suburb || address.neighbourhood || address.hamlet ||
            address.village || address.town || address.city || "";

        document.getElementById("landmark").value = address.road || "";
        document.getElementById("address").value = data.display_name || "";
        document.getElementById("pincode").value = address.postcode || "";

        resetLocationBtn("Location detected");
        setTimeout(() => resetLocationBtn(), 1800);
    } catch (e) {
        console.error(e);
        resetLocationBtn();
        alert("Location was detected, but address lookup failed. Please review the filled details manually.");
    }
}


// Address lookup + incident-location picker. The citizen can report a place
// different from their current GPS location by clicking or dragging the pin.
(function setupAddressGeocoding() {
    const resolveBtn = document.getElementById("resolveAddressBtn");
    const status = document.getElementById("addressGeocodeStatus");
    const candidateBox = document.getElementById("addressGeocodeCandidate");
    const candidateText = document.getElementById("addressGeocodeCandidateText");
    const confirmBtn = document.getElementById("confirmAddressPointBtn");
    const discardBtn = document.getElementById("discardAddressPointBtn");
    const latInput = document.getElementById("latitude");
    const lonInput = document.getElementById("longitude");
    const sourceInput = document.getElementById("locationSource");
    const mapElement = document.getElementById("incidentLocationMap");
    const pinStatus = document.getElementById("incidentPinStatus");
    let pendingCandidate = null;
    let incidentMap = null;
    let incidentMarker = null;
    let pinMovedByUser = false;
    let leafletLoadPromise = null;

    if (!resolveBtn || !status || !candidateBox) return;

    // Keep a temporary draft so an unexpected navigation/reset during the
    // address lookup cannot erase the citizen's typed complaint location.
    const form = document.getElementById("complaintForm");
    const draftKey = `civicflow_location_draft:${window.location.pathname}`;
    const locationFieldIds = ["state", "district", "area", "landmark", "address", "pincode"];
    function saveLocationDraft() {
        const draft = {};
        for (const id of locationFieldIds) {
            const field = document.getElementById(id);
            if (field) draft[id] = field.value;
        }
        try { sessionStorage.setItem(draftKey, JSON.stringify({ savedAt: Date.now(), fields: draft })); }
        catch (_) { /* Storage can be unavailable in private/restricted contexts. */ }
    }
    function restoreLocationDraftIfCleared() {
        try {
            const raw = sessionStorage.getItem(draftKey);
            if (!raw) return;
            const saved = JSON.parse(raw);
            if (!saved || !saved.fields || Date.now() - Number(saved.savedAt || 0) > 30 * 60 * 1000) {
                sessionStorage.removeItem(draftKey);
                return;
            }
            // Restore only blank fields; never overwrite text the citizen has
            // already entered after a reload.
            for (const id of locationFieldIds) {
                const field = document.getElementById(id);
                const value = saved.fields[id];
                if (field && !field.value.trim() && typeof value === "string" && value.trim()) {
                    field.value = value;
                }
            }
        } catch (_) { /* Ignore malformed/unavailable draft storage. */ }
    }
    restoreLocationDraftIfCleared();
    for (const id of locationFieldIds) {
        const field = document.getElementById(id);
        field?.addEventListener("input", saveLocationDraft);
        field?.addEventListener("change", saveLocationDraft);
    }
    // A real complaint submission should not restore an old draft later.
    form?.addEventListener("submit", () => {
        try { sessionStorage.removeItem(draftKey); } catch (_) {}
    }, true);

    const setStatus = (message, isError = false) => {
        status.textContent = message;
        status.style.color = isError ? "#b91c1c" : "var(--text-secondary, #475569)";
    };

    function updateCandidateCoordinates(lat, lon, userMoved = false) {
        if (!pendingCandidate) return;
        pendingCandidate.latitude = Number(lat);
        pendingCandidate.longitude = Number(lon);
        if (userMoved) pinMovedByUser = true;
        if (pinStatus) pinStatus.textContent = userMoved
            ? `Selected incident point: ${Number(lat).toFixed(6)}, ${Number(lon).toFixed(6)}. This is the place you selected, not your device's current location.`
            : `Suggested point: ${Number(lat).toFixed(6)}, ${Number(lon).toFixed(6)}. Click the affected place or drag the pin to correct it.`;
    }

    function loadLeafletWhenNeeded() {
        if (window.L) return Promise.resolve();
        if (leafletLoadPromise) return leafletLoadPromise;
        leafletLoadPromise = new Promise((resolve, reject) => {
            const stylesheet = document.createElement("link");
            stylesheet.rel = "stylesheet";
            stylesheet.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
            stylesheet.integrity = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";
            stylesheet.crossOrigin = "anonymous";
            document.head.appendChild(stylesheet);

            const script = document.createElement("script");
            script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
            script.integrity = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=";
            script.crossOrigin = "anonymous";
            const timeout = window.setTimeout(() => reject(new Error("Map library timed out")), 10000);
            script.onload = () => { window.clearTimeout(timeout); resolve(); };
            script.onerror = () => { window.clearTimeout(timeout); reject(new Error("Map library unavailable")); };
            document.head.appendChild(script);
        }).catch(error => {
            leafletLoadPromise = null;
            throw error;
        });
        return leafletLoadPromise;
    }

    async function showCandidateOnMap(candidate) {
        if (!mapElement) return;
        if (!window.L) {
            if (pinStatus) pinStatus.textContent = "Loading the map so you can verify this suggested point…";
            try {
                await loadLeafletWhenNeeded();
            } catch (_) {
                if (pinStatus) pinStatus.textContent = "The map service is unavailable or slow. You can still confirm this approximate address point, or retry when online.";
                return;
            }
        }
        if (!window.L) {
            if (pinStatus) pinStatus.textContent = "The map is unavailable. You can still confirm this approximate address point.";
            return;
        }
        const lat = Number(candidate.latitude), lon = Number(candidate.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
        if (!incidentMap) {
            incidentMap = window.L.map(mapElement, {scrollWheelZoom: true, zoomControl: true}).setView([lat, lon], 17);
            window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
            }).addTo(incidentMap);
            incidentMap.on("click", event => {
                if (!pendingCandidate || !incidentMarker) return;
                incidentMarker.setLatLng(event.latlng);
                updateCandidateCoordinates(event.latlng.lat, event.latlng.lng, true);
            });
        } else {
            incidentMap.setView([lat, lon], 17);
        }
        if (incidentMarker) incidentMarker.remove();
        incidentMarker = window.L.marker([lat, lon], {draggable: true}).addTo(incidentMap);
        incidentMarker.on("dragend", () => {
            const point = incidentMarker.getLatLng();
            updateCandidateCoordinates(point.lat, point.lng, true);
        });
        updateCandidateCoordinates(lat, lon, false);
        // Leaflet needs a size refresh after its parent is unhidden.
        setTimeout(() => incidentMap && incidentMap.invalidateSize(), 100);
    }

    resolveBtn.addEventListener("click", async (event) => {
        // This action must never submit or navigate the surrounding complaint form.
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        saveLocationDraft();
        const payload = {
            state: document.getElementById("state")?.value?.trim() || "",
            district: document.getElementById("district")?.value?.trim() || "",
            area: document.getElementById("area")?.value?.trim() || "",
            address: document.getElementById("address")?.value?.trim() || "",
            landmark: document.getElementById("landmark")?.value?.trim() || "",
            pincode: document.getElementById("pincode")?.value?.trim() || ""
        };
        if (!payload.state || !payload.district || !payload.address) {
            setStatus("Enter the state, district and address first. Area and pincode also improve the match.", true);
            return;
        }
        const token = localStorage.getItem("access_token");
        if (!token) {
            setStatus("Please sign in first, then return to this form to look up the complaint location.", true);
            return;
        }
        resolveBtn.disabled = true;
        const oldText = resolveBtn.textContent;
        resolveBtn.textContent = "Finding address…";
        candidateBox.hidden = true;
        pendingCandidate = null;
        pinMovedByUser = false;
        setStatus("Searching for the affected place, not necessarily your current location…");
        try {
            const controller = new AbortController();
            // Local-language translation plus rate-limited locality fallbacks can
            // require several provider calls. Keep this lookup alive through them.
            const requestTimeout = window.setTimeout(() => controller.abort(), 75000);
            let response;
            try {
                response = await fetch(`${API_BASE}/complaints/geocode-address`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                    body: JSON.stringify(payload),
                    signal: controller.signal
                });
            } finally {
                window.clearTimeout(requestTimeout);
            }
            const data = await response.json().catch(() => ({}));
            if (response.status === 401) throw new Error("Your sign-in has expired. Sign in again, then retry the address lookup.");
            if (!response.ok) throw new Error(data.detail || `Address lookup failed (HTTP ${response.status}). Check that the CivicFlow backend is running and try again.`);
            if (!data.success || !data.result) {
                setStatus(data.message || "No suitable match found. Try adding a village, road or landmark.", true);
                return;
            }
            pendingCandidate = data.result;
            candidateText.textContent = `${pendingCandidate.display_name} — ${pendingCandidate.match_level === "address_or_road" ? "address/road-level match" : pendingCandidate.match_level === "locality_approximate" ? "approximate locality match" : "approximate area match"}. Verify the point on the map; geocoding does not guarantee an exact incident location. ${pendingCandidate.warnings?.join(" ") || ""}`;
            candidateBox.hidden = false;
            showCandidateOnMap(pendingCandidate);
            setStatus("Review the map. Click the incident location or drag the pin, then confirm it.");
        } catch (err) {
            const message = err.name === "AbortError"
                ? "Address lookup took too long. Check your internet connection and that the CivicFlow backend is running, then retry."
                : err instanceof TypeError
                    ? "Could not reach the CivicFlow backend. Check that it is running on port 8000 and that this page is using the correct local address."
                    : (err.message || "Address lookup failed. Add more address details and try again.");
            setStatus(message, true);
        } finally {
            resolveBtn.disabled = false;
            resolveBtn.textContent = oldText || "Find approximate point from address";
        }
    }, true);

    confirmBtn?.addEventListener("click", () => {
        if (!pendingCandidate) return;
        latInput.value = pendingCandidate.latitude;
        lonInput.value = pendingCandidate.longitude;
        if (sourceInput) sourceInput.value = pinMovedByUser ? "user_confirmed_map_pin" : `osm_${pendingCandidate.match_level || "approximate"}`;
        setStatus(`Incident location saved: ${pendingCandidate.display_name}. ${pinMovedByUser ? "You confirmed the point on the map." : "This is an address match; it may be approximate."}`);
        candidateBox.hidden = true;
        pendingCandidate = null;
        pinMovedByUser = false;
    });

    discardBtn?.addEventListener("click", () => {
        pendingCandidate = null;
        pinMovedByUser = false;
        candidateBox.hidden = true;
        setStatus("Location suggestion discarded. Your complaint address is unchanged; no suggested coordinates will be submitted.");
    });
})();
