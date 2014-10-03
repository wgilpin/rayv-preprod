var currentItem = {
    address: "",
    lat: 0.0,
    lng: 0.0,
    place_name: "",
    descr: "",
    category: "",
    key: "",
    vote: 0,
    mine: "",
    img: null,
    rotation: 0,
    isFromMap: false,
    loadFromKey: function (key) {
        if (!key) {
            key = this.key;
        }
        if (key) {
            this._innerLoad(UserData.places[key], false);
        }
    },
    _innerLoad: function (data, is_json) {
        var obj = is_json ? jQuery.parseJSON(data) : data;
        this.address = obj.address;
        console.assert(this.address != null);
        console.assert(this.address != "null");
        this.place_name = obj.place_name;
        this.category = obj.category;
        console.log("_innerLoad: " + obj.category);
        this.descr = obj.descr;
        this.telephone = obj.telephone;
        this.lat = obj.lat;
        this.lng = obj.lng;
        this.key = obj.key;
        this.mine = obj.mine;
        this.img = obj.img;
        this.vote = obj.vote;
        this.distance = obj.distance;
        this.rotation = 0;
        this.isFromMap = false;
        this.untried = obj.untried;
    },
    clear: function () {
        this.address = "";
        this.place_name = "";
        this.category = "";
        this.descr = "";
        this.lat = "";
        this.lng = "";
        this.key = null;
        this.mine = "";
        this.img = "";
        this.vote = "";
        this.distance = "";
        this.rotation = "";
        this.isFromMap = true;
    }
};

//todo: put this in local storage
var UserData = {
    my_id: 0,
    places: {},
    friends: {},
    updatePlaceCache: function (obj) {
        // only adds - no deletion here (as we don't ref count)
        for (var place_idx in obj.places) {
            if (!(obj.places[place_idx].key in this.places)) {
                // dict indexed by place key
                this.places[obj.places[place_idx].key] = obj.places[place_idx]
            }
        }
    },
    load: function (callback) {
        //get All user data from the server
        var request = {};
        if (!BB.splash) {
            $("#list-loading").show();
        }
        $.get("/getFullUserRecord",
            request,
            function (data) {
                //populate the list
                var obj = $.parseJSON(data);
                UserData.my_id = obj.id;
                // first one is me
                UserData.myBook = obj.friendsData[0];
                delete UserData.places;
                UserData.places = {};
                UserData.updatePlaceCache(obj);
                delete UserData.friends;
                UserData.friends = {};
                var skippedFirstAsThatOneIsMe = false;
                for (var frIdx in obj.friendsData) {
                    if (skippedFirstAsThatOneIsMe) {
                        // dictionary indexed by user id
                        UserData.friends[obj.friendsData[frIdx].id] = obj.friendsData[frIdx];
                    }
                    else {
                        skippedFirstAsThatOneIsMe = true;
                    }
                }
                callback();
            });
    },
    getThumbs: function (listULId) {
        //load, cache & display the thumbs for the current list, async
        $(listULId).find("li").each(function () {
            var key = $(this).find('a').data('key');                    // get the data-key from the <a>
            var place = UserData.places[key];                            // lookup the place for that key
            if (place.imageData) {                                     // if no cached image
                $(this).find(".item-img-container").html(place.imageData);            // replace the existing image with cached one
            }
            else {
                var imgUrl = place['thumbnail'];                        //      get the image URL
                if (imgUrl == "") {                                     //      blank means no thumb
                    $(this).find(".item-pic").attr("src", "");             //      no image
                }
                else {
                    //todo: create the cached image
                    var imgCache = $("<img>");
                    imgCache.attr("src", imgUrl);         //      create img, load from URL
                    imgCache.addClass('item-pic');                      //      class for w x h
                    place.imageData = imgCache;                         //      cache it
                    //todo: load the cached image into the dom
                    $(this).find(".item-img-container").html(imgCache);           // replace the existing image
                }
            }
        });
    },

    get_most_relevant_comment: function (key) {
        // my comment, else a friend's
        if (this.myBook.votes[key]) {
            return this.myBook.votes[key].comment
        }
        //not in my list
        for (var frIdx in this.friends) {
            if (this.friends[frIdx].votes[key]) {
                return this.friends[frIdx].votes[key].comment
            }
        }
        return "";
    },

    get_my_comment: function (key) {
        // my comment,
        if (this.myBook.votes[key]) {
            return this.myBook.votes[key].comment
        }
        return "";
    },

    get_votes_for_item: function (key) {
        var result = [];
        for (var frIdx in this.friends) {
            var vote = {name: this.friends[frIdx].name};
            if (this.friends[frIdx].votes[key]) {
                vote.vote = this.friends[frIdx].votes[key];
                result.push(vote);
            }
        }
        return result;
    }
};

var BB = {
        isOnline: true,
        list_item_template: null,
        item_votes_template: null,
        friend_comment_template: null,
        add_search_nearby_template: null,
        //global timestamp = time of next list load - initially one minute ago
        nextListLoad: null,
        mapInfoWindows: [],
        mapMarkers: [],
        creatorMapMarker: null,
        marker: null,
        navBarActive: false,
        // lastPosition is a navigator.geolocation.getCurrentPosition object
//      -.coords {latitude, longitude }
//      -.timestamp
        lastGPSPosition: {"latitude": 0,
            "longitude": 0,
            "isSet": false,
            "zoomIn": false},
        // map_centred set if blue home button pressed, reset if dragged
        map_centred: false,
        lastGPSTime: 0,
        lastMapPosition: {"latitude": 0,
            "longitude": 0,
            "isSet": false,
            "zoomIn": false},
        theMap: null,
        creatorMap: null,
        geocoder: null,
        iconPath: "/static/images/",
        filter: "mine",
        use_test_location: false,
        test_lat: null,
        test_lng: null,
        imageRotation: 0,
        watchPositionOptions: {
            enableHighAccuracy: true,
            maximumAge: 30000 //30 seconds
        },
        map_center: function () {
            var last = BB.googleFormatPosition(BB.lastGPSPosition);
            BB.theMap.setCenter(last);
            BB.dragMap();
            BB.map_centred = true;
        },
        map_init: function () {
            //map
            var mapOptions = {
                zoom: 14,
                center: new google.maps.LatLng(-34.397, 150.644)
            };
            BB.theMap = new google.maps.Map(document.getElementById('map-div'),
                mapOptions);
            google.maps.event.addListener(BB.theMap, 'dragend', BB.dragMap);
            // Create a div to hold the control.
            var controlDiv = document.createElement('div');

            // Set CSS styles for the DIV containing the control
            // Setting padding to 5 px will offset the control
            // from the edge of the map.
            controlDiv.style.padding = '5px';

            // Set CSS for the control border.
            var controlUI = document.createElement('div');
            //controlUI.style.backgroundColor = 'white';
            controlUI.style.borderStyle = 'none';
            //controlUI.style.borderWidth = '2px';
            controlUI.style.cursor = 'pointer';
            controlUI.style.padding = '5px';
            //controlUI.style.textAlign = 'center';
            controlUI.title = 'Click to set the map to Home';
            controlDiv.appendChild(controlUI);

            // Set CSS for the control interior.
            var controlImg = document.createElement('img');
            controlImg.setAttribute("src", "/static/images/centre-button.png");
            controlUI.appendChild(controlImg);
            google.maps.event.addDomListener(controlUI, 'click', BB.map_center);
            BB.theMap.controls[google.maps.ControlPosition.LEFT_CENTER].push(controlUI);
        },
        init: function () {
            this.splash = true;
            $("#list-loading").hide();
            this.geocoder = new google.maps.Geocoder();
            BB.map_init();

        },

//every server call, we look for dirty data and append it if needed
        check_for_dirty_data: function (obj) {
            if (obj) {
                if ("dirty_list" in obj) {
                    for (var frIdx in obj.dirty_list.friends) {
                        //these friends are dirty
                        UserData.friends[obj.dirty_list.friends[frIdx].id] = obj.dirty_list.friends[frIdx];
                    }
                    for (var plIdx in obj.dirty_list.places) {
                        //these places are dirty
                        UserData.places[obj.dirty_list.places[plIdx].key] = obj.dirty_list.places[plIdx];
                    }
                }

            }
        },

        pretty_dist: function (dist) {
            if (dist >= 1.0) {
                return dist.toFixed(1) + " miles";
            }
            var yds = Math.floor(dist * 90) * 20;
            return yds + " yds";
        },

        approx_distance: function (point, origin) {
            //based on 1/60 rule
            //delta lat. Degrees * 69 (miles)
            var p_lat , p_lng;
            try {
                p_lat = point.lat;
                p_lng = point.lng;
            }
            catch (e) {
                p_lat = point["lat"];
                p_lng = point["lng"];
            }
            var d_lat = (origin.latitude - p_lat) * 69;
            //cos(lat) approx by 1/60
            var cos_lat = Math.min(1, (90 - p_lat) / 60);
            //delta lng = degrees * cos(lat) *69 miles
            var d_lng = (origin.longitude - p_lng) * 69 * cos_lat;
            return Math.sqrt(d_lat * d_lat + d_lng * d_lng);
        },

        log: function (msg) {
            try {
                console.log(msg + " / map lat :" + BB.theMap.getCenter().lat());
            }
            catch (e) {
                console.log(msg);
            }
        },


        updateCurrentItemInCache: function () {
            //we have changed the current item, update the cache
            if (currentItem.key in UserData.places) {
                UserData.places[currentItem.key].address = currentItem.address;
                UserData.places[currentItem.key].category = currentItem.category;
                if ((UserData.places[currentItem.key].img != currentItem.img) ||
                    (UserData.places[currentItem.key].vote != currentItem.vote)) {
                    console.log("Can't update in cache - reload");
                    return false;
                }
                UserData.myBook.votes[currentItem.key].vote = currentItem.vote == 'dislike' ? -1 : 1;
                UserData.myBook.votes[currentItem.key].comment = currentItem.descr;
                console.log("Updated in cache ");
                return true;
            }
            else {
                console.log("New item for cache - reload");
                return false;
            }
        },

        codeLatLng: function () {
            BB.geocoder.geocode({'latLng': BB.creatorMap.getCenter()}, function (results, status) {
                if (status == google.maps.GeocoderStatus.OK) {
                    if (results[1]) {
                        $("#dragged-address").text(results[0].formatted_address);
                        $("#dragged-address").show();
                    }
                } else {
                    console.log("Geocoder failed due to: " + status);
                }
            });
        },
        saveCurrentItem: function () {
            console.log("saveCurrentItem");
            var file = $("#image-input").prop("files")[0];
            // https://github.com/gokercebeci/canvasResize
            function build_form(f) {
                var fd = new FormData();
                if (f) {
                    fd.append("new-photo", f);
                }
                fd.append("new-item-category", currentItem.category);
                fd.append("new-title", currentItem.place_name);
                fd.append("address", currentItem.address);
                fd.append("myComment", currentItem.descr);
                fd.append("latitude", currentItem.lat);
                fd.append("longitude", currentItem.lng);
                fd.append("voteScore", currentItem.vote);
                fd.append("untried", 'untried' in currentItem ? currentItem.untried : false);
                fd.append("rotation", currentItem.rotation);
                fd.append("key", currentItem.key);
                return fd;
            }

            function saveMultiPart() {
                var _URL;
                console.log("With file");
                currentItem.img = true; // to trigger a reload, make it different
                // if a file is present
                //     resize it
                //     multipart form with image upload
                var img = new Image();
                //_URL = window.URL || window.webkitURL;
                img.onload = function () {
                    canvasResize(file, {
                        width: 288,
                        height: 0,
                        crop: false,
                        quality: 80,
                        callback: function (data, width, height) {
                            // Create a new form-data
                            // Add file data
                            var f = canvasResize('dataURLtoBlob', data);
                            f.name = file.name;
                            var fd = build_form(f);
                            var xhr = new XMLHttpRequest();
                            xhr.open('POST', '/item', true);
                            xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
                            xhr.setRequestHeader("pragma", "no-cache");
                            // File uploaded
                            xhr.addEventListener("load", function () {
                                // clear the form as per #86
                                $('#new-shout-form')[0].reset();
                                $.mobile.changePage("#list-page");
                                if (BB.updateCurrentItemInCache()) {
                                    BB.populateMainList("");
                                }
                                else {
                                    BB.loadUserData();
                                }
                            });
                            // Send data
                            xhr.send(fd);
                        }

                    });
                };
                _URL = window.URL || window.webkitURL;
                img.src = _URL.createObjectURL(file);
            }

            function saveSinglePart() {
                // no photo attached
                // simple post, no upload
                $.ajax({
                    url: '/item',
                    data: build_form(null),
                    cache: false,
                    contentType: false,
                    processData: false,
                    type: 'POST',
                    success: function () {
                        $.mobile.changePage("#list-page");
                        if (BB.updateCurrentItemInCache()) {
                            BB.populateMainList("");
                        }
                        else {
                            BB.loadUserData();
                        }
                    }
                });
                console.log("AJAX saveCurrentItem");
            }

            if (file) {
                saveMultiPart();
            }
            else {
                saveSinglePart();
            }
        },

        SaveItemAtPos: function (position) {
            console.log("SaveItemAtPos");
            currentItem.lat = position.coords.latitude;
            currentItem.lng = position.coords.longitude;
            this.saveCurrentItem();
        },


        clearMapMarkers: function () {
            //todo: markers?
            if (this.marker) {
                this.marker.setMap(null);
            }
            for (var mIdx in BB.mapMarkers) {
                BB.mapMarkers[mIdx].setMap(null);
            }
            BB.mapMarkers = [];

            /*for (var j in this.mapInfoWindows) {
             this.mapInfoWindows[j].setMap(null);
             this.mapInfoWindows = [];
             }*/
        },

//todo: is this the right name?
        loadMapItemForEdit: function (place_name, lat, lng) {
            $('#new-item-votes li').removeClass('ui-btn-hover-b').addClass('ui-btn-up-b').removeClass('ui-btn-active');
            $('#new-item-like').addClass('ui-btn-active');
            $("#new-category>option").removeAttr('selected');
            $("#new-title-hdg").text(place_name);
            $("input[name=new-title]").val(place_name);
            $("#new-text").val("");
            currentItem.isFromMap = true;
            var pos = {"coords": ""};
            pos.coords = {"latitude": lat, "longitude": lng};
            this.SaveItemAtPos(pos)
        },

        format: function () {
            var s = arguments[0];
            for (var i = 0; i < arguments.length - 1; i++) {
                var reg = new RegExp("\\{" + i + "\\}", "gm");
                s = s.replace(reg, arguments[i + 1]);
            }

            return s;
        },

        setupList: function (UIlist) {
            console.log('setupList');
            var LIPrototype = "<li data-theme='c' data-icon='false'><a style='background-color:white;' onclick='";

            $(UIlist).find('li').remove();
            if (this.isMapPage()) {
                this.clearMapMarkers();
            }
            var placeList = [];
            for (var it in UserData.myBook.votes) {
                if ((BB.filter != 'untried') || (BB.filter == 'untried' && UserData.myBook.votes[it].untried))
                    placeList.push(it);
            }
            if (BB.filter == "all") {
                //add the other lists
                for (var friend in UserData.friends) {
                    for (it in UserData.friends[friend].votes) {
                        if (placeList.indexOf(it) == -1) {
                            placeList.push(it)
                        }
                    }
                }
            }
            var detailList = [];
            for (var geoPtIdx in placeList) {
                var geoPt = UserData.places[placeList[geoPtIdx]];
                detailList.push(geoPt);
            }

            function compare_by_distance(a, b) {
                if (a.dist_float < b.dist_float)
                    return -1;
                if (a.dist_float > b.dist_float)
                    return 1;
                return 0;
            }

            function compare_by_map_distance(a, b) {
                if (a.map_dist_float < b.map_dist_float)
                    return -1;
                if (a.map_dist_float > b.map_dist_float)
                    return 1;
                return 0;
            }

            if (BB.isMapPage()) {
                detailList.sort(compare_by_map_distance);
                console.log("list sorted by map distance")
            }
            else {
                detailList.sort(compare_by_distance);
                console.log("list sorted by gps distance")
            }


            function inner_setup_list() {
                console.log("inner_setup_list");
                // marker for us
                this.marker = new google.maps.Marker({
                    position: BB.googleFormatPosition(BB.lastGPSPosition),
                    map: BB.theMap,
                    icon: BB.iconPath + "blue_dot.png"
                    //infoWindowIndex: geoPtIdx
                });
                BB.mapMarkers.push(this.marker);
                for (var geoPtIdx  in detailList) {
                    var geoPt = detailList[geoPtIdx],
                        newListItem,
                        click_fn,
                        newListItemEnd;
                    if (geoPt.is_map) {
                        // it's a google place result - place_name, lat, long
                        click_fn = BB.format("javascript:loadMapItemForEdit('{0}','{1}','{2}');", geoPt.place_name, geoPt.lat, geoPt.lng);
                        newListItemEnd = click_fn + "' href='\#new-detail' data-transition='slide'>" + geoPt.place_name + " [" + geoPt.distance + "]</a></li>";
                        newListItem = LIPrototype + newListItemEnd;
                    }
                    else {
                        // it's a db item

                        var context = { pt: geoPt, isMap: BB.isMapPage() };
                        if (geoPtIdx < 6 && BB.isMapPage()) {
                            context.icon = Number(geoPtIdx) + 1;
                        }
                        // https://github.com/adammark/Markup.js/
                        newListItem = Mark.up(BB.list_item_template, context);
                    }
                    UIlist.append(newListItem);

                    //todo: infoWindow?
                    if (BB.isMapPage() && (geoPtIdx < 7)) {
                        var n = Number(geoPtIdx) + 1;
                        this.marker = new google.maps.Marker({
                            position: new google.maps.LatLng(geoPt.lat, geoPt.lng),
                            map: BB.theMap,
                            title: geoPt.place_name,
                            icon: BB.iconPath + n + ".png",
                            key: geoPt.key
                        });
                        BB.mapMarkers.push(this.marker);
                        google.maps.event.addListener(marker, 'click',
                            function () {
                                if (this.key) {
                                    currentItem.loadFromKey(this.key);
                                    BB.showAnotherItemOnMap();
                                }
                            }
                        );
                        /*var infoWindow = new google.maps.InfoWindow({
                         content: geoPt.title
                         });
                         BB.mapInfoWindows.push(infoWindow);*/
                    }
                }
                $(UIlist).find("A").on("click", BB.ItemLoadPage);
                //FLIGHT
                // Get cached thumbs
                UserData.getThumbs(UIlist);
                try {
                    $(UIlist).find('div[data-role=collapsible]').collapsible();
                    try {
                        UIlist.listview().listview('refresh');
                        UIlist.trigger('updatelayout');
                    } catch (e) {
                    }
                }
                catch (e) {
                    BB.log(e);
                }
                return UIlist;
            }

            if (BB.list_item_template == null) {
                //load from file
                $.get(
                    'static/templates/list-item-template.htt',
                    null,
                    function (data) {
                        BB.list_item_template = data;

                        return inner_setup_list();
                    }
                )
            }

            else {
                return inner_setup_list();
            }
        },

        isMapPage: function () {
            try {
                return $.mobile.activePage.attr("id") == "map-page";
            }
            catch (e) {
                return false
            }
        },


//Load Data


        populateMainListError: function (data) {
            console.log("populateMainListError");
            if (data.status == 401) {
                $.mobile.changePage("#login-page");
            }
            $("#new-place-list-loading").hide();
            $("#map-list-loading").hide();
            BB.navBarEnable();
            $("#splash").hide();
        },

        populateMainList: function () {
            console.log("populateMainList");
            // if lat=0 & long=0 then we will use the map position, else GPS
            if (!BB.splash) {
                $("#list-loading").show();
            }
            BB.navBarDisable();
            var last = null;
            if (BB.lastMapPosition)
                if (BB.lastMapPosition.isSet) {
                    last = BB.googleFormatPosition(BB.lastMapPosition);
                    console.log("populateMainListSuccess set map to last map position, lat: " + last.lat());
                }
            if (!last) {
                last = BB.googleFormatPosition(BB.lastGPSPosition);
                console.log("populateMainListSuccess set map to last GPS position, lat: " + last.lat());
            }
            BB.theMap.setCenter(last);

            // update points with distance
            var map_centre = {"latitude": BB.theMap.getCenter().lat(),
                "longitude": BB.theMap.getCenter().lng() };
            console.log("distances from Map: " + map_centre.latitude + ", " + map_centre.longitude);
            for (var pt in UserData.places) {
                var place = UserData.places[pt];
                var dist = BB.approx_distance(place, BB.lastGPSPosition);
                place.distance = BB.pretty_dist(dist);
                place.dist_float = dist;
                var map_centre_dist = BB.approx_distance(place, map_centre);
                place.map_dist_float = map_centre_dist;
                place.map_distance = BB.pretty_dist(map_centre_dist);
            }
            BB.navBarEnable();

            if (BB.isMapPage()) {

                console.log("populateMainListSuccess set");
                BB.setupList($("#map-list"));
                $("#map-list-loading").hide();
            }
            else {
                $("#main-search").val("");
                BB.setupList($("#main-list"));
                $("#list-loading").hide();
            }
            $("#splash").hide();
            BB.splash = false;
            try {
                $('div[data-role=listview]').listview().listview('refresh').trigger('updatelayout');
            } catch (e) {
            }

        },

        new_places_list_click: function (event) {
            console.log("new_places_list_click");
            //user clicked on a place (or db entry) in the new Shout page
            if ($(this).data("shoutIsMap")) {
                // it's a map item
                //copy the text from the <a> tag to the text box on the New Item page
                var text = $(this).find(".list-item-title").text().trim();
                $("#new-detail-name").val(text);
                $("input[name=new-title]").val(text);
                $("#new-name").val(text);
                currentItem.place_name = text;
                currentItem.address = $(this).data("address");
                currentItem.descr = "";

                currentItem.category = $(this).data("category");
                $("#new-detail-address").val(currentItem.address);
                $("#new-detail-comment").val("");   // no comment as it's not in db
                $("#cat-lookup input").val(currentItem.category);
                currentItem.key = $(this).data("shoutKey");
                currentItem.lat = $(this).data("lat");
                currentItem.lng = $(this).data("lng");
                currentItem.isFromMap = true;

            }
            else {
                //new place from scratch
                var place = $("#new-place-name-box").val();
                if (place.length < 2) {
                    alert("You need to enter a name");
                    event.preventDefault();
                    return false;
                }
                else {
                    currentItem.isFromMap = false;
                    $("#new-title-hdg").text($("#new-place-name-box").val());
                    currentItem.place_name = $("#new-place-name-box").val();
                    $("input[name=new-title]").val(currentItem.place_name);
                    currentItem.key = "";
                    //TODO: What does it mean when the lat and long is zero?

                    //todo: what's the address?
                    currentItem.address = "";
                    $("#new-category>option").removeAttr('selected');
                    $("#new-category>option:contains('" + $("#selectmenu2").val() + "')").attr("selected", true);
                    $("#new-name").val(place);
                }
                $.mobile.changePage("#new-page");
            }
            // go to the page
        },

        loadPlacesListSuccessHandler: function (data) {
            console.log("loadPlacesListSuccessHandler");
            BB.navBarEnable();
            $("#new-place-list").html(data);
            $("#new-place-list").trigger("create");
            $("#new-place-list ul a").on("click", BB.new_places_list_click);
            $("#new-place-list-loading").hide();
        },


        navBarDisable: function () {
            BB.navBarActive = false;
        },

        navBarEnable: function () {
            BB.navBarActive = true;
        },

        loadLocalPlaces: function (search_text) {
            // this is for the "new place" page list -
            //  from google maps and from my db
            console.log("loadLocalPlaces");
            var request = {};
            $("#new-place-list-loading").show();
            console.log("AJAX gotPositionForPlaces");
            BB.navBarDisable();
            request.lat = BB.lastGPSPosition.latitude;
            request.lng = BB.lastGPSPosition.longitude;
            request.text = search_text;
            $.ajax({
                url: "/getMapList_Ajax",
                type: "GET",
                data: request,
                handleAs: "json",
                success: BB.loadPlacesListSuccessHandler,
                error: BB.populateMainListError
            });
        },


        new_item_save_click: function () {
            // save a new item
            //called from new-detail-page
            console.log("new_item_save_click");

            //currentItem.descr = $("#new-detail-comment").val();
            currentItem.category = $("#new-category").val();
            if (currentItem.category === "None" || currentItem.category == null || currentItem.category.length == 0) {
                alert("You must pick a type of cuisine");
                return;
            }
            currentItem.address = $("#new-detail-address").val();
            currentItem.place_name = $("#new-detail-name").val();
            currentItem.descr = $("#new-detail-comment").val();
            currentItem.vote = 1;
            currentItem.untried = false;
            var hasVote = false;
            if ($('#new-item-dislike').hasClass('ui-btn-active')) {
                currentItem.vote = -1;
                currentItem.untried = false;
                hasVote = true;
            }
            if ($('#new-item-untried').hasClass('ui-btn-active')) {
                currentItem.untried = true;
                currentItem.vote = 0;
                hasVote = true;
            }
            if ($('#new-item-like').hasClass('ui-btn-active')) {
                hasVote = true;
            }
            if (!hasVote) {
                alert('Please vote!');
                return;
            }
            if (currentItem.key == "") {
                //from map or db, use supplied pos
                var pos = {"coords": 0};
                pos.coords = {"latitude": currentItem.lat,
                    "longitude": currentItem.lng};
                BB.SaveItemAtPos(pos);
            }
            else {
                BB.saveCurrentItem();
            }
            return;
        },

        googleFormatPosition: function (pos) {
            return new google.maps.LatLng(pos.latitude, pos.longitude)
        },


//load the votes from friends into the UL
        loadVotes: function () {
            /**
             * load the list of votes for an item
             */
            //todo: use a template
            if (this.item_votes_template == null) {
                //load from file
                $.get(
                    'static/templates/item-votes-list.htt',
                    null,
                    function (data) {
                        BB.item_votes_template = data;
                        BB.loadVotesInner();
                    }
                )
            }
            else {
                this.loadVotesInner()
            }
        },
        loadVotesInner: function () {
            var votes = [];
            for (var frIdx in UserData.friends) {
                for (var voteIdx in UserData.friends[frIdx].votes) {
                    var vote = UserData.friends[frIdx].votes[voteIdx];
                    if (vote == currentItem.key) {
                        vote.userName = UserData.friends[frIdx].name;
                        votes.push(vote)
                    }
                }
            }
            var context = { votes: votes };
            // https://github.com/adammark/Markup.js/
            var newVoteList = Mark.up(this.item_votes_template, context);
            $("#item-votes-list-container").html(newVoteList);
            $("#item-votes").trigger("create");
            $("#item-votes-collapsible").show();
        },

        updateitem: function () {
            console.log("updateitem");
            currentItem.descr = $("#item-descr").val();
            currentItem.vote = 1;
            currentItem.untried = false;
            if ($('#item-dislike').hasClass('ui-btn-active')) {
                currentItem.vote = -1;
            }
            else if ($('#item-untried').hasClass('ui-btn-active')) {
                currentItem.untried = true;
                currentItem.vote = 0;
            }
            BB.saveCurrentItem();
        },

        /**
         * on change event for the new place lookup
         */
        place_search_by_name: function () {
            // hide all items
            // now show those containing our text
            var search_for = $("#new-place-name-box").val();
            if (search_for.length > 0) {
                $("#new-place-list>ul>li").hide();
                $("#new-place-list>ul>li:" + "contains('Add New')").show();
                $('#new-place-list>ul>li:contains("' + search_for + '")').show();
            }
            else {
                $("#new-place-list>ul>li").show();
            }
        },

        /**
         * on change event for the new place lookup
         */
        list_text_filter: function () {
            // hide all items
            // now show those containing our text
            var search_for = $("#main-search").val();
            if (search_for.length > 0) {
                $("#main-list>li").hide();
                $('#main-list>li:contains("' + search_for + '")').show();
            }
            else {
                $("#main-list>li").show();
            }
        },

        /**
         * copy details from the Item page to the New Item age to edit them
         */
        item_load_for_edit: function () {
            // copy over the vals from the item page
            //todo: check for new Item path
            console.log("cat: " + $("#item-category").val());
            currentItem.loadFromKey();
            if (currentItem.key in UserData.myBook.votes) {
                $("#new-item-delete").show();
            }
            else {
                $("#new-item-delete").hide();
            }
            $("#new-detail-name").val(currentItem.place_name);
            $("#new-detail-address").val(currentItem.address);
            $("#new-category>option").removeAttr('selected');
            try {
                $("#new-category>option:contains('" + currentItem.category + "')").attr("selected", true);
                $("#new-category").val(currentItem.category);
                $("#new-category").selectmenu("refresh", true);
            }
            catch (e) {
                $("#new-category").val("");
            }
            $("#new-detail-comment").val(UserData.get_most_relevant_comment(currentItem.key));

            //set the likes radio
            if (currentItem.untried) {
                $('#new-item-votes li').removeClass('ui-btn-hover-b').addClass('ui-btn-up-b').removeClass('ui-btn-active');
                $('#new-item-untried').addClass('ui-btn-active');
            }
            else {
                if (currentItem.vote >= 0) {
                    $('#new-item-votes li').removeClass('ui-btn-hover-b').addClass('ui-btn-up-b').removeClass('ui-btn-active');
                    $('#new-item-like').addClass('ui-btn-active');
                }
                else {
                    $('#new-item-votes li').removeClass('ui-btn-hover-b').addClass('ui-btn-up-b').removeClass('ui-btn-active');
                    $('#new-item-dislike').addClass('ui-btn-active');
                }
            }
            $("#new-preview-box>div>img").removeClass("rotr").removeClass("rotu").removeClass("rotl");
            BB.imageRotation = 0;
            if (currentItem.img) {
                console.log("Show item image");
                $("#new-preview-box").show();
                $("#new-img>img").attr("src", currentItem.img);
                $("#new-img>img").attr("style", "");
            }
            else {
                $("#new-preview-box").hide();
            }
        },

        /*validate_vote_comment: function () {
         if ($("#item-vote-comment").val().length == 0) {
         return confirm("Vote without commenting?");
         }
         else {
         return true;
         }
         },*/

// map-search key press event
        map_search_key: function (e) {
            if ($("#map-search").val().length == 0) {
                $("#googlemapsjs1").show();
                $("#map-search-btn-box").hide();
            } else
                $("#map-search-btn-box").show();
            // if it's return do the search
            if (e.which == 13 || (e.which == 8 && $("#map-search").val().length == 0 )) {
                console.log("map_search_key: 13");
                $("#googlemapsjs1").hide();
                //hide keyboard
                document.activeElement.blur();
                $("#map-search-btn").hide();
                $("input").blur();
                //load results
                this.populateMainList($("#map-search").val());
                $("#map-list-loading").show();
            }
        },


        showItemOnMap: function () {
            //show the map page, centered on the current item
            BB.lastMapPosition.latitude = currentItem.lat;
            BB.lastMapPosition.longitude = currentItem.lng;
            //BB.clearMapMarkers();
            /*var pos = new google.maps.LatLng(currentItem.lat, currentItem.lng);
             BB.marker = new google.maps.Marker({
             position: pos,
             map: BB.theMap,
             title: currentItem.place_name
             });
             BB.marker.setMap(BB.theMap);*/
            google.maps.event.trigger(BB.theMap, 'resize');
            BB.lastMapPosition.isSet = true;
            BB.lastMapPosition.zoomIn = true;
            $.mobile.changePage("#map-page");
        },
        showAnotherItemOnMap: function () {
            // centered on the current item
            BB.lastMapPosition.latitude = currentItem.lat;
            BB.lastMapPosition.longitude = currentItem.lng;
            BB.populateMainList("");
            BB.lastMapPosition.isSet = true;
            BB.lastMapPosition.zoomIn = false;
            BB.pageToMap();
        },
        dragMap: function () {
            // centered on the map
            BB.lastMapPosition.latitude = BB.theMap.getCenter().lat();
            BB.lastMapPosition.longitude = BB.theMap.getCenter().lng();
            BB.populateMainList("");
            BB.lastMapPosition.isSet = true;
            BB.lastMapPosition.zoomIn = false;
            BB.map_centred = false;
            BB.pageToMap();
        },

        imageRotate: function (e) {
            e.preventDefault();
            BB.imageRotation = (BB.imageRotation + 1) % 4;
            switch (BB.imageRotation) {
                case 0:
                    //original
                    $("#new-preview-box>div>img").removeClass("rotr").removeClass("rotu").removeClass("rotl");
                    currentItem.rotation = 0;
                    break;
                case 1:
                    //right
                    $("#new-preview-box>div>img").removeClass("rotl").removeClass("rotu").addClass("rotr");
                    currentItem.rotation = 1;
                    break;
                case 2:
                    // invert
                    $("#new-preview-box>div>img").removeClass("rotl").removeClass("rotr").addClass("rotu");
                    currentItem.rotation = -2;
                    break;

                case 3:
                    //left
                    $("#new-preview-box>div>img").removeClass("rotr").removeClass("rotu").addClass("rotl");
                    currentItem.rotation = -1;
                    break;

            }
        },


        imageSaveClick: function () {
            $("input[name=image-id]").val(currentItem.key);
            if ($("#image-img>img").hasClass("rotl"))
                $("input[name=image-rotate]").val(-1);
            else
                $("input[name=image-rotate]").val(1);

            $("#image-working").show();
            console.log("imageSaveClick");
            $("#image-form").submit();
        },

        pageToList: function (event) {
            console.log("PAGE list");

            if (this.navBarActive) {

                BB.populateMainList("");
                $("#list-loading").hide();
            }
            else
                event.preventDefault();
        },

        imagePreview: function () {
            var oFReader = new FileReader();
            try {
                oFReader.readAsDataURL(this.files[0]);
            }
            catch (e) {
                $('#image-dialog').popup('close')
            }
            console.log(this.files[0]);
            oFReader.onload = function (oFREvent) {
                $("#new-preview-box>div>img").html('<img height="150" id="new-image" data-inline="true" src="' + oFREvent.target.result + '">');
                $('#new-preview-box').show();
                $("#new-preview-box>div>img").attr('src', oFREvent.target.result);
                $("#item-img").show();
                try {
                    $('#image-dialog').popup('close')
                } catch (e) {
                }
            };

        },


        pageToMap: function () {
            console.log("PAGE map");
            if (this.navBarActive) {
                $("#map-list-loading").show();
                $("#map-search-btn").hide();
                $("#map-search").val("");
                var last;
                if (this.lastMapPosition.isSet) {
                    last = this.googleFormatPosition(this.lastMapPosition);
                    console.log("set map to last position, lat: " + last.lat());
                    try {
                        this.theMap.setCenter(last);
                        this.map_centred = false;
                        console.log("set map (1) to last position, lat: " + last.lat());
                        if (this.lastMapPosition.zoomIn) {
                            this.theMap.setZoom(18);
                            this.lastMapPosition.zoomIn = false;
                        }
                    }
                    catch (e) {
                        console.log("MAIN MAP NOT SET")
                    }
                } else {
                    last = this.googleFormatPosition(this.lastGPSPosition);
                    console.log("set map (2) to last position, lat: " + last.lat());
                    try {
                        this.theMap.setCenter(last);
                        if (this.lastMapPosition.zoomIn) {
                            this.theMap.setZoom(18);
                            this.lastMapPosition.zoomIn = false;
                        }
                    }
                    catch (e) {
                        console.log("MAIN MAP NOT SET")
                    }
                }
                /*BB.marker = new google.maps.Marker({
                 position: last,
                 map: BB.theMap,
                 title: 'Hello World!'
                 });*/
                google.maps.event.trigger(BB.theMap, 'resize');
                this.populateMainList("");
            }
            else
                event.preventDefault();
        },

        pageToNewPlace: function (event, previousPage) {
            console.log("PAGE new place");
            if (this.navBarActive) {
                $('#new-preview-box').hide();
                $("#new-place-near").hide();
                $("#new-search-place-btn").hide();
                if (previousPage == "new-detail") {
                    //don't reload
                    console.log("PAGE new place - no reload")
                }
                else {
                    this.loadLocalPlaces(null, false);
                    $("input[name=new-title]").val("");
                }
            }
            else
                event.preventDefault();
        },

        pageToImage: function () {
            $("#image-img>img").attr("src", currentItem.img);
            //$("#image-img>img").attr("style", "");
            $("#image-header").text(currentItem.place_name);
        },

        ItemLoadPage: function () {
            console.log('ItemLoadPage');
            currentItem.key = $(this).data('key');
            $.mobile.changePage("#item-page")
        },

        dragCreatorMap: function () {
            //put & keep marker at centre
            if (BB.creatorMapMarker) {
                BB.creatorMapMarker.setMap(null);
                BB.creatorMapMarker = null;
            }
            BB.creatorMapMarker = new google.maps.Marker({
                position: BB.creatorMap.getCenter(),
                map: BB.creatorMap,
                icon: BB.iconPath + "pointer.png"
                //infoWindowIndex: geoPtIdx
            });
            //lookup nearest address
            BB.codeLatLng();
        },
        pageToCreateAddress: function () {
            //init map
            if (!BB.creatorMap) {
                var mapOptions = {
                    zoom: 15,
                    center: BB.googleFormatPosition(BB.lastGPSPosition)
                };
                BB.creatorMap = new google.maps.Map(document.getElementById('find-on-map-div'),
                    mapOptions);
                google.maps.event.addListener(BB.creatorMap, 'dragend', BB.dragCreatorMap);
            }
            else {
                BB.creatorMap.setCenter(BB.googleFormatPosition(BB.lastGPSPosition))
            }
            $("#create-name").val($("#new-name").val());
            $("#dragged-address").hide();
        },

        clearItemPage: function () {
            $("#item-img>img").attr("src", "");
            $("#item-title").html("Loading");
            $("#item-address").html("");

            $("#item-category").html("Loading");
            $("#item-phone-link").hide();

            $("#item-title-2").html("Loading");
            $("#item-comments").html("None");

            $("#item-distance").html("");

            $("#item-delete").hide();
            $('#item-votes-inner').trigger('collapse').trigger('updatelayout');
            $("#vote-cursor").val("");
            $("#item-votes").html("");
        },

        pageToItem: function (event, previousPage) {
            function pageTo_item_inner() {
                console.log("pageToItem");
                //todo: check for new Item path
                // if we have come from the image page, the image should be shown on the item page too
                if (previousPage == "image-page")
                    $("#item-img").show();
                $("#item-img").show();
                currentItem.loadFromKey();
                $("#item-title").html(currentItem.place_name);
                $("#item-address").html(currentItem.address);

                $("#item-category").html(currentItem.category);
                if (currentItem.telephone) {
                    $("#item-phone-link").attr('href', 'tel:' + currentItem.telephone);
                    $("#item-phone-link").show();
                }
                else {
                    $("#item-phone-link").hide();
                }

                $("#item-title-2").html(currentItem.place_name);
                var comment = UserData.get_my_comment(currentItem.key);
                var comment_header = comment;

                if (comment.length == 0) {
                    comment_header = "Friends' Comments";
                }

                var $btn_text = $("#item-comment-btn a .ui-btn-text");
                var $btn_child = $btn_text.find('.ui-collapsible-heading-status');
                //overwrite the header text, then append its child to restore the previous structure
                $btn_text.text(comment_header).append($btn_child);

                $("#item-descr").val(comment);

                $("#item-comments").html();
                var votes = UserData.get_votes_for_item(currentItem.key);
                var html = "";
                for (var vote in votes) {
                    if (votes[vote].vote.comment.length > 0) {
                        html += Mark.up(BB.friend_comment_template, votes[vote]);
                    }
                }
                $("#item-comments").html(html);

                $("#item-distance").html(currentItem.distance);

                //set the likes radio
                $('#item-page-votes li a').removeClass('ui-btn-hover-b').addClass('ui-btn-up-b').removeClass('ui-btn-active');
                if (currentItem.untried) {
                    $('#item-untried').addClass('ui-btn-active');
                }
                else {
                    if (currentItem.vote > 0) {
                        $('#item-like').addClass('ui-btn-active');
                    }
                    else {
                        $('#item-dislike').addClass('ui-btn-active');
                    }
                }
                if (currentItem.img) {
                    console.log("Show item image");
                    $("#item-img").show();
                    $("#item-img>img").attr("src", currentItem.img);
                    $("#item-img>img").attr("style", "");
                }
                else {
                    //$("#item-img").hide();
                    $("#item-img>img").attr("src", '/static/images/no-image.png');
                    $("#item-img>img").attr("style", "");
                }
                if (currentItem.key in UserData.myBook.votes) {
                    $("#item-delete").show();
                }
                else {
                    $("#item-delete").hide();
                }
                $('#item-votes-inner').trigger('collapse').trigger('updatelayout');
                $("#vote-cursor").val("");
                $("#item-votes").html("");
                this.loadVotes()
            }

            if (currentItem.key) {
                if (BB.friend_comment_template == null) {
                    //load from file
                    $.get(
                        'static/templates/friend-comment-template.htt',
                        null,
                        function (template) {
                            BB.friend_comment_template = template;
                            pageTo_item_inner.call(this);
                        })
                }
                else {
                    pageTo_item_inner.call(this);
                }
            }
        },

        mapSearchClick: function () {
            BB.map_search_key({"which": 13});
        },

        clickColumnHeader: function (event) {
            // click a column header on the list page
            BB.filter = BB.get_list_column_filter();
            BB.populateMainList("", 0, 0);
        },

// proper case function (JScript 5.5+)
        toProperCase: function (s) {
            return s.toLowerCase().replace(/^(.)|\s(.)/g,
                function ($1) {
                    return $1.toUpperCase();
                });
        },

        item_create: function (/*title, address, lat, lng*/) {
            var properTitle = BB.toProperCase($(this).data('title'));
            $("#new-detail-name").val(decodeURIComponent(properTitle));
            $("#new-detail-address").val($(this).data('address'));
            $("#new-category>option").removeAttr('selected');
            $("#new-category").val("Select Cuisine ...");
            try {
                $("#new-category").selectmenu("refresh", true);
            } catch (e) {
            }
            $("#new-detail-comment").val("");

            //set the likes radio
            $("#new-detail-vote a").removeClass('ui-btn-hover-b').addClass('ui-btn-up-b').removeClass('ui-btn-active');
            $('#new-item-like').addClass('ui-btn-active');
            $("#new-preview-box").hide();

            currentItem.address = $(this).data('address');
            currentItem.key = $(this).data('key');
            currentItem.lat = $(this).data('lat');
            currentItem.lng = $(this).data('lng');
            currentItem.place_name = properTitle;
        },

        process_template: function (data, callback) {
            if (BB.add_search_nearby_template == null) {
                //load from file
                $.get(
                    'static/templates/add-search-nearby-template.htt',
                    null,
                    function (template) {
                        BB.add_search_nearby_template = template;
                        callback(data);
                    })
            }
            else {
                callback(data);
            }
        },

        lookupAddressList: function (event) {
            var addr;
            $("#new-place-list-loading").show();
            function lookAddressList_inner(obj) {
                try {

                BB.check_for_dirty_data(obj);

                //safe_title = .replace(/\"/g, "&quot;").replace(/\'/g, "&lsquo;"),
                // https://github.com/adammark/Markup.js/
                var context = {'items': obj.local.points};
                var UIlist = Mark.up(BB.add_search_nearby_template, context);

                $("#new-place-list").html(UIlist).listview().trigger('create').trigger('updatelayout');
                $(".found-address").on("click", BB.item_create);
                $("#manual-address-lookup").val(currentItem.address);
                }
                catch (e) {
                    console.error("lookupAddressList");
                }
                $("#new-place-list-loading").hide();
            }


            function lookupAddressListSuccessHandler(data) {
                $("#search-location-loading").hide();
                //$.mobile.changePage("#new-address-list-page");
                $("#new-place ul").remove();
                BB.process_template(jQuery.parseJSON(data), lookAddressList_inner)
            }

            function lookupAddressListErrorHandler() {
                $("#search-location-loading").hide();
                console.log("no address found");
                alert("Not Found");
                $("#new-page ul").remove();
                $("#create-new-address-box").show();
                BB.process_template({items: []}, lookAddressList_inner);  // string to be parsed
            }

            console.log("AJAX lookupAddressList");
            addr = currentItem.address;
            var request = {};
            request.lat = this.lastGPSPosition.latitude;
            request.lng = this.lastGPSPosition.longitude;
            request.addr = addr;
            // get the place name from the new screen
            request.place_name = $("#new-place-name-box").val();
            if (event.currentTarget.id == "new-search-place-btn") {
                //near address
                request.near_me = 0;
            } else {
                request.near_me = 1;
            }
            $("#search-location-loading").show();
            $.ajax({
                url: "/getAddresses_ajax",
                type: "GET",
                handleAs: "json",
                data: request,
                success: lookupAddressListSuccessHandler,
                error: lookupAddressListErrorHandler
            });
        },

        lookupMyAddress: function (event) {
            currentItem.address = "";
            BB.lookupAddressList(event);
        },

        lookupManualAddress: function (event) {
            currentItem.address = $("#new-place-near").val();
            BB.lookupAddressList(event);
        },
        
        add_search_name: function(){
          //lookup a place by name in the add page
          name = $("#new-place-name-box").val();
        },

        take_photo_click: function () {
            try {
                $('#image-dialog').popup('close');
            }
            catch (e) {
                console.log("take_photo_click error: " + e);
            }
            $("#image-input").click();
        },

        open_image_file_click: function () {
            try {
                $('#image-dialog').popup('close');
            }
            catch (e) {
                console.log("take_photo_click error: " + e);
            }
            $("#file-input").click();
        },

        editItem: function (event) {
            console.log("editItem");
            event.preventDefault();
            $.mobile.changePage("#new-detail")
        },

        show_create_new_address: function () {
            $.mobile.changePage("#create-new-address");
        },

        do_create_new_address: function () {
            currentItem.clear();
            currentItem.place_name = $("#create-name").val();
            currentItem.address = $("#dragged-address").text();
            currentItem.lat = BB.creatorMap.getCenter().lat();
            currentItem.lng = BB.creatorMap.getCenter().lng();
            BB.item_load_for_edit();
            $.mobile.changePage("#new-detail");
        },

//FLIGHT
        offlineEventHandler: function () {
            alert("This action requires an internet connection (3G/WiFi)")
        },


//FLIGHT
//test for online
        checkOnline: function (callback) {
            $.get("/ping",
                {},
                function () {
                    //ok
                    console.log("ONLINE");
                    BB.isOnline = true;
                    callback();
                },
                function () {
                    //offline
                    console.log("OFFLINE");
                    alert("Server not available. Functionality will be limited");
                    BB.isOnline = false;
                    callback();
                })
        },

        itemDelete: function () {
            //delete the current item
            //is it in my list?
            if (currentItem.key in UserData.myBook.votes) {
                if (confirm("Remove place from your list?")) {
                    $.ajax(
                        {url: '/item/del/' + currentItem.key,
                            type: 'post',
                            success: function () {
                                $.mobile.changePage("#list-page");
                                UserData.load(BB.populateMainList);
                            }})
                }
            }
        },

        set_list_column_filter: function (val) {
            $("#filter-radio input[type='radio']").attr("checked", null);
            $("#filter-radio input[type='radio'][value='" + val + "']").attr("checked", "checked");
            $("#filter-radio  input[type='radio']").checkboxradio().checkboxradio("refresh");
        },

        get_list_column_filter: function () {
            return $("#filter-radio").find("input:checked").val();
        },

        set_test_location: function () {
            if ($(this).val() == 'on') {
                BB.use_test_location = true;
                BB.test_lat = parseFloat($("#test-lat").val());
                BB.test_lng = parseFloat($("#test-lng").val());
                BB.lastGPSPosition.latitude = BB.test_lat;
                BB.lastGPSPosition.longitude = BB.test_lng;
            }
            else {
                BB.use_test_location = false;
            }
        },


        comment_validate: function () {
            var text = $(this).val();
            var chars = text.length;
            //check if there are more characters than allowed (140)
            if (chars > 140) {
                //and if there are use substr to get the text before the limit
                var new_text = text.substr(0, 140);
                //and change the current text with the new text
                $(this).val(new_text);
            }
        },

        watchPositionSuccess: function (pos) {
            console.log("watchPositionSuccess: " + pos.coords.latitude + "," + pos.coords.longitude);
            BB.lastGPSPosition = pos.coords;
            var now = new Date();
            if (now - BB.lastGPSTime > (2 * BB.watchPositionOptions.maximumAge)) {
                BB.watch_position_id = navigator.geolocation.watchPosition(BB.watchPositionSuccess, BB.watchPositionError, BB.watchPositionOptions);
            }
            BB.lastGPSTime = now;
            if (BB.isMapPage() && BB.map_centred) {
                BB.map_center();
            }
        },

        watchPositionError: function (err) {
            console.warn('watchPositionError ERROR(' + err.code + '): ' + err.message);
        },

        firstWatchPositionSuccess: function (pos) {
            BB.watchPositionSuccess(pos);
            BB.init();
            BB.loadUserData();
        },

        save_profile: function () {
            $.post(
                '/user_profile',
                {'screen_name': $('#settings-screen-name').val()},
                function (data) {

                });
        },

        set_search_to_near_place: function () {
            $("#new-select input[type='radio']").attr("checked", "");
            $("#new-search-radio-place").attr("checked", "checked");
            $("#new-select input[type='radio']").checkboxradio("refresh");
        },

        add_search_radio_change: function (e) {
            switch ($(this).val()) {
                case "place":
                    $("#new-place-near").show();
                    $("#new-search-place-btn").show();
                    break;
                case "me":
                    $("#new-place-near").hide();
                    $("#new-search-place-btn").hide();
                    BB.lookupMyAddress(e);
                    break;
            }

        },


        setupListeners: function () {
            $("#new-shout-form").submit(BB.SaveItemAtPos);
            //when the cam icon is clicked, send a click to the file input widget
            $("#new-item-camera-img").on("click", this.take_photo_click);
            $("#camera-dlg-btn").on("click", this.take_photo_click);
            $("#file-dlg-btn").on("click", this.open_image_file_click);
            //$("#item-camera-img").on("click",  take_photo_click);
            //hide the default one
            $("#image-input").hide();
            $("div[data-controltype='camerainput']").hide();
            //vote buttons
            $("#refresh-btn").on("click", BB.loadUserData);

            $("#create-new-save-btn").on("click", this.do_create_new_address);
            $("#create-new-address-btn").on("click", this.show_create_new_address);
            $("#item-edit").on("click", BB.editItem);
            $("#new-rotr").on("click", this.imageRotate);
            $("#image-save").on("click", this.imageSaveClick);
            $("#image-input").change(this.imagePreview);
            $("#new-address-next-btn").on("click", this.lookupManualAddress);
            $("#enter-new-addr-btn").on("click", this.lookupManualAddress);
            $("#new-address-my-locn-btn").on("click", this.lookupMyAddress);
            $("#forgot-btn").attr("data-ajax", "false");
            $("#column-headers span").on("click", this.clickColumnHeader);
            this.set_list_column_filter('mine');
            $("#filter-radio").on("change", this.clickColumnHeader);
            $("#sort-dist").addClass("list-sort-selected");
            $("#col-mine").addClass("list-filter-selected");
            $("#new-place-name-box").on('change input', this.place_search_by_name);
            $("#new-place-near").on('keyup', this.set_search_to_near_place);
            $("#new-search-place-btn").click(BB.lookupManualAddress);
            $("#new-top-controls input[type='radio']").bind("change", BB.add_search_radio_change);
            // edit item btn hidden by default. Shown if you own it
            // event handler for map search box on map-page
            $("#map-search").keyup(this.map_search_key);
            $("#item-see-map").on("click", BB.showItemOnMap);
            $("#new-item-save").on("click", BB.new_item_save_click);
            $("#item-save").on("click", BB.updateitem);
            $('#new-preview-box').hide();
            //on click map search btn, simulate Enter key in search box
            $("#map-search-btn").on("click", BB.mapSearchClick);
            $("#map-search-btn-box").on("click", BB.mapSearchClick);
            $("#map-search-btn-box").hide();
            $("#main-search").on('keyup change', this.list_text_filter);
            $("#item-delete").on("click", BB.itemDelete);
            $("#new-item-delete").on("click", BB.itemDelete);
            $("#main-search").parent().removeClass('ui-body-a').addClass('ui-body-b');
            $("#main-search").removeClass('ui-body-a').addClass('ui-body-b');
            $("#test-loc-set").change(BB.set_test_location);
            $('#item-descr').keypress(BB.comment_validate);
            $("#settings-save-profile").click(BB.save_profile);
            $("#new-search-title-btn").click(BB.add_search_name);
            $("#new-search-name-btn").click(BB.lookupMyAddress);

            /*window.onerror = function errorHandler(msg, url, line) {
             alert(msg + ": " + line);
             // Just let default handler run.
             return false;
             }*/
        },

        loadUserData: function () {
            UserData.load(
                function () {
                    BB.populateMainList("");
                });
        }
    }
    ;


//                BB.populateMainList("", BB.lastMapPosition.latitude, BB.lastMapPosition.longitude);


$(function () {


    function onPageShow(event, ui) {
        var previousPage = ui.prevPage.attr("id");
        switch (event.target.id) {
            case "list-page":
                BB.pageToList(event, previousPage);
                break;
            case "map-page":
                BB.pageToMap(event);
                break;
            case "new-place":
                BB.pageToNewPlace(event, previousPage);
                break;
            case "image-page":
                BB.pageToImage(event);
                break;
            case "new-detail":
                if (currentItem.key) {
                    BB.item_load_for_edit();
                }
                break;
            case "item-page":
                BB.pageToItem(event, previousPage);
                break;
            case "create-new-address":
                BB.pageToCreateAddress(event, previousPage);
                break;
            case "new-address-list-page":
                $("#new-addresses-list").trigger('create').trigger('updatelayout');
                try {
                    $("#new-addresses-list").listview('refresh');
                } catch (e) {
                }
                break;
            case "settings-page":
                $.get('/user_profile', {}, function (data) {
                    $("#settings-screen-name").val(jQuery.parseJSON(data).screen_name);
                });
                break;
        }
    }

    function beforePageShow(event, data) {
        //some pages are ones you mustn't land on from outside as they need loading
        console.log("beforePageShow " + data.prevPage.attr("id") + ">" + event.target.id);
        if (event.target.id == "item-page") {
            BB.clearItemPage();
        }
        if ((event.target.id == "item-page") ||
            (event.target.id == "map-page") ||
            (event.target.id == "new-detail") ||
            (event.target.id == "new-page") ||
            (event.target.id == "new-address-list-page") ||
            (event.target.id == "create-new-address") ||
            (event.target.id == "new-place")) {
            if (!data.prevPage.attr("id"))
                $.mobile.changePage("#list-page");
        }

        if (event.target.id == "map-page") {
            if (!BB.theMap) {
                BB.map_init();
            }
        }
        function remove_old_place_searches() {
            var UIlist = Mark.up(BB.add_search_nearby_template, {});
            $("#new-page").append(UIlist).listview().trigger('create').trigger('updatelayout');
        }

        if (event.target.id == "new-page") {
            $("#search-location-loading").hide();
            //remove old results
            $("#new-page ul").remove();
            BB.process_template({}, remove_old_place_searches);
        }
        if (event.target.id == "new-place") {
            if (data.prevPage.attr("id") == "new-detail") {
                //coming back from new page
            }
        }
        if (!BB.navBarActive) {
            event.preventDefault();
        }
        //$("#item-img").hide();
    }


    try {
        $('div[data-role=page]').bind('pageshow', onPageShow);
        $(document).bind("pagebeforeshow", beforePageShow);
    }
    catch (e) {
        BB.log(e);
    }

    // change the default jquery "contains" selector so it matches case insensitive
    // from: http://css-tricks.com/snippets/jquery/make-jquery-contains-case-insensitive/
    $.expr[":"].contains = $.expr.createPseudo(function (arg) {
        return function (elem) {
            return $(elem).text().toUpperCase().indexOf(arg.toUpperCase()) >= 0;
        };
    });

    //add a pipe to markup.js so we can do x-> 100%-x
    Mark.pipes.subFrom = function (a, b) {
        try {
            return parseInt(b) - parseInt(a);
        }
        catch (e) {
            return 0;
        }
    };


    //add a pipe to markup.js to show x if x>y
    Mark.pipes.above = function (a, b) {
        try {
            if (parseInt(a) > parseInt(b))
                return a;
            else
                return "";
        }
        catch (e) {
            return "";
        }
    };


    if (!navigator.geolocation) {
        console.error("$. NEED GEO");
        alert("LBS Are Off");
        //todo: Note: jQuery.mobile.changePage is deprecated as of jQuery Mobile 1.4.0 and will be removed in 1.5.0. Use the pagecontainer widget's change() method instead.
        //   $( ":mobile-pagecontainer" ).pagecontainer( "change", "need-geo.html");
        $.mobile.changePage("/need-geo.html")
    }
    else {
        console.log("populateMainList call");


        window.scrollTo(0, 1);
    }


    BB.lastGPSTime = 0;
    if (!navigator.geolocation) {
        alert("Please check Location Services are on for Safari");
        console.log("Could not get position");
        $.mobile.changePage("#need-geo");
    }
    else {
        navigator.geolocation.getCurrentPosition(BB.firstWatchPositionSuccess, BB.watchPositionError, BB.watchPositionOptions)
    }
    BB.setupListeners();
    console.log("JS Init'd");
    $("#loading").html('.');
});


/////////////////
//
// Codiqa hacks
//
/////////////////

// NewItem form
//
//    add data-ajax="false"
//  Login Form
//      data-url="/#map-page"
//
// Load JQUERY V10!!
//
// remove maps script from Map page - it's in this code already, mod'd
//
// before shout.js
// <script src="/static/js/jquery.canvasResize.js"></script>

