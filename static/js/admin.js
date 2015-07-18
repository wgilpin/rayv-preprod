/**
 * Created by Will on 03/10/2014.
 * 0.4.3
 */

var Admin = Admin||{};

Admin.send = function(){
    var send_list = []
    $("input:checked").each(function(){
        send_list.push('"'+$(this).data('key')+'"');
    })
    $.ajax({
        url:'/admin/sync_to_prod',
        method:'POST',
        data:{'list': '['+send_list.join()+']'},
        success:function(){
            alert('Done')
        },
        dataType: "json"
    });
}

Admin.updatePhotos = function(){
    var send_list = []
    $("input:checked").each(function(){
        send_list.push('"'+$(this).data('key')+'"');
    })
    $.ajax({
        url:'/admin/update_photos',
        method:'POST',
        data:{'list': '['+send_list.join()+']'},
        success:function(){
            alert('Done')
        },
        dataType: "json"
    });
};

Admin.cleanup_after_delete = function(){
    $.ajax({
        url:'/admin/cleanup_votes',
        method:'GET',
        data:{},
        success:function(d){
            alert('Done')
        },
        error:function(jqXHR, textStatus, errorThrown){
            alert('Failed - see server logs');
            console.error('cleanup_after_delete: '+
                jqXHR+', '+
                textStatus+', '+
                errorThrown);
        },
        dataType: "json"
    });
};

Admin.GetCuisines = function(){

    $.ajax({
        url:'/getCuisines_ajax',
        method:'GET',
        data:{},
        success:function(d){
            Admin.cuisineList = d["categories"];
            console.log("Cuisines got");
        },
        error:function(jqXHR, textStatus, errorThrown){
            alert('Cusine fetch Failed - see server logs');
            console.error('GetCuisines: '+jqXHR+', '+textStatus+', '+errorThrown);
        },
        dataType: "json"
    });

};

Admin.SelectCuisine = function(){

    var optionSelected = $("option:selected", this);
    var valueSelected = this.value;
    $(".cuisine-btn").show();
    $(this).parent().find('.cuisine-btn').text(valueSelected);
    $(".cuisine-picker").remove();
    return false;
};

Admin.CreateCuisinePicker = function (){
    var el = $(this);

    // kill old ones
    $(".cuisine-picker").remove();
    $(".cuisine-btn").show();

    var s = $('<select class="cuisine-picker" />');

    for(var val in Admin.cuisineList) {
            $('<option />', {
                value: Admin.cuisineList[val],
                text: Admin.cuisineList[val]
            }).appendTo(s);
    }
    s.val($(el).text());


    s.appendTo(el.parent());
    el.hide();
    $('.cuisine-picker').change(Admin.SelectCuisine);
    return false;
};


Admin.update_vote = function(){
    var voteKey = $(this).parent().parent().data('key');
    var placeKey = $(this).parent().parent().parent().parent().parent().parent().parent().parent().data('key');
    var kind_bfast = $(this).parent().parent().find("button:contains('fast')");
    var kind_lunch = $(this).parent().parent().find("button:contains('Lunch')");
    var kind_dinner = $(this).parent().parent().find("button:contains('Dinner')");
    var kind_coffee= $(this).parent().parent().find("button:contains('Coffee')");
    var kind = 0;
    if (kind_bfast.hasClass('btn-primary') || kind_bfast.hasClass('btn-danger'))
        kind += 1;
    if (kind_coffee.hasClass('btn-primary') || kind_coffee.hasClass('btn-danger'))
        kind += 8;
    if (kind_lunch.hasClass('btn-primary') || kind_lunch.hasClass('btn-danger'))
        kind += 2;
    if (kind_dinner.hasClass('btn-primary') || kind_dinner.hasClass('btn-danger'))
      kind += 4;
    var quick = $(this).parent().parent().find("button:contains('Quick')");
    var relaxed = $(this).parent().parent().find("button:contains('Relaxed')");
    var fancy = $(this).parent().parent().find("button:contains('Fancy')");
    var style=0;
    if (quick.hasClass('btn-primary')||quick.hasClass('btn-danger'))
        style = 1;
    if (relaxed.hasClass('btn-primary')||relaxed.hasClass('btn-danger'))
        style = 2;
    if (fancy.hasClass('btn-primary')||fancy.hasClass('btn-danger'))
        style = 3;
    var cuisine =  $(this).parent().parent().find("option:selected").text();
    if (!cuisine)
        cuisine = $(this).parent().parent().find(".cuisine-btn").text();

    $.ajax({
        url:'/admin/update_vote',
        method:'POST',
        data:{
            'vote_key': voteKey,
            'item_key': placeKey,
            'kind':kind,
            'style':style,
            'cuisine': cuisine
        },
        success:function(d){
            alert('Done')
        },
        error:function(jqXHR, textStatus, errorThrown){
            if (jqXHR.status = 200){
                alert ("Done");
                return;
            }
            alert('Failed - see server logs');
            console.error('update_vote: '+
                jqXHR+', '+
                textStatus+', '+
                errorThrown);
        },
        dataType: "json"
    });
    return false;
};

Admin.expand_all = function(){
    $(".collapse").collapse('show');
};

Admin.collapse_all = function(){
    $(".collapse").collapse('hide');
};

Admin.toggle_kind = function(){
    if ($(this).hasClass('btn-primary')){
        $(this).removeClass('btn-primary');
        $(this).addClass('btn-inverse');
        return;
    }
    if ($(this).hasClass('btn-default')){
        $(this).removeClass('btn-default');
        $(this).addClass('btn-danger');
        return;
    }
    if ($(this).hasClass('btn-danger')){
        $(this).removeClass('btn-danger');
        $(this).addClass('btn-default');
        return;
    }
    if ($(this).hasClass('btn-inverse')){
        $(this).removeClass('btn-inverse');
        $(this).addClass('btn-primary');
    }
};
Admin.toggle_style = function(){
    $(this).parent().find('.btn-primary').addClass('btn-inverse').removeClass('btn-primary');
    $(this).addClass('btn-danger');
};



$(function(){
    Admin.GetCuisines();
    $("#admin-send").click(Admin.send);
    $("#admin-photos").click(Admin.updatePhotos);
    $("#admin-clean-votes").click(Admin.cleanup_after_delete);
    $("#admin-expand-all").click(Admin.expand_all);
    $("#admin-collapse-all").click(Admin.collapse_all);
    $(".vote-save-btn").click(Admin.update_vote);
    $(".btn-style").click(Admin.toggle_style);
    $(".btn-kind").click(Admin.toggle_kind);
    $(".cuisine-btn").click(Admin.CreateCuisinePicker);
})
