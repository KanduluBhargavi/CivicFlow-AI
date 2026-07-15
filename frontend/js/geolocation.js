const locationBtn = document.getElementById("locationBtn");

locationBtn.addEventListener("click", () => {

    if (!navigator.geolocation) {

        alert("Geolocation is not supported.");

        return;

    }

    navigator.geolocation.getCurrentPosition(success, error);

});

function success(position){

    document.getElementById("latitude").value =
    position.coords.latitude;

    document.getElementById("longitude").value =
    position.coords.longitude;

    reverseGeocode(
        position.coords.latitude,
        position.coords.longitude
    );

}

function error(){

    alert("Location permission denied.");

}

async function reverseGeocode(lat, lon){

    const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}`
    );

    const data = await response.json();

    const address = data.address;

    document.getElementById("latitude").value = lat;
    document.getElementById("longitude").value = lon;

    /* ---------- STATE ---------- */

    if(address.state){

        stateSelect.value = address.state;

        stateSelect.dispatchEvent(new Event("change"));

    }

    /* ---------- DISTRICT ---------- */

    let district =
        address.state_district ||
        address.county ||
        address.city_district ||
        address.district ||
        "";

    setTimeout(()=>{

        if(district){

            const options =
            [...districtSelect.options].map(o=>o.value);

            const matched = options.find(option =>
                option.toLowerCase().includes(district.toLowerCase()) ||
                district.toLowerCase().includes(option.toLowerCase())
            );

            if(matched){

                districtSelect.value = matched;

            }

        }

    },300);

    /* ---------- AREA ---------- */

    document.getElementById("area").value =
        address.suburb ||
        address.neighbourhood ||
        address.hamlet ||
        address.village ||
        address.town ||
        address.city ||
        "";

    /* ---------- LANDMARK ---------- */

    document.getElementById("landmark").value =
        address.road ||
        "";

    /* ---------- ADDRESS ---------- */

    document.getElementById("address").value =
        data.display_name;

    /* ---------- PINCODE ---------- */

    document.getElementById("pincode").value =
        address.postcode || "";

}