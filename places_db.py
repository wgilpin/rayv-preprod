import json
import logging
from operator import itemgetter
import urllib2
from google.appengine._internal.django.utils.html import escape
from geo import findDbPlacesNearLoc, item_to_json_point, LatLng
from models import Vote
import settings

__author__ = 'Will'

class PlacesDB():

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
    logging.debug("map_and_db_search")
    search_filter = {
      "kind": filter_kind,
      "userId": user_id,
      "exclude_user": exclude_user_id}
    calc_dist_from = my_locn if include_maps_data else None
    list_of_place_names = []
    points = findDbPlacesNearLoc(
      my_locn,
      request,
      search_text=text_to_search,
      filter=search_filter,
      uid=user_id,
      position=LatLng(lat, lng),
      place_names=list_of_place_names,
      ignore_votes=True)
    if include_maps_data:
      googPts = cls.get_google_db_places(lat, lng, text_to_search, 3000)
      if googPts == None:
        return None
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
        jPt = item_to_json_point(gpt, request, my_locn)
        points["points"].append(jPt)
        points["count"] += 1

      sorted_results = points["points"]
      # this is sorted as the client doesnt for map items
      points["points"] = sorted_results
    result = {"local": points}
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
      escaped_name = urllib2.quote(name)
      url = ("https://maps.googleapis.com/maps/api/place/nearbysearch/"
            "json?rankby=distance&types=%s&location=%f,%f&name=%s&sensor=false&key=%s")\
            % \
            (settings.config['place_types'],
             lat,
             lng,
             escaped_name,
             settings.config['google_api_key'] )
      response = urllib2.urlopen(url)
      jsonResult = response.read()
      addressResult = json.loads(jsonResult)
      addresses = []
    except Exception, e:
      logging.error('get_google_db_places Exception in Load', exc_info=True)
      return None
    if addressResult['status'] == "OK":
      try:
        origin = LatLng(lat=lat, lng=lng)
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
                    "lng": r['geometry']['location']['lng']}
          addresses.append(detail)
          results["item_count"] += 1
        results['items'] = addresses
        return results
      except Exception, e:
        logging.error('get_google_db_places Exception processing', exc_info=True)
        return results
    else:
      logging.error(
        "get_google_db_places near [%f,%f]: %s" %
          (lat, lng, addressResult['status']),
        exc_info=True)
      return results
