import base64
import urllib2
import datetime
from google.appengine.api import images, memcache
from google.appengine.api.images import Image
from google.appengine.api.mail import EmailMessage
from google.appengine.ext import db
from webapp2_extras import auth
import json
from webob.exc import HTTPUnauthorized
from auth_logic import user_required
from auth_model import UserProfile, User
from caching import memcache_get_user_dict, memcache_touch_user, \
  memcache_put_user_dict, memcache_touch_place
from dataloader import load_data
from geo import getPlaceDetailFromGoogle, geoCodeAddress, \
  adjust_votes_for_JSON_pt, item_to_json_point
from models import Item, DBImage, Vote, Category, getProp
from geo import LatLng, itemKeyToJSONPoint
from places_db import PlacesDB
from profiler import profile_in, profile_out
import settings
import logging
from webapp2_extras.auth import InvalidAuthIdError
from webapp2_extras.auth import InvalidPasswordError
from base_handler import BaseHandler

__author__ = 'Will'


class getItems_Ajax(BaseHandler):
  @user_required
  def get(self):
    """ get the items for a user
    @return:
    """
    profile_in("getItems_Ajax")
    result = PlacesDB.get_item_list(self.request, False, self.user_id)
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
      result.append(itemKeyToJSONPoint(it.key()))
    json.dump({"points": result,
               "length": len(result)},
              self.response.out)



#TODO: change to ndb! Then drop the memcache crazies, and do Since properly
def get_user_votes(current_user_id, user_id, since=None):
  user_dict = memcache_get_user_dict(user_id)
  votes = {}
  if 'v' in user_dict:
    votes = user_dict['v']
    if votes:
      logging.debug("get_user_votes: from memcache %d votes"%len(votes))
    else:
      logging.debug("get_user_votes: from memcache no votes")
  if not votes or len(votes) == 0 or not 'v' in user_dict:
    # we are going to memcache the votes so we get ALL votes & ignore since
    votes = Vote.get_user_votes(user_id)
    user_dict['v'] = votes
    memcache_put_user_dict(user_dict)
    logging.debug("get_user_votes: from db %d votes"%len(votes))
  # we ignore any 'untried' votes from a friend
  have_removed = 0
  #TODO: This is commented out for iOS bug #209, show wishlist items in news
  #TODO: BUT it was put here for some good reason for the web client?
  # if user_id != current_user_id:
  #   to_be_removed = []
  #   if votes:
  #     for vote in votes:
  #       if votes[vote]['untried']:
  #         to_be_removed.append(vote)
  #     for idx in to_be_removed:
  #       del votes[idx]
  #   logging.debug('get_user_votes: removed %d '%len(to_be_removed))

  return user_dict, votes


def serialize_user_details(user_id, places, current_user, request, since=None):
  """ give the list of votes & places for a user
  @param user_id: int: which user
  @param places: dict: list of places indexed by key (BY VALUE)
  @param current_user: int: current user - if same as user_id then
    we exclude untried
  @return:
  """
  try:
    logging.debug("serialize_user_details %d"%user_id)
    # get it from the cache
    user_dict, votes = get_user_votes(current_user, user_id, since)

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
          place_json = itemKeyToJSONPoint(place_key, request)
          if user_id == current_user:
            place_json['vote'] = votes[place_key]['vote']
            place_json['untried'] = votes[place_key]['untried']
          places[place_key] = place_json
      for place in places:
        places[place] = adjust_votes_for_JSON_pt(places[place])
      logging.debug('serialize_user_details: Added %d places'%len(places))
    else:
      logging.debug("serialize_user_details: No Votes")
    return result
  except Exception, e:
    logging.error("serialize_user_details Exception", exc_info=True)
    profile_out("serialize_user_details")

class friendsVotesAPI(BaseHandler):
  @user_required
  def get(self, id):
    """
    Get the votes for a friend
    :param id: string
    :return: json
    """
    friend_id = int(id)
    user_dict, votes = get_user_votes(self.user_id, friend_id)
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
    if settings.config['all_are_friends']:
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
        res.append(itemKeyToJSONPoint(key))
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
    gn = self.request.params["gender"]
    self.user.screen_name = sn
    self.user.sex = gn
    self.user.put()
    self.response.out.write("OK")


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
            settings.config['DATETIME_FORMAT']) - \
                  settings.config['TIMING_DELTA'];
        # is it for a specific user?
        if "forUser" in self.request.params:
          for_1_user = long(self.request.get("forUser"))
        else:
          for_1_user = None

        # either the first lookup is for me, plus everyone,
        # or it is for a specified user
        result = {"id": my_id}
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
          if settings.config['all_are_friends']:
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
  @user_required
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
             settings.config['google_api_key'],
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
      names[0].lower(),
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
      sender=settings.config['system_email'],
      to=email,
      subject="Rayv Registration",
      body="Click here to confirm your email address " + verification_url
    )
    message.send()
    logging.info('Verification email sent to '+email)
    self.display_message(msg.format(url=verification_url))

class updateItem(BaseHandler):
  @user_required
  def get(self, key):
    """
    " get a single item
    """
    try:
      it = Item.get_item(key)
      it_json = item_to_json_point(it, self.request, uid_for_votes=self.user_id)
      # adjust the votes so my own is not added to the up/down score
      adjust_votes_for_JSON_pt(it_json)
      json.dump(it_json, self.response.out)
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
    # it.put()
    # old_votes = it.votes.filter("voter =", self.user_id)
    # for v in old_votes:
    #   v.delete()
    # vote = Vote()
    # vote.item = it
    # vote.voter = self.user_id
    # vote.comment = self.request.get('descr')
    # vote.vote = 1 if self.request.get("vote") == "like" else -1
    # vote.put()
    # it.put()  # again
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
      changed[field_name]=str(old_val)+"->"+str(value)
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
      it.telephone = detail['telephone'] if 'telephone' in detail else None
      it.website = detail['website'] if 'website' in detail else None

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
  it.put()
  # refresh cache
  memcache_touch_place(it)
  update_votes(it, self, user_id)
  # todo: why?
  it.put()  # again
  # mark user as dirty
  memcache_touch_user(user_id)
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
    it_json = item_to_json_point(it, self.request, uid_for_votes=self.user_id)
    # adjust the votes so my own is not added to the up/down score
    adjust_votes_for_JSON_pt(it_json)
    json.dump(it_json, self.response.out)


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
    it.put()
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
