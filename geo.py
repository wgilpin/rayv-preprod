import json
import logging
from math import sqrt
from operator import itemgetter
import urllib
import urllib2
from google.appengine.api import memcache
from google.appengine.ext import db
import time
from caching import memcache_get_user_dict
import geohash
from models import Item, getProp, get_category
from settings import config

__author__ = 'Will'



def getPlaceDetailFromGoogle(item):
  logging.debug('getPlaceDetailFromGoogle '+item.place_name)
  params = {'radius': 150,
            'types': config['place_types'],
            'location': '%f,%f' % (item.lat, item.lng),
            'name': item.place_name,
            'sensor': False,
            'key': config['google_api_key']}
  url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?" + \
        urllib.urlencode(params)
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
      url = "https://maps.googleapis.com/maps/api/place/photo?" \
            "maxwidth=%%d&photoreference=%s&key=%s" % (
        photo_ref, config['google_api_key'])
      res = {'photo': url}
    else:
      res = {'photo': None}
      logging.info("getPlaceDetailFromGoogle  NO URL %s: %s" %
                   (item.place_name, address_result['status']))
    if place_id:
      params = {'placeid': place_id,
                'key': config['google_api_key']}
      detail_url = "https://maps.googleapis.com/maps/api/place/details/json?" + \
                   urllib.urlencode(params)
      response = urllib2.urlopen(detail_url)
      json_result = response.read()
      detail_result = json.loads(json_result)
      if "formatted_phone_number" in detail_result['result']:
        res['telephone'] = detail_result['result']["formatted_phone_number"]
      else:
        logging.info("getPlaceDetailFromGoogle - No number for %s" %
                     item.place_name)
      if "website" in detail_result['result']:
        res['website'] = detail_result['result']["website"]
      else:
        logging.info("getPlaceDetailFromGoogle - No website for %s" %
                     item.place_name)
    else:
      logging.info("getPlaceDetailFromGoogle - No place_id for %s" %
                   item.place_name)
    return res
  else:
    logging.warning(
      "getPlaceDetailFromGoogle %s: %s" %
        (item.place_name, address_result['status']))
    return {"photo": None, "telephone": None}


def geoCodeLatLng(lat, lng):
  url = ("https://maps.googleapis.com/maps/api/geocode/json?latlng=%s,"
         "%s&sensor=false&key=%s") % \
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
  url = ("https://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor"
         "=false&key=%s") % \
        (urllib2.quote(address), config['google_api_key' ])
  response = urllib2.urlopen(url)
  jsonGeoCode = response.read()
  geoCode = json.loads(jsonGeoCode)
  if geoCode['status'] == "OK":
    pos = geoCode['results'][0]['geometry']['location']
  else:
    pos = None
    logging.error("geoCodeAddress", {"message": "Bad geoCode"}, exc_info=True)
  return pos





def findDbPlacesNearLoc(my_location,
                        search_text=None,
                        filter=None,
                        uid=None,
                        position=None,
                        exclude_user_id=None,
                        place_names=None,
                        ignore_votes=False):
  try:
    for geo_precision in range(6, 3, -1):
      geo_code = geohash.encode(
        my_location.lat, my_location.lng, precision=geo_precision)
      initial_results = Item.all(keys_only=True).\
        filter("geo_hash >", geo_code).\
        filter("geo_hash <", geo_code + "{")
      if initial_results.count() > 10:
        break
    search_results = []
    return_data = {}
    exclude_user_id = None
    if filter:
      if filter["kind"] == "mine":
        my_id = filter["userId"]
        initial_results = Item.all(keys_only=True).\
          filter("owner =", my_id)  # TODO: owner does not make it mine - votes
      if 'exclude_user' in filter:
        exclude_user_id = filter['exclude_user']
    user = memcache_get_user_dict(uid)
    for point_key in initial_results:
      it = Item.get_item(str(point_key))
      if search_text:
        # we only want ones that match the search text
        if not search_text in it.place_name.lower():
          continue
      if not ignore_votes:
        jsonPt = itemToJSONPoint(it, position, uid_for_votes=uid)
      else:
        jsonPt = itemToJSONPoint(it, position)


      search_results.append(adjust_votes_for_JSON_pt(jsonPt))
      place_names.append(it.place_name)

    return_data['count'] = len(search_results)
    # search_results.sort(key=itemgetter('distance_map_float'))
    return_data['points'] = search_results
    return return_data
  except Exception:
    logging.error("findDbPlacesNearLoc Exception", exc_info=True)


def geoSearch(search_centre,
              my_location,
              radius=10,
              max=10,
              include_maps=False,
              search_text=None,
              filter=None):
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
    points_list = Item.all(keys_only=True).\
      filter("geo_hash >", geo_code).\
      filter("geo_hash <", geo_code + "{")
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
    url = ('https://maps.googleapis.com/maps/api/place/search/json?location=%s'
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
            # the item was already in the db -
            # don't add it to the list, skip to next
            skip_it = True
            break
        if not skip_it:
          pt = LatLng(lat=place["geometry"]["location"]["lat"],
                      lng=place["geometry"]["location"]["lng"])
          detail = {
            'lat': place["geometry"]["location"]["lat"],
            'lng': place["geometry"]["location"]["lng"],
            'key': place["id"],
            'place_name': place["name"],
            'place_id': place['placeId'],
            'category': "Local Place",
            'address': place["vicinity"],
            'voteRatio': -1,
            'invVoteRatio': -1,
            'is_map': True}
          local_results.append(detail)
    # profile_out("geoSearch MAP")

  # profile_in("geoSearch MAP Final")
  return_data['points'] = local_results
  # profile_out("geoSearch MAP Final")
  # profile_out("geoSearch")
  return return_data






class LatLng():
  lat = 0
  lng = 0

  def __init__(self, lat, lng):
    self.lat = lat
    self.lng = lng





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


def itemToJSONPoint(it, GPS_origin=None, map_origin=None, uid_for_votes=None):
  """
  create a json object for the web.
  :param it: Item
  :param GPS_origin: LatLng
  :param map_origin: bool - do we calculate distances from where the map is
          centred, as opposed to from my location?
  :return: dict - json repr of the place
  """
  try:
    if getProp(it, 'photo'):
      if it.photo.picture:
        image_url = '/img/' + str(it.photo.key())
        thumbnail_url = '/thumb/' + str(it.photo.key())
      else:
        image_url = ''
        thumbnail_url = ''
    else:
      image_url = ''
      thumbnail_url = ''
      # image_url = "/static/images/noImage.jpeg"
    # get key only from referenceProperty
    if type(it) is Item:
      category = get_category(str(Item.category.get_value_for_datastore(it)))
    else:
      category = None
    edit_time = getProp(it,'edited')
    if edit_time:
      edit_time_unix = int(time.mktime(edit_time.timetuple())) * 1000
    else:
      edit_time_unix = 0
    data = {
      'lat': getProp(it, 'lat'),
      'lng': getProp(it, 'lng'),
      'website': getProp(it, 'website'),
      'address': getProp(it, 'address'),
      'key': str(it.key()) if type(it) is Item else "",
      'place_name': getProp(it, 'place_name'),
      'place_id': getProp(it,'place_id'),
      'category': category.title if category else "",
      'telephone': getProp(it, 'telephone'),
      'untried': False,
      'vote': 'null',
      'img': image_url,
      'edited': edit_time_unix,
      'thumbnail': thumbnail_url,
      'up': it.votes.filter("vote =", 1).count() if hasattr(it, 'votes') else 0,
      'down': it.votes.filter("vote =", -1).count() if
                                                hasattr(it, 'votes') else 0,
      'owner': getProp(it, 'owner'),
      # is_map is True if the point came
      # from a google places API search. Default False
      'is_map': False}
    if hasattr(it, 'key'):
      memcache.add("JSON:" + str(it.key()), data)
      if uid_for_votes:
        vote = it.votes.filter("voter =", uid_for_votes).get()
        if vote:
          # if the user has voted for this item, and the user is excluded, next
          data["mine"] = True;
          data["vote"] = int(vote.vote)
          data["descr"] = vote.comment
          if vote.untried:
            data["untried"] = True

    return data
  except Exception, E:
    logging.exception('itemToJSONPoint', exc_info=True)


def adjust_votes_for_JSON_pt(json_pt):
  """
  The up & down scores in a json pt include the vote of the current user
  This routine removes the vote of the current user from the calculation
  :param json_pt: dict: the jsonPt
  :return: dict: the amended jsonPt
  """
  if hasattr(json_pt, 'adjusted'):
    #already done
    return json_pt
  try:
    if json_pt['vote'] == 1:
      if json_pt['up'] > 0:
        json_pt['up'] -= 1
        json_pt['adjusted'] = True
    elif json_pt['vote'] == -1:
      if json_pt['down'] > 0:
        json_pt['down'] -= 1
        json_pt['adjusted'] = True
  except:
    pass
  return json_pt