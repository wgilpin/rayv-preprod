import json
import logging
from random import random
import urllib2
from datetime import datetime
from logging_ext import logging_ext
import settings
import geo

__author__ = 'Will'

class PlacesDB():

  @classmethod
  def log_to_console(cls, message):
    if settings.running_on_test_server():
      print datetime.now()," LOG: ", message
    else:
      logging.info(message)

  @classmethod
  def map_and_db_search(
      cls,
      request,
      exclude_user_id,
      filter_kind,
      include_maps_data,
      lat,
      lng,
      my_locn,
      text_to_search,
      user_id):
    """
    Get the list of place near a point from the DB & from geo search
    :param exclude_user_id: int - ignore this user's results
    :param filter_kind: string - eg 'mine' or 'all'
    :param include_maps_data: bool - do we include geo data from google
    :param lat: float
    :param lng: float
    :param my_locn: LatLng
    :param text_to_search: string
    :param user_id: int userId of the current user
    :return: dict {"local": [points]}
    """
    points = []
    def add_if_unique (point):
      for p in points:
        if point["place_name"] == p["place_name"]:
          distance = geo.approx_distance(point, p)
          if distance < 0.05:
            #found, don't add
            return
      #wasn't found in list, add
      points.append(point)

    logging.debug("map_and_db_search")
    search_filter = {
      "kind": filter_kind,
      "userId": user_id,
      "exclude_user": exclude_user_id}
    calc_dist_from = my_locn if include_maps_data else None
    list_of_place_names = []

    cls.log_to_console("Enter DB search")
    points = geo.findDbPlacesNearLoc(
      my_locn,
      search_text=text_to_search,
      place_names=list_of_place_names)["points"]
    cls.log_to_console("Exit DB search")

    if include_maps_data:
      g_points = cls.get_google_db_places(lat, lng, text_to_search, 3000)
      points_2 = g_points["items"]
      cls.log_to_console("Exit Google search")


      # todo: step through both in sequence
      try:
        # deDup the list - if it's come back from google check if we had it already:
        # same name AND nearby

        for pt in points_2:
          add_if_unique(pt)
        cls.log_to_console("Deduped")


      except Exception, e:
        pass

    result = {"local": {
      "points": points,
      "count": len(points)
    }}
    return result

  @classmethod
  def get_item_list(cls, request, include_maps_data, user_id,
                    exclude_user_id=None):
    """ get the list of item around a place
    @param request:
    @param include_maps_data: bool: include data from google maps?
    @param user_id:
    @return: list of JSON points
    """
    around = geo.LatLng(lat=float(request.get("lat")),
                    lng=float(request.get("lng")))
    try:
      my_locn = geo.LatLng(lat=float(request.get("myLat")),
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
    return cls.map_and_db_search(
      request,
      exclude_user_id,
      filter_kind,
      include_maps_data,
      lat,
      lng,
      my_locn,
      text_to_search,
      user_id)

  @classmethod
  def get_word_list(cls, text):
    words = text.split(' ')
    search_words = []
    for w in words:
      if w=='and' or w=='&':
        continue
      search_words.append(w)
    return  search_words

  @classmethod
  def get_google_db_places(cls, lat, lng, name, radius):
    """
    do a google geo search
    :param lat: float
    :param lng: float
    :param name: string - to look for
    :param radius: int - search radius (m)
    :return: dict - {"item_count": int, "items": []}
    """
    results = {"item_count": 0,
                 "items": []}
    try:
      # remove AND or & from name
      search_words = cls.get_word_list(name)
      search_text_or = "|".join(search_words)
      search_text_and = " ".join(search_words)
      escaped_name = "%s%%7C%s"%( urllib2.quote(search_text_or),urllib2.quote(search_text_and))
      url = ("https://maps.googleapis.com/maps/api/place/nearbysearch/"
            "json?rankby=distance&types=%s&location=%f,%f&name=%s&sensor=false&key=%s")\
            % \
            (settings.config['place_types'],
             lat,
             lng,
             escaped_name,
             settings.config['google_api_key'] )
      addresses = []
      response = urllib2.urlopen(url, timeout=15)
      jsonResult = response.read()
      addressResult = json.loads(jsonResult)
      logging.info("get_google_db_places: Url=%s"%url)

    except Exception, e:
      if settings.running_on_test_server():
        # make up a test
        print "get_google_db_places OFFLINE - Making Up Fake Data"
        addressResult = {
          'status':'OK',
          'results':[
            {
              'formatted_address':'1 Crouch Hill, London',
              'name':'A Madeup Place',
              'place_id':'0',
              'geometry':{
                'location':{
                  'lat':54.0 + random(),
                  'lng': -(1.0 + random())
                }
              }
            }
          ]
        }
      else:
        logging_ext.error('get_google_db_places Exception in Load', exc_info=True)
        return None
    if addressResult['status'] == "OK":
      try:
        origin = geo.LatLng(lat=lat, lng=lng)
        for r in addressResult['results']:
          if "formatted_address" in r:
            address = r['formatted_address']
          else:
            address = r['vicinity']
          post_code = r['postal_code'].split(' ')[0] if 'postal_code' in r else ''
          detail = {'place_name': r['name'],
                    'address': address,
                    'post_code': post_code,
                    'place_id': r['place_id'],
                    "lat": r['geometry']['location']['lat'],
                    "lng": r['geometry']['location']['lng'],
                    'website': '',
                    'key': "",
                    'cuisineName': "",
                    'telephone': '',
                    'img': '',
                    'edited': 0,
                    'thumbnail': '',
                    'up': 0,
                    'down': 0,
                    'owner': None,
                    # is_map is True if the point came
                    # from a google places API search. Default False
                    'is_map': True}
          addresses.append(detail)
          results["item_count"] += 1
        results['items'] = addresses
        return results
      except Exception, e:
        logging_ext.error('get_google_db_places Exception processing', exc_info=True)
        return results
    elif addressResult['status'] == "ZERO_RESULTS":
      logging.info(
        "get_google_db_places near [%f,%f]: %s - %s" %
          (lat, lng, name, addressResult['status']),
        exc_info=True)
      return results
    else:
      logging_ext.error(
        "get_google_db_places near [%f,%f]: %s" %
          (lat, lng, addressResult['status']),
        exc_info=True)
      return results
