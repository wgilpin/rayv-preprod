from operator import itemgetter
import urllib
import urllib2
import datetime
from google.appengine.api import images, memcache
from google.appengine.api.app_identity import app_identity
from google.appengine.api.mail import EmailMessage
from google.appengine.ext import db
from webapp2_extras import auth
from google.appengine.ext.webapp import template
from auth_logic import BaseHandler
import json
import os.path
from auth_model import memcache_get_user_dict, memcache_touch_user, UserProfile, \
  memcache_put_user_dict, memcache_touch_place, User
from dataloader import load_data
from models import Item, DBImage, itemToJSONPoint, Vote, LatLng, Category, findDbPlacesNearLoc, \
  itemKeyToJSONPoint, approx_distance
from profiler import profile_in, profile_out
import settings
import logging
from webapp2_extras.auth import InvalidAuthIdError
from webapp2_extras.auth import InvalidPasswordError

__author__ = 'Will'


def logged_in():
  """ True if logged in
  @return: bool
  """
  user = session_auth = auth.get_auth()
  if session_auth.get_user_by_session():
    return user
  else:
    return False


def map_and_db_search(exclude_user_id, filter_kind, include_maps_data, lat, lng, my_locn, text_to_search, user_id):
  search_filter = {
    "kind": filter_kind,
    "userId": user_id,
    "exclude_user": exclude_user_id}
  calc_dist_from = my_locn if include_maps_data else None
  list_of_place_names = []
  points = findDbPlacesNearLoc(
    my_locn,
    search_text=text_to_search,
    filter=search_filter,
    uid=user_id,
    position=calc_dist_from,
    place_names=list_of_place_names,
    ignore_votes=True)
  if include_maps_data:
    googPts = get_google_db_places(lat, lng, text_to_search, 5000)
    includeList = []
    # todo: step through both in sequence
    try:
      for gpt in googPts["items"]:
        if gpt["place_name"] in list_of_place_names:
          continue
        includeList.append(gpt)
    except Exception, e:
      pass
    # points["points"] = []
    #points["count"] = 0
    # todo: this returns all items - limit?
    for gpt in includeList:
      jPt = itemToJSONPoint(gpt,my_locn)
      points["points"].append(jPt)
      points["count"] += 1

    sorted_results = points["points"]
    # this is sorted as the client doesnt for map items
    sorted_results.sort(key=itemgetter('distance_map_float'))
    points["points"] = sorted_results
  result = {"local": points}
  return result


def get_item_list(request, include_maps_data, user_id, exclude_user_id=None):
  """ get the list of item around a place
  @param request:
  @param include_maps_data: bool: include data from google maps?
  @param user_id:
  @return: list of JSON points
  """
  around = LatLng(lat=float(request.get("lat")),
                  lng=float(request.get("lng")))
  try:
    my_locn = LatLng(lat=float(request.get("myLat")),
                     lng=float(request.get("myLng")))
  except Exception, E:
    # logging.exception("get_item_list " + str(E))
    my_locn = around
  lat = my_locn.lat
  lng = my_locn.lng
  text_to_search = request.get("text")
  # by default we apply no filter: return all results
  search_filter = None
  filter_kind = request.get("filter")
  return map_and_db_search(exclude_user_id, filter_kind, include_maps_data, lat, lng, my_locn, text_to_search, user_id)


class getItems_Ajax(BaseHandler):
  def get(self):
    """ get the items for a user
    @return:
    """
    profile_in("getItems_Ajax")
    if logged_in():
      result = get_item_list(self.request, False, self.user_id)
      check_for_dirty_data(self.user_id, result)
      json.dump(result,
                self.response.out)
    else:
      self.error(401)
    profile_out("getItems_Ajax")


class getBook(BaseHandler):
  def get(self):
    if logged_in():
      voter_id = self.request.get("voter") if "voter" in self.request.params else str(self.user_id)
      vote_list = Vote.all().filter("voter =", voter_id)
      result = []
      for vote in vote_list:
        it = vote.Item
        result.append(itemKeyToJSONPoint(it.key()))
      json.dump({"points": result,
                 "length": len(result)},
                self.response.out)
    else:
      self.error(401)


def get_user_votes(friend, current_user):
  try:
    profile_in("get_user_votes")
    entry = {}
    friend_vote_list = Vote.all().filter("voter =", friend)
    for user_vote in friend_vote_list:
      vote_detail = {"vote": user_vote.vote,
                     "untried": user_vote.untried,
                     "comment": user_vote.comment
      }
      entry[str(user_vote.item.key())] = vote_detail
    profile_out("get_user_votes")
    return entry
  except Exception, e:
    logging.error("get_user_votes Exception")
    logging.error("get_user_votes Exception " + str(e))


def serialize_user_details(user_id, places, current_user):
  """ give the list of votes & places for a user
  @param user_id: int: which user
  @param places: dict: list of places indexed by key (BY VALUE)
  @param current_user: int: current user - if same as user_id then we exclude untried
  @return:
  """
  try:
    user_dict = memcache_get_user_dict(user_id)
    if 'v' in user_dict:
      votes = user_dict['v']
    else:
      votes = get_user_votes(user_id, current_user)
      user_dict['v'] = votes
      memcache_put_user_dict(user_dict)
    if user_id != current_user:
      to_be_removed = []
      for vote in votes:
        if votes[vote]['untried']:
          to_be_removed.append(vote)
      for idx in to_be_removed:
        del votes[idx]

    last_write = user_dict['p'].last_write if hasattr(user_dict['p'], 'last_write') else None
    result = {"votes": votes,
              "id": user_id,
              # todo is it first_name?
              'name': user_dict['u'].screen_name,
              'last_write': last_write}
    for place_key in votes:
      if not place_key in places:
        place_json = itemKeyToJSONPoint(place_key)
        place_json['vote'] = votes[place_key]['vote']
        place_json['untried'] = votes[place_key]['untried']
        places[place_key] = place_json
    return result
  except Exception, e:
    logging.error("serialize_user_details Exception")
    logging.error("serialize_user_details Exception " + str(e))


class getFullUserRecord(BaseHandler):
  def get(self):
    my_id = self.user_id
    if my_id:
      profile_in("getFullUserRecord")
      user = memcache_get_user_dict(my_id)
      if user:
        # logged in
        # is it for a specific user?
        for_1_user = long(self.request.get("forUser")) if "forUser" in self.request.params else None
        # either the first lookup is for me, plus everyone, or it is for a specified user
        result = {"id": my_id}
        if for_1_user:
          first_user = for_1_user
          result["for_1_user"] = for_1_user
        else:
          first_user = self.user_id
        places = {}
        # load the data for the 1 user  - me or specified
        friends_data = [serialize_user_details(first_user, places, my_id)]
        # was it for all users? If so we've only done ourselves
        if not for_1_user:
          # for all users
          prof = user['p']
          if settings.config['all_are_friends']:
            for userProf in UserProfile().all():
              if userProf.userId == my_id:
                continue  # don't add myself again
              friends_data.append(serialize_user_details(userProf.userId, places, my_id))
          else:
            for friend in prof.friends:
              friends_data.append(serialize_user_details(friend, places, my_id))
          result["friendsData"] = friends_data
        result["places"] = places
        # encode using a custom encoder for datetime


        json.dump(result,
                  self.response.out,
                  default=json_serial)
        profile_out("getFullUserRecord")
        return
    self.error(401)


class user_profile(BaseHandler):
  def get(self):
    user = auth.get_auth().get_user_by_session()
    user_obj = User().get_by_id(user['user_id'])
    json.dump({'screen_name': user_obj.screen_name}, self.response.out)

  def post(self):
    user = auth.get_auth().get_user_by_session()
    user_obj = User().get_by_id(user['user_id'])
    user_obj.screen_name = self.request.get('screen_name')
    user_obj.put()

def json_serial(o):
  """JSON serializer for objects not serializable by default json code
     http://stackoverflow.com/questions/11875770/how-to-overcome-datetime-datetime-not-json-serializable-in-python"""
  if type(o) is datetime.date or type(o) is datetime.datetime:
    return o.isoformat()


def get_google_db_places(lat, lng, name, radius):
  url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?radius=%d&types=food|restaurant|bar|cafe|meal_delivery|meal_takeaway&location=%f,%f&name=%s&sensor=false&key=%s" % \
        (radius, lat, lng, name, settings.config['google_api_key'] )
  response = urllib2.urlopen(url)
  jsonResult = response.read()
  addressResult = json.loads(jsonResult)
  results = {"item_count": 0,
             "items": []}
  addresses = []
  if addressResult['status'] == "OK":
    origin = LatLng(lat=lat, lng=lng)
    for r in addressResult['results']:
      if "formatted_address" in r:
        address = r['formatted_address']
      else:
        address = r['vicinity']
      distance = approx_distance(r['geometry']['location'], origin)
      detail = {'place_name': r['name'],
                'address': address,
                'distance_map_float': distance,
                "lat": r['geometry']['location']['lat'],
                "lng": r['geometry']['location']['lng']}
      addresses.append(detail)
      results["item_count"] += 1
    results['items'] = addresses
    return results
  else:
    logging.error("get_google_db_places near [%f,%f]: %s" % (lat, lng, addressResult['status']))
    return []


def check_for_dirty_data(user_id, results):
  # every server call, we look for dirty data and append it if needed
  prof = memcache_get_user_dict(user_id)['p']
  my_last_check = prof.last_read
  dirty_friends = []
  dirty_places = {}
  for friend in prof.friends:
    if (not my_last_check) or (memcache_get_user_dict(friend)['p'].last_write > my_last_check):
      dirty_friends.append(serialize_user_details(friend, dirty_places, user_id))
  if len(dirty_friends) > 0:
    results['dirty_list'] = {"friends": dirty_friends,
                             "places": dirty_places}


class getAddresses_ajax(BaseHandler):
  def get(self):
    address = self.request.get("addr")
    lat = float(self.request.get("lat"))
    lng = float(self.request.get("lng"))
    names = self.request.get("place_name").split(" ")
    near_me = self.request.get("near_me")
    if near_me == u'0':
      # near the address
      url = "https://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor=false&key=%s" % \
            (urllib2.quote(address), settings.config['google_api_key'])
      response = urllib2.urlopen(url)
      jsonResult = response.read()
      addressResult = json.loads(jsonResult)
      if addressResult['status'] == "OK":
        lat = addressResult['results'][0]['geometry']['location']['lat']
        lng = addressResult['results'][0]['geometry']['location']['lng']
    results = map_and_db_search(-1, '', True, lat, lng, LatLng(lat=lat, lng=lng), names[0], self.user_id)
    if results:
      check_for_dirty_data(self.user_id, results)
      json.dump(results,
                self.response.out,
                default=json_serial)
    else:
      # logging.info("get_google_db_places near [%f,%f]: %s" % (lat, lng, "none found"))
      logging.debug("getAddresses_ajax - none found ")
      self.error(401)


def handle_error(request, response, exception):
  if request.path.startswith('/json'):
    response.headers.add_header('Content-Type', 'application/json')
    result = {
      'status': 'error',
      'status_code': exception.code,
      'error_message': exception.explanation,
    }
    response.write(json.dumps(result))
  else:
    response.write(exception)
  response.set_status(exception.code)


def is_mobile(request):
  if 'm' in request.params:
    return True
  if settings.config["mobile"]:
    return True
  if request.user_agent.find("iPhone") > -1:
    return True
  if request.user_agent.find("iPod") > -1:
    return True
  if request.user_agent.find("Android") > -1:
    return True
  if request.user_agent.find("BlackBerry") > -1:
    return True
  return False


def global_context(request, con):
  return con


def get_template_file(template_file, handler, con=None):
  try:
    logging.debug("get_template_file: "+template_file)
    if con and 'mobile' in con:
      if not con['Mobile']:
        try_file = settings.config["templates_dir"] + template_file
        if os.path.exists(try_file):
          logging.debug("template path 1: "+template_file)
          return template_file
        logging.debug("template path 1 pass")
    tablet = False
    if is_mobile(handler.request):
      try_file = settings.config["templates_dir"] + 'mobile/' + template_file
      if os.path.exists(try_file):
        logging.debug("template path 2: "+'mobile/' + template_file)
        return "mobile/" + template_file
      logging.debug("template path 2 pass "+try_file)
    else:
      if "t" in handler.request.params:
        tablet = True
      if handler.request.user_agent.find("iPad") > -1:
        tablet = True
      if tablet:
        # tablets get the desktop page, unless a tablet one exists
        for tmp in settings.config["template_dirs"]:
          if os.path.exists(tmp + "/tablet/t_" + template):
            logging.debug("template path 3: "+'mobile/' + template_file)
            return "tablet/t_" + template_file
        logging.debug("template path 3 pass")
      else:
        for tmp in settings.config["template_dirs"]:
          try_file = settings.config["templates_dir"] + tmp + '/' + template_file
          if os.path.exists(try_file):
            logging.debug("template path 4: "+tmp + '/' + template_file)
            return tmp + '/' + template_file
        logging.debug("template path 4 pass")
    return template_file
  except Exception, E:
    logging.exception("get_template_file " + str(E))
    logging.debug("template path 5: "+template_file)
    return template_file


class MainHandler(BaseHandler):
  def get(self):
    if logged_in():
      con = {"cats": Category.all()}

      self.render_template("index.html", con)
    else:
      self.render_template("login.html")


class register(BaseHandler):
  def get(self):
    self.render_template('signup.html')

  def post(self):
    email = self.request.get('email')
    name = self.request.get('name')
    password = self.request.get('password')
    last_name = self.request.get('lastname')

    unique_properties = ['email_address']
    user_data = self.user_model.create_user(email,
                                            unique_properties,
                                            email_address=email, name=name, password_raw=password,
                                            last_name=last_name, verified=False)
    if not user_data[0]:  # user_data is a tuple
      self.render_template('signup.html', {"message": "That userId is already registered", })
      return

    user = user_data[1]
    user_id = user.get_id()

    token = self.user_model.create_signup_token(user_id)

    verification_url = self.uri_for('verification', type='v', user_id=user_id,
                                    signup_token=token, _full=True)

    msg = 'An email has been sent to your account'

    message = EmailMessage(
      sender='shoutaboutemail@gmail.com',
      to=email,
      subject="Shout! Registration",
      body="Click here to confirm your email address " + verification_url
    )

    message.send()

    self.display_message(msg.format(url=verification_url))


class updateItem(BaseHandler):
  def post(self):
    if logged_in():
      it = None
      try:
        it = Item.get_item(self.request.get('key'))
      except Exception, E:
        logging.exception("updateItem " + str(E))
        # not found
        self.error(400)
      # it.descr = self.request.get('descr')
      # category
      posted_cat = self.request.get("cat")
      try:
        cat = Category.get_by_key_name(posted_cat)
        if cat:
          it.category = cat
      except:
        logging.exception("Category not found %s" % posted_cat)

      it.put()
      old_votes = it.votes.filter("voter =", self.user_id)
      for v in old_votes:
        v.delete()
      vote = Vote()
      vote.item = it
      vote.voter = self.user_id
      vote.comment = self.request.get('descr')
      vote.vote = 1 if self.request.get("vote") == "like" else -1
      vote.put()

      it.put()  # again
      # refresh cache
      memcache_touch_place(it)


      # CategoryStatsDenormalised.addPost(self.user_id,master_cat)
      # TODO this should be ajax
      self.response.out.write("OK")

    else:
      self.display_message("Unable to save item")


def getPlaceDetailFromGoogle(item):
  params = {'radius': 150,
            'types': "food|restaurant",
            'location': '%f,%f' % (item.lat, item.lng),
            'name': item.place_name,
            'sensor': False,
            'key': settings.config['google_api_key']}
  url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?" + urllib.urlencode(params)
  response = urllib2.urlopen(url)
  json_result = response.read()
  address_result = json.loads(json_result)
  photo_ref = None
  place_id = None
  if address_result['status'] == "OK":
    for r in address_result['results']:
      photos_done = False
      place_done = False
      if not photos_done and ("photos" in r):
        photo_ref = r['photos'][0]['photo_reference']
        photos_done = True
      if "place_id" in r:
        place_id = r['place_id']
        place_done = True
      if photos_done and place_done:
        break
    if photo_ref:
      url = "https://maps.googleapis.com/maps/api/place/photo?maxwidth=%%d&photoreference=%s&key=%s" % (
        photo_ref, settings.config['google_api_key'])
      res = {'photo': url}
    else:
      res = {'photo': None}
      logging.info("getPlaceDetailFromGoogle  NO URL %s: %s" % (item.place_name, address_result['status']))
    if place_id:
      params = {'placeid': place_id,
                'key': settings.config['google_api_key']}
      detail_url = "https://maps.googleapis.com/maps/api/place/details/json?" + urllib.urlencode(params)
      response = urllib2.urlopen(detail_url)
      json_result = response.read()
      detail_result = json.loads(json_result)
      if "formatted_phone_number" in detail_result['result']:
        res['telephone'] = detail_result['result']["formatted_phone_number"]
      else:
        logging.info("getPlaceDetailFromGoogle - No number for %s" % item.place_name)
    else:
      logging.info("getPlaceDetailFromGoogle - No place_id for %s" % item.place_name)
    return res
  else:
    logging.error("getPlaceDetailFromGoogle %s: %s" % (item.place_name, address_result['status']))
    return {"photo": None, "telephone": None}


def update_item_internal(self, user_id):
  # is it an edit or a new?
  it = Item.get_unique_place(self.request)
  try:
    raw_file = self.request.get('new-photo')
    rot = self.request.get("rotation")
    if len(raw_file) > 0:
      if it.photo:  # the item has an image already?
        img = it.photo  # - yes: use it
        img.thumb = None  # but reset the thumb as it's invalid now
      else:
        img = DBImage()  # - no: create it

      if rot and (rot <> u'0'):  # is a rotation requested?
        angle = int(rot) * 90
        raw_file = images.rotate(raw_file, angle)
      # exif = raw_file.get_original_metadata()
      img.picture = db.Blob(raw_file)
      img.owner = self.user_id
      img.put()
    else:
      img = None  # no image supplied
      if rot and (rot != u'0'):  # is a rotation requested?
        old_img = it.photo
        if old_img and old_img.picture:  # if so, does the item have a pic already?
          angle = int(rot) * 90  # rotate & save in place
          rotated_pic = images.rotate(old_img.picture, angle)
          old_img.picture = db.Blob(rotated_pic)
          old_img.thumb = None
          old_img.put()
  except Exception, E:
    logging.exception("newOrUpdateItem Image Resize: " + str(E))
    img = None

  # it.place_name = self.request.get('new-title') set in get_unique_place
  it.address = self.request.get('address')
  it.owner = self.user_id
  if img:
    it.photo = img
  else:
    if not it.photo:
      # load one from google
      img = DBImage()
      detail = getPlaceDetailFromGoogle(it)
      remoteURL = detail['photo']
      main_url = remoteURL % 250
      data = urllib2.urlopen(main_url)
      img.picture = db.Blob(data.read())
      img.remoteURL = None
      thumb_url = remoteURL % 65
      thumb_data = urllib2.urlopen(thumb_url)
      img.thumb = db.Blob(thumb_data.read())
      img.put()
      it.telephone = detail['telephone'] if 'telephone' in detail else None
      it.photo = img

  # category
  posted_cat = self.request.get("new-item-category")
  try:
    cat = Category.get_by_key_name(posted_cat)
  except:
    cat = None
  it.category = cat
  it.put()
  # refresh cache
  memcache_touch_place(it)
  try:
    old_votes = it.votes.filter("voter =", user_id)
    for v in old_votes:
      v.delete()
    vote = Vote()
    vote.item = it
    vote.voter = user_id
    vote.comment = self.request.get('myComment')
    if self.request.get("untried") == 'true':
      vote.untried = True
      vote.vote = 0
    else:
      vote_str = self.request.get("voteScore")
      vote.vote = 1 if vote_str == "1" or vote_str == "like" else -1
    vote.put()
  except Exception, e:
    logging.error("newOrUpdateItem votes exception")
    logging.error("newOrUpdateItem votes exception " + str(e))


  # todo: why?
  it.put()  # again
  # mark user as dirty
  memcache_touch_user(user_id)

class updateItemAPI(BaseHandler):
  def post(self):
    #https://cloud.google.com/appengine/docs/python/appidentity/#Python_Asserting_identity_to_other_App_Engine_apps
    logging.debug("updateItemAPI")
    if app_identity.get_application_id() != settings.API_TARGET_APP_ID:
      logging.debug("updateItemAPI 403: %s != %s"%(app_identity.get_application_id(),settings.API_TARGET_APP_ID))
      self.abort(403)
    app_id = self.request.headers.get('X-Appengine-Inbound-Appid', None)
    logging.info('updateItemAPI: from app %s'%app_id)
    if app_id in settings.ALLOWED_APP_IDS:
      seed_user = None
      for u in User.query():
        if 'pegah' in u.auth_ids:
          seed_user = u.key.id()
          break
      if seed_user:
        logging.debug("updateItemAPI user:"+str(seed_user))
        update_item_internal(self, seed_user)
        self.response.out.write("OK")
      else:
        logging.error("updateItemAPI - couldn't get seed user")
        self.abort(500)
    else:
      logging.debug("updateItemAPI not allowed")
      self.abort(403)


class newOrUpdateItem(BaseHandler):
  def post(self):
    if logged_in():
      update_item_internal(self, self.user_id)

      self.response.out.write("OK")
    else:
      self.display_message("Unable to save item")


class loadTestData(BaseHandler):
  def get(self):
    results = None
    try:
      section = self.request.get("section")
      geoCode = self.request.get("useFakeGeoCoder")
      results = load_data(section=section, useFakeGeoCoder=geoCode)
      self.render_template("dataLoader.html", {"results": results})
    except Exception, E:
      self.render_template("dataLoader.html", {"results": results, "message": E})


class wipeAndLoadTestData(BaseHandler):
  def get(self):
    results = None
    try:
      results = load_data(wipe=True)
      self.render_template("dataLoader.html", {"results": results})
    except Exception, E:
      self.render_template("dataLoader.html", {"results": results, "message": E})


class loadPlace(BaseHandler):
  def get(self):
    self.render_template("item.html")

  def post(self):
    pass


def geoCodeAddress(address):
  url = "https://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor=false&key=%s" % \
        (urllib2.quote(address), settings.config['google_api_key'])
  response = urllib2.urlopen(url)
  jsonGeoCode = response.read()
  geoCode = json.loads(jsonGeoCode)
  if geoCode['status'] == "OK":
    pos = geoCode['results'][0]['geometry']['location']
  else:
    pos = None
    logging.error("geoCodeAddress", {"message": "Bad geoCode"})
  return pos


def geoCodeLatLng(lat, lng):
  url = "https://maps.googleapis.com/maps/api/geocode/json?latlng=%s,%s&sensor=false&key=%s" % \
        (lat, lng, settings.config['google_api_key'])
  response = urllib2.urlopen(url)
  serverResponse = response.read()
  geoCode = json.loads(serverResponse)
  if geoCode['status'] == "OK":
    addr = geoCode['results'][0]['formatted_address']
  else:
    logging.warning("geoCodeLatLng: Failed to geocode %s,%s" % (lat, lng))
    addr = None
  return addr


class geoLookup(BaseHandler):
  def get(self):
    self.render_template("geoLookup.html", {"mobile": False})


  def post(self):
    address = self.request.get('address')
    pos = geoCodeAddress(address)
    if pos:
      params = {
        "lat": pos['lat'],
        "lng": pos['lng'],
        "mobile": False,
        "categories": ["deprecated"],
      }
      self.render_template("newOrUpdateItem.html", params)
    else:
      self.display_message("Unable to lookup address")


class getItem_ajax(BaseHandler):
  def get(self, key):
    try:
      it = Item.get_item(key)
      res = {"place_name": it.place_name,
             "address": it.address,
             "category": it.category.title,
             "lat": str(it.lat),
             "lng": str(it.lng),
             "key": str(it.key()),
             "distance": it.distance_from(float(self.request.get("lat")), float(self.request.get("lng")))
      }
      if it.photo:
        res["img"] = str(it.key())
      if it.owner == self.user_id:
        res["mine"] = True
        res["descr"], res["vote"] = it.vote_from(it.owner)
      else:
        res["mine"] = False
        res["descr"], res["vote"] = it.vote_from(self.user_id)
      json.dump(res, self.response.out)
    except Exception, e:
      logging.error("getItem_ajax Exception")
      self.error(500)


class getItemVotes_ajax(BaseHandler):
  def get(self, key):
    res = {}
    it = Item.get_item(key)
    if it:
      votes = it.votes
      # TODO: .order("when") but there are missing values for when
      cursor = self.request.get("cursor")
      if cursor:
        votes.with_cursor(start_cursor=cursor)
      results = votes[0:20]
      next_cursor = votes.cursor()
      res["cursor"] = next_cursor
      more = len(results) >= 20
      html = self.render_template_to_string("item-votes-list.htt", {"votes": results, "more": more})
      res["votesList"] = html
      res["more"] = more
      json.dump(res, self.response.out)
    else:
      self.abort(501)


class ImageHandler(BaseHandler):
  def get(self):
    key = self.request.get('img_id')
    try:
      item = db.get(key)
      if item.photo:
        self.response.headers['Content-Type'] = 'image/png'
        self.response.out.write(item.photo.picture)
    except:
      self.response.headers['Content-Type'] = 'image/png'
      no_pic = DBImage.get_by_key_name("default")
      self.response.out.write(no_pic.picture)


class ThumbHandler(BaseHandler):
  def get(self):
    key = self.request.get('img_id')
    try:
      item = db.get(key)
      if item.photo:
        self.response.headers['Content-Type'] = 'image/png'
        self.response.out.write(item.photo.get_thumb())
    except Exception, e:
      self.response.headers['Content-Type'] = 'image/png'
      no_pic = DBImage.get_by_key_name("default")
      self.response.out.write(no_pic.picture)


class search(BaseHandler):
  def get(self):
    return None


class logout(BaseHandler):
  def get(self):
    logging.info("Logging out")
    self.auth.unset_session()
    return self.render_template("login.html")


class login(BaseHandler):
  def post(self):
    username = ""
    try:
      logging.debug("Login Started")
      username = self.request.get('username')
      password = self.request.get('password')
      self.auth.get_user_by_password(username, password, remember=True,
                                     save_session=True)
      logging.debug("Login Done")
      return self.redirect("/")
    except (InvalidAuthIdError, InvalidPasswordError) as e:
      logging.info('Login failed for userId %s because of %s', username, type(e))
      return self.render_template("login.html", {"message": "Login Failed"})
    except Exception, e:
      logging.exception('Login failed because of unexpected error %s', type(e))
      return self.render_template("login.html", {"message": "Server Error"})
    except:
      logging.exception('Login failed for unknown reasons')
      return self.render_template("login.html", {"message": "Bad Server Error"})

  def get(self):
    logging.debug("Login GET")
    return self.render_template("login.html")


class addVote_ajax(BaseHandler):
  def post(self):
    it_key = self.request.get('item_id')
    it = Item.get_item(it_key)
    voteScore = int(self.request.get("vote"))
    my_votes = it.votes.filter('voter =', self.user_id)
    if my_votes.count() == 0:
      # a new vote
      new_vote = Vote()
      new_vote.item = it
      new_vote.voter = self.user_id
    else:
      # roll back the old vote
      new_vote = my_votes.get()
      oldVote = new_vote.vote
      if oldVote:
        if oldVote > 0:
          it.votesUp -= oldVote
        else:
          # all votes are abs()
          it.votesDown -= oldVote
    new_vote.vote = voteScore
    new_vote.comment = self.request.get("comment")
    new_vote.put()
    if voteScore > 0:
      it.votesUp += voteScore
    else:
      it.votesDown += abs(voteScore)
    it.put()
    # refresh cache
    memcache.set(it_key, it)
    memcache.delete("JSON:" + it_key)
    self.response.out.write('OK')


class getMapList_Ajax(BaseHandler):
  def get(self):
    if logged_in():
      result = get_item_list(request=self.request, include_maps_data=True, user_id=self.user_id,
                             exclude_user_id=self.user_id)
      r = self.render_template("new-place-list.htt", {"results": result})
      return r
    else:
      self.error(401)


class imageEdit_Ajax(BaseHandler):
  def post(self):
    it = Item.get_item(self.request.get('image-id'))
    rotate_direction = int(self.request.get("image-rotate"))
    if it.photo:
      db_image = it.photo
    else:
      db_image = DBImage()
    raw_file = images.Image(self.request.get('image-img'))
    if rotate_direction == 1:
      # clockwise
      raw_file.rotate(90)
    elif rotate_direction == -1:
      raw_file.rotate(-90)
    db_image.picture = db.Blob(raw_file)
    db_image.put()
    memcache_touch_place(it)
    self.response.out.write('OK')


class ping(BaseHandler):
  def get(self):
    self.response.write('OK')


class deleteItem(BaseHandler):
  def post(self, key):
    if logged_in():
      try:
        item = Item.get_item(key)
        if item:
          my_votes = item.votes.filter('voter =', self.user_id)
          for vote in my_votes:
            logging.info("deleteItem: " + str(vote.key()))
            vote.delete()
        memcache_touch_user(self.user_id)
        self.response.write('OK')
      except Exception, E:
        logging.error("deleteItem", E)
        self.abort(500)
    else:
      self.abort(401)
