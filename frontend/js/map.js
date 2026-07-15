const states = document.querySelectorAll(".india-map svg path");

states.forEach(state => {

    state.addEventListener("click", function(){

        alert(this.getAttribute("title"));

    });

});