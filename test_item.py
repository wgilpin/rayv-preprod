import os
import webapp2
os.environ['DJANGO_SETTINGS_MODULE'] = os.path.dirname(__file__)
import models


from dataloader import load_data, load_one_item, load_one_user, items_data_list, ITEM_NAME, ITEM_ADDRESS
from unittest import TestCase
from google.appengine.ext import testbed
from models import Item, Vote

__author__ = 'Will'


class TestItem(TestCase):
  item = None
  user = None
  item_data = items_data_list[0]

  def setUp(self):
    self.tb = testbed.Testbed()
    self.tb.setup_env()
    self.tb.activate()
    self.tb.init_datastore_v3_stub()
    self.tb.init_memcache_stub()



  def tearDown(self):
    self.tb.deactivate()

  def load_user_and_item(self):
    self.user = load_one_user(0)[1]
    assert self.user
    self.item = load_one_item(self.user)
    assert self.item

  def load_votes(self, user, vote_score, vote_comment):
    vote = Vote()
    vote.item = self.item
    vote.vote = vote_score
    vote.comment = vote_comment
    vote.voter = user.key.id()
    vote.put()

  def test_prop(self):
    self.load_user_and_item()
    item = Item.all().filter("place_name =",self.item_data[ITEM_NAME]).get()
    assert item.prop('address') == self.item_data[ITEM_ADDRESS]

  def test_qualified_title(self):
    self.load_user_and_item()
    assert self.item.__unicode__() == unicode(self.item_data[ITEM_NAME])

  def test_get_unique_place(self):
    self.load_user_and_item()
    r = webapp2.Request.blank('/?key=%s&lat=%d&lng=%d&new-title=%s'%(self.item.key(), self.item.lat, self.item.lng, self.item.place_name))
    it = self.item.get_unique_place(r)
    assert str(self.item.key()) == str(it.key())
    r_no_key = webapp2.Request.blank('/?key=%s&lat=%d&lng=%d&new-title=%s'%("", self.item.lat, self.item.lng, self.item.place_name))
    new_it = self.item.get_unique_place(r_no_key)
    assert str(self.item.key()) == str(it.key())


  def test_vote_from(self):
    self.load_user_and_item()
    self.load_votes(self.user,1,"Good Place")
    comment, vote, untried = self.item.vote_from(self.user.key.id())
    assert comment == "Good Place"
    assert vote == 1

  def test_closest_vote_from(self):
    self.load_user_and_item()
    self.load_votes(self.user,1,"Good Place")
    self.user.key.id()
    cvf = self.item.closest_vote_from(self.user.key.id())
    assert cvf.comment == "Good Place"
    assert cvf.vote == 1

  def test_get_item(self):
    self.load_user_and_item()
    got = Item.get_by_id(str(self.item.key()))
    assert got.place_name == self.item.place_name
