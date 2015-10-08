import logging
import urllib
import urllib2
import time
from google.appengine.api import memcache
import math
from google.appengine.ext.ndb import QueryOptions
import auth_logic
import places_db
from settings_per_server import server_settings
import settings
import json
import base_handler
import geohash
import models

__author__ = 'Will'

def getPlaceDetailFromGoogle(item):
  logging.debug('getPlaceDetailFromGoogle '+item.place_name)
  place_name = item.place_name.encode('utf-8')
  params = {'radius': 150,
            'types': settings.config['place_types'],
            'location': '%f,%f' % (item.lat, item.lng),
            'name': place_name,
            'sensor': False,
            'key': settings.config['google_api_key']}
  url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?" + \
        urllib.urlencode(params)
  try:
    response = urllib2.urlopen(url)
    json_result = response.read()
    address_result = json.loads(json_result)
  except:
    logging.error(
      'getPlaceDetailFromGoogle: Exception [%s]',
      item.place_name,
      exc_info=True)
    return {"photo": None, "telephone": None}

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
        photo_ref, settings.config['google_api_key'])
      res = {'photo': url}
    else:
      res = {'photo': None}
      logging.info("getPlaceDetailFromGoogle  NO URL %s: %s" %
                   (item.place_name, address_result['status']))
    if place_id:
      params = {'placeid': place_id,
                'key': settings.config['google_api_key']}
      detail_url = "https://maps.googleapis.com/maps/api/place/details/json?" + \
                   urllib.urlencode(params)
      response = urllib2.urlopen(detail_url)
      json_result = response.read()
      detail_result = json.loads(json_result)
      if "formatted_address" in detail_result['result']:
        res['address'] = detail_result['result']["formatted_address"]
      if "international_phone_number" in detail_result['result']:
        res['telephone'] = detail_result['result']["international_phone_number"]
      elif "formatted_phone_number" in detail_result['result']:
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
        (lat, lng, settings.config['google_api_key'])
  try:
    response = urllib2.urlopen(url)
    serverResponse = response.read()
    geoCode = json.loads(serverResponse)
  except:
    logging.error(
      'geoCodeLatLng: Exception @[%d,%d]', lat, lng, exc_info=True)
    return None
  if geoCode['status'] == "OK":
    addr = geoCode['results'][0]['formatted_address']
  else:
    logging.warning("geoCodeLatLng: Failed to geocode %s,%s" % (lat, lng))
    addr = None
  return addr

class geoCodeAddressMultiple(base_handler.BaseHandler):

  @auth_logic.api_login_required
  def get(self):
    address = self.request.params['address']
    #TODO: these could be trivially cached
    url = ("https://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor"
           "=false&key=%s") % \
          (urllib2.quote(address), settings.config['google_api_key' ])
    try:
      response = urllib2.urlopen(url)
      jsonGeoCode = response.read()
      geoCode = json.loads(jsonGeoCode)
      json.dump(geoCode, self.response.out)
    except:
      logging.error( 'geoCodeAddressMultiple: Exception [%s]', address, exc_info=True)
      return None

def geoCodeAddress(address):
  url = ("https://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor"
         "=false&key=%s") % \
        (urllib2.quote(address), settings.config['google_api_key' ])
  try:
    response = urllib2.urlopen(url)
    jsonGeoCode = response.read()
    geoCode = json.loads(jsonGeoCode)
  except:
    logging.error( 'geoCodeAddress: Exception [%s]', address, exc_info=True)
    return None
  if geoCode['status'] == "OK":
    pos = geoCode['results'][0]['geometry']['location']
  else:
    pos = None
    logging.error("geoCodeAddress", {"message": "Bad geoCode"}, exc_info=True)
  return pos





def findDbPlacesNearLoc(my_location,
                        search_text=None,
                        place_names=None):
  try:
    map_id_to_item = {}
    logging.debug("findDbPlacesNearLoc Start")
    result_key_list = []
    reject_list = []
    for geo_precision in range(5, 2, -1):
      geo_code = geohash.encode(
        my_location.lat, my_location.lng, precision=geo_precision)
      items_geo_query_result = models.Item.query(
        default_options=QueryOptions(keys_only=True)).\
        filter(models.Item.geo_hash > geo_code).\
        filter(models.Item.geo_hash < geo_code + "{")
      if search_text:
        #if we're looking for a name, filter the results to find it
        search_words = places_db.PlacesDB.get_word_list(search_text)
        for point_key in items_geo_query_result:
          if point_key in result_key_list:
            continue
          if point_key in reject_list:
            continue
          if point_key.id() in map_id_to_item:
            it = map_id_to_item[point_key.id()]
          else:
            it = point_key.get()
            map_id_to_item[point_key.id()] = it
          for w in search_words:
            if w in it.place_name.lower():
              result_key_list.append(point_key)
              continue
          #reject_list.append(point_key)
        if len(result_key_list)>5:
          break
        continue
      else:
        for point_key in items_geo_query_result:
          if not point_key in result_key_list:
            it = models.Item.get_by_id(point_key.id())
            map_id_to_item[point_key.id()] = it
            result_key_list.append(point_key)
      if items_geo_query_result.count() > 10:
        break

    if len(result_key_list) == 0 and search_text:
      #didn't find the name so try splitting it
      words_candidates = search_text.split(' ')
      words = []
      exclude = ['and','&','the','in','on']
      for w in words_candidates:
        if not w in exclude:
          words.append(w)
      for point_key in items_geo_query_result:
        if point_key in result_key_list:
            continue
        if point_key in reject_list:
          continue
        it = map_id_to_item[point_key.id()]
        if not it:
          continue
        place_name_words = it.place_name.lower().split(' ')
        for w in words:
          if w in place_name_words :
            result_key_list.append(point_key)
            break

    search_results = []
    return_data = {
      'count': 0,
      'points': []
    }

    for point_key in result_key_list:
      if point_key.id() in map_id_to_item:
        it = map_id_to_item[point_key.id()]
      else:
        it = point_key.get()
      json_data = it.get_json()
      search_results.append(json_data)
      place_names.append(it.place_name)

    return_data['count'] = len(search_results)
    # search_results.sort(key=itemgetter('distance_map_float'))
    return_data['points'] = search_results
    return return_data
  except Exception, ex:
    logging.error("findDbPlacesNearLoc Exception", exc_info=True)
    return return_data


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
    points_list = models.Item.query(default_options=QueryOptions(
                      keys_only=True)).\
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
  my_id = None
  if filter:
    if filter["kind"] == "mine":
      my_id = filter["userId"]
  for point_key in initial_results:
    jit = models.Item.id_to_json(point_key)
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
    auth_key = server_settings['auth_key']

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

def approx_distance(point, place):
  # params are dicts.
  # based on 1/60 rule
  # delta lat. Degrees * 69 (miles)
  p_lat = point["lat"]
  p_lng = point["lng"]
  d_lat = (place["lat"] - p_lat) * 69
  # cos(lat) approx by 1/60
  cos_lat = min(1, (90 - p_lat) / 60)
  #delta lng = degrees * cos(lat) *69 miles
  d_lng = (place["lng"] - p_lng) * 69 * cos_lat
  dist = math.sqrt(d_lat * d_lat + d_lng * d_lng)
  return dist
