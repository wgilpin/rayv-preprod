function show_password() {
    //on the login page
    var pwd = $('#pwd').val();
    if ($("#login-show-btn").val()=="on")
        $('#pwd').attr('type', 'text')
    else
        $('#pwd').attr('type', 'password');
    $("#pwd").val(pwd);
}

$(function () {
    $("#forgot-btn").attr("data-ajax", "false");
    $("#login-show-btn").change(show_password);
    console.log("JS Init'd Login")
    $("#loading").html('.');
});


