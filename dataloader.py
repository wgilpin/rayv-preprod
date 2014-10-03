import logging
from random import random
from google.appengine.ext import db
import time
from webapp2_extras import auth
import auth_logic
from auth_model import User
from models import Category, Item, Vote, DBImage
import views
import geohash
from os.path import isfile
from auth_logic import BaseHandler


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

Users = [["Will", "will@google.com", "William", "Gilpin", "tortois"],
         ["Matt", "matt@google.com", "Matthew", "Gilpin", "tortois"],
         ["evan", "evan@geodeticapartners.com", "Evan", "Wienburg", "casper"],
         ["pegah", "pegah.pp@googlemail.com", "Pegah", "Parandian", "pegah"], ]

Items = [  # Name, Address, Kind
           ['WOW Japanese', '18 Crouch End Hill, London', 'Japanese'],
           ['Devonshire House', 'Crouch End 2-4 The Broadway, London', 'British'],
           ['St James', '4, Topsfield Parade Middle Ln, London', 'Modern European'],
           ['The Old Dairy', '1-3 Crouch Hill London', 'British'],
           ['The Queens', '26 Broadway Parade London', 'British'],
           ['Satay Malaysia', '10 Crouch End Hill London', 'Indonesian'],
           ['TooTooMoo', '12 Crouch End Hill, London, Crouch End, London N8 8AA', 'Pan-Asian'],
]

LatLongItems = [
  # ['Shit broadband', 51.381, -2.428, 'local'],
]

Friends = [['Will', 'pegah']]


def fakeGeoCode():
  lat = 54.0 + random()
  lng = -(1.0 + random())
  return {"lat": lat,
          "lng": lng}


def wipe_table(model):
  while True:
    q = db.GqlQuery("SELECT __key__ FROM " + model)
    if q.count() > 0:
      db.delete(q.fetch(200))
      time.sleep(0.5)
    else:
      break


def add_addresses_to_db():
  res = []
  for it in Item.all():
    if (not it.address) or (it.address == "") or (it.address == "null"):
      logging.info("add_addresses_to_db %s @ %f,%f" % (it.place_name, it.lat, it.lng))
      new_addr = views.geoCodeLatLng(it.lat, it.lng)
      if new_addr:
        it.address = new_addr
        it.put()
        res.append(it.place_name + ": " + it.address)
  return res


def load_data(wipe=False, section=None, useFakeGeoCoder=None):
  # TODO: THIS MUST BE REMOVED BEFORE LIVE!!
  if section == "addresses":
    return add_addresses_to_db()
  else:
    if wipe:
      # wipe_table("User")
      wipe_table("Category")
      wipe_table("Item")
      wipe_table("Vote")

    res = []
    print "wiped"
    if not section or section == 'user':
      for usr in Users:
        user_name = usr[0]
        this_user = User.get_by_auth_id(user_name)
        if not this_user:
          email = usr[1]
          name = usr[2]
          last_name = usr[3]
          password = usr[4]

          unique_properties = ['email_address']
          this_user = auth.get_auth().store.user_model.create_user(user_name,
                                                                   unique_properties,
                                                                   email_address=email, name=name,
                                                                   password_raw=password,
                                                                   last_name=last_name, verified=False)
          if not this_user[0]:  # user_data is a tuple
            res.append("ERROR - User: " + usr[0])
          res.append("User: " + usr[0])
        else:
          this_user.set_password(usr[4])
          this_user.profile().is_admin = True
          this_user.profile().put()
          res.append("User exists: " + usr[0])
    a_sample_user = User.get_by_auth_id(Users[0][0])  # used for the owner of the records
    print "users ok"
    if not section or section == "category":
      for cat in Categories:
        if Category.get_by_key_name(cat):
          res.append("Category exists: " + cat)
        else:
          new_cat = Category(key_name=cat)
          new_cat.title = cat
          new_cat.put()
          res.append("Created: " + cat)

    print "category ok"
    if not section or section == "item":
      for item in Items:
        it = Item.all().filter('place_name =', item[0]).get()
        if it:
          res.append("Item exists: " + item[0])
          it.category = Category.get_by_key_name(item[2])
          it.put()
        else:
          new_it = Item()
          new_it.category = Category.get_by_key_name(item[2])
          new_it.place_name = item[0]
          lat_long = fakeGeoCode() if useFakeGeoCoder else views.geoCodeAddress(item[1])
          new_it.lat = lat_long['lat']
          new_it.lng = lat_long['lng']
          new_it.address = item[1]
          new_it.owner = a_sample_user.key.id()
          # new_it.descr = "blah"
          new_it.geo_hash = geohash.encode(new_it.lat, new_it.lng)
          img = DBImage()
          detail = views.getPlaceDetailFromGoogle(new_it)
          img.remoteURL = detail['photo']
          img.put()
          new_it.photo = img
          new_it.telephone = detail['telephone']
          new_it.put()
          res.append('Item: ' + item[0])

      print "items"
      # votes
      items = Item.all()
      i = 0
      for vote_item in items:
        vote = Vote()
        vote_score = 1 if (vote_item.key().id() % 2) == 0 else -1
        vote.vote = vote_score
        vote.comment = "blah v" + str(i)
        vote.voter = a_sample_user.key.id()
        vote.item = vote_item
        vote.put()
        i += 1
      res.append("Votes")
      print "votes"

    if not section or section == 'friends':
      for pair in Friends:
        left = User.get_by_auth_id(pair[0])
        right = User.get_by_auth_id(pair[1])
        left_prof = left.profile()
        right_prof = right.profile()
        if not left.key.id() in right_prof.friends:
          right_prof.friends.append(left.key.id())
          right_prof.put()
        if not right.key.id() in left_prof.friends:
          left_prof.friends.append(right.key.id())
          left_prof.put()
        res.append("Friends %s - %s" % (pair[0], pair[1]))
    print "friends"
    return res


