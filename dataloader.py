import logging
from random import random, randint
import urllib2
from google.appengine.ext import db
import time
from auth_model import User
import models
import geohash
import geo
import settings

__author__ = 'Will'

Categories = ['American',
              'Argentinian',
              'British',
              'Burger',
              'Cafe',
              'Caribbean',
              'Chinese',
              'Deli',
              'Fast food',
              'Fish and chips',
              'French',
              'Gastro pub',
              'Greek',
              'Indian',
              'Italian',
              'Indonesian',
              'Japanese',
              'Korean',
              'Kosher',
              'Lebanese',
              'Lounge',
              'Malaysian',
              'Mexican',
              'Modern European',
              'Moroccan',
              'Pan-Asian',
              'Persian',
              'Peruvian',
              'Pizza',
              'Polish',
              'Portuguese',
              'Russian',
              'Seafood',
              'Spanish',
              'Steakhouse',
              'Swedish',
              'Thai',
              'Turkish',
              'Vegetarian']

Users = [["pegah", "pegah.pp@googlemail.com", "Pegah", "Parandian", "pegah"],
         ["Will", "will@google.com", "William", "Gilpin", "tortois"],
         ["evan", "evan@geodeticapartners.com", "Evan", "Wienburg", "casper"], ]

#for testing
UserRecords=[]

items_data_list = [  # Name, Address, Kind
           ['The Queens', '26 Broadway Parade London', 'British'],
           ['WOW Japanese', '18 Crouch End Hill, London', 'Japanese'],
           ['Devonshire House', 'Crouch End 2-4 The Broadway, London', 'British'],
           ['St James', '4, Topsfield Parade Middle Ln, London', 'Modern European'],
           ['The Old Dairy', '1-3 Crouch Hill London', 'British'],
           ['Satay Malaysia', '10 Crouch End Hill London', 'Indonesian'],
           ['TooTooMoo', '12 Crouch End Hill, London, Crouch End, London N8 8AA', 'Pan-Asian'],
]
ITEM_NAME = 0
ITEM_ADDRESS = 1
ITEM_CATEGORY = 2

LatLongItems = [
  # ['Shit broadband', 51.381, -2.428, 'local'],
]

FriendsList = [['Will', 'pegah']]


def fakeGeoCode():
  lat = 54.0 + random()
  lng = -(1.0 + random())
  return {"lat": lat,
          "lng": lng}


def wipe_table(model):
  while True:
    q = db.GqlQuery("SELECT __key__ FROM " + model)
    if q.count() > 0:
      #TODO: ndb!
      db.delete(q.fetch(200))
      time.sleep(0.5)
    else:
      break


def add_addresses_to_db():
  res = []
  for it in models.Item.query():
    if (not it.address) or (it.address == "") or (it.address == "null"):
      logging.info("add_addresses_to_db %s @ %f,%f" % (it.place_name, it.lat, it.lng))
      new_addr = geo.geoCodeLatLng(it.lat, it.lng)
      if new_addr:
        it.address = new_addr
        it.save()
        res.append(it.place_name + ": " + it.address)
  return res

def load_one_user(user_number):
  usr = Users[user_number]
  user_name = usr[0]
  this_user = User.get_by_auth_id(user_name)
  if not this_user:
    email = usr[1]
    name = usr[2]
    last_name = usr[3]
    password = usr[4]

    unique_properties = ['email_address']
    this_user = User.create_user(user_name,
                                 unique_properties,
                                 email_address=email, name=name,
                                 password_raw=password,
                                 last_name=last_name, verified=False)
  else:
    this_user.set_password(usr[4])
    this_user.profile().is_admin = True
    this_user.profile().put()
  return this_user

def load_one_item(owner):
  item_test_data = items_data_list[0]
  it = models.Item.query(models.Item.place_name == item_test_data[ITEM_NAME]).get()
  if it:
    return it
  else:
    new_it = models.Item()
    cat = models.Category.get_by_id(item_test_data[ITEM_CATEGORY])
    if not cat:
      cat = models.Category(id=item_test_data[ITEM_CATEGORY]).put()
    new_it.category = cat
    new_it.place_name = item_test_data[ITEM_NAME]
    home = geo.LatLng(lat=51.57, lng=-0.13)
    lat_long = geo.geoCodeAddress(item_test_data[1], home)
    new_it.lat = lat_long['lat']
    new_it.lng = lat_long['lng']
    new_it.address = item_test_data[ITEM_ADDRESS]
    new_it.owner = owner.key.integer_id()
    # new_it.descr = "blah"
    new_it.geo_hash = geohash.encode(new_it.lat, new_it.lng)
    img = models.DBImage()
    detail = geo.getPlaceDetailFromGoogle(new_it)
    img.remoteURL = detail['photo']
    img.put()
    new_it.photo = img
    new_it.telephone = detail['telephone']
    new_it.put()
    return new_it



def load_data(wipe=False, section=None, Max=None):
  if not settings.running_on_test_server():
    return "Forbidden"
  result_strings = []
  if geo.geoCodeAddress("1 Crouch Hill, London"):
    # if we can geocode, we will - no fake
    fakeGeoCoder = None
  else:
    # if we cant geocode, use the fake one
    fakeGeoCoder = fakeGeoCode
  if section == "addresses":
    return add_addresses_to_db()
  else:
    if wipe:
      # wipe_table("User")
      wipe_table("Category")
      wipe_table("Item")
      wipe_table("Vote")
      print "wiped"
    if not section or section == 'user':
      for idx, usr in enumerate(Users):
        if Max:
          if idx >= Max:
            break
        user_name = usr[0]
        this_user = User.get_by_auth_id(user_name)
        if not this_user:
          email = usr[1]
          name = usr[2]
          last_name = usr[3]
          password = usr[4]

          unique_properties = ['email_address']
          this_user = User.create_user(user_name,
                                       unique_properties,
                                       email_address=email, name=name,
                                       password_raw=password,
                                       last_name=last_name, verified=False)
          if not this_user[0]:  # user_data is a tuple
            result_strings.append("ERROR - User: " + usr[0])
          else:
            user = this_user[1]
            user.screen_name = name
            user.put()
            UserRecords.append(user)
            result_strings.append("User: " + usr[0])
        else:
          this_user.set_password(usr[4])
          this_user.profile().is_admin = True
          this_user.profile().put()
          result_strings.append("User exists: " + usr[0])
    a_sample_user = User.get_by_auth_id(Users[0][0])  # used for the owner of the records
    print "users ok"
    if not section or section == "category":
      for idx, cat in enumerate(Categories):
        if Max:
          if idx >= Max:
            break
        if models.Category.get_by_id(cat):
          result_strings.append("Category exists: " + cat)
        else:
          new_cat = models.Category(id=cat)
          new_cat.title = cat
          new_cat.put()
          result_strings.append("Created: " + cat)

    print "category ok"
    if not section or section == "item":
      home = geo.LatLng(lat=51.57, lng=-0.13)
      for idx, item in enumerate(items_data_list):
        if Max:
          if idx >= Max:
            break
        it = models.Item.query(models.Item.place_name == item[0]).get()
        if it:
          result_strings.append("Item exists: " + item[0])
          it.category = models.Category.get_by_id(item[2]).key
          it.save()
        else:
          new_it = models.Item()
          new_it.category = models.Category.get_by_id(item[2]).key
          new_it.place_name = item[0]
          lat_long = fakeGeoCode() if fakeGeoCoder else geo.geoCodeAddress(item[1])
          new_it.lat = lat_long['lat']
          new_it.lng = lat_long['lng']
          new_it.address = item[1]
          new_it.owner = a_sample_user.key.id()
          # new_it.descr = "blah"
          new_it.geo_hash = geohash.encode(new_it.lat, new_it.lng)
          img = models.DBImage()
          detail = geo.getPlaceDetailFromGoogle(new_it)
          remoteURL = detail['photo']
          if remoteURL:
            main_url = remoteURL % 250
            data = urllib2.urlopen(main_url)
            img.picture = db.Blob(data.read())
            img.remoteURL = None
            thumb_url = remoteURL % 65
            thumb_data = urllib2.urlopen(thumb_url)
            img.thumb = db.Blob(thumb_data.read())
          img.put()
          new_it.photo = img.key
          new_it.telephone = detail['telephone']
          new_it.put()
          result_strings.append('Item: ' + item[0])

      print "items"
      # votes
      items = models.Item.query()
      i = 0
      for idx, vote_item in enumerate(items):
        if Max:
          if idx >= Max:
            break
        vote = models.Vote()
        vote_score = randint(0,5)
        if vote_score == 0:
          vote.stars = 0
          vote.untried = True
        else:
          vote.stars = vote_score
          vote.untried = False
        vote.comment = "blah v" + str(i)
        vote.voter = a_sample_user.key.integer_id()
        vote.item = vote_item.key
        vote.cuisine = vote_item.category
        vote.put()
        i += 1
      result_strings.append("Votes")
      print "votes"

    if not section or section == 'friends':
      for idx, pair in enumerate(FriendsList):
        if Max:
          if idx >= Max:
            break
        left = User.get_by_auth_id(pair[0])
        right = User.get_by_auth_id(pair[1])
        left_prof = left.profile()
        models.Friends.addFriends(left.get_id(), right.get_id())
        result_strings.append("Friends %s - %s" % (pair[0], pair[1]))
    print "friends"
    return result_strings


