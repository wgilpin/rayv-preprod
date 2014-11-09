/**
 * Created by Will on 07/11/14.
 */

var templates = templates || {
    template_list: {},
    load: function (templ_name) {
        $.get(
                'static/templates/' + templ_name + '.htt',
            null,
            function (data) {
                templates.template_list[templ_name] = data;
            }
        )
    },
    render: function (templ_name, context) {
        if (templ_name in templates.template_list) {
            return Mark.up(templates.template_list[templ_name], context);
        }
        else {
            console.error('no template ' + templ_name);
        }
    }
};

$(function () {

    // load templates
    templates.load('item-votes-list');
    templates.load('friend-comment-template');
    templates.load('add-search-nearby-template');
    templates.load('list-item-template');
    templates.load('new-place-list-js');
    templates.load('list-geo-item-template');

    //add a pipe to markup.js so we can do x-> 100%-x
    Mark.pipes.subFrom = function (a, b) {
        try {
            return parseInt(b, 10) - parseInt(a, 10);
        }
        catch (e) {
            return 0;
        }
    };


    //add a pipe to markup.js to show x if x>y
    Mark.pipes.above = function (a, b) {
        try {
            if (parseInt(a, 10) > parseInt(b, 10))
                return a;
            else
                return "";
        }
        catch (e) {
            return "";
        }
    };
});