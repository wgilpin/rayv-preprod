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
}

$(function(){
    $("#admin-send").click(Admin.send);
    $("#admin-photos").click(Admin.updatePhotos);
})
