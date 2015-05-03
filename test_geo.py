import os
os.environ['DJANGO_SETTINGS_MODULE'] = os.path.dirname(__file__)
from unittest import TestCase
from dataloader import load_one_user, load_one_item
import geo

__author__ = 'Will'


class TestGeo(TestCase):
  item = None
  user = None

  def load_user_and_item(self):
    self.user = load_one_user(0)[1]
    assert self.user
    self.item = load_one_item(self.user)
    assert self.item

  def test_getPlaceDetailFromGoogle(self):
    self.fail()

  def test_geoCodeLatLng(self):
    # lat, lng):
    addr = geo.geoCodeLatLng(51.574841, -0.121519)
    assert addr.find('Crouch Hill') > -1

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
    crouch = geo.LatLng(lat=51.579585, lng=-0.123729)
    cinema = geo.LatLng(lat=51.536812, lng=-0.103633)
    dist = geo.approx_distance(crouch, cinema)
    actual = 3.06
    assert (actual * 0.9) < dist < (actual * 1.1)

  def test_itemKeyToJSONPoint(self):
    #key):
    self.fail()

  def test_itemToJSONPoint(self):
    #it, GPS_origin=None, map_origin=None):
    self.fail()
