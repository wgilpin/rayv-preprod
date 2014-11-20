//var google={};
var rayv = rayv || {};
/**
 * create a geo posn
 * @param lat
 * @param lng
 * @constructor
 */
rayv.LatLng = function (lat, lng) {
    this.lat = lat;
    this.lng = lng;
    this.googleFormat = function () {
        return new google.maps.LatLng(this.lat, this.lng);
    };
    this.loadFromGoogleFormat = function (g_fmt) {
        this.lat = g_fmt.lat();
        this.lng = g_fmt.lng();
        return this;
    }
};

rayv.currentItem = rayv.currentItem || {};
(function () {
    this.address = "";
    this.position = new rayv.LatLng(0.0, 0.0);
    this.place_name = "";
    this.descr = "";
    this.category = "";
    this.key = "";
    this.vote = 0;
    this.website = "";
    this.mine = "";
    this.img = null;
    this.thumbnail = null;
    this.rotation = 0;
    this.telephone = null;
    this.distance = null;
    this.untried = null;
    /**
     * loads the current item given its key
     * @param [key] {string} - urlsafe key
     */
    this.loadFromKey = function (key) {
        if (!key) {
            key = this.key;
        }
        if (key) {
            try {
                _innerLoad(rayv.UserData.places.get(key), false);
            }
            catch (e) {
                console.error('loadFromKey')
            }
        }
    };
    /**
     * loads the currentItem from an ajax return object
     * @param data {object} The ajax objet
     * @param is_json {bool} is the object already parsed as json?
     * @private
     */
    var _innerLoad = function (data, is_json) {
        var obj = is_json ? jQuery.parseJSON(data) : data;
        rayv.currentItem.address = obj.address;
        console.assert(rayv.currentItem.address != null);
        console.assert(rayv.currentItem.address != "null");
        rayv.currentItem.place_name = obj.place_name;
        rayv.currentItem.category = obj.category;
        console.log("_innerLoad: " + obj.category);
        rayv.currentItem.descr = obj.descr;
        rayv.currentItem.telephone = obj.telephone;
        rayv.currentItem.website = obj.website;
        rayv.currentItem.position = new rayv.LatLng(obj.lat, obj.lng);
        rayv.currentItem.lat = obj.lat;
        rayv.currentItem.lng = obj.lng;
        rayv.currentItem.key = obj.key;
        rayv.currentItem.mine = obj.mine;
        rayv.currentItem.img = obj.img;
        rayv.currentItem.thumbnail = obj.thumbnail;
        rayv.currentItem.vote = obj.vote;
        rayv.currentItem.distance = obj.distance;
        rayv.currentItem.rotation = 0;
        rayv.currentItem.untried = obj.untried;
    };
    /**
     * Clears the currentItem
     */
    this.clear = function () {
        rayv.currentItem.address = "";
        rayv.currentItem.place_name = "";
        rayv.currentItem.category = "";
        rayv.currentItem.website = "";
        rayv.currentItem.descr = "";
        rayv.currentItem.position = new rayv.LatLng(0, 0);
        rayv.currentItem.key = null;
        rayv.currentItem.mine = "";
        rayv.currentItem.img = "";
        rayv.currentItem.thumbnail = "";
        rayv.currentItem.vote = "";
        rayv.currentItem.distance = "";
        rayv.currentItem.rotation = "";
    }
}).apply(rayv.currentItem);


DictStore = function (dict_name) {
    this.dict_name = dict_name;
    var has_local_storage = !(typeof window.localStorage == 'undefined');
    var mem_data = null;
    this.make_key = function (k) {
        return this.dict_name + ':' + k;
    };

    this.is_empty = function () {
        // try a load first
        if (mem_data && mem_data.length > 0) {
            return false;
        }
        this.load();
        // if, after a load, still empty then it's Really Empty
        if (!mem_data || mem_data.length == 0) {
            return true;
        }
        ;
        return false;
    };
    /**
     * load from localStorage
     */
    this.load = function () {
        mem_data = {};
        var item_key_starts_at = this.dict_name.length + 1;
        for (var i = 0; i < window.localStorage.length; i++) {
            var key = window.localStorage.key(i);
            if (key.indexOf(this.dict_name) == 0) {

                var stored = window.localStorage.getItem(key);
                if (stored) {
                    var k = key.substring(item_key_starts_at);
                    var obj = JSON.parse(stored);
                    mem_data[k] = obj;
                }
                ;
            }
        }
    };
    /**
     * Store in mem & localStorage
     * @param k {string} key
     * @param v {Object} value - must be serialisable
     */
    this.set = function (k, v) {
        if (!mem_data) {
            this.load();
        }
        mem_data[k] = v;
        if (has_local_storage) {
            var json_val = JSON.stringify(v);
            window.localStorage.setItem(this.make_key(k), json_val);
        }
    };
    /**
     * get value from local storage
     * @param k {string} key
     * @returns {Object}
     */
    this.get = function (k) {
        if (!mem_data) {
            this.load();
        }
        if (mem_data.hasOwnProperty(k)) {
            return mem_data[k];
        }
        return null;
    };
    this.exists = function (k) {
        if (!mem_data) {
            this.load();
        }
        if (mem_data.hasOwnProperty(k)) {
            return true;
        }
        return false;
    };
    this.clear = function () {
        if (has_local_storage) {
            for (k in mem_data) {
                window.localStorage.removeItem(this.make_key(k));
            }
        }
        mem_data = {};
    };
    this.forEach = function (fn) {
        for (k in mem_data) {
            fn(mem_data[k]);
        }
    }

};

ObjectStore = function (obj_name) {
    this.obj_name = obj_name;
    var has_local_storage = !(typeof window.localStorage == 'undefined');
    var obj = null;
    /**
     * load from localStorage
     */
    this.load = function () {
        obj = JSON.parse(localStorage.getItem(this.obj_name + ':'));
    };
    /**
     * Store in mem & localStorage
     * @param k {string} key
     * @param v {Object} value - must be serialisable
     */
    this.set = function (v) {
        if (!obj) {
            this.load();
        }
        obj = v;
        if (has_local_storage) {
            var json_val = JSON.stringify(v);
            try {
                window.localStorage.setItem(this.obj_name + ':', json_val);
            } catch (e) {
                alert('Please ensure your browser is not in Private mode')
            }
        }
    };
    this.get = function () {
        if (!obj) {
            this.load();
        }
        return obj;
    };

};

//todo: put this in local storage
rayv.UserData = rayv.UserData || {};
(function () {
    this.places = new DictStore('PLACE');
    this.myBook = new ObjectStore('MYBOOK');
    this.friends = new DictStore('FRIEND');
    this.lastUpdate = new ObjectStore('LASTUPDATE');

    this.init = function () {
        var LSsupport = !(typeof window.localStorage == 'undefined');
        if (LSsupport) {
            console.log("localStorage and sessionStorage are available");
            this.has_local_storage = true;
            this.storage = window.localStorage;
        }
        rayv.UserData.my_id = new ObjectStore('my_id');
        rayv.UserData.my_id.set(0);
    };

    /**
     * adds places to the cache
     * only adds - no deletion here (as we don't ref count)
     * @param obj {object} has a .places element which is {list}
     */
    var updatePlaceCache = function (obj) {
        for (var idx in obj.places) {
            //noinspection JSUnfilteredForInLoop
            var place = obj.places[idx];
            if (!rayv.UserData.places.exists(place.key)) {
                // dict indexed by place key
                rayv.UserData.places.set(place.key, place);
            }
        }
    };
    /**
     * get All user data from the server
     * @param callback {function} callback on completion
     */
    this.load = function (callback) {
        var request = {};
        var last_update = rayv.UserData.lastUpdate.get();
        if (rayv.UserData.places.is_empty()) {
            rayv.UserData.places.load();
        }
        ;
        if (last_update > 0 && !rayv.UserData.places.is_empty()) {
            request.since = last_update;
            callback();
        }
        else {
            if (!BB.splash) {
                $("#list-loading").show();
            }
        }
        $.get("/getFullUserRecord",
            request,
            function (data) {
                //populate the list
                var obj = $.parseJSON(data);
                if (obj.result && obj.result == 'FAIL'){
                    $.mobile.changePage('#login-page')
                }
                my_id = obj.id;
                // first one is me
                rayv.UserData.myBook.set(obj.friendsData[0]);
                rayv.UserData.lastUpdate.set((new Date()).getTime());
                if (!request.since) {
                    rayv.UserData.places.clear();
                }
                ;
                updatePlaceCache(obj);
                rayv.UserData.friends.clear();
                var skippedFirstAsThatOneIsMe = false;
                obj.friendsData.forEach(function (data) {
                    if (skippedFirstAsThatOneIsMe) {
                        // dictionary indexed by user id
                        rayv.UserData.friends.set(data.id, data);
                    }
                    else {
                        skippedFirstAsThatOneIsMe = true;
                    }
                });
                callback();
            });
    };
    /**
     * load, cache & display the thumbs for the current list, async
     * @param listULId {string} element ID of the list
     */
    this.getThumbs = function (listULId) {
        $(listULId).find("li").each(function () {
            // get the data-key from the <a>
            var key = $(this).find('a').data('key');
            // lookup the place for that key
            var place = rayv.UserData.places.get(key);
            // if no cached image
            if (place.imageData) {
                // replace the existing image with cached one
                $(this).find(".item-img-container").html(place.imageData);
            }
            else {
                //      get the image URL
                var imgUrl = place['thumbnail'];
                //      blank means no thumb
                if (imgUrl == "") {
                    //      no image
                    $(this).find(".item-pic").attr("src", "");
                }
                else {
                    //todo: create the cached image
                    var imgCache = $("<img>");
                    //      create img, load from URL
                    imgCache.attr("src", imgUrl);
                    //      class for w x h
                    imgCache.addClass('item-pic');
                    //      cache it
                    place.imageData = imgCache;
                    //todo: load the cached image into the dom
                    // replace the existing image
                    $(this).find(".item-img-container").html(imgCache);
                }
            }
        });
    };

    /**
     * gets the single most relevant comment for a place
     * my comment, else a friend's
     * @param key {string} the key to the object
     * @returns {string} comment text
     */
    this.get_most_relevant_comment = function (key) {
        var myBook = this.myBook.get();
        if (myBook.votes[key]) {
            return myBook.votes[key].comment
        }
        //not in my list
        var comment = "";
        this.friends.forEach(function (friend) {
            //noinspection JSUnfilteredForInLoop
            if (friend.votes[key]) {
                comment = friend.votes[key].comment
            }
        });
        return comment;
    };

    /**
     * gets my comment for a place
     * @param key {string} the key to the object
     * @returns {string} comment text
     */
    this.get_my_comment = function (key) {
        // my comment;
        var myBook = this.myBook.get();
        if (myBook.votes[key]) {
            return myBook.votes[key].comment
        }
        return '';
    };

    /**
     * gets all the vote for a place give the key
     * @param key {string} urlsafe place key
     * @returns {Array} of votes
     */
    this.get_votes_for_item = function (key) {
        var result = [];
        this.friends.forEach(function (friend) {
            //noinspection JSUnfilteredForInLoop
            var vote = {name: friend.name};
            if (friend.votes[key]) {
                vote.vote = friend.votes[key];
                result.push(vote);
            }
        });
        return result;
    }
}).apply(rayv.UserData);


var BB = {
        isOnline: true,
        //global timestamp = time of next list load - initially one minute ago
        nextListLoad: null,
        mapInfoWindows: [],
        mapMarkers: [],
        creatorMapMarker: null,
        marker: null,
        navBarActive: false,
        lastGPSPosition: new rayv.LatLng(0, 0),
        // map_centred set if blue home button pressed, reset if dragged
        map_centred: false,
        lastGPSTime: 0,
        lastMapPosition: {"position": new rayv.LatLng(0, 0),
            "isSet": false,
            "zoomIn": false},
        theMap: null,
        creatorMap: null,
        geocoder: null,
        iconPath: "/static/images/",
        filter: "mine",
        use_test_location: false,
        test_position: new rayv.LatLng(0, 0),
        imageRotation: 0,
        watchPositionOptions: {
            enableHighAccuracy: true,
            maximumAge: 30000 //30 seconds
        },
        detail_saving: false,
        /**
         * hide all waiting spinners
         */
        hide_waiting: function () {
            $('.waiting').hide();
            BB.detail_saving = false;
            console.log('hide_waiting timeout');
        },
        /**
         * show the requested spinner
         * @param selector {string} jQuery selector for the element
         * @returns {number} time id
         */
        show_waiting: function (selector) {
            //show the ajax spinner & set time to turn off
            var timer = window.setTimeout(BB.hide_waiting, 20000);
            $(selector).show();
            BB.detail_saving = true;
            return timer;
        },
        /**
         * center the map
         */
        map_center: function () {
            var last = BB.lastGPSPosition.googleFormat();
            BB.theMap.setCenter(last);
            BB.dragMap();
            BB.map_centred = true;
        },
        /**
         * set up the main map
         */
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
            BB.theMap.controls[google.maps.ControlPosition.LEFT_CENTER].
                push(controlUI);
        },
        /**
         * initialise app on load
         */
        init: function () {
            BB.splash = true;
            $("#list-loading").hide();
            BB.geocoder = new google.maps.Geocoder();
            BB.map_init();

        },

        /**
         * every server call, we look for dirty data and append it if needed
         * @param obj {object} ajax return object
         */
        check_for_dirty_data: function (obj) {
            if (obj) {
                if ("dirty_list" in obj) {
                    for (var frIdx in obj.dirty_list.friends) {
                        //these friends are dirty
                        //noinspection JSUnfilteredForInLoop
                        rayv.UserData.friends.set(
                            obj.dirty_list.friends[frIdx].id,
                            obj.dirty_list.friends[frIdx]);
                    }
                    for (var plIdx in obj.dirty_list.places) {
                        //these places are dirty
                        //noinspection JSUnfilteredForInLoop
                        rayv.UserData.places.set(
                            obj.dirty_list.places[plIdx].key,
                            obj.dirty_list.places[plIdx]);
                    }
                }

            }
        },

        /**
         * get the distance as yards if close, else miles
         * @param dist {number} distance in miles
         * @returns {string} prettified distance string
         */
        pretty_dist: function (dist) {
            if (dist >= 1.0) {
                return dist.toFixed(1) + " miles";
            }
            var yds = Math.floor(dist * 90) * 20;
            return yds + " yds";
        },

        /**
         * one in 60 rule distance calc
         * @param point {LatLng}
         * @param origin {LatLng}
         * @returns {number} distance between points
         */
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
            var d_lat = (origin.lat - p_lat) * 69;
            //cos(lat) approx by 1/60
            var cos_lat = Math.min(1, (90 - p_lat) / 60);
            //delta lng = degrees * cos(lat) *69 miles
            var d_lng = (origin.lng - p_lng) * 69 * cos_lat;
            return Math.sqrt(d_lat * d_lat + d_lng * d_lng);
        },

        /**
         * log the message
         * @param msg {string} message
         */
        log: function (msg) {
            try {
                console.log(msg + " / map lat :" + BB.theMap.getCenter().lat());
            }
            catch (e) {
                console.log(msg);
            }
        },

        vote_is_like: function (vote) {
            if (vote == 'like' || vote == 1) {
                return true;
            }
            return false;
        },
        vote_is_dislike: function (vote) {
            if (vote == 'dislike' || vote == -1) {
                return true;
            }
            return false;
        },

        /**
         * we have changed the current item, update the cache
         * @returns {boolean} updated
         */
        updateCurrentItemInCache: function () {
            var myBook = rayv.UserData.myBook.get();
            var vote = myBook.votes[rayv.currentItem.key];
            if (!vote) {
                myBook.votes[rayv.currentItem.key] = {
                    vote: 0,
                    comment: '',
                    untried: false
                };
                vote = myBook.votes[rayv.currentItem.key];
            }
            ;
            vote.vote = rayv.currentItem.vote;
            if (BB.vote_is_dislike(rayv.currentItem.vote)) {
                vote.vote = -1;
            }
            if (BB.vote_is_like(rayv.currentItem.vote)) {
                vote.vote = 1;
            }
            vote.untried = vote.vote == 0;
            vote.comment = rayv.currentItem.descr;
            rayv.UserData.myBook.set(myBook);
            console.log("Updated in cache ");
            return true;
        },

        /**
         * encode a latLng
         */
        codeLatLng: function () {
            BB.geocoder.geocode({'latLng': BB.creatorMap.getCenter()},
                function (results, status) {
                    $("#create-new-save-btn").addClass("ui-disabled");
                    if (status == google.maps.GeocoderStatus.OK) {
                        if (results[1]) {
                            var el = $("#dragged-address");
                            el.text(results[0].formatted_address);
                            el.show();
                            if ($('#create-name').val().length > 0) {
                                $("#create-new-save-btn").removeClass("ui-disabled")
                            }
                        }
                    } else {
                        console.log("Geocoder failed due to: " + status);
                    }
                });
        },

        /**
         * handler for updating an item
         * Called from the image error handle
         * if the item has no image, it doesn't update
         * @param item {Object}
         * @returns {boolean} Was an update saved?
         */
        update_item_from_server: function (item) {
            if (item.thumbnail.length == 0) {
                return false;
            }
            BB.set_distance_for_place(item);
            rayv.UserData.places.set(item.key, item);
            rayv.currentItem.loadFromKey(item.key);
            return BB.updateCurrentItemInCache();
        },

        /**
         * save to server
         */
        saveCurrentItem: function () {
            console.log("saveCurrentItem");
            var file = $("#image-input").prop("files")[0];
            // https://github.com/gokercebeci/canvasResize
            function build_form(f) {
                var fd = new FormData();
                if (f) {
                    fd.append("new-photo", f);
                }
                fd.append("new-item-category", rayv.currentItem.category);
                fd.append("new-title", rayv.currentItem.place_name);
                fd.append("address", rayv.currentItem.address);
                fd.append("myComment", rayv.currentItem.descr);
                fd.append("latitude", rayv.currentItem.position.lat);
                fd.append("longitude", rayv.currentItem.position.lng);
                fd.append("voteScore", rayv.currentItem.vote);
                fd.append("website", rayv.currentItem.website);
                fd.append("untried", 'untried' in rayv.currentItem ?
                    rayv.currentItem.untried : false);
                fd.append("rotation", rayv.currentItem.rotation);
                fd.append("key", rayv.currentItem.key);
                return fd;
            };

            function save_success_handler(res) {
                // clear the form as per #86
                $('#new-shout-form')[0].reset();
                var it = res;//JSON.parse(res);
                $.mobile.changePage("#list-page");
                if (BB.update_item_from_server(it)) {
                    BB.populateMainList("");
                }
                else {
                    BB.loadUserData();
                }
            };
            /**
             * save with an image upload
             */
            function saveMultiPart() {
                var _URL;
                console.log("With file");
                // to trigger a reload, make it different
                rayv.currentItem.img = true;
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
                            $.ajax({
                                url: '/item',
                                data: build_form(f),
                                dataType: 'json',
                                cache: false,
                                contentType: false,
                                processData: false,
                                type: 'POST',
                                success: save_success_handler,
                                error: function (a, b, c) {
                                    BB.hide_waiting();
                                    console.error(
                                            'saveMultiPart /item: ' + b + ', ' + c);
                                }
                            });
//                            var fd = build_form(f);
//                            var xhr = new XMLHttpRequest();
//                            xhr.open('POST', '/item', true);
//                            xhr.setRequestHeader("X-Requested-With",
//                                "XMLHttpRequest");
//                            xhr.setRequestHeader("pragma", "no-cache");
//                            // File uploaded
//                            xhr.addEventListener("load", save_success_handler);
//                            // Send data
//                            xhr.send(fd);
                        }

                    });
                };
                _URL = window.URL || window.webkitURL;
                img.src = _URL.createObjectURL(file);
            }

            /**
             * save with no image upload
             */
            function saveSinglePart() {
                // no photo attached
                // simple post, no upload
                $.ajax({
                    url: '/item',
                    data: build_form(null),
                    dataType: 'json',
                    cache: false,
                    contentType: false,
                    processData: false,
                    type: 'POST',
                    success: save_success_handler,
                    error: function (data) {
                        BB.hide_waiting();
                        console.error('saveSinglePart: ' + data);
                        alert('Sorry, save failed for some reason. Please try again');
                    }
                });
                console.log("AJAX saverayv.currentItem");
            }

            if (file) {
                saveMultiPart();
            }
            else {
                saveSinglePart();
            }
        },

        /**
         * set the position of the item, then save it
         * @param position {LatLng}
         */
        saveItemAtPos: function (position) {
            console.log("saveItemAtPos");
            rayv.currentItem.position = position;
            BB.saveCurrentItem();
        },

        /**
         * remove all map markers
         */
        clearMapMarkers: function () {
            //todo: markers?
            if (BB.marker) {
                BB.marker.setMap(null);
            }
            BB.mapMarkers.forEach(function (marker) {
                marker.setMap(null);
            });
            BB.mapMarkers = [];
        },

//todo: is this the right name?
        /**
         *
         * @param place_name {string}
         * @param posn {LatLng}
         */
        loadMapItemForEdit: function (place_name, posn) {
            console.log('loadMapItemForEdit');
            $('#new-detail-vote').find('li').removeClass('ui-btn-hover-b').
                addClass('ui-btn-up-b').removeClass('ui-btn-active');
            $('#new-item-like').addClass('ui-btn-active');
            $("#new-category").val('');
            $("#cuisine-lookup").hide();
            $("#new-title-hdg").text(place_name);
            $("input[name=new-title]").val(place_name);
            $("#new-text").val("");
            BB.saveItemAtPos(posn)
        },

        /**
         * sprintf type {1}, {2} etc
         * arg list of values
         * @returns {string}
         */
        format: function () {
            var s = arguments[0];
            for (var i = 0; i < arguments.length - 1; i++) {
                var reg = new RegExp("\\{" + i + "\\}", "gm");
                s = s.replace(reg, arguments[i + 1]);
            }

            return s;
        },

        /**
         * setup a list of places
         * @param UIlist {string} list selector #map-list or #pagelist
         * @returns {*}
         */
        setupList: function (UIlist) {
            console.log('setupList');
            $("#list-loading").show();
            $(UIlist).find('li').remove();
            if (BB.isMapPage()) {
                BB.clearMapMarkers();
            }
            var placeList = [];
            var votes = rayv.UserData.myBook.get().votes;

            switch (BB.filter) {
                case  'untried':
                    //add the other lists
                    rayv.UserData.friends.forEach(function (friend) {
                        for (it in friend.votes) {
                            //noinspection JSUnfilteredForInLoop
                            if (placeList.indexOf(it) == -1 &&
                                votes[it] == null) {
                                // it is in a friends list, but not in mine
                                placeList.push(it)
                            }
                        }
                    });
                // FALL THROUGH
                case 'wishlist':
                    for (var it in votes) {
                        //noinspection JSUnfilteredForInLoop
                        if (votes[it].untried) {
                            if (placeList.indexOf(it) == -1) {
                                placeList.push(it)
                            }
                        }
                    }
                    break;
                case 'all':
                    //add the other lists
                    rayv.UserData.friends.forEach(function (friend) {
                        for (it in friend.votes) {
                            //noinspection JSUnfilteredForInLoop
                            if (placeList.indexOf(it) == -1) {
                                placeList.push(it)
                            }
                        }
                    });
                // FALL THROUGH
                case 'mine':
                    for (var it in votes) {
                        //noinspection JSUnfilteredForInLoop
                        if (placeList.indexOf(it) == -1) {
                            placeList.push(it)
                        }
                    }
                    break;
            }
            var detailList = [];
            placeList.forEach(function (place) {
                var geoPt = rayv.UserData.places.get(place);
                if (geoPt) {
                    detailList.push(geoPt);
                }
                else {
                    console.error('placeList has a null');
                }
            });

            if (BB.isMapPage()) {
                detailList.sort(function (a, b) {
                    return a.map_dist_float - b.map_dist_float
                });
                console.log("list sorted by map distance")
            }
            else {
                detailList.sort(function (a, b) {
                    return a.dist_float - b.dist_float;
                });
                console.log("list sorted by gps distance")
            }

            console.log("inner_setup_list");
            $(UIlist).find('li').remove();
            if (BB.isMapPage()) {
                // marker for us
                BB.marker = new google.maps.Marker({
                    position: BB.lastGPSPosition.googleFormat(),
                    map: BB.theMap,
                    icon: BB.iconPath + "blue_dot.png"
                    //infoWindowIndex: geoPtIdx
                });
                BB.mapMarkers.push(BB.marker);
            }
            for (var geoPtIdx in detailList) {
                //noinspection JSUnfilteredForInLoop
                var geoPt = detailList[geoPtIdx],
                    newListItem;
                if (geoPt.is_map) {
                    // it's a google place result - place_name, lat, long
                    newListItem = templates.render(
                        'list-geo-item-template',
                        {'geoPt': geoPt}
                    );
                }
                else {
                    // it's a db item

                    var context = { pt: geoPt, isMap: BB.isMapPage() };
                    if (geoPtIdx < 6 && BB.isMapPage()) {
                        context.icon = Number(geoPtIdx) + 1;
                    }
                    // https://github.com/adammark/Markup.js/
                    newListItem = templates.render(
                        'list-item-template',
                        context);
                }
                UIlist.append(newListItem);

                //todo: infoWindow?
                if (BB.isMapPage() && (geoPtIdx < 7)) {
                    var n = Number(geoPtIdx) + 1;
                    var marker = new google.maps.Marker({
                        position: new google.maps.LatLng(
                            geoPt.lat, geoPt.lng),
                        map: BB.theMap,
                        title: geoPt.place_name,
                        icon: BB.iconPath + n + ".png",
                        key: geoPt.key
                    });
                    BB.mapMarkers.push(marker);
                    google.maps.event.addListener(marker, 'click',
                        function () {
                            //todo: what this?
                            if (this.key) {
                                rayv.currentItem.loadFromKey(this.key);
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
            console.log("inner list loaded")
            $(UIlist).find("a").on("click", BB.ItemLoadPage);
            $(UIlist).find("a").find('img').error(BB.imageLoadErrorHandler);

            // Get cached thumbs
            //rayv.UserData.getThumbs(UIlist);
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
            $("#list-loading").hide();
            return UIlist;
        },

        /**
         * are we on the Map page?
         * @returns {boolean}
         */
        isMapPage: function () {
            try {
                return $.mobile.activePage.attr("id") == "map-page";
            }
            catch (e) {
                return false
            }
        },


//Load Data


        /**
         * Error handler if we didnt get the list data
         * from loadLocalPlaces()
         * @param data {object} server return value
         */
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

        /**
         * populate the place list on main page
         */
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
                    last = BB.lastMapPosition.position.googleFormat();
                    console.log(
                            "populateMainListSuccess set map to last" +
                            " map position, lat: " + last.lat());
                }
            if (!last) {
                last = BB.lastGPSPosition.googleFormat();
                console.log("populateMainListSuccess set map to last GPS " +
                    "position, lat: " + last.lat());
            }
            BB.theMap.setCenter(last);

            // update points with distance
            var map_centre = new rayv.LatLng(0, 0).
                loadFromGoogleFormat(BB.theMap.getCenter());
            console.log("distances from Map: " +
                map_centre.lat + ", " +
                map_centre.lng);
            rayv.UserData.places.forEach(function (place) {
                var dist = BB.approx_distance(place, BB.lastGPSPosition);
                place.distance = BB.pretty_dist(dist);
                place.dist_float = dist;
                var map_centre_dist = BB.approx_distance(place, map_centre);
                place.map_dist_float = map_centre_dist;
                place.map_distance = BB.pretty_dist(map_centre_dist);
            });
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
                $('div[data-role=listview]').listview().listview('refresh').
                    trigger('updatelayout');
                $("#splash").hide();
            } catch (e) {
            }

        },

        cuisine_load_categories: function () {
            if (BB.cuisine_categories) {
                console.info('cuisine_load_categories');
                return;
            }
            console.info('cuisine_load_categories Loading...');
            BB.cuisine_categories = [];
            $.get('/getCuisines_ajax',
                {},
                function (data) {
                    var obj = jQuery.parseJSON(data);
                    for (var idx = 0; idx < obj.categories.length; idx++) {
                        BB.cuisine_categories.push(obj.categories[idx])
                    }
                    console.info('cuisine_load_categories Loaded');
                })
        },

        cuisine_setup_categories_picker: function () {
            console.info('cuisine_setup_categories_picker');
            if ($("#new-category-list").find('a').length > 0) {
                return;
            }
            var group = $("#new-category-list"),
                $el;
            group.controlgroup();
            for (var idx = 0; idx < BB.cuisine_categories.length; idx++) {
                $el = $("<a href='#'>" +
                    BB.cuisine_categories[idx] +
                    "</a>").bind("click", BB.cuisine_lookup_click);
                group.controlgroup("container")["append"]($el);
                $el.buttonMarkup();
            }
            group.controlgroup("refresh");
            if (rayv.currentItem.category) {
                $('#new-category-list').hide();
            }
            else {
                $('#new-category-list').show();
            }
        },

        cuisine_show_all_options: function () {
            var lookup = $('#new-category-list');
            lookup.show();
            lookup.find('a').each(function () {
                $(this).show();
            });
        },

        cuisine_keyup: function () {
            var text = $('#new-category').val().toLowerCase();
            var lookup = $('#new-category-list');
            lookup.show();
            lookup.find('a').each(function () {
                if ($(this).text().toLowerCase().indexOf(text) > -1) {
                    $(this).show();
                }
                else {
                    $(this).hide();
                }
            });
        },

        cuisine_lookup_click: function () {
            console.log('cuisine_lookup_click');
            $('#new-category').val($(this).text());
            $('#new-category-list').hide();
        },

        set_edit_page_category: function () {
            console.log('set_edit_page_category = ' + rayv.currentItem.category);
            $("#new-category").val(rayv.currentItem.category);
            if (rayv.currentItem.category) {
                $("#cuisine-lookup").hide();
            }
            BB.cuisine_setup_categories_picker()
        },

        /**
         * Click handler for the list of places on the Add page
         * @param event {event}
         */
        new_places_list_click: function (event) {
            console.log("new_places_list_click");
            //user clicked on a place (or db entry) in the new Shout page
            if ($(this).data("shoutIsMap")) {
                // it's a map item
                //copy the text from the <a> tag to the text box on the
                // New Item page
                var text = $(this).find(".list-item-title").text().trim();
                $("#new-detail-name").val(text);
                $("input[name=new-title]").val(text);
                rayv.currentItem.place_name = text;
                rayv.currentItem.address = $(this).data("address");
                rayv.currentItem.descr = "";
                rayv.currentItem.category = $(this).data("category");
                $("#new-detail-address").val(rayv.currentItem.address);
                // no comment as it's not in db
                $("#new-detail-comment").val("");
                BB.set_edit_page_category();
                rayv.currentItem.key = $(this).data("shoutKey");
                console.log("key set new_places_list_click");
                rayv.currentItem.position = new rayv.LatLng(
                    $(this).data("lat"),
                    $(this).data("lng"));
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
                    $("#new-title-hdg").text(place);
                    rayv.currentItem.place_name = place;
                    $("input[name=new-title]").val(rayv.currentItem.place_name);
                    rayv.currentItem.key = "";
                    console.log("key set new_places_list_click 2");
                    //TODO: What does it mean when the lat and long is zero?

                    //todo: what's the address?
                    rayv.currentItem.address = "";
                    BB.set_edit_page_category();
                }
                $.mobile.changePage("#new-detail");
            }
            // go to the page
        },

        set_distance_for_place: function (pt, from /* opt */) {
            calc_dist_from = from ? from : BB.lastGPSPosition;
            var posn = new rayv.LatLng(pt.lat, pt.lng);
            pt.dist_float = BB.approx_distance(
                posn,
                calc_dist_from);
            var dist_str = BB.pretty_dist(pt.dist_float);
            pt.distance = dist_str;
        }, /**
         * ajax callback on loaded list of possible places to Add
         * @param data {object} server data
         */
        loadPlacesListSuccessHandler: function (data) {
            console.log("loadPlacesListSuccessHandler");
            var obj = $.parseJSON(data);
            var pts = obj.local.points;
            var search_center;
            try {
                search_center = new rayv.LatLng(obj.search.lat, obj.search.lng);
            }
            catch (e) {
                search_center = BB.lastGPSPosition;
            }
            for (var idx = 0; idx < pts.length; idx++) {
                var pt = pts[idx];
                BB.set_distance_for_place(pt, search_center);
            }
            pts.sort(function (a, b) {
                return a.dist_float - b.dist_float
            });
            var el = $("#new-place-list");
            el.html(templates.render(
                'new-place-list-js',
                {'points': obj.local.points}));
            el.trigger("create");
            el.find("ul").find("a").on("click", BB.item_create_lookup_full_address);
            BB.navBarEnable();
            $("#new-place-list-loading").hide();
        },


        navBarDisable: function () {
            BB.navBarActive = false;
        },

        navBarEnable: function () {
            BB.navBarActive = true;
        },

        /**
         * load the list of local places for Add New
         * @param search_text {string}
         */
        loadLocalPlaces: function (search_text) {
            // this is for the "new place" page list -
            //  from google maps and from my db
            console.log("loadLocalPlaces");
            var request = {};
            $("#new-place-list-loading").show();
            console.log("AJAX gotPositionForPlaces");
            BB.navBarDisable();
            request.lat = BB.lastGPSPosition.lat;
            request.lng = BB.lastGPSPosition.lng;
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

        /**
         * save the item being edited
         */
        new_item_save_click: function () {
            // save a new item
            //called from new-detail-page
            if (BB.detail_saving) {
                console.log("new_item_save_click ignored");
                return;
            }
            console.log("new_item_save_click");
            var hasVote = false;
            rayv.currentItem.untried = false;
            rayv.currentItem.vote = 1;
            if ($('#new-item-dislike').hasClass('ui-btn-active')) {
                rayv.currentItem.vote = -1;
                rayv.currentItem.untried = false;
                hasVote = true;
            }
            if ($('#new-item-untried').hasClass('ui-btn-active')) {
                rayv.currentItem.untried = true;
                rayv.currentItem.vote = 0;
                hasVote = true;
            }
            if ($('#new-item-like').hasClass('ui-btn-active')) {
                hasVote = true;
            }
            if (!hasVote) {
                alert('Please vote!');
                BB.detail_saving = false;
                return;
            }

            BB.show_waiting("#details-save-waiting");

            //rayv.currentItem.descr = $("#new-detail-comment").val();
            rayv.currentItem.category = $("#new-category").val();
            if (!rayv.currentItem.category) {
                alert("You must pick a type of cuisine");
                BB.detail_saving = false;
                return;
            }
            rayv.currentItem.address = $("#new-detail-address").val();
            if (rayv.currentItem.address.length == 0) {
                alert('Please enter address');
                BB.detail_saving = false;
                return;
            }
            rayv.currentItem.place_name = $("#new-detail-name").val();
            if (rayv.currentItem.place_name.length == 0) {
                alert('Please enter place name');
                BB.detail_saving = false;
                return;
            }
            rayv.currentItem.descr = $("#new-detail-comment").val();

            if (rayv.currentItem.key == "") {
                //from map or db, use supplied pos
                var pos = rayv.currentItem.position;
                BB.saveItemAtPos(pos);
            }
            else {
                BB.saveCurrentItem();
            }
        },


        /**
         * load the votes from friends into the UL on the detail page
         */
        loadVotes: function () {
            var votes = [];
            rayv.UserData.friends.forEach(function (friend) {
                for (var key in friend.votes) {
                    //noinspection JSUnfilteredForInLoop
                    var vote = friend.votes[key];
                    if (vote == rayv.currentItem.key) {
                        vote.userName = friend.name;
                        votes.push(vote)
                    }
                }
            });
            var context = { votes: votes };
            // https://github.com/adammark/Markup.js/
            var newVoteList = templates.render('item-votes-list', context);
            $("#item-votes-list-container").html(newVoteList);
            $("#item-votes").trigger("create");
            $("#item-votes-collapsible").show();
        },

        /**
         *  click handler for item save button
         */
        updateitem: function () {
            console.log("updateitem");
            rayv.currentItem.descr = $("#item-descr").val();
            rayv.currentItem.vote = null;
            rayv.currentItem.untried = false;
            if ($('#item-dislike').hasClass('ui-btn-active')) {
                rayv.currentItem.vote = -1;
            }
            else if ($('#item-like').hasClass('ui-btn-active')) {
                rayv.currentItem.vote = 1;
            }
            else if ($('#item-untried').hasClass('ui-btn-active')) {
                rayv.currentItem.untried = true;
                rayv.currentItem.vote = 0;
            }
            if (!$.isNumeric(rayv.currentItem.vote)) {
                alert('You need to vote');
                return;
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
            var el = $("#new-place-list").children("ul");
            if (search_for.length > 0) {
                el.children("li").hide();
                el.children("li:" + "contains('Add New')").show();
                el.children('li:contains("' + search_for + '")').show();
            }
            else {
                el.children('li').show();
            }
        },

        /**
         * on change event for the new place lookup
         */
        list_text_filter: function () {
            console.log('list_text_filter');
            var search_for = $("#main-search").val();
            if (search_for.length > 0) {
                // hide all items
                var list = $("#main-list");
                list.children("li").hide();
                // now show those containing our text
                list.children('li:contains("' + search_for + '")').
                    show();
            }
            else {
                $("#main-list").children("li").show();
            }
        },

        /**
         * copy details from the Item page to the New Item age to edit them
         */
        page_to_edit_item: function () {
            // copy over the vals from the item page
            //todo: check for new Item path
            console.log("cat: " + $("#item-category").val());
            rayv.currentItem.loadFromKey();
            var myBook = rayv.UserData.myBook.get();
            if (rayv.currentItem.key in myBook.votes) {
                $("#new-item-delete").show();
            }
            else {
                $("#new-item-delete").hide();
            }
            $("#new-detail-name").val(rayv.currentItem.place_name);
            $("#new-detail-address").val(rayv.currentItem.address);
            BB.set_edit_page_category();
            // add my comment if there is one
            if (myBook.votes[rayv.currentItem.key]) {
                $("#new-detail-comment").val(
                    myBook.votes[rayv.currentItem.key].comment);
            }
            ;
            //set the likes radio
            $('#new-detail-vote a').
                removeClass('ui-btn-hover-b').
                addClass('ui-btn-up-b').
                removeClass('ui-btn-active');
            if (rayv.currentItem.untried) {
                $('#new-item-untried').addClass('ui-btn-active');
            }
            else {
                if (rayv.currentItem.vote >= 0) {
                    $('#new-item-like').addClass('ui-btn-active');
                }
                else {
                    $('#new-item-dislike').addClass('ui-btn-active');
                }
            }
            $("#new-preview-box").
                children("div").
                children("img").
                removeClass("rotr").
                removeClass("rotu").
                removeClass("rotl");
            BB.imageRotation = 0;
            if (rayv.currentItem.img) {
                console.log("Show item image");
                $("#new-preview-box").show();
                var el = $("#new-img").children("img");
                el.attr("src", rayv.currentItem.img);
                el.attr("style", "");
                $("#new-img").show();
            }
            else {
                $("#new-img").hide();
            }
        },


        /**
         * map-search key press event
         * @param e {event}
         */
        map_search_key: function (e) {
            var el = $("#map-search");
            if (el.val().length == 0) {
                $("#googlemapsjs1").show();
                $("#map-search-btn-box").hide();
            } else
                $("#map-search-btn-box").show();
            // if it's return do the search
            if (e.which == 13 || (e.which == 8 && el.val().length == 0 )) {
                console.log("map_search_key: 13");
                $("#googlemapsjs1").hide();
                //hide keyboard
                document.activeElement.blur();
                $("#map-search-btn").hide();
                $("input").blur();
                //load results
                BB.populateMainList($("#map-search").val());
                $("#map-list-loading").show();
            }
        },


        /**
         * show the map page, centered on the current item
         */
        showItemOnMap: function () {
            BB.lastMapPosition.position = rayv.currentItem.position;
            google.maps.event.trigger(BB.theMap, 'resize');
            BB.lastMapPosition.isSet = true;
            BB.lastMapPosition.zoomIn = true;
            $.mobile.changePage("#map-page");
        },

        /**
         * open the web page associated with the place
         */
        showItemWebPage: function () {
            window.location = rayv.currentItem.website;
        },

        /**
         * center map on the current item
         * called on marker click
         */
        showAnotherItemOnMap: function () {
            BB.lastMapPosition.position = rayv.currentItem.position;
            BB.populateMainList("");
            BB.lastMapPosition.isSet = true;
            BB.lastMapPosition.zoomIn = false;
            BB.pageToMap();
        },

        /**
         * redo distances and order on map drag
         */
        dragMap: function () {
            // centered on the map
            BB.lastMapPosition.position =
                new rayv.LatLng(0, 0).loadFromGoogleFormat(BB.theMap.getCenter());
            BB.populateMainList("");
            BB.lastMapPosition.isSet = true;
            BB.lastMapPosition.zoomIn = false;
            BB.map_centred = false;
            BB.pageToMap();
        },

        /**
         * work out image rotation change on details page
         * @param e {event}
         */
        imageRotate: function (e) {
            e.preventDefault();
            BB.imageRotation = (BB.imageRotation + 1) % 4;
            var img = $("#new-preview-box").children("div").children("img");
            switch (BB.imageRotation) {
                case 0:
                    //original
                    img.removeClass("rotr").
                        removeClass("rotu").
                        removeClass("rotl");
                    rayv.currentItem.rotation = 0;
                    break;
                case 1:
                    //right
                    img.removeClass("rotl").
                        removeClass("rotu").
                        addClass("rotr");
                    rayv.currentItem.rotation = 1;
                    break;
                case 2:
                    // invert
                    img.removeClass("rotl").
                        removeClass("rotr").
                        addClass("rotu");
                    rayv.currentItem.rotation = -2;
                    break;

                case 3:
                    //left
                    img.removeClass("rotr").
                        removeClass("rotu").
                        addClass("rotl");
                    rayv.currentItem.rotation = -1;
                    break;

            }
        },


        pageToList: function (event) {
            console.log("PAGE list");

            if (BB.navBarActive) {
                BB.populateMainList("");
                $("#list-loading").hide();
                var search = $("#main-search")
                search.off('keyup change', BB.list_text_filter);
                search.on('keyup change', BB.list_text_filter);
            }
            else
                event.preventDefault();
        },

        imagePreview: function () {
            var oFReader = new FileReader();
            try {
                //todo: what this?
                oFReader.readAsDataURL(this.files[0]);
            }
            catch (e) {
                $('#image-dialog').popup('close')
            }
            console.log(this.files[0]);
            oFReader.onload = function (oFREvent) {
                var img = $("#new-preview-box").children("div").children("img");
                img.html(
                        '<img height="150" ' +
                        'id="new-image" ' +
                        'data-inline="true" ' +
                        'src="' + oFREvent.target.result + '">');
                $('#new-preview-box').show();
                img.attr('src', oFREvent.target.result);
                // show the preview
                $("#new-img").show();
                try {
                    $('#image-dialog').popup('close')
                } catch (e) {
                }
            };

        },


        pageToMap: function () {
            console.log("PAGE map");
            if (BB.navBarActive) {
                BB.set_map_column_filter("all");
                $("#map-list-loading").show();
                $("#map-search-btn").hide();
                $("#map-search").val("");
                var last;
                if (BB.lastMapPosition.isSet) {
                    last = BB.lastMapPosition.position.googleFormat();
                    console.log("set map to last position, lat: " + last.lat());
                    try {
                        BB.theMap.setCenter(last);
                        BB.map_centred = false;
                        console.log(
                                "set map (1) to last position, lat: " +
                                last.lat());
                        if (BB.lastMapPosition.zoomIn) {
                            BB.theMap.setZoom(18);
                            BB.lastMapPosition.zoomIn = false;
                        }
                    }
                    catch (e) {
                        console.log("MAIN MAP NOT SET")
                    }
                } else {
                    last = BB.lastGPSPosition.googleFormat();
                    console.log("set map (2) to last position, lat: " +
                        last.lat());
                    try {
                        BB.theMap.setCenter(last);
                        if (BB.lastMapPosition.zoomIn) {
                            BB.theMap.setZoom(18);
                            BB.lastMapPosition.zoomIn = false;
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
                BB.populateMainList("");
            }
            else
                event.preventDefault();
        },

        pageToNewPlace: function (event, previousPage) {
            console.log("PAGE new place");
            if (BB.navBarActive) {
                $('#new-preview-box').hide();
                $("#new-place-near").hide();
                $("#new-search-place-btn").hide();
                if (previousPage == "new-detail") {
                    //don't reload
                    console.log("PAGE new place - no reload")
                }
                else {
                    BB.loadLocalPlaces(null);
                    $("input[name=new-title]").val("");
                }
            }
            else
                event.preventDefault();
        },

        pageToImage: function () {
            $("#image-img").children("img").attr("src", rayv.currentItem.img);
            $("#image-header").text(rayv.currentItem.place_name);
        },

        ItemLoadPage: function () {
            console.log('ItemLoadPage');
            rayv.currentItem.key = $(this).data('key');
            console.log("key set ItemLoadPage");
            $.mobile.changePage("#item-page")
        },

        /**
         * on error handler for list images
         * The cache is assumed to be dirty
         */
        imageLoadErrorHandler: function () {
            console.info('imageLoadErrorHandler');
            var key = $(this).parent().parent().parent().data('key');
            $.get(
                    '/item/' + key,
                {},
                function (res) {
                    BB.update_item_from_server(res)

                },
                'json');
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

        create_name_validate: function (e) {
            var addr = $("#dragged-address").text();
            if (addr.length > 0 && $('#create-name').val().length > 0) {
                $("#create-new-save-btn").removeClass("ui-disabled")
            } else {
                $("#create-new-save-btn").addClass("ui-disabled")
            }
        },
        pageToCreateAddress: function () {
            //init map
            console.log('pageToCreateAddress');
            if (!BB.creatorMap) {
                var mapOptions = {
                    zoom: 15,
                    center: BB.lastGPSPosition.googleFormat()
                };
                BB.creatorMap = new google.maps.Map(
                    document.getElementById('find-on-map-div'),
                    mapOptions);
                google.maps.event.addListener(
                    BB.creatorMap, 'dragend', BB.dragCreatorMap);
            }
            else {
                BB.creatorMap.setCenter(
                    BB.lastGPSPosition.googleFormat());
            }
            $("#create-name").val($("#new-place-name-box").val());
            var $addr = $("#dragged-address");
            $addr.text('');
            $addr.hide();
            $("#create-new-save-btn").addClass("ui-disabled")
        },

        clearItemPage: function () {
            $("#item-img").children("img").attr("src", "");
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
            if (rayv.currentItem.key) {
                console.log("pageToItem");
                //todo: check for new Item path
                // if we have come from the image page,
                // the image should be shown on the item page too
                if (previousPage == "image-page")
                    $("#item-img").show();
                //$("#item-img").show();
                rayv.currentItem.loadFromKey();
                $("#item-title").html(rayv.currentItem.place_name);
                $("#item-address").html(rayv.currentItem.address);
                $("#item-category").html(rayv.currentItem.category);
                if (rayv.currentItem.telephone) {
                    var phone = $("#item-phone-link");
                    phone.attr('href', 'tel:' + rayv.currentItem.telephone);
                    phone.show();
                }
                else {
                    $("#item-phone-link").hide();
                }
                if (rayv.currentItem.website) {
                    $("#item-web-link").show();
                }
                else {
                    $("#item-web-link").hide();
                }

                $("#item-title-2").html(rayv.currentItem.place_name);
                var comment = rayv.UserData.get_my_comment(rayv.currentItem.key);
                var comment_header = comment;

                if (comment.length == 0) {
                    comment_header = "Friends' Comments / Tips";
                }

                var $btn_text = $("#item-comment-btn").
                    find("a").
                    find(".ui-btn-text");
                var $btn_child = $btn_text.find(
                    '.ui-collapsible-heading-status');
                //overwrite the header text, then append its
                // child to restore the previous structure
                $btn_text.text(comment_header).append($btn_child);

                $("#item-descr").val(comment);

                // friends' comments
                $("#item-comments").html();
                var votes = rayv.UserData.get_votes_for_item(
                    rayv.currentItem.key);
                var html = "";
                votes.forEach(function (vote) {
                    if (vote.vote.comment.length > 0) {
                        html += templates.render('friend-comment-template', vote);
                    }
                });
                $("#item-comments").html(html);

                $("#item-distance").html(rayv.currentItem.distance);

                //set the likes radio
                $('#item-page-votes').find('li').find('a').removeClass('ui-btn-hover-b').
                    addClass('ui-btn-up-b').removeClass('ui-btn-active');
                if (rayv.currentItem.untried) {
                    $('#item-untried').addClass('ui-btn-active');
                }
                else {
                    var vote = rayv.currentItem.vote;
                    if ($.isNumeric(vote)) {
                        if (vote > 0) {
                            $('#item-like').addClass('ui-btn-active');
                        }
                        else {
                            $('#item-dislike').addClass('ui-btn-active');
                        }
                    }
                }
                var img = $("#item-img");
                if (rayv.currentItem.img) {
                    console.log("Show item image");
                    img.show();
                    img.children("img").attr("src", rayv.currentItem.img);
                    img.children("img").attr("style", "");
                }
                else {
                    //$("#item-img").hide();
                    img.children("img").attr(
                        "src", '/static/images/no-image.png');
                    img.children("img").attr("style", "");
                }
                if (rayv.currentItem.key in rayv.UserData.myBook.get().votes) {
                    $("#item-delete").show();
                }
                else {
                    $("#item-delete").hide();
                }
                $('#item-votes-inner').
                    trigger('collapse').
                    trigger('updatelayout');
                $("#vote-cursor").val("");
                $("#item-votes").html("");
                BB.loadVotes()
            }
        },

        mapSearchClick: function () {
            BB.map_search_key({"which": 13});
        },

        clickColumnHeader: function () {
            // click a column header on the list page
            BB.filter = BB.get_list_column_filter();
            BB.populateMainList("", 0, 0);
        },
        clickMapColumnHeader: function () {
            // click a column header on the list page
            BB.filter = BB.get_map_column_filter();
            BB.populateMainList("", 0, 0);
        },

// proper case function (JScript 5.5+)
        toProperCase: function (s) {
            return s.toLowerCase().replace(/^(.)|\s(.)/g,
                function ($1) {
                    return $1.toUpperCase();
                });
        },

        item_create_lookup_full_address: function () {
            var properTitle = BB.toProperCase($(this).data('title'));
            $("#new-detail-name").val(decodeURIComponent(properTitle));
            $("#new-detail-address").val($(this).data('address'));
            $("#new-category").val('');
            BB.cuisine_setup_categories_picker();
            $("#new-detail-comment").val("");

            //set the likes radio
            $("#new-detail-vote").find("a").
                removeClass('ui-btn-hover-b').
                addClass('ui-btn-up-b').
                removeClass('ui-btn-active');
            $('#new-item-like').addClass('ui-btn-active');
            $("#new-preview-box").hide();
            rayv.currentItem.key = $(this).data('key');
            rayv.currentItem.position = new rayv.LatLng(
                $(this).data('lat'),
                $(this).data('lng'));
            rayv.currentItem.place_name = properTitle;
            var id = $(this).data('place_id');
            var request = {
                placeId: id
            };
            if (!BB.creatorMap) {
                BB.pageToCreateAddress();
            }
            var service = new google.maps.places.PlacesService(BB.creatorMap);
            service.getDetails(request, BB.item_create);
        },
        /**
         * load a place for edit when it comes from a geo search on Add New
         */
        item_create: function (place, status) {
            if (status == google.maps.places.PlacesServiceStatus.OK) {
                rayv.currentItem.address = place.formatted_address;
                $("#new-detail-address").val(place.formatted_address);
            }
            else {
                rayv.currentItem.address = $(this).data('address');
            }
            console.log('item_create');
            $.mobile.changePage('#new-detail')
        },

        /**
         * Look up the places near an address
         * @param event
         */
        lookupAddressList: function (event) {
            var addr;
            $("#new-place-list-loading").show();
            function lookAddressList_inner(obj) {
                try {
                    BB.check_for_dirty_data(obj);
                    var search_center;
                    try {
                        search_center = new rayv.LatLng(obj.search.lat, obj.search.lng);
                    }
                    catch (e) {
                        search_center = BB.lastGPSPosition;
                    }
                    for (var idx = 0; idx < obj.local.points.length; idx++) {
                        var pt = obj.local.points[idx];
                        BB.set_distance_for_place(pt, search_center);
                    }
                    obj.local.points.sort(function (a, b) {
                        return a.dist_float - b.dist_float;
                    });
                    var context = {'items': obj.local.points};
                    var UIlist = templates.render(
                        'add-search-nearby-template',
                        context);
                    $("#new-place-list").
                        html(UIlist).listview().
                        trigger('create').
                        trigger('updatelayout');
                    $(".found-address").on(
                        "click",
                        BB.item_create_lookup_full_address);
                    $("#manual-address-lookup").val(rayv.currentItem.address);
                }
                catch (e) {
                    console.error("lookupAddressList");
                }
                $("#new-place-list-loading").hide();
            }


            function lookupAddressListSuccessHandler(data) {
                $("#search-location-loading").hide();
                $("#new-place-list-loading").hide();
                //$.mobile.changePage("#new-address-list-page");
                $("#new-place").find("ul").remove();
                lookAddressList_inner(jQuery.parseJSON(data));
            }

            function lookupAddressListErrorHandler() {
                $("#search-location-loading").hide();
                $("#new-place-list-loading").hide();
                console.log("no address found");
                alert("Not Found");
                $("#new-page").find("ul").remove();
                $("#create-new-address-box").show();
                // string to be parsed
                lookAddressList_inner({items: []});
            }

            console.log("AJAX lookupAddressList");
            addr = rayv.currentItem.address;
            var request = {};
            request.lat = BB.lastGPSPosition.lat;
            request.lng = BB.lastGPSPosition.lng;
            request.addr = addr;
            // get the place name from the new screen
            request.place_name = $("#new-place-name-box").val();
            if (event || event.currentTarget.id == "new-search-place-btn") {
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
            rayv.currentItem.address = "";
            BB.lookupAddressList(event);
        },

        lookupManualAddress: function (event) {
            rayv.currentItem.address = $("#new-place-near").val();
            BB.lookupAddressList(event);
        },

        add_search_name: function () {
            //lookup a place by name in the add page
            rayv.currentItem.place_name = $("#new-place-name-box").val();
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
            var addr = $("#dragged-address").text();
            if (addr.length > 0 && $('#create-name').val().length > 0) {
                rayv.currentItem.clear();
                rayv.currentItem.place_name = $("#create-name").val();
                rayv.currentItem.address = addr;
                rayv.currentItem.position =
                    new rayv.LatLng(0, 0).
                        loadFromGoogleFormat(BB.creatorMap.getCenter());
                BB.page_to_edit_item();
                $.mobile.changePage("#new-detail");
            } else {
                $("#create-new-save-btn").addClass("ui-disabled")
            }

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

        /**
         * delete an item - means remove my vote for it
         */
        itemDelete: function () {
            //delete the current item
            //is it in my list?
            if (rayv.currentItem.key in rayv.UserData.myBook.get().votes) {
                if (confirm("Remove place from your list?")) {
                    $.ajax(
                        {url: '/item/del/' + rayv.currentItem.key,
                            type: 'post',
                            success: function () {
                                $.mobile.changePage("#list-page");
                                rayv.UserData.load(BB.populateMainList);
                            }})
                }
            }
        },

        /**
         * set the main list filter
         * @param val
         */
        set_list_column_filter: function (val) {
            var filter = $("#filter-radio");
            filter.find("input[type='radio']").attr("checked", null);
            filter.find("input[type='radio'][value='" + val + "']").attr(
                "checked", "checked");
            filter.find("input[type='radio']").
                checkboxradio().
                checkboxradio("refresh");
        },

        /**
         * set the main list filter
         * @param val
         */
        set_map_column_filter: function (val) {
            var filter = $("#map-filter-radio");
            filter.find("input[type='radio']").attr("checked", null);
            filter.find("input[type='radio'][value='" + val + "']").attr(
                "checked", "checked");
            filter.find("input[type='radio']").
                checkboxradio().
                checkboxradio("refresh");
        },

        /**
         * Which filter is selected for the main list?
         * @returns {string} the name of the filter
         */
        get_list_column_filter: function () {
            return $("#filter-radio").find("input:checked").val();
        },
        /**
         * Which filter is selected for the MAP list?
         * @returns {string} the name of the filter
         */
        get_map_column_filter: function () {
            return $("#map-filter-radio").find("input:checked").val();
        },

        set_test_location: function () {
            if ($(this).val() == 'on') {
                BB.use_test_location = true;
                BB.test_lat = parseFloat($("#test-lat").val());
                BB.test_lng = parseFloat($("#test-lng").val());
                BB.lastGPSPosition = new rayv.LatLng(
                    BB.test_lat,
                    BB.test_lng);
            }
            else {
                BB.use_test_location = false;
            }
        },


        /**
         * check comment has no more characters than allowed (140)
         * on details page
         */
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

        /**
         * got gps pos
         * @param pos
         */
        watchPositionSuccess: function (pos) {
            console.log("watchPositionSuccess: " +
                pos.coords.latitude + "," +
                pos.coords.longitude);
            BB.lastGPSPosition = new rayv.LatLng(
                pos.coords.latitude,
                pos.coords.longitude);
            var now = new Date();
            if (now - BB.lastGPSTime > (2 * BB.watchPositionOptions.maximumAge)) {
                BB.watch_position_id = navigator.geolocation.watchPosition(
                    BB.watchPositionSuccess,
                    BB.watchPositionError,
                    BB.watchPositionOptions);
            }
            BB.lastGPSTime = now;
            if (BB.isMapPage() && BB.map_centred) {
                BB.map_center();
            }
        },

        /**
         * couldn't get gps
         * @param err
         */
        watchPositionError: function (err) {
            console.warn(
                    'watchPositionError ERROR(' +
                    err.code + '): ' +
                    err.message);
            navigator.geolocation.getCurrentPosition(
                BB.firstWatchPositionSuccess,
                BB.watchPositionError,
                BB.watchPositionOptions);
        },

        /**
         * got first gps pos
         * @param pos
         */
        firstWatchPositionSuccess: function (pos) {
            BB.watchPositionSuccess(pos);
            BB.init();
            BB.loadUserData();
        },

        /**
         * save user profile
         */
        save_profile: function () {
            $.post(
                '/user_profile',
                {'screen_name': $('#settings-screen-name').val()},
                function (data) {
                    alert('Saved');
                });
        },

        /**
         * for Add New - search near a place, show the box to type it in
         */
        set_search_to_near_place: function () {
            var radios = $("#new-select").find("input[type='radio']");
            radios.attr("checked", "");
            $("#new-search-radio-place").attr("checked", "checked");
            radios.checkboxradio("refresh");
        },

        /**
         * are we adding near me, or near a place?
         * @param e {event}
         */
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
        goto_external: function () {
            window.location.hash = "";
        },


        /***
         * clear the local storager then logout
         */
        logout: function () {
            window.localStorage.clear();
            window.location = '/logout';
        },
        /**
         * event listeners
         */
        setupListeners: function () {
            $("#new-shout-form").submit(BB.saveItemAtPos);
            //when the cam icon is clicked, send a click to the file input widget
            $("#new-item-camera-img").on("click", BB.take_photo_click);
            $("#camera-dlg-btn").on("click", BB.take_photo_click);
            $("#file-dlg-btn").on("click", BB.open_image_file_click);
            //$("#item-camera-img").on("click",  take_photo_click);
            //hide the default one
            var img_input = $("#image-input");
            img_input.hide();
            img_input.change(BB.imagePreview);
            $("div").find("[data-controltype='camerainput']").hide();
            //vote buttons
            $("#refresh-btn").on("click", BB.fullLoadUserData);

            $("#create-new-save-btn").on("click", BB.do_create_new_address);
            $("#create-new-address-btn").on(
                "click", BB.show_create_new_address);
            $("#new-item-li").on("click", BB.show_create_new_address);
            $("#item-edit").on("click", BB.editItem);
            $("#new-rotr").on("click", BB.imageRotate);
            $("#new-address-next-btn").on("click", BB.lookupManualAddress);
            $("#enter-new-addr-btn").on("click", BB.lookupManualAddress);
            $("#new-address-my-locn-btn").on("click", BB.lookupMyAddress);
            $("#forgot-btn").attr("data-ajax", "false");
            BB.set_list_column_filter('mine');
            $("#filter-radio").on("change", BB.clickColumnHeader);
            $("#map-filter-radio").on("change", BB.clickMapColumnHeader);
            $("#sort-dist").addClass("list-sort-selected");
            $("#new-place-name-box").on('change input', BB.place_search_by_name);
            $("#new-place-near").on('keyup', BB.set_search_to_near_place);
            $("#new-search-place-btn").click(BB.lookupManualAddress);
            $("#new-top-controls").find("input[type='radio']").bind("change",
                BB.add_search_radio_change);
            // edit item btn hidden by default. Shown if you own it
            // event handler for map search box on map-page
            $("#map-search").keyup(BB.map_search_key);
            $("#item-see-map").on("click", BB.showItemOnMap);
            $("#item-web-link").on("click", BB.showItemWebPage);
            $("#new-item-save").on("click", BB.new_item_save_click);
            $("#item-save").on("click", BB.updateitem);
            $('#new-preview-box').hide();
            //on click map search btn, simulate Enter key in search box
            $("#map-search-btn").on("click", BB.mapSearchClick);
            $("#map-search-btn-box").on("click", BB.mapSearchClick);
            $("#map-search-btn-box").hide();
            var search_box = $("#main-search");
            search_box.on('keyup change', BB.list_text_filter);
            $("#item-delete").on("click", BB.itemDelete);
            $("#new-item-delete").on("click", BB.itemDelete);
            search_box.parent().removeClass('ui-body-a').addClass('ui-body-b');
            search_box.removeClass('ui-body-a').addClass('ui-body-b');
            $("#test-loc-set").change(BB.set_test_location);
            $('#item-descr').keypress(BB.comment_validate);
            $('#create-name').keypress(BB.create_name_validate);
            $("#settings-save-profile").click(BB.save_profile);
            $("#new-search-title-btn").click(BB.add_search_name);
            $("#new-search-name-btn").click(BB.lookupMyAddress);
            $('#new-category').keyup(BB.cuisine_keyup);
            $('#cuisine-lookup').click(BB.cuisine_lookup_click);
            $('#item-web-link').click(BB.goto_external);
            $('#logout-btn').click(BB.logout);
            var app_cache = window.applicationCache;
            if (app_cache) {
                $(app_cache).bind(
                    "updateready",
                    function (event) {
                        // This gets fired when new cache files have been downloaded
                        // and are ready to replace the *existing* cache. The old
                        // cache will need to be swapped out.
                        console.info("New cache available - RELOAD");
                        // Swap out the old cache.
                        app_cache.swapCache();
                        window.location.reload();
                    }
                );
            }


            /*window.onerror = function errorHandler(msg, url, line) {
             alert(msg + ": " + line);
             // Just let default handler run.
             return false;
             }*/
        },


        loadUserData: function () {
            rayv.UserData.load(
                function () {
                    BB.populateMainList("");
                });
        },

        fullLoadUserData: function () {
            rayv.UserData.lastUpdate.set(0);
            BB.loadUserData();
        }
    }
    ;


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
                    BB.hide_waiting();
                    if (rayv.currentItem.key) {
                        BB.page_to_edit_item();
                    }
                    break;
                case "item-page":
                    BB.pageToItem(event, previousPage);
                    break;
                case "create-new-address":
                    BB.pageToCreateAddress(event, previousPage);
                    break;
                case "new-address-list-page":
                    $("#new-addresses-list").
                        trigger('create').
                        trigger('updatelayout');
                    try {
                        $("#new-addresses-list").listview('refresh');
                    } catch (e) {
                    }
                    break;
                case "settings-page":
                    $.get('/user_profile', {}, function (data) {
                        $("#settings-screen-name").
                            val(jQuery.parseJSON(data).screen_name);
                    });
                    break;
            }
        }

        function beforePageShow(event, data) {
            //some pages are ones you mustn't land on from
            // outside as they need loading
            console.log("beforePageShow " +
                data.prevPage.attr("id") + ">" +
                event.target.id);
            if (event.target.id == "item-page") {
                BB.clearItemPage();
            }
            if ((event.target.id == "item-page") ||
                (event.target.id == "map-page") ||
                (event.target.id == "new-detail") ||
//            (event.target.id == "new-page") ||
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
//
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

        // change the default jquery "contains" selector so
        // it matches case insensitive
        // from: http://css-tricks.com/snippets/jquery/
        // make-jquery-contains-case-insensitive/
        $.expr[":"].contains = $.expr.createPseudo(function (arg) {
            return function (elem) {
                return $(elem).text().toUpperCase().indexOf(arg.toUpperCase()) >= 0;
            };
        });


        if (!navigator.geolocation) {
            console.error("$. NEED GEO");
            alert("LBS Are Off");
            //todo: Note: jQuery.mobile.changePage is deprecated as of
            // jQuery Mobile 1.4.0 and will be removed in 1.5.0. Use the
            // pagecontainer widget's change() method instead.
            //   $( ":mobile-pagecontainer" ).pagecontainer(
            // "change", "need-geo.html");
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
            navigator.geolocation.getCurrentPosition(
                BB.firstWatchPositionSuccess,
                BB.watchPositionError,
                BB.watchPositionOptions)
        }
        BB.cuisine_load_categories();
        BB.setupListeners();
        console.log("JS Init'd");
        $("#loading").html('.');

    }
)
;

