/**
 * Created by Will on 03/10/2014.
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
}

$(function(){
    $("#admin-send").click(Admin.send);
    $("#admin-photos").click(Admin.updatePhotos);
    $("#admin-clean-votes").click(Admin.cleanup_after_delete);
})
