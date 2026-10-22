let civicFlowLocationDataPromise = null;

async function getCivicFlowLocationData() {
    const cacheKey = "civicflow_state_district_v1";
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
        try { return JSON.parse(cached); } catch (_) { sessionStorage.removeItem(cacheKey); }
    }
    if (!civicFlowLocationDataPromise) {
        civicFlowLocationDataPromise = fetch("data/state_district_wise.json", { cache: "force-cache" })
            .then(response => {
                if (!response.ok) throw new Error("Location dataset unavailable");
                return response.json();
            })
            .then(data => {
                try { sessionStorage.setItem(cacheKey, JSON.stringify(data)); } catch (_) {}
                return data;
            });
    }
    return civicFlowLocationDataPromise;
}

async function initStateDistrictDropdown(stateId, districtId, selectedState = "", selectedDistrict = "") {
    const stateEl = document.getElementById(stateId);
    const districtEl = districtId ? document.getElementById(districtId) : null;
    if (!stateEl) return;
    try {
        const data = await getCivicFlowLocationData();
        stateEl.innerHTML = '<option value="">Select State</option>';
        data.forEach(item => {
            const option = document.createElement("option");
            option.value = item.state;
            option.textContent = item.state;
            stateEl.appendChild(option);
        });
        if (selectedState) stateEl.value = selectedState;

        const populateDistricts = (wanted = "") => {
            if (!districtEl) return;
            districtEl.innerHTML = '<option value="">Select District</option>';
            const match = data.find(item => item.state === stateEl.value);
            if (!match) return;
            match.districts.forEach(d => {
                const option = document.createElement("option");
                option.value = d;
                option.textContent = d;
                districtEl.appendChild(option);
            });
            if (wanted) districtEl.value = wanted;
        };
        if (districtEl) {
            populateDistricts(selectedDistrict);
            stateEl.addEventListener("change", () => populateDistricts(""));
        }
    } catch (err) {
        console.error("Unable to load state/district list", err);
    }
}
