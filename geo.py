import json
import logging
from math import sqrt
from operator import itemgetter
import urllib
import urllib2
from google.appengine.api import memcache
from google.appengine.ext import db
from caching import memcache_get_user_dict
import geohash
from models import Item, getProp, get_category
from settings import config

__author__ = 'Will'



def getPlaceDetailFromGoogle(item):
  params = {'radius': 150,
            'types': "food|restaurant",
            'location': '%f,%f' % (item.lat, item.lng),
            'name': item.place_name,
            'sensor': False,
            'key': config['google_api_key']}
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
        photo_ref, config['google_api_key'])
      res = {'photo': url}
    else:
      res = {'photo': None}
      logging.info("getPlaceDetailFromGoogle  NO URL %s: %s" % (item.place_name, address_result['status']))
    if place_id:
      params = {'placeid': place_id,
                'key': config['google_api_key']}
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


def geoCodeLatLng(lat, lng):
  url = "https://maps.googleapis.com/maps/api/geocode/json?latlng=%s,%s&sensor=false&key=%s" % \
        (lat, lng, config['google_api_key'])
  response = urllib2.urlopen(url)
  serverResponse = response.read()
  geoCode = json.loads(serverResponse)
  if geoCode['status'] == "OK":
    addr = geoCode['results'][0]['formatted_address']
  else:
    logging.warning("geoCodeLatLng: Failed to geocode %s,%s" % (lat, lng))
    addr = None
  return addr

def geoCodeAddress(address, search_centre):
  url = "https://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor=false&key=%s&bounds=%d,%d|%d,%d" % \
        (urllib2.quote(address), config['google_api_key', ])
  response = urllib2.urlopen(url)
  jsonGeoCode = response.read()
  geoCode = json.loads(jsonGeoCode)
  if geoCode['status'] == "OK":
    pos = geoCode['results'][0]['geometry']['location']
  else:
    pos = None
    logging.error("geoCodeAddress", {"message": "Bad geoCode"})
  return pos


# it is an item dictionary
# origin is a LatLng
def geo_distance(point, origin):
  # deprecated for approx_distance
  assert False;
  # profile_in("distance_geo")
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
  # profile_out("geo_distance")
  return d



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
  except Exception:
    logging.error("findDbPlacesNearLoc Exception", exc_info=True)


def geoSearch(search_centre, my_location, radius=10, max=10, include_maps=False, search_text=None, filter=None):
  # profile_in("geoSearch")
  count = 0
  iterations = 0
  lng = float(search_centre.lng)
  lat = float(search_centre.lat)

  # profile_in("geoSearch DB")
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
  # profile_out("geoSearch DB")
  # profile_in("geoSearch MAP Build")
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
  # profile_out("geoSearch MAP Build")

  def get_dist(item):
    return item["distance"]

  if include_maps:
    # profile_in("geoSearch MAP")

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
    # profile_out("geoSearch MAP")

  # profile_in("geoSearch MAP Final")
  local_results.sort(key=itemgetter('distance_map_float'))
  return_data['points'] = local_results
  # profile_out("geoSearch MAP Final")
  # profile_out("geoSearch")
  return return_data



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
  dist = sqrt(d_lat * d_lat + d_lng * d_lng)
  return dist


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
  except Exception:
    logging.exception('itemKeyToJSONPoint', exc_info=True)


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
    logging.exception('itemToJSONPoint', exc_info=True)


"""get a json list of db places around a position
"""