from unittest import TestCase
from geo import approx_distance, LatLng

__author__ = 'Will'


class TestGeo(TestCase):
  def test_getPlaceDetailFromGoogle(self):
    self.fail()

  def test_geoCodeLatLng(self):
    # lat, lng):
    self.fail()

  def test_geo_distance(self):
    #point, origin):
    self.fail()

  def test_findDbPlacesNearLoc(self):
    #my_location, search_text=None, filter=None, uid=None, position=None, exclude_user_id=None,place_names=None, ignore_votes=False):
    self.fail()

  def test_geoSearch(self):
    #search_centre, my_location, radius=10, max=10, include_maps=False, search_text=None, filter=None):
    self.fail()

  def test_prettify_distance(self):
    #d):
    self.fail()

  def test_approx_distance(self):
    #point, origin):
    #crouch end to screen on the green
    crouch = LatLng(lat=51.579585, lng=-0.123729)
    cinema = LatLng(lat=51.536812, lng=-0.103633)
    dist = approx_distance(crouch, cinema)
    actual = 3.06
    assert (actual * 0.9) < dist < (actual * 1.1)

  def test_itemKeyToJSONPoint(self):
    #key):
    self.fail()

  def test_itemToJSONPoint(self):
    #it, GPS_origin=None, map_origin=None):
    self.fail()