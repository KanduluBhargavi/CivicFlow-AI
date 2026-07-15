const stateSelect = document.getElementById("state");
const districtSelect = document.getElementById("district");

let statesData = [];

async function loadStates() {

    const response = await fetch("data/state_district_wise.json");

    statesData = await response.json();

    stateSelect.innerHTML = '<option value="">Select State</option>';

    statesData.forEach(item => {

        stateSelect.innerHTML += `
            <option value="${item.state}">
                ${item.state}
            </option>
        `;

    });

}

stateSelect.addEventListener("change", function () {

    districtSelect.innerHTML =
        '<option value="">Select District</option>';

    const selectedState = statesData.find(
        item => item.state === this.value
    );

    if (!selectedState) return;

    selectedState.districts.forEach(district => {

        districtSelect.innerHTML += `
            <option value="${district}">
                ${district}
            </option>
        `;

    });

});

loadStates();