import base64
import urllib
import urllib2
import time
import datetime
from google.appengine.api import images, memcache
from google.appengine.api.images import Image
from google.appengine.api.mail import EmailMessage
from google.appengine.ext import db
import json
import math
from webob.exc import HTTPUnauthorized
from auth_logic import user_required, api_login_required
from auth_model import User
from dataloader import load_data
import geohash
from models import Item, DBImage, Vote, Category, getProp, \
  memcache_get_user_dict, memcache_put_user_dict, memcache_touch_user, \
  memcache_update_user_votes, memcache_touch_place, get_category, get_user_votes
from places_db import PlacesDB
from profiler import profile_in, profile_out
from settings import config
import logging
from webapp2_extras.auth import InvalidAuthIdError
from webapp2_extras.auth import InvalidPasswordError
from base_handler import BaseHandler
from settings_per_server import server_settings

__author__ = 'Will'


class getItems_Ajax(BaseHandler):
  @user_required
  def get(self):
    """ get the items for a user
    @return:
    """
    profile_in("getItems_Ajax")
    result = PlacesDB.get_item_list(self.request, False, self.user_id)
    if result == None:
      self.abort(500)
    check_for_dirty_data(self.user_id, result, self.request)
    json.dump(result,
              self.response.out)
    profile_out("getItems_Ajax")

class getBook(BaseHandler):
  @user_required
  def get(self):
    voter_id = self.request.get("voter") if \
      "voter" in self.request.params else str(self.user_id)
    vote_list = Vote.all().filter("voter =", voter_id)
    result = []
    for vote in vote_list:
      it = vote.Item
      result.append(Item.key_to_json(it.key()))
    json.dump({"points": result,
               "length": len(result)},
              self.response.out)





def serialize_user_details(user_id, places, current_user, request, since=None):
  """ give the list of votes & places for a user
  @param user_id: int: which user
  @param places: dict: list of places indexed by key (BY VALUE)
  @param current_user: int: current user - if same as user_id then
    we exclude untried
  @return:
  """
  try:
    logging.info("serialize_user_details 1")
    # get it from the cache
    user_dict, votes = get_user_votes(user_id, since)

    if getProp(user_dict['p'], 'last_write'):
      last_write = user_dict['p'].last_write
    else:
      last_write = None
    result = {"votes": votes,
              "id": user_id,
              # todo is it first_name?
              'name': user_dict['u'].screen_name,
              'last_write': last_write}
    if votes:
      logging.debug("serialize_user_details: %d votes"%len(votes))
      added_places = 0
      for place_key in votes:
        if not place_key in places:
          place_json = Item.key_to_json(place_key, request)
          if user_id == current_user:
            place_json['vote'] = votes[place_key]['vote']
            place_json['untried'] = votes[place_key]['untried']
          if "category" in place_json:
            places[place_key] = place_json
      for place in places:
        pl = Item.get(places[place])
        json_data = pl.get_json()
        json_data['up'], json_data['down']= pl.json_adjusted_votes()
        places[place] = json_data
      logging.debug('serialize_user_details: Added %d places'%len(places))
    else:
      logging.debug("serialize_user_details: No Votes")
    return result
  except Exception, e:
    logging.error("serialize_user_details Exception", exc_info=True)

class friendsVotesAPI(BaseHandler):
  @user_required
  def get(self, id):
    """
    Get the votes for a friend
    :param id: string
    :return: json
    """
    friend_id = int(id)
    user_dict, votes = get_user_votes(friend_id)
    #votes is a dict, we want a array
    res = {
      'id': friend_id,
      'votes': votes.values()
    }
    json.dump(res, self.response.out, default=json_serial)
    return

class friendsAPI(BaseHandler):
  @user_required
  def get(self):
    """
    get the users friends
    :return:
    """
    friends_data = []
    if config['all_are_friends']:
      for user in User.query():
        if self.user_id == self.user_id:
          continue  # don't add myself again
        friends_data.append(self.user_id)
    else:
      assert False
      #TODO: check friends
      prof = user['p']
      for friend in prof.friends:
        friends_data.append(friend.userId)
    json.dump(friends_data, self.response.out, default=json_serial)
    return

class itemsAPI(BaseHandler):
  @user_required
  def get(self):
    """
    A list of keys is supplied in 'key_list', returns detail list
    :return: json: {items: list of places}
    """
    if 'key_list' in self.request.params:
      res = []
      key_list = json.loads(self.request.params['key_list'])
      for key in key_list:
        res.append(Item.key_to_json(key))
      json.dump({'items':res}, self.response.out, default=json_serial)
      return
    self.abort(403)

class profileAPI(BaseHandler):
  @user_required
  def get(self):
    if not hasattr(self.user,'sex'):
      self.user.sex = "";
    res = {
      'screen_name': self.user.screen_name,
      'email': self.user.email_address,
      'sex': self.user.sex,
    }
    json.dump({'profile':res}, self.response.out, default=json_serial)
    return

  @user_required
  def post(self):
    sn = self.request.params["screen_name"]
    if 'gender' in self.request.params:
      gn = self.request.params["gender"]
      self.user.sex = gn
    self.user.screen_name = sn
    self.user.put()
    self.response.out.write("OK")

class getUserRecordFast(BaseHandler):
  @user_required
  def get(self):
    """ get the user record, including friends' places """
    try:
      if self.user.blocked:
        raise Exception('Blocked')
      my_id = self.user_id

    except:
      logging.error('getFullUserRecord: User Exception')
      json.dump({'result':'FAIL'},
                  self.response.out,
                  default=json_serial)
      return

    if my_id:
      user = memcache_get_user_dict(my_id)
      if user:
        # logged in
        result = {
          "id": my_id,
          "admin": self.user.profile().is_admin }
        since = None
        if 'since' in self.request.params:
          # move since back in time to allow for error
          since = datetime.datetime.strptime(
            self.request.params['since'],
            config['DATETIME_FORMAT']) - \
                  config['TIMING_DELTA'];
        user_list = []
        user_results = []
        # is it for a specific user?
        if "forUser" in self.request.params:
          user_list.append(user.get(self.request.params['forUser']))
        else:
          if config['all_are_friends']:
            q = User.gql('')
            for user in q:
              user_list.append(user)
        places = {}
        my_user_dict, my_votes = get_user_votes(my_id, since)
        for u in user_list:
          user_id = u.get_id()
          if user_id == my_id:
            user_dict = my_user_dict
            votes = my_votes
          else:
            user_dict, votes = get_user_votes(u.get_id(), since)
          for v in votes:
            #add to the list if it's not there, or overwrite if this is my version
            if not v in places or user_id == my_id:
              place = Item.get(v)
              if user_id == my_id:
                place_json = place.json_adjusted_votes(user_id=my_id)
              else:
                place_json = place.get_json()
              places [v] = place_json

          if getProp(user_dict['p'], 'last_write'):
            last_write = user_dict['p'].last_write
          else:
            last_write = None
          user_str = {"votes": votes,
              "id": u.get_id(),
              # todo is it first_name?
              'name': user_dict['u'].screen_name,
              'last_write': last_write}
          user_results.append(user_str)

        result["places"] = places
        result["friendsData"] = user_results
        json_str = json.dumps(
          result,
          default=json_serial)
        self.response.out.write(json_str)
        #profile_out("getFullUserRecord")
        return
    self.error(401)






class getFullUserRecord(BaseHandler):
  @user_required
  def get(self):
    """ get the entire user record, including friends' places """
    try:
      if self.user.blocked:
        raise Exception('Blocked')
      my_id = self.user_id

    except:
      logging.error('getFullUserRecord: User Exception')
      json.dump({'result':'FAIL'},
                  self.response.out,
                  default=json_serial)
      return

    if my_id:
      #profile_in("getFullUserRecord")
      user = memcache_get_user_dict(my_id)
      if user:
        # logged in
        since = None
        if 'since' in self.request.params:
          # move since back in time to allow for error
          since = datetime.datetime.strptime(
            self.request.params['since'],
            config['DATETIME_FORMAT']) - \
                  config['TIMING_DELTA'];
        # is it for a specific user?
        if "forUser" in self.request.params:
          for_1_user = long(self.request.get("forUser"))
        else:
          for_1_user = None

        # either the first lookup is for me, plus everyone,
        # or it is for a specified user
        result = {
          "id": my_id,
          "admin": self.user.profile().is_admin }
        if for_1_user:
          logging.info("getFullUserRecord: 1 user")
          first_user = for_1_user
          result["for_1_user"] = for_1_user
        else:
          logging.info("getFullUserRecord: 1+ user")
          first_user = my_id
        places = {}
        # load the data for the 1 user  - me or specified
        friends_data = [
          serialize_user_details(
            first_user,
            places,
            my_id,
            self.request,
            since)]
        # was it for all users? If so we've only done ourselves
        if not for_1_user:
          # for all users
          prof = user['p']
          if config['all_are_friends']:
            q = User.gql('')
            logging.info("getFullUserRecord: %d friends"%q.count())
            for user in q:
            # for userProf in UserProfile().all():
              if user.get_id() == my_id:
                continue  # don't add myself again
              data = serialize_user_details(
                user.get_id(), places, my_id, self.request, since)
              logging.info("getFullUserRecord: record %s"%data)
              friends_data.append(data)
          else:
            for friend in prof.friends:
              friends_data.append(serialize_user_details(
                friend, places, my_id, self.request, since))
          result["friendsData"] = friends_data
          logging.debug('getFullUserRecord: return %d places'%len(places))
        result["places"] = places
        # encode using a custom encoder for datetime

        json_str = json.dumps(
          result,
          default=json_serial)
        self.response.out.write(json_str)
        #profile_out("getFullUserRecord")
        return
    self.error(401)

class api_log(BaseHandler):
  """
  Level is one of :
    'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG',
  """
  @user_required
  def post(self):
    message = self.request.POST["message"]
    level = int(self.request.POST["level"])
    logging.log(level, message)

class user_profile(BaseHandler):
  @user_required
  def get(self):
    user_obj = User().get_by_id(self.user_id)
    json.dump({'screen_name': user_obj.screen_name}, self.response.out)

  @user_required
  def post(self):
    user_obj = User().get_by_id(self.user_id)
    user_obj.screen_name = self.request.get('screen_name')
    user_obj.put()
    memcache_touch_user(self.user_id)

def json_serial(o):
  """
  JSON serializer for objects not serializable by default json code
     http://stackoverflow.com/questions/11875770/how-to-overcome-
            datetime-datetime-not-json-serializable-in-python
  """
  if type(o) is datetime.date or type(o) is datetime.datetime:
    return o.isoformat()


def check_for_dirty_data(user_id, results, request):
  # every server call, we look for dirty data and append it if needed
  prof = memcache_get_user_dict(user_id)['p']
  my_last_check = prof.last_read
  dirty_friends = []
  dirty_places = {}
  for friend in prof.friends:
    if (not my_last_check) or \
        (memcache_get_user_dict(friend)['p'].last_write > my_last_check):
      dirty_friends.append(
        serialize_user_details(friend, dirty_places, user_id, request))
  if len(dirty_friends) > 0:
    results['dirty_list'] = {"friends": dirty_friends,
                             "places": dirty_places}


class getCuisines_ajax(BaseHandler):
  @user_required
  def get(self):
    list = []
    cats =  Category.all()
    for cat in cats:
      list.append(cat.title)
    results = {'categories': list}
    json.dump(results,
               self.response.out);


class getAddresses_ajax(BaseHandler):
  @api_login_required
  def get(self):
    logging.debug('getAddresses_ajax')
    address = self.request.get("addr")
    lat = float(self.request.get("lat"))
    lng = float(self.request.get("lng"))
    names = self.request.get("place_name").split(" ")
    near_me = self.request.get("near_me")
    if near_me == u'0':
      # near the address
      url = ("https://maps.googleapis.com/maps/api/geocode/json?address=%s"
             "&sensor=false&key=%s&bounds=%f,%f|%f,%f") % \
            (urllib2.quote(address),
             config['google_api_key'],
             lat-0.3,
             lng-0.3,
             lat+0.3,
             lng+0.3)
      response = urllib2.urlopen(url)
      jsonResult = response.read()
      addressResult = json.loads(jsonResult)
      if addressResult['status'] == "OK":
        lat = addressResult['results'][0]['geometry']['location']['lat']
        lng = addressResult['results'][0]['geometry']['location']['lng']
    results = PlacesDB.map_and_db_search(
      self.request,
      -1,
      '',
      True,
      lat,
      lng,
      LatLng(lat=lat, lng=lng),
      self.request.get("place_name").lower(),
      self.user_id)
    if results:
      results['search'] = {'lat': lat,'lng':lng}
      check_for_dirty_data(self.user_id, results, self.request)
      json.dump(results,
                self.response.out,
                default=json_serial)
    else:
      # logging.info("get_google_db_places near [%f,%f]: %s" %
      # (lat, lng, "none found"))
      logging.debug("getAddresses_ajax - none found ")
      self.error(401)


def handle_error(request, response, exception):
  if request.path.startswith('/json'):
    response.headers.add_header('Content-Type', 'application/json')
    result = {
      'status': 'error',
      'status_code': exception.code,
      'error_message': exception.explanation,
    }
    response.write(json.dumps(result))
  else:
    response.write(exception)
  response.set_status(exception.code)


class MainHandler(BaseHandler):
  def get(self):
    if self.user:
      con = {"cats": Category.all()}
      logging.info('MainHandler: Logged in')
      self.render_template("index.html", con)
    else:
      logging.info('MainHandler: Not logged in')
      self.render_template("login.html")


class register(BaseHandler):
  def get(self):
    self.render_template('signup.html')

  def post(self):
    email = self.request.get('email')
    name = self.request.get('name')
    password = self.request.get('password')
    last_name = self.request.get('lastname')
    unique_properties = ['email_address']
    user_data = self.user_model.create_user(
      email,
      unique_properties,
      email_address=email,
      name=name,
      password_raw=password,
      last_name=last_name,
      verified=False)
    if not user_data[0]:  # user_data is a tuple
      self.render_template(
        'signup.html', {"message": "That userId is already registered", })
      return
    user = user_data[1]
    user_id = user.get_id()
    token = self.user_model.create_signup_token(user_id)
    verification_url = self.uri_for('verification', type='v', user_id=user_id,
                                    signup_token=token, _full=True)
    msg = 'An email has been sent to your account'
    message = EmailMessage(
      sender=config['system_email'],
      to=email,
      subject="Rayv Registration",
      body="Click here to confirm your email address " + verification_url
    )
    message.send()
    logging.info('Verification email sent to '+email)
    self.display_message(msg.format(url=verification_url))

class getPlaceDetailsApi(BaseHandler):
  @api_login_required
  def get(self):
    place_id = self.request.params['place_id']
    logging.debug('getPlaceDetailsApi '+place_id)
    params = {'placeid': place_id,
              'key': config['google_api_key']}
    url = "https://maps.googleapis.com/maps/api/place/details/json?" + \
          urllib.urlencode(params)
    res = {}
    try:
      response = urllib2.urlopen(url)
      json_result = response.read()
      details_result = json.loads(json_result)
    except:
      logging.error(
        'getPlaceDetailFromGoogle: Exception [%s]',
        place_id,
        exc_info=True)
      return {"photo": None, "telephone": None}

    if details_result['status'] == "OK":
      if "international_phone_number" in details_result['result']:
        res['telephone'] = details_result['result']["international_phone_number"]
      if "website" in details_result['result']:
        res['website'] = details_result['result']["website"]
    json.dump(res, self.response.out)


class updateItem(BaseHandler):
  @user_required
  def get(self, key):
    """
    " get a single item
    """
    try:
      it = Item.get(key)
      json_data = it.get_json()
      json_data['up'], json_data['down'] = it.json_adjusted_votes(user_id=self.user_id)
      json.dump(json_data, self.response.out)
    except:
      logging.error('updateItem GET Exception '+key,exc_info=True)

  @user_required
  def post(self, key):
    logging.error("updateitem is deprecated")
    self.abort(501)
    # it = None
    # try:
    #   it = Item.get_item(key)
    # except Exception:
    #   logging.exception("updateItem ", exc_info=True)
    #   # not found
    #   self.error(400)
    # # it.descr = self.request.get('descr')
    # # category
    # posted_cat = self.request.get("cat")
    # try:
    #   cat = Category.get_by_key_name(posted_cat)
    #   if cat:
    #     it.category = cat
    # except:
    #   logging.exception("Category not found %s" % posted_cat, exc_info=True)
    # it.save()
    # old_votes = it.votes.filter("voter =", self.user_id)
    # for v in old_votes:
    #   v.delete()
    # vote = Vote()
    # vote.item = it
    # vote.voter = self.user_id
    # vote.comment = self.request.get('descr')
    # vote.vote = 1 if self.request.get("vote") == "like" else -1
    # vote.put()
    # it.save()  # again
    # # refresh cache
    # memcache_touch_place(it)
    # # CategoryStatsDenormalised.addPost(self.user_id,master_cat)
    # # TODO this should be ajax
    # self.response.out.write(str(it.key()))


def update_photo(it, request_handler):
  try:
    raw_file = request_handler.request.get('new-photo')
    rot = request_handler.request.get("rotation")
    if len(raw_file) > 0:
      # a new image saved
      img = DBImage()  # - no: create it
      if rot and (rot <> u'0'):  # is a rotation requested?
        angle = int(rot) * 90
        raw_file = images.rotate(raw_file, angle)
      # exif = raw_file.get_original_metadata()
      img.picture = db.Blob(raw_file)
      img.make_thumb()
      img.owner = request_handler.user_id
      img.put()
      print 'update_photo Ins:',str(img.key())
      if it.photo:  # the item has an image already?
        print 'update_photo Del:',str(it.photo.key())
        db.delete(it.photo)
    else:
      # no new image - rotate an existing image?
      img = None  # no image supplied
      if rot and (rot != u'0'):  # is a rotation requested?
        old_img = it.photo
        if old_img and old_img.picture:
          # if so, does the item have a pic already?
          angle = int(rot) * 90  # rotate & save in place
          rotated_pic = images.rotate(old_img.picture, angle)
          old_img.picture = db.Blob(rotated_pic)
          old_img.thumb = None
          old_img.put()
  except Exception:
    logging.exception("newOrUpdateItem Image Resize: ", exc_info=True)
    img = None
  return img


def update_votes(item, request_handler, user_id):
  """
  save the vote for an item
  :param item: {Item}
  :param request_handler: {BaseHandler} for the request
  :param user_id: {int}
  """
  try:
    old_votes = item.votes.filter("voter =", user_id)
    for v in old_votes:
      v.delete()
    vote = Vote()
    vote.item = item
    vote.voter = user_id
    vote.comment =  request_handler.request.get('myComment')
    if request_handler.request.get("untried") == 'true':
      vote.untried = True
      vote.vote = 0
    else:
      vote_str = request_handler.request.get("voteScore")
      voteScore = 1 if vote_str == "1" or vote_str == "like" else -1
      vote.vote = voteScore
    vote.put()
    logging.info ('update_votes for %s "%s"=%d'%
                  (item.place_name,vote.comment,vote.vote))

  except Exception:
    logging.error("newOrUpdateItem votes exception", exc_info=True)


def update_item_internal(self, user_id, allow_update=True):
  def update_field(field_name, value):
    # so we can log edits
    old_val = getProp(it,field_name)
    if old_val != value:
      setattr(it,field_name,value)
      changed[field_name]="%s->%s"%(old_val,value)
  # is it an edit or a new?
  it = Item.get_unique_place(self.request, allow_update)
  if not it:
    # it will be None if it exists and not allow_update
    return None
  img = update_photo(it, self)
  # it.place_name = self.request.get('new-title') set in get_unique_place
  changed = {}
  update_field ('address', self.request.get('address'))
  it.owner = user_id
  if img:
    it.photo = img
  else:
    if not it.photo or not it.website:
      detail = getPlaceDetailFromGoogle(it)
      if not it.photo:
        # load one from google
        img = DBImage()
        remoteURL = detail['photo']
        if remoteURL:
          thumb_url=None
          try:
            main_url = remoteURL % 250
            data = urllib2.urlopen(main_url)
            img.picture = db.Blob(data.read())
            img.remoteURL = None
            thumb_url = remoteURL % 65
            thumb_data = urllib2.urlopen(thumb_url)
            img.thumb = db.Blob(thumb_data.read())
            img.put()
            it.photo = img
          except:
            if thumb_url:
              logging.error("update_item_internal: remote url ["+str(thumb_url)+"] Exception", exc_info=True)
            else:
              logging.error("update_item_internal: remote url Exception", exc_info=True)
            it.photo = None
      if 'telephone' in detail and detail['telephone'] != None:
        it.telephone = detail['telephone']
      if 'website' in detail and detail['website']:
        it.website = detail['website']

  if not it.telephone:
    it.telephone = self.request.get('telephone')
  if not it.website:
    it.website = self.request.get('website')

  # category
  if "new-item-category" in self.request.params:
    posted_cat = self.request.get("new-item-category")
  else:
    posted_cat = self.request.get("category")
  try:
    cat = Category.get_by_key_name(posted_cat)
  except:
    cat = None
  update_field('category', cat)
  if "place_name" in self.request.params:
    update_field('place_name', self.request.params['place_name'])
  it.save()
  # refresh cache
  memcache_touch_place(it)
  update_votes(it, self, user_id)
  # todo: why?
  it.save()  # again
  # mark user as dirty
  memcache_update_user_votes(user_id)
  logging.info("update_item_internal for "+it.place_name+": "+str(changed))
  return it

class UpdateItemFromAnotherAppAPI(BaseHandler):
  def post(self):
    #https://cloud.google.com/appengine/docs/python/
    # appidentity/#Python_Asserting_identity_to_other_App_Engine_apps
    logging.debug("UpdateItemFromAnotherAppAPI")
    #TODO: Security
    #if app_identity.get_application_id() != settings.API_TARGET_APP_ID:
    #  logging.debug("UpdateItemFromAnotherAppAPI 403: %s != %s"%\
    # (app_identity.get_application_id(),settings.API_TARGET_APP_ID))
    #  self.abort(403)
    #app_id = self.request.headers.get('X-Appengine-Inbound-Appid', None)
    #logging.info('UpdateItemFromAnotherAppAPI: from app %s'%app_id)
    #if app_id in settings.ALLOWED_APP_IDS:
    if True:
      seed_user = None
      for u in User.query():
        if 'pegah' in u.auth_ids:
          seed_user = u.key.id()
          break
      if seed_user:
        logging.debug("UpdateItemFromAnotherAppAPI user:"+str(seed_user))
        params = ""
        for k in self.request.params:
          params += '"%s": "%s"'%(k, self.request.params[k])
        logging.debug("UpdateItemFromAnotherAppAPI params: "+params)
        if update_item_internal(self, seed_user, allow_update=False):
          logging.debug("UpdateItemFromAnotherAppAPI Done ")
        else:
          logging.debug("UpdateItemFromAnotherAppAPI Existed ")
        self.response.out.write("OK")
      else:
        logging.error("UpdateItemFromAnotherAppAPI - couldn't get seed user",
                      exc_info=True)
        self.abort(500)
    else:
      logging.debug("UpdateItemFromAnotherAppAPI not allowed")
      self.abort(403)


class newOrUpdateItem(BaseHandler):
  @user_required
  def post(self):
    it = update_item_internal(self, self.user_id, allow_update=True)
    # adjust the votes so my own is not added to the up/down score
    json.dump(it.json_adjusted_votes(self.user_id), self.response.out)


class loadTestData(BaseHandler):
  def get(self):
    results = None
    try:
      section = self.request.get("section")
      geoCode = self.request.get("useFakeGeoCoder")
      results = load_data(section=section, useFakeGeoCoder=geoCode)
      self.render_template("dataLoader.html", {"results": results})
    except Exception, E:
      self.render_template(
        "dataLoader.html", {"results": results, "message": E})


class wipeAndLoadTestData(BaseHandler):
  def get(self):
    results = None
    try:
      results = load_data(wipe=True)
      self.render_template(
        "dataLoader.html", {"results": results})
    except Exception, E:
      self.render_template(
        "dataLoader.html", {"results": results, "message": E})


class loadPlace(BaseHandler):
  @user_required
  def get(self):
    self.render_template("item.html")

class geoLookup(BaseHandler):
  def get(self):
    self.render_template("geoLookup.html", {"mobile": False})


  def post(self):
    address = self.request.get('address')
    posn = LatLng(
      lat=self.request.params['lat'],
      lng=self.request.params['lng'])
    pos = geoCodeAddress(address, posn)
    if pos:
      params = {
        "lat": pos['lat'],
        "lng": pos['lng'],
        "mobile": False,
        "categories": ["deprecated"],
      }
      self.render_template("newOrUpdateItem.html", params)
    else:
      self.display_message("Unable to lookup address")


class getItem_ajax(BaseHandler):
  @user_required
  def get(self, key):
    try:
      it = Item.get_item(key)
      res = {"place_name": it.place_name,
             "address": it.address,
             "category": it.category.title,
             "lat": str(it.lat),
             "lng": str(it.lng),
             "key": str(it.key())
      }
      if it.photo:
        res["img"] = str(it.key())
      if it.owner == self.user_id:
        res["mine"] = True
        res["descr"], res["vote"] = it.vote_from(it.owner)
      else:
        res["mine"] = False
        res["descr"], res["vote"] = it.vote_from(self.user_id)
      json.dump(res, self.response.out)
    except Exception:
      logging.error("getItem_ajax Exception", exc_info=True)
      self.error(500)


class getItemVotes_ajax(BaseHandler):
  @user_required
  def get(self, key):
    res = {}
    it = Item.get_item(key)
    if it:
      votes = it.votes
      # TODO: .order("when") but there are missing values for when
      cursor = self.request.get("cursor")
      if cursor:
        votes.with_cursor(start_cursor=cursor)
      results = votes[0:20]
      next_cursor = votes.cursor()
      res["cursor"] = next_cursor
      more = len(results) >= 20
      html = self.render_template_to_string(
        "item-votes-list.htt",
        {"votes": results, "more": more})
      res["votesList"] = html
      res["more"] = more
      json.dump(res, self.response.out)
    else:
      self.abort(501)


class ImageHandler(BaseHandler):
  def get(self, key):
    try:
      photo = db.get(key)
      if photo:
        self.response.headers['Content-Type'] = 'image/png'
        self.response.out.write(photo.picture)
    except:
      logging.error('ImageHandler '+key, exc_info=True)


class ThumbHandler(BaseHandler):
  def get(self, key):
    try:
      photo = db.get(key)
      if photo:
        self.response.headers['Content-Type'] = 'image/png'
        self.response.out.write(photo.get_thumb())
      else:
        default_thumb = memcache.get('DEFAULT-THUMB')
        if not default_thumb:
          default_thumb = Image()
          default_thumb.resize(65,55)
          self.response.headers['Content-Type'] = 'image/png'
          self.response.out.write(default_thumb)
          memcache.set('DEFAULT-THUMB', default_thumb)
    except Exception:
      logging.error('ThumbHandler '+key, exc_info=True)

class search(BaseHandler):
  def get(self):
    return None


class logout(BaseHandler):
  def get(self):
    logging.info("Logging out")
    self.auth.unset_session()
    return self.render_template("login.html")


class loginAPI(BaseHandler):
  def get(self):
    username = ""
    try:
      logging.debug("Login API Started")
      logging.debug("Login headers " + str(self.request.headers.environ))
      token = None
      if 'HTTP_AUTHORIZATION' in self.request.headers.environ:
        token = self.request.headers.environ['HTTP_AUTHORIZATION']
      elif 'Authorization' in self.request.headers:
        token = self.request.headers['Authorization']
      if token:
        (username, password) = base64.b64decode(token.split(' ')[1]).split(':')
        user = self.user_model.get_by_auth_id(username)
        if user and user.blocked:
            logging.info('views.loginAPI: Blocked user '+username)
            self.abort(403)
        self.auth.get_user_by_password(username, password, remember=True,
                                       save_session=True)
        logging.info('LoginAPI: Logged in')
        #tok = user.create_auth_token(self.user_id)
        #self.response.out.write('{"auth":"%s"}'%tok)
      else:
        logging.warning('LoginAPI no auth header')
        self.abort(401)
    except (InvalidAuthIdError, InvalidPasswordError, HTTPUnauthorized) :
      logging.info(
        'LoginAPI failed for userId %s',
        username, exc_info=True)
      self.abort(401)
    except Exception:
      logging.exception(
        'LoginAPI failed because of unexpected error', exc_info=True)
      self.abort(500)

class login(BaseHandler):
  def post(self):
    username = ""
    try:
      logging.debug("Login Started")
      username = self.request.get('username')
      user = self.user_model.get_by_auth_id(username)
      if user and user.blocked:
          logging.info('views.login: Blocked user '+username)
          return self.render_template("login.html", {"message": "Login Denied"})
      password = self.request.get('password')
      self.auth.get_user_by_password(username, password, remember=True,
                                     save_session=True)
      con = {"cats": Category.all()}
      logging.info('Login: Logged in')
      return self.render_template("index.html", con)
    except (InvalidAuthIdError, InvalidPasswordError) :
      logging.info(
        'Login failed for userId %s'%username, exc_info=True)
      return self.render_template("login.html", {"message": "Login Failed"})
    except Exception:
      logging.exception(
        'Login failed because of unexpected error %s', exc_info=True)
      return self.render_template("login.html", {"message": "Server Error"})

  def get(self):
    logging.debug("Login GET")
    return self.render_template("login.html")


class addVote_ajax(BaseHandler):
  @user_required
  def post(self):
    it_key = self.request.get('item_id')
    it = Item.get_item(it_key)
    voteScore = int(self.request.get("vote"))
    my_votes = it.votes.filter('voter =', self.user_id)
    if my_votes.count() == 0:
      # a new vote
      new_vote = Vote()
      new_vote.item = it
      new_vote.voter = self.user_id
    else:
      # roll back the old vote
      new_vote = my_votes.get()
      oldVote = new_vote.vote
      if oldVote:
        if oldVote > 0:
          it.votesUp -= oldVote
        else:
          # all votes are abs()
          it.votesDown -= oldVote
    new_vote.vote = voteScore
    new_vote.comment = self.request.get("comment")
    new_vote.when = datetime.datetime.now()
    new_vote.put()
    if voteScore > 0:
      it.votesUp += voteScore
    else:
      it.votesDown += abs(voteScore)
    it.save()
    # refresh cache
    memcache.set(it_key, it)
    memcache.delete("JSON:" + it_key)
    self.response.out.write('OK')

class getMapList_Ajax(BaseHandler):
  @user_required
  def get(self):
    result = PlacesDB.get_item_list(
      request=self.request,
      include_maps_data=True,
      user_id=self.user_id,
      exclude_user_id=self.user_id)
    if result == None:
      self.abort(500)
    json.dump(result,
              self.response.out)


class imageEdit_Ajax(BaseHandler):
  @user_required
  def post(self):
    it = Item.get_item(self.request.get('image-id'))
    rotate_direction = int(self.request.get("image-rotate"))
    if it.photo:
      db_image = it.photo
    else:
      db_image = DBImage()
    raw_file = images.Image(self.request.get('image-img'))
    if rotate_direction == 1:
      # clockwise
      raw_file.rotate(90)
    elif rotate_direction == -1:
      raw_file.rotate(-90)
    db_image.picture = db.Blob(raw_file)
    db_image.put()
    memcache_touch_place(it)
    self.response.out.write('OK')


class ping(BaseHandler):
  @user_required
  def get(self):
    self.response.write('OK')

class api_delete(BaseHandler):
  @user_required
  def post(self):
    deleteItem.delete_item(self, self.request.POST["key"])


class deleteItem(BaseHandler):
  @user_required
  def post(self, key):
    self.delete_item(self, key)

  @staticmethod
  def delete_item(handler, key):
    try:
      item = Item.get_item(key)
      if item:
        my_votes = item.votes.filter('voter =', handler.user_id)
        for vote in my_votes:
          logging.info("deleteItem: " + str(vote.key()))
          vote.delete()
      memcache_touch_user(handler.user_id)
      handler.response.write('OK')
    except Exception:
      logging.error("delete_item", exc_info=True)
      handler.abort(500)

class passwordVerificationHandler(BaseHandler):
    def get(self, *args, **kwargs):

        user = None
        user_id = kwargs['user_id']
        signup_token = kwargs['signup_token']
        verification_type = kwargs['type']

        # it should be something more concise like
        # self.auth.get_user_by_token(user_id, signup_token)
        # unfortunately the auth interface does not (yet) allow to manipulate
        # signup tokens concisely
        user, ts = self.user_model.get_by_auth_token(int(user_id), signup_token,
                                                     'signup')

        if not user:
            logging.info(
              'Could not find any userId with id "%s" signup token "%s"',
              user_id,
              signup_token)
            self.abort(404)

        # store userId data in the session
        self.auth.set_session(self.auth.store.user_to_dict(user), remember=True)

        if verification_type == 'v':
            # remove signup token,
            # we don't want users to come back with an old link
            self.user_model.delete_signup_token(self.user_id, signup_token)

            if not user.verified:
                user.verified = True
                user.put()

            self.display_message('User email address has been verified.')
            return
        elif verification_type == 'p':
            # supply userId to the page
            params = {
                'userId': user,
                'token': signup_token
            }
            self.render_template('resetpassword.html', params)
        else:
            logging.info('verification type not supported')
            self.abort(404)

def getPlaceDetailFromGoogle(item):
  logging.debug('getPlaceDetailFromGoogle '+item.place_name)
  place_name = item.place_name.encode('utf-8')
  params = {'radius': 150,
            'types': config['place_types'],
            'location': '%f,%f' % (item.lat, item.lng),
            'name': place_name,
            'sensor': False,
            'key': config['google_api_key']}
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
        (lat, lng, config['google_api_key'])
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

class geoCodeAddressMultiple(BaseHandler):

  @api_login_required
  def get(self):
    address = self.request.params['address']
    #TODO: these could be trivially cached
    url = ("https://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor"
           "=false&key=%s") % \
          (urllib2.quote(address), config['google_api_key' ])
    try:
      response = urllib2.urlopen(url)
      jsonGeoCode = response.read()
      geoCode = json.loads(jsonGeoCode)
      json.dump(geoCode, self.response.out)
    except:
      logging.error( 'geoCodeAddressMultiple: Exception [%s]', address, exc_info=True)
      return None

def geoCodeAddress(address, search_centre):
  url = ("https://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor"
         "=false&key=%s") % \
        (urllib2.quote(address), config['google_api_key' ])
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
                        request,
                        search_text=None,
                        filter=None,
                        uid=None,
                        position=None,
                        exclude_user_id=None,
                        place_names=None,
                        ignore_votes=False):
  try:
    cache = {}
    logging.debug("findDbPlacesNearLoc Start")
    result_list = []
    reject_list = []
    for geo_precision in range(6, 3, -1):
      geo_code = geohash.encode(
        my_location.lat, my_location.lng, precision=geo_precision)
      query_result = Item.all(keys_only=True).\
        filter("geo_hash >", geo_code).\
        filter("geo_hash <", geo_code + "{")
      if search_text:
        #if we're looking for a name, filter the results to find it
        for point_key in query_result:
          if point_key in result_list:
            continue
          if point_key in reject_list:
            continue
          if point_key in cache:
            it = cache[point_key]
          else:
            it = Item.get_item(str(point_key))
            cache[point_key] = it
          if search_text in it.place_name.lower():
            result_list.append(point_key)
            continue
          reject_list.append(point_key)
        if len(result_list)>5:
          break
        continue
      elif query_result.count() > 10:
        for point_key in query_result:
          if not point_key in result_list:
            it = Item.get_item(str(point_key))
            cache[point_key] = it
            result_list.append(point_key)
        break
    search_results = []
    return_data = {}
    return_data['count'] = 0
    return_data['points'] = []
    exclude_user_id = None
    if filter:
      if filter["kind"] == "mine":
        # how does this fit? geo search and list of all mine are too different
        logging.error("findDbPlacesNearLoc Assertion failure")
        assert False
        my_id = filter["userId"]
        temp_results = []
        for key in result_list:
          if cache[key].owner == my_id:
            temp_results.append(key)
        # initial_results = Item.all(keys_only=True).\
        #   filter("owner =", my_id)  # TODO: owner does not make it mine - votes
      if 'exclude_user' in filter:
        exclude_user_id = filter['exclude_user']
    user = memcache_get_user_dict(uid)
    for point_key in result_list:
      if point_key in cache:
        it = cache[point_key]
      else:
        it = Item.get_item(str(point_key))
      json_data = it.get_json()
      json_data['up'], json_data['down'] = it.json_adjusted_votes(user_id=uid)
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
    jit = Item.key_to_json(point_key)
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



def google_point_to_json(it, request, GPS_origin=None, map_origin=None, uid_for_votes=None):
  """
  create a json object for the web.
  :param it: Gooogle result
  :param request: BaseHandler
  :param GPS_origin: LatLng
  :param map_origin: bool - do we calculate distances from where the map is
          centred, as opposed to from my location?
  :return: dict - json repr of the place
  """
  try:
    if request:
      base_url = request.url[:request.url.find(request.path)]
    else:
      base_url = ""
    if getProp(it, 'photo'):
      if it.photo.picture:
        image_url = base_url+'/img/' + str(it.photo.key())
        thumbnail_url = base_url+'/thumb/' + str(it.photo.key())
        image_url.replace('https','http')
        thumbnail_url.replace('https','http')
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
      try:
        edit_time_unix = int(time.mktime(edit_time.timetuple())) * 1000
      except:
        edit_time_unix = 0
    else:
      edit_time_unix = 0
    data = {
      'lat': getProp(it, 'lat'),
      'lng': getProp(it, 'lng'),
      'website': getProp(it, 'website',''),
      'address': getProp(it, 'address',''),
      'key': str(it.key()) if type(it) is Item else "",
      'place_name': getProp(it, 'place_name'),
      'place_id': getProp(it,'place_id',''),
      'category': category.title if category else "",
      'telephone': getProp(it, 'telephone', ''),
      'untried': False,
      'vote': 'null',
      'img': image_url,
      'edited': edit_time_unix,
      'thumbnail': thumbnail_url,
      'up': it.votes.filter("vote =", 1).count() if hasattr(it, 'votes') else 0,
      'down': it.votes.filter("vote =", -1).count() if
                                                hasattr(it, 'votes') else 0,
      'owner': getProp(it, 'owner',''),
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
    logging.exception('to_json', exc_info=True)



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
