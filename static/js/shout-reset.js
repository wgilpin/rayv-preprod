
$(function () {
    $("#reset-frm").submit(function(){
        // validate passwords
        if ($("input[name=password]").val() != $("input[name=pwd2]").val()){
            alert("Passwords don't match");
            return false;
        }
        if ($("input[name=pwd]").val().length < 6){
            alert("Passwords must be at least 6 characters long");
            return false;
        }
        return true;
    })
    console.log("JS Init'd Reset")
    $("#loading").html('.');
});


