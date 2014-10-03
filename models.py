from datetime import timedelta, time
import logging
from operator import itemgetter
import pickle
from google.appengine.api import images, memcache
from google.appengine.api.images import CORRECT_ORIENTATION
from google.appengine.ext import db
import math
from auth_model import User, memcache_get_user_dict
import geohash
from profiler import profile_in, profile_out
import settings
from datetime import datetime

__author__ = 'Will'


def getProp(obj, propName):
  try:
    if hasattr(obj, propName):
      return getattr(obj, propName, None)
    return obj[propName]
  except:
    return False


# #####################################################################################
class Audit(db.Model):
  # who is logged on
  usr = db.IntegerProperty(required=False)
  # timestanp
  dt = db.DateTimeProperty(auto_now=True)
  # JSON object with data values - if NULL then only TextProperty is used
  values = db.TextProperty()
  # action - text
  action = db.TextProperty()
  subjectId = db.IntegerProperty(required=False)
  #TODO log ip - request.get_host()

  @classmethod
  def write(cls, kind, usr, msg, send_mail=True, subject=None, trace=None):
    # print kind+' - '+str(usr)+' - '+msg
    if send_mail:
      try:
        if settings.config['online']:  #DEBUG
          if trace:
            pass
            # TODO mail admins
            #mail_admins("Audit", "%s - %s \n %s" % (kind, msg, trace))
          else:
            pass
            # TODO mail admins
            #mail_admins("Audit", "%s - %s" % (kind, msg))
      except Exception as err:
        a = Audit()
        a.usr = None
        a.action = "Exception"
        a.values = "###### Cannot send Audit Mail: %s - %s - %s:%s" % (kind, msg, type(err), err)
        if subject:
          a.subjectId = subject
        a.save()
    try:
      a = Audit()
      if usr:
        if not usr.id:
          # fight the anonymous userId
          usr = None
      a.usr = usr
      a.action = kind
      a.values = msg
      if subject:
        a.subjectId = subject
      a.save()
    except Exception as err:
      Audit.log(None, "####### AUDIT FAIL. %s:%s" % (type(err), err))

  @classmethod
  def error(cls, usr, msg, send_mail=True, trace=None):
    Audit.write('Error', usr, msg, send_mail, trace=trace)
    try:
      print 'ERROR %s' % msg
    except:
      pass

  @classmethod
  def payment(cls, msg, send_mail=False, item=None):
    Audit.write('Payment', None, msg, send_mail)

  @classmethod
  def security(cls, usr, msg, send_mail=True, item=None):
    Audit.write('Payment', usr, msg, send_mail)

  @classmethod
  def log(cls, usr, msg, send_mail=False, item=None):
    try:
      if item:
        try:
          msg = msg + item.__str__()
        except:
          pass
      Audit.write('Log', usr, msg, send_mail)
    except:
      pass

  @classmethod
  def track(cls, usr, item, kind):
    Audit.write('Track', usr, kind, False, item)

  def __unicode__(self):
    return "%s %s [%s] User:%s" % (self.dt, self.action, self.values, self.usr)


class Address(db.Model):
  address = db.TextProperty()
  city = db.TextProperty()
  state = db.TextProperty(required=False)
  postal_code = db.TextProperty(required=False)
  country = db.TextProperty()


"""
The semantic tree for items
"""


class Category(db.Model):
  # key_name is the slug
  title = db.TextProperty()


def get_category(key):
  try:
    cat = memcache.get(key)
    if cat:
      return cat
    cat = Category().get(key)
    return cat
  except:
    logging.error("get_category failed for key" + key)
    return None


class DBImage(db.Model):
  title = db.TextProperty(required=False)
  picture = db.BlobProperty()
  thumb = db.BlobProperty(required=False)
  owner = db.IntegerProperty(required=False)  # key
  remoteURL = db.StringProperty(required=False)


  def get_thumb(self):
    # get or make a thumbnail
    if not self.thumb:
      window_ratio = 65.0 / 55.0
      height = images.Image(image_data=self.picture).height
      width = images.Image(image_data=self.picture).width
      image_ratio = float(width) / float(height)
      logging.info("thumb " + str(image_ratio))
      if image_ratio > window_ratio:
        # wide
        new_height = 55
        new_width = int(55.0 * image_ratio)
        self.thumb = images.resize(self.picture, new_width, new_height, output_encoding=images.JPEG, quality=55,
                                   correct_orientation=CORRECT_ORIENTATION)
        self.thumb = images.crop(self.thumb,
                                 left_x=0.5 - 32.0 / new_width,
                                 top_y=0.0,
                                 right_x=0.5 + 32.0 / new_width,
                                 bottom_y=1.0)
      else:
        new_width = 65
        new_height = int(65.0 / image_ratio)
        self.thumb = images.resize(self.picture, new_width, new_height, output_encoding=images.JPEG, quality=55,
                                   correct_orientation=CORRECT_ORIENTATION)
        self.thumb = images.crop(self.thumb,
                                 left_x=0.0,
                                 top_y=0.5 - 27.0 / new_height,
                                 right_x=1.0,
                                 bottom_y=0.5 + 27.0 / new_height)
      self.put()
    return self.thumb


class Item(db.Model):
  title = db.StringProperty()
  place_name = db.StringProperty()
  # TODO how to pass title.max_length?
  owner = db.IntegerProperty()  # key
  # descr = db.TextProperty()
  address = db.TextProperty()
  active = db.IntegerProperty(default=1)
  when_added = db.DateTimeProperty()
  category = db.ReferenceProperty(Category)
  photo = db.ReferenceProperty(DBImage, required=False)
  # latitude = db.FloatProperty()
  # longitude = db.FloatProperty()
  lat = db.FloatProperty()
  # long = db.FloatProperty()
  lng = db.FloatProperty()
  telephone = db.StringProperty(required=False)
  geo_hash = db.StringProperty()
  thumbsUp = db.IntegerProperty(default=0)
  googleID = db.TextProperty(default="")  #Maps ID
  created = db.DateTimeProperty(auto_now_add=True)

  def prop(self, name):
    return getProp(self, name)

  def is_new(self):
    # any item added within the last N days is new, where N = HOW_OLD_IS_NEW
    cutoff = datetime.now() - timedelta(days=settings.config['how_old_is_new'])
    return self.when_added > cutoff

  def __unicode__(self):
    return self.place_name

  def qualified_title(self):
    return self.__unicode__()

  @classmethod
  def get_unique_place(cls, request):
    it = Item.get_item(request.get('key'))
    if it:
      return it
    place_name = request.get('new-title')
    if 'latitude' in request.params:
      lat = float(request.get('latitude'))
    else:
      lat = float(request.get('lat'))
    if 'longitude' in request.params:
      lng = float(request.get('longitude'))
    else:
      lng = float(request.get('lngllow lat ot lati'))
    geo_code = geohash.encode(lat, lng, precision=6)
    local_results = Item.all().filter("geo_hash >", geo_code).filter("geo_hash <", geo_code + "{")
    lower_name = place_name.lower()
    for place in local_results:
      if lower_name in place.place_name.lower():
        return place
    it = Item(place_name=place_name)
    it.lat = lat
    it.lng = lng
    it.geo_hash = geohash.encode(lat, lng)
    return it

  def owners_comment(self):
    # return the text from the owners vote
    owners_vote = self.votes.filter("voter =", self.owner).get()
    if owners_vote:
      return owners_vote.comment
    else:
      return ""

  def owners_vote(self):
    # return the text & score from the owners vote
    owners_vote = self.votes.filter("voter =", self.owner).get()
    if owners_vote:
      return owners_vote.comment, owners_vote.vote
    else:
      return "", 0

  def vote_from(self, user_id):
    """
    return the text & score from the owners vote
    @param user_id:
    @return user's comment, user's vote score:
    """
    users_vote = self.votes.filter("voter =", user_id).get()
    if users_vote:
      return users_vote.comment, users_vote.vote
    else:
      return "", 0

  def closest_vote_from(self, user_record):
    """
    return the text & score from the owners vote
    @param user_id:
    @return user's comment, user's vote score:
    """
    uid = user_record['p'].userId
    users_vote = self.votes.filter("voter =", uid).get()
    if users_vote:
      return users_vote


    # first one
    for friend_id in user_record['p'].friends:
      users_vote = self.votes.filter("voter =", friend_id).get()
      logging.debug("friend " + str(friend_id))
      if users_vote:
        return users_vote
    logging.debug("closest_vote_from " + str(uid))
    logging.debug("num friends " + str(len(user_record['p'].friends)))
    return None

  @classmethod
  def get_item(cls, key):
    """
    memcache enabled get Item
    @param key:
    @return item:
    """
    try:
      item = memcache.get(key)
      if item:
        return item
      item = Item().get(key)
      if item:
        if not memcache.set(key, item):
          logging.error("could not memcache Item " + key)
      return item
    except Exception, e:
      logging.error("get_item", exc_info=True)
      return None


def prettify_distance(d):
  # profile_in("prettify_distance")
  if d >= 1.0:
    dist_str = "%.1f miles" % d
  else:
    yds = int(d * 90) * 20
    dist_str = "%d yds" % yds
  # profile_out("prettify_distance")
  return dist_str


class LatLng():
  lat = 0
  lng = 0

  def __init__(self, lat, lng):
    self.lat = lat
    self.lng = lng


def approx_distance(point, origin):
  # todo: can this be moved client side?
  # based on 1/60 rule
  # delta lat. Degrees * 69 (miles)
  try:
    p_lat = point.lat
    p_lng = point.lng
  except AttributeError, e:
    p_lat = point["lat"]
    p_lng = point["lng"]
  d_lat = (origin.lat - p_lat) * 69
  # cos(lat) approx by 1/60
  cos_lat = min(1, (90 - p_lat) / 60)
  #delta lng = degrees * cos(lat) *69 miles
  d_lng = (origin.lng - p_lng) * 69 * cos_lat
  dist = math.sqrt(d_lat * d_lat + d_lng * d_lng)
  return dist


# it is an item dictionary
# origin is a LatLng
def geo_distance(point, origin):
  # deprecated for approx_distance
  assert False;
  profile_in("distance_geo")
  # Equirectangular approximation
  # http://www.movable-type.co.uk/scripts/latlong.html
  d_lng = abs(origin.lng - point.lng)
  d_lat = abs(origin.lat - point.lat)
  memcache_key = "D:%.5f:%.5f" % (d_lat * 1000, d_lng * 1000)
  old = memcache.get(memcache_key)
  if old:
    profile_out("geo_distance")
    return float(old)
  lat1 = math.radians(origin.lat)
  lon1 = math.radians(origin.lng)
  lat2 = math.radians(point.lat)
  lon2 = math.radians(point.lng)
  R = 6371  # radius of the earth in km
  x = (lon2 - lon1) * math.cos(0.5 * (lat2 + lat1))
  y = lat2 - lat1
  d = R * math.sqrt(x * x + y * y)
  # to miles
  d /= 1.609344
  memcache.set(memcache_key, str(d))
  profile_out("geo_distance")
  return d


def itemKeyToJSONPoint(key):
  try:
    # memcache has item entries under Key, and JSON entries under JSON:key
    if type(key) is db.Key:
      key = str(key)
    res = memcache.get('JSON:' + key)
    if res:
      return res
    item = memcache.get(key)
    if not item:
      item = Item.get(key)
    res = itemToJSONPoint(item)  # convert and memcache
    memcache.add('JSON:' + key, res)
    return res
  except Exception, E:
    logging.exception('itemKeyToJSONPoint')


def itemToJSONPoint(it, GPS_origin=None, map_origin=None):
  # create a json object for the web.
  # dist_from_GPS = approx_distance(it, GPS_origin)
  try:
    if getProp(it, 'photo'):
      if it.photo.picture:
        image_url = '/img?img_id=' + str(it.key())
        thumbnail_url = '/thumb?img_id=' + str(it.key())
      else:
        image_url = it.photo.remoteURL % 200 if it.photo.remoteURL else ''
        thumbnail_url = it.photo.remoteURL % 65 if it.photo.remoteURL else ''
      if it.photo.key() == "ag1zfnNob3V0LWFib3V0chQLEgdEQkltYWdlGICAgIDJlr4JDA":
        logging.debug(thumbnail_url)
    else:
      image_url = ''
      thumbnail_url = ''
      # image_url = "/static/images/noImage.jpeg"
    # get key only from referenceProperty
    if type(it) is Item:
      category = get_category(str(Item.category.get_value_for_datastore(it)))
    else:
      category = None
    data = {
      'lat': getProp(it, 'lat'),
      'lng': getProp(it, 'lng'),
      'address': getProp(it, 'address'),
      'key': str(it.key()) if type(it) is Item else "",
      'place_name': getProp(it, 'place_name'),
      'category': category.title if category else "",
      'telephone': getProp(it, 'telephone'),
      'vote': 0,
      'untried': False,
      'img': image_url,
      'thumbnail': thumbnail_url,
      'up': it.votes.filter("vote =", 1).count() if hasattr(it, 'votes') else 0,
      'down': it.votes.filter("vote =", -1).count() if hasattr(it, 'votes') else 0,
      'owner': getProp(it, 'owner'),
      # is_map is True if the point came from a google places API search. Default False
      'is_map': False}
    if hasattr(it, 'key'):
      memcache.add("JSON:" + str(it.key()), data)
    if GPS_origin:
      # If GPS_origin is None then we include no distnce info (done client side)
      dist_from_GPS = approx_distance(it, GPS_origin)
      if map_origin:
        if GPS_origin.lat == map_origin.lat and GPS_origin.lng == map_origin.lng:
          dist_from_map = dist_from_GPS
        else:
          dist_from_map = approx_distance(it, map_origin)
      else:
        dist_from_map = dist_from_GPS

      dist_str = prettify_distance(dist_from_GPS)
      data['distance'] = dist_str
      data['distance_float'] = dist_from_GPS
      data['distance_map_float'] = dist_from_map

    return data
  except Exception, E:
    logging.exception('itemToJSONPoint')


"""get a json list of db places around a position
"""


def findDbPlacesNearLoc(my_location, search_text=None, filter=None, uid=None, position=None, exclude_user_id=None,
                        place_names=None, ignore_votes=False):
  try:
    for geo_precision in range(6, 3, -1):
      geo_code = geohash.encode(my_location.lat, my_location.lng, precision=geo_precision)
      initial_results = Item.all(keys_only=True).filter("geo_hash >", geo_code).filter("geo_hash <", geo_code + "{")
      if initial_results.count() > 10:
        break
    search_results = []
    return_data = {}
    exclude_user_id = None
    if filter:
      if filter["kind"] == "mine":
        my_id = filter["userId"]
        initial_results = Item.all(keys_only=True).filter("owner =", my_id)  # TODO: owner does not make it mine - votes
      if 'exclude_user' in filter:
        exclude_user_id = filter['exclude_user']
    user = memcache_get_user_dict(uid)
    for point_key in initial_results:
      it = Item.get_item(str(point_key))
      if search_text:
        # we only want ones that match the search text
        if not search_text in it.place_name.lower():
          continue
      jsonPt = itemToJSONPoint(it, position)
      if not ignore_votes:
        vote = it.closest_vote_from(user)
        if vote:
          # if the user has voted for this item, and the user is excluded, next
          if exclude_user_id and exclude_user_id == vote.voter:
            jsonPt["mine"] = True;
          jsonPt["vote"] = vote.vote
          if vote.voter == uid:
            jsonPt["descr"] = vote.comment
            jsonPt["thumb"] = "thumbdownred.png" if vote.vote == -1 else "thumbupgreen.png"
            if vote.untried:
              jsonPt["untried"] = True
          else:
            jsonPt["descr"] = ""
            jsonPt["thumb"] = "thumbdown.png" if vote.vote == -1 else "thumbup.png"
        else:
          pass
      search_results.append(jsonPt)
      place_names.append(it.place_name)

    return_data['count'] = len(search_results)
    # search_results.sort(key=itemgetter('distance_map_float'))
    return_data['points'] = search_results
    return return_data
  except Exception, e:
    logging.error("findDbPlacesNearLoc Exception")
    logging.error("findDbPlacesNearLoc Exception " + str(e))


def geoSearch(search_centre, my_location, radius=10, max=10, include_maps=False, search_text=None, filter=None):
  profile_in("geoSearch")
  count = 0
  iterations = 0
  lng = float(search_centre.lng)
  lat = float(search_centre.lat)

  profile_in("geoSearch DB")
  if search_text:
    search_text = search_text.lower()
  # 69 mi = 111,111 metres, = 1 degree of arc approx
  # delta_deg = float(radius) / 69.0

  # right = lng + delta_deg
  #left = lng - delta_deg
  #top = lat + delta_deg
  #bottom = lat - delta_deg

  # #
  # Two stage lookup
  #   1. Get at least twenty results by widening the geo search until you do
  #   2. Get those items from memcache / DB and fill in the list
  ##
  geo_precision = 6
  initial_results = []
  return_data = {"count": 0,
                 "points": None}
  while count == 0 and iterations < 3:
    count = 0
    geo_code = geohash.encode(search_centre.lat, search_centre.lng, geo_precision)
    #https://code.google.com/p/python-geohash/wiki/Tips
    points_list = Item.all(keys_only=True).filter("geo_hash >", geo_code).filter("geo_hash <", geo_code + "{")
    #we now have a bounded rectangle with maybe some points in it.
    for possibility in points_list:
      possibility_key = str(possibility)
      if not possibility_key in initial_results:
        initial_results.append(possibility_key)
      count += 1
    iterations += 1
    geo_precision -= 1  #wider search
  # end while

  # iterate them and add to results - and check for text-search if needed
  logging.info("geoSearch precision " + str(geo_precision))
  local_results = []
  profile_out("geoSearch DB")
  profile_in("geoSearch MAP Build")
  if filter:
    if filter["kind"] == "mine":
      my_id = filter["userId"]
  for point_key in initial_results:
    jit = itemKeyToJSONPoint(point_key)
    if search_text:
      #we only want ones that match the search text
      if not search_text in jit['place_name'].lower():
        continue
    if filter:
      if filter["kind"] == "mine":
        # only return my items
        if not jit['owner'] == my_id:
          continue
      if filter["kind"] == "starred":
        # todo: stars
        continue
    local_results.append(jit)

  return_data['count'] = len(local_results)
  profile_out("geoSearch MAP Build")

  def get_dist(item):
    return item["distance"]

  if include_maps:
    profile_in("geoSearch MAP")

    # include the google maps local data
    # Import the relevant libraries
    import urllib2
    import json

    # Set the Places API key for your application
    auth_key = 'AIzaSyCLAhYubQhsrI5rhVfzN21ItL5U6R1QSxU'

    # Define the location coordinates
    location = "%f,%f" % (lat, lng)

    # Define the radius (in meters) for the search
    radius_m = 100

    # Compose a URL to query a predefined location with a radius of 5000 meters
    url = ('https://maps.googleapis.com/maps/api/place/search/json?location=%s' +
           '&radius=%s&sensor=false&key=%s') % (location, radius_m, auth_key)

    # Send the GET request to the Place details service (using url from above)
    response = urllib2.urlopen(url)

    # Get the response and use the JSON library to decode the JSON
    json_raw = response.read()
    json_data = json.loads(json_raw)

    # Iterate through the results and print them to the console
    if json_data['status'] == 'OK':
      for place in json_data['results']:

        skip_it = False
        # Don't add a place if it's there already (from the db)
        if search_text:
          if not search_text in place["name"].lower():
            skip_it = True
            continue
        for db_list_idx in range(1, count):
          if local_results[db_list_idx]["place_name"] == place["name"]:
            # the item was already in the db - don't add it to the list, skip to next
            skip_it = True
            break
        if not skip_it:
          pt = LatLng(lat=place["geometry"]["location"]["lat"],
                      lng=place["geometry"]["location"]["lng"])
          dist_gps = approx_distance(pt, my_location)
          dist_map = approx_distance(pt, search_centre)
          dist_str = prettify_distance(dist_gps)
          detail = {
            'lat': place["geometry"]["location"]["lat"],
            'lng': place["geometry"]["location"]["lng"],
            'key': place["id"],
            'place_name': place["name"],
            'category': "Local Place",
            'address': place["vicinity"],
            'distance': dist_str,
            'distance_float': dist_gps,
            'distance_map_float': dist_map,
            'voteRatio': -1,
            'invVoteRatio': -1,
            'is_map': True}
          local_results.append(detail)
    profile_out("geoSearch MAP")

  profile_in("geoSearch MAP Final")
  local_results.sort(key=itemgetter('distance_map_float'))
  return_data['points'] = local_results
  profile_out("geoSearch MAP Final")
  profile_out("geoSearch")
  return return_data


"""
A vote for an item
"""


class Vote(db.Model):
  item = db.ReferenceProperty(Item, collection_name="votes")
  voter = db.IntegerProperty()
  vote = db.IntegerProperty()
  untried = db.BooleanProperty(default=False)
  comment = db.TextProperty()
  when = db.DateTimeProperty(auto_now=True)

  @property
  def voter_name(self):
    name = memcache.get('USERNAME' + str(self.voter))
    if name:
      return name
    user = User.get_by_id(self.voter)
    name = user.screen_name
    memcache.set('USERNAME' + str(self.voter), name)


class Trust(db.Model):
  # Trust value from first user to second user, where firstId < secondId
  first = db.IntegerProperty()
  second = db.IntegerProperty()
  trust = db.IntegerProperty()

  @classmethod
  def updateTrust(user_a, user_b):
    if user_a < user_b:
      first = user_a
      second = user_b
    else:
      first = user_b
      second = user_a
    # get list of common item votes
    user_a_hits = Vote.all().filter("voter =", user_a)
    user_b_hits = Vote.all().filter("voter =", user_b)
    similar = []
    user_a_ids = []
    user_b_ids = []
    for r in user_a_hits:
      user_a_ids.append(r.id())
    for r in user_b_hits:
      user_b_ids.append(r.id())
    for id in user_a_ids:
      if id in user_b_ids:
        similar.append(id)
        #count similarity of votes
