const stateSelect = document.getElementById("state");
const districtSelect = document.getElementById("district");
const districtOptions = document.getElementById("districtOptions");

let statesData = [];

function populateDistrictSuggestions(districts = []) {
    if (!districtOptions) return;
    districtOptions.innerHTML = "";
    districts.forEach(district => {
        const option = document.createElement("option");
        option.value = district;
        districtOptions.appendChild(option);
    });
}

async function loadStates() {
    if (!stateSelect || !districtSelect) return;

    try {
        const response = await fetch("data/state_district_wise.json");
        statesData = await response.json();

        stateSelect.innerHTML = '<option value="">Select State</option>';

        statesData.forEach(item => {
            const option = document.createElement("option");
            option.value = item.state;
            option.textContent = item.state;
            stateSelect.appendChild(option);
        });
    } catch (error) {
        console.error("Unable to load state/district data:", error);
    }
}

stateSelect?.addEventListener("change", function () {
    districtSelect.value = "";

    const selectedState = statesData.find(item => item.state === this.value);
    populateDistrictSuggestions(selectedState?.districts || []);
});

/*
 * District is intentionally an editable autocomplete input instead of a rigid
 * select. Administrative boundaries change and a stale local JSON file must
 * never prevent a citizen from submitting a valid district.
 */
loadStates();
