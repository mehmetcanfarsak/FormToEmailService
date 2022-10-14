window.onload = start;

function start() {
    let submitButton = document.getElementById("submit");
    submitButton.addEventListener("click", submitForm);
    $("#captcha").on('keyup', function (e) {
    if (e.key === 'Enter' || e.keyCode === 13) {
        submitForm();
    }
});
}



function submitForm() {
    let captcha_text = document.getElementById("captcha").value;
    if(captcha_text==="" || captcha_text===undefined){
        alert("Please fill captcha text");
        return;
    }
    let filled_form_key = document.getElementById("filled_form_key").value;
    let alias = document.getElementById("alias").value;
    var spinner = $('#loader');

    spinner.show();
    let data = {
        text_of_captcha: captcha_text,
        filled_form_key: filled_form_key,
    };

    fetch(alias+"/captcha-submit", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(res => {
        if (res.ok) {
            res.json()
                .then(data => {

                    let resultDiv = document.createElement("div");
                    resultDiv.className = "subtitle";
                    resultDiv.style.textAlign = "center"

                    if (data.is_submit_successful === true) {
                        $('#loader').css('background','rgba(0,0,0,0.75) url(static/check-circle.gif) no-repeat center center');
                    }
                    else {
                        alert("Error: Looks like you typed wrong words. \n\n Please try again");
                        spinner.hide();
                    }
                })



        }else{
            res.json().then(data=>{
                alert(data.detail);
            })

        }

    });
}