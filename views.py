import re
import urllib
import urllib2
import datetime
from time import strptime

from google.appengine.ext import ndb
from google.appengine.api import images, memcache
from google.appengine.api.images import Image
from google.appengine.ext import db
import json
from webob.exc import HTTPUnauthorized
from auth_logic import user_required, api_login_required, CheckAPILogin
from auth_model import User
from dataloader import load_data
import mail_wrapper
from models import Item, DBImage, Vote, Category, getProp, \
  Invite, Friends, InviteInternal, Comment, Feedback
from places_db import PlacesDB
from profiler import profile_in, profile_out
from settings import config
import logging
from webapp2_extras.auth import InvalidAuthIdError
from webapp2_extras.auth import InvalidPasswordError
from base_handler import BaseHandler
from logging_ext import logging_ext
import ndb_models
import geo
import settings

__author__ = 'Will'


class GetItemsAjax(BaseHandler):
  @user_required
  def get(self):
    """ get the items for a user
    @return:
    """
    profile_in("GetItemsAjax")
    result = PlacesDB.get_item_list(self.request, False, self.user_id)
    if not result:
      self.abort(500)
    json.dump(result,
              self.response.out)
    profile_out("GetItemsAjax")




def serialize_user_details(user_id, places_ids, current_user, request, since=None):
  """ give the list of votes & places_ids for a user
  @param user_id: int: which user
  @param places_ids: dict: list of places_ids indexed by key (BY VALUE)
  @param current_user: int: current user - if same as user_id then
    we exclude untried
  @return:
  """
  try:
    logging.info("serialize_user_details 1")
    # get it from the cache
    user_id = int(user_id)
    votes = Vote.query(Vote.voter == user_id)
    user = User.get_by_id(user_id)
    user_profile = user.profile()
    if getProp(user_profile, 'last_write'):
      last_write = user_profile.last_write
    else:
      last_write = None
    result = {"votes": votes,
              "id": user_id,
              # todo is it first_name?
              'name': user_profile.screen_name,
              'last_write': last_write}
    if votes:
      logging.debug("serialize_user_details: %d votes"%len(votes))
      for place_key in votes:
        if not place_key in places_ids:
          place_json = Item.id_to_json(place_key)
          # if user_id == current_user:
          #   place_json['vote'] = votes[place_key]['vote']
          if "category" in place_json:
            places_ids[place_key] = place_json
      for place_id in places_ids:
        pl = ndb.Key(Item,place_id).get()
        json_data = pl.get_json()
        places_ids[place_id] = json_data
      logging.debug('serialize_user_details: Added %d places_ids'%len(places_ids))
    else:
      logging.debug("serialize_user_details: No Votes")
    return result
  except Exception, e:
    logging_ext.error("serialize_user_details Exception", exc_info=True)

class FriendsVotesApi(BaseHandler):
  @user_required
  def get(self, id):
    """
    Get the votes for a friend
    :param id: string
    :return: json
    """
    friend_id = int(id)
    votes = Vote.query(Vote.voter ==friend_id)
    res = {
      'id': friend_id,
      'votes': [vote.json for vote in votes]
    }
    json.dump(res, self.response.out, default=json_serial)
    return

class FriendsApiRemove(BaseHandler):
  @api_login_required
  def post(self):
    """
    accept a friend request
    :return:
    """
    other_id = int(self.request.params['unfriend_id'])
    my_id = int(self.user_id)
    low = min(other_id, my_id)
    high = max(other_id, my_id)
    record = Friends.query(Friends.lower == low, Friends.higher == high).get()
    if record:
      record.key.delete()
      # delete invites
      inv_from = InviteInternal.query().\
        filter(InviteInternal.inviter == other_id).\
        filter(InviteInternal.invitee == my_id)
      for i in inv_from:
        i.key.delete()
      inv_to = InviteInternal.query().\
        filter(InviteInternal.inviter == my_id).\
        filter(InviteInternal.invitee == other_id)
      for i in inv_to:
        i.key.delete()
      self.response.out.write("OK")
      return
    self.response.out.write("FAIL")



class FriendsApiAccept(BaseHandler):
  @api_login_required
  def post(self):
    """
    accept a friend request
    :return:
    """
    from_id = self.request.params['from_id']
    #find the invite
    # inv = InviteInternal.all().get()
    # inv = InviteInternal.all().filter("invitee =", self.user_id).get()
    inv = InviteInternal.query().\
      filter(InviteInternal.invitee == self.user_id).\
      filter(InviteInternal.inviter == int(from_id)).\
      get()
    if not inv:
      self.response.out.write("NO INVITE")
      return
    Friends.addFriends(self.user_id, from_id)
    logging.info("FriendsApiAccept %s from %s"%(self.user_id, from_id))
    #delete invite
    inv.accepted = True
    inv.when = datetime.datetime.now()
    inv.put()
    self.response.out.write("OK")

class FriendsApiReject(BaseHandler):
  @api_login_required
  def post(self):
    """
    accept a friend request
    :return:
    """
    from_id = self.request.params['from_id']
    #find the invite
    # inv = InviteInternal.all().get()
    # inv = InviteInternal.all().filter("invitee =", self.user_id).get()
    inv = InviteInternal.query().\
      filter(InviteInternal.invitee == self.user_id).\
      filter(InviteInternal.inviter == int(from_id)).\
      get()
    if inv:
      inv.key.delete()
    self.response.out.write("OK")

class FriendsApi(BaseHandler):
  @api_login_required
  def get(self):
    """
    get the users friends
    :return:
    """
    friends_data = []
    if config['all_are_friends']:
      for user in User.query():
        if user.get_id() == self.user_id:
          continue  # don't add myself again
        friends_data.append(self.user_id)
    else:
      assert False
      #TODO: check friends
      prof = user.profile()
      for friend in prof.friends:
        friends_data.append(friend.userId)
    json.dump(friends_data, self.response.out, default=json_serial)
    return

class itemsAPI(BaseHandler):
  @api_login_required
  def get(self):
    """
    A list of keys is supplied in 'key_list', returns detail list
    :return: json: {items: list of places}
    """
    if 'key_list' in self.request.params:
      res = []
      key_list = json.loads(self.request.params['key_list'])
      for key in key_list:
        res.append(Item.id_to_json(key))
      json.dump({'items':res}, self.response.out, default=json_serial)
      return
    self.abort(403)

class profileAPI(BaseHandler):
  @user_required
  def get(self):
    if not hasattr(self.user,'sex'):
      self.user.sex = ""
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
      logging_ext.error('getFullUserRecord: User Exception')
      json.dump({'result':'FAIL'},
                  self.response.out,
                  default=json_serial)
      return

    if my_id:
      user = User.get_by_id(my_id)
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
                  config['TIMING_DELTA']
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
        my_votes = Vote.query(Vote.voter==my_id)
        for u in user_list:
          user_id = u.get_id()
          if user_id == my_id:
            votes = my_votes
          else:
            votes = Vote.query(Vote.voter==u.get_id())
          for v in votes:
            #add to the list if it's not there, or overwrite if this is my version
            if not v in places or user_id == my_id:
              places [v] = Item.id_to_json(v)

          user_profile = u.profile()
          if getProp(user_profile, 'last_write'):
            last_write = user_profile.last_write
          else:
            last_write = None
          user_str = {"votes": votes,
              "id": u.get_id(),
              # todo is it first_name?
              'name': u.screen_name,
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
      logging_ext.error('getFullUserRecord: User Exception')
      json.dump({'result':'FAIL'},
                  self.response.out,
                  default=json_serial)
      return

    if my_id:
      #profile_in("getFullUserRecord")
      user = User.get_by_id(my_id)
      if user:
        # logged in
        since = None
        if 'since' in self.request.params:
          # move since back in time to allow for error
          since = datetime.datetime.strptime(
            self.request.params['since'],
            config['DATETIME_FORMAT']) - \
                  config['TIMING_DELTA']
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
        dict_id_place = {}
        # load the data for the 1 user  - me or specified
        friends_data = [
          serialize_user_details(
            first_user,
            dict_id_place,
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
                user.get_id(), dict_id_place, my_id, self.request, since)
              logging.info("getFullUserRecord: record %s"%data)
              friends_data.append(data)
          else:
            for friend in prof.friends:
              friends_data.append(serialize_user_details(
                friend, dict_id_place, my_id, self.request, since))
          result["friendsData"] = friends_data
          logging.debug('getFullUserRecord: return %d places'%len(dict_id_place))
        result["places"] = dict_id_place
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

def json_serial(o):
  """
  JSON serializer for objects not serializable by default json code
     http://stackoverflow.com/questions/11875770/how-to-overcome-
            datetime-datetime-not-json-serializable-in-python
  """
  if type(o) is datetime.date or type(o) is datetime.datetime:
    return o.isoformat()




class getCuisines_ajax(BaseHandler):
  @api_login_required
  def get(self):
    cuisines_list = []
    cats =  Category.query()
    for cat in cats:
      cuisines_list.append(cat.title)
    results = {'categories': cuisines_list}
    json.dump(results,
               self.response.out)


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
      geo.LatLng(lat=lat, lng=lng),
      self.request.get("place_name").lower(),
      self.user_id)
    if results:
      results['search'] = {'lat': lat,'lng':lng}
      # check_for_dirty_data(self, results)
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
      con = {"cats": Category.query()}
      logging.info('MainHandler: Logged in')
      self.render_template("index.html", con)
    else:
      logging.info('MainHandler: Not logged in')
      self.render_template("login.html")

class InviteUserAPI(BaseHandler):
  @api_login_required
  def get(self):
    # invite a user to the system - get the invite URI
    token = Invite.getInviteToken(self.user_id)
    uri = self.uri_for('register',type='i', invite_token=token, _full=True)
    self.response.out.write(uri)


class register(BaseHandler):
  def get(self):
    # get the registration form. Embed the invite token in it
    params = None
    if 'type' in self.request.params:
      if self.request.params["type"] == "i":
        # it's an invite
        params = {'invite_token':self.request.params['invite_token']}
    logging.info("register,GET token=%s"%self.request.params['invite_token'])
    self.render_template('signup.html', params)

  def post(self):
    # posted a filled out reg form
    # create the user,
    # and send an email verification including token to the new user
    email = self.request.get('email').lower()
    name = self.request.get('name')
    password = self.request.get('password')
    last_name = self.request.get('lastname')
    unique_properties = ['email_address']
    logging.info("register,POST email=%s"%email)
    user_data = self.user_model.create_user(
      email,
      unique_properties,
      email_address=email,
      name=name,
      password_raw=password,
      last_name=last_name,
      verified=False)
    if not user_data[0]:  # user_data is a tuple
      logging.warning("register,POST Duplicate %s"%email)
      self.render_template(
        'signup.html', {"message": "That userId is already registered", })
      return
    user = user_data[1]
    user_id = user.get_id()
    token = self.user_model.create_signup_token(user_id)
    invite_token = self.request.params['invite_token'] if \
      'invite' in self.request.params \
      else "none"
    inviter = Invite.checkInviteToken(invite_token)
    if inviter:
       passwordVerificationHandler.handle_verification(self,user_id,token,"v",invite_token)
    else:
        verification_url = self.uri_for('verification', type='v', user_id=user_id,
                                        signup_token=token, _full=True)
        verification_url += "&invite_token=" + str(invite_token)
        logging.info("register,POST emailing")
        mail_wrapper.send_mail(
          sender=config['system_email'],
          to=[email, 'wgilpin+taste5@gmail.com'],
          subject="Rayv Registration",
          body='Click on this link to verify your address and '
               'complete the sign-up process \n'+
                verification_url
        )
        logging.info('Verification email sent to %s [%s] [%s]'%(email,verification_url, invite_token))
        params = {
          'email':email,
          'password':password
        }
        self.render_template('signup-verify.html', params)

class AddUserAsFriend(BaseHandler):
  @api_login_required
  def get(self):
    user_email = self.request.get('email').lower()
    logging.info("AddUserAsFriend "+user_email)
    user = User.query(ndb.GenericProperty('email_address') == user_email).get()
    if not user:
          user = User.query(ndb.GenericProperty('email_address') == user_email).get()

    if user.get_id() == self.user_id:
      self.response.out.write("EMAIL TO SELF")
      return
    if user:
      InviteInternal.add_invite(self.user_id, user.key.id())
      self.response.out.write("FOUND")
    else:
      self.response.out.write("NOT FOUND")

class emailInviteFriend(BaseHandler):
  @api_login_required
  def post(self):
    user_email = self.request.get('email').lower()
    if not re.match('[^@]+@[^@]+\.[^@]+',user_email):
      self.response.out.write("BAD EMAIL")
      return
    logging.info("emailInviteFriend "+user_email.lower())
    token = Invite.getInviteToken(self.user_id)
    uri = self.uri_for('register',type='i', invite_token=token, _full=True)
    msg = "Hi,\n I'd like to share my favourite eateries with you using the Taste5 app, "+\
    "Click this link to join for free!\n\n"+uri+"\n\n"+self.user.screen_name
    mail_wrapper.send_mail(sender=settings.config['system_email'],
                   to=user_email,
                   subject="Share my list of places to eat!",
                   body=msg)
    logging.info("Email invite sent to %s by %s"%(user_email,self.user_id))
    self.response.out.write("OK")


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
      logging_ext.error(
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
      json.dump(Item.id_to_json(key), self.response.out)
    except:
      logging_ext.error('updateItem GET Exception '+key,exc_info=True)


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
      logging.debug('update_photo Ins:',img.key.id())
      if it.photo:  # the item has an image already?
        logging.debug( 'update_photo Del:',it.photo.id())
        it.photo.delete()
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
    old_votes = Vote.query(Vote.voter == user_id, Vote.item == item.key)
    for v in old_votes:
      v.key.delete()
    vote = Vote()
    vote.item = item.key
    vote.voter = user_id
    vote.comment =  unicode(request_handler.request.get('myComment'))
    vote.meal_kind =  int(request_handler.request.get('kind'))
    vote.place_style=  int(request_handler.request.get('style'))
    vote.cuisine = Category.get_by_id(request_handler.request.get('cuisine')).key
    vote_stars = int(request_handler.request.get("voteScore"))
    vote.stars = vote_stars
    if vote_stars == 0:
      vote_untried= bool(request_handler.request.get("voteUntried"))
    else:
      vote_untried = False
    vote.untried = vote_untried
    vote.put()
    ndb_models.mark_vote_as_updated(str(vote.key.id()), user_id)
    logging.info ('update_votes for %s "%s"=%d'%
                  (item.place_name,vote.comment,vote.stars))

  except Exception, ex:
    logging_ext.error("newOrUpdateItem votes exception", exc_info=True)
    raise


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
        #TODO: make this async: load one from google
      detail = geo.getPlaceDetailFromGoogle(it)
      if not it.photo:
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
            it.photo = img.key
          except:
            if thumb_url:
              logging_ext.error("update_item_internal: remote url ["+str(thumb_url)+"] Exception", exc_info=True)
            else:
              logging_ext.error("update_item_internal: remote url Exception", exc_info=True)
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
  posted_cat = self.request.get("cuisine")
  try:
    cat_key = ndb.Key(Category,posted_cat)
  except:
    cat_key = None
  update_field('category', cat_key)
  if "place_name" in self.request.params:
    update_field('place_name', self.request.params['place_name'])
  it.put() # so the key is set
  # refresh cache
  update_votes(it, self, user_id)
  # todo: why?
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
        logging_ext.error("UpdateItemFromAnotherAppAPI - couldn't get seed user",
                      exc_info=True)
        self.abort(500)
    else:
      logging.debug("UpdateItemFromAnotherAppAPI not allowed")
      self.abort(403)

def check_good_server_version(request):
  good_version = False
  if 'version' in request.params:
    version = float(request.params['version'])
    min_version = ndb_models.Config.min_server_version_allowed()
    if version >= float(min_version):
      return True
  if not good_version:
    logging_ext.error("check_good_server_version BAD VERSION")
    return False

class newOrUpdateItem(BaseHandler):
  @user_required
  def post(self):
    try:
      if not check_good_server_version(self.request):
        self.response.out.write("BAD VERSION")
        return
      it = update_item_internal(self, self.user_id)
      logging.info('newOrUpdateItem %s by %s'%(it.place_name, self.user_id))
      ndb_models.mark_place_as_updated(str(it.key.id()),str(self.user_id))
      vote = Vote.query(Vote.voter == self.user_id, Vote.item == it.key).get()
      res = {'place':it.get_json(),
             'vote': vote.to_json()}
      json.dump(res, self.response.out)
    except:
      logging_ext.error('newOrUpdateItem', exc_info=True)

class UpdateVote(BaseHandler):
  @user_required
  def post(self):
    if not check_good_server_version(self.request):
        self.response.out.write("BAD VERSION")
        return
    id = self.request.get('key')
    it = ndb.Key(Item, int(id)).get()
    if it:
      update_votes(it, self, self.user_id)
      # mark user as dirty
      self.response.out.write('OK')
      logging.debug("UpdateVote OK")
      return
    logging_ext.error("UpdateVote 404 for %s"%id)
    self.abort(404)



class loadTestData(BaseHandler):
  def get(self):
    results = None
    try:
      section = self.request.get("section")
      results = load_data(section=section)
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

    pos = geo.geoCodeAddress(address)
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
  def get(self, id):
    """
    get an Item
    :param id: int
    :return: string json
    """
    try:
      it = Item.get_by_id(int(id))
      res = {"place_name": it.place_name,
             "address": it.address,
             "cuisineName": it.category.title,
             "lat": str(it.lat),
             "lng": str(it.lng),
             "id": it.key.id()
      }
      if it.photo:
        res["img"] = it.key.id()
      if it.owner == self.user_id:
        res["mine"] = True
        res["descr"], res["stars"], res["untried"] = it.vote_from(it.owner)
      else:
        res["mine"] = False
        res["descr"], res["stars"], res["untried"] = it.vote_from(self.user_id)
      json.dump(res, self.response.out)
    except Exception:
      logging_ext.error("getItem_ajax Exception", exc_info=True)
      self.error(500)


class getItemVotes_ajax(BaseHandler):
  @user_required
  def get(self, id):
    """
    votes for an item
    :param id: int
    :return: json dict
    """
    res = {}
    it = Item.get_by_id(int(id))
    if it:
      votes = Vote.query(Vote.item == it.key)
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
      photo = ndb.Key(urlsafe=key).get()
      if photo:
        self.response.headers['Content-Type'] = 'image/png'
        self.response.out.write(photo.picture)
    except:
      logging_ext.error('ImageHandler '+key, exc_info=True)


class ThumbHandler(BaseHandler):
  def get(self, key):
    try:
      photo = ndb.Key(urlsafe=key).get()
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
      logging_ext.error('ThumbHandler '+key, exc_info=True)

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
    username = ''
    try:
      logging.debug("Login API Started")
      username, isOk = CheckAPILogin(self)
    except (InvalidAuthIdError, InvalidPasswordError, HTTPUnauthorized) :
      logging.info(
        'LoginAPI failed for userId %s',
        username)
      self.abort(401)
    except Exception, ex:
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
      if not user:
          logging.info('views.login: No such user '+username)

          return self.render_template("login.html", {"message": "Bad User"})
      if user and user.blocked:
          logging.info('views.login: Blocked user '+username)
          return self.render_template("login.html", {"message": "Login Denied"})
      password = self.request.get('password')
      self.auth.get_user_by_password(username, password, remember=True,
                                     save_session=True)
      con = {"cats": Category.query()}
      logging.info('Login: Logged in')
      return self.render_template("index.html", con)
    except InvalidAuthIdError, E:
      if config['log_passwords']:
        logging.info(
          'Login failed for userId %s/%s - InvalidAuthIdError'%(username, password))
      else:
        logging.info(
          'Login failed for userId %s - InvalidAuthIdError'%(username))
      return self.render_template("login.html", {"message": "Login Failed"})
    except InvalidPasswordError, E:
      if config['log_passwords']:
        logging.info(
          'Login failed for userId %s/%s - InvalidPasswordError'%(username, password))
      else:
        logging.info(
          'Login failed for userId %s - InvalidPasswordError'%(username))
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
    it_id = int(self.request.get('item_id'))
    it = Item.get_by_id(it_id)
    voteScore = int(self.request.get("vote"))
    voteUntried = bool(self.request.get("untried"))
    my_votes = Vote.query(Vote.voter == self.user_id, Vote.item == it.key)
    if my_votes.count() == 0:
      # a new vote
      new_vote = Vote()
      new_vote.item = it
      new_vote.voter = self.user_id
    else:
      # roll back the old vote
      new_vote = my_votes.get()
      oldVote, oldUntried = new_vote.stars, new_vote.untried
    new_vote.stars = voteScore
    new_vote.untried = voteUntried
    new_vote.comment = self.request.get("comment")
    new_vote.when = datetime.datetime.now()
    new_vote.put()
    it.save()
    # refresh cache
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
    it = Item.get_by_id(int(self.request.get('image-id')))
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
  # delete the votes for an item
  @user_required
  def post(self, key):
    self.delete_item(self, key)

  @staticmethod
  def delete_item(handler, id):
    """
    deletes the votes for an item
    :param handler: RequestHandler
    :param id: int
    :return:
    """
    try:
      item = Item.get_by_id(int(id))
      if item:
        my_votes = Vote.query(Vote.voter == handler.user_id, Vote.item == item.key)
        for vote in my_votes:
          logging.info("deleteItem: " + str(vote.key))
          vote.key.delete()
      handler.response.write('OK')
    except Exception:
      logging_ext.error("delete_item", exc_info=True)
      handler.abort(500)


class passwordVerificationHandler(BaseHandler):
    @classmethod
    def handle_verification(cls, handler, user_id,signup_token,verification_type,invite_token):
        # it should be something more concise like
        # self.auth.get_user_by_token(user_id, signup_token)
        # unfortunately the auth interface does not (yet) allow to manipulate
        # signup tokens concisely
        user, ts = handler.user_model.get_by_auth_token(int(user_id), signup_token,
                                                     'signup')

        if not user:
            logging.info(
              'Could not find any userId with id "%s" signup token "%s"',
              user_id,
              signup_token)
            handler.display_message("Not found - if you've already followed this link there is no need to do it again")
            return

        # store userId data in the session
        handler.auth.set_session(handler.auth.store.user_to_dict(user), remember=True)

        if verification_type == 'v':
            # remove signup token,
            # we don't want users to come back with an old link
            handler.user_model.delete_signup_token(handler.user_id, signup_token)

            if not user.verified:
                user.verified = True
                user.put()
            try:
              if invite_token and invite_token != 'none':
                inv = Invite.checkInviteToken(invite_token)
                Friends.addFriends(inv, handler.user_id)
                Invite.delInviteToken(invite_token)
                logging.info("passwordVerificationHandler complete "+user.email_address)
            except:
              logging_ext.error(
                "Failed to add friend: passwordVerificationHandler GET",
                exc_info=True)
            handler.render_template('signup-complete.html')
        elif verification_type == 'p':
            # supply userId to the page
            params = {
                'userId': user,
                'token': signup_token
            }
            handler.render_template('resetpassword.html', params)
        else:
            logging.info('verification type not supported')
            handler.abort(404)


    def get(self, *args, **kwargs):

        user = None
        user_id = kwargs['user_id']
        signup_token = kwargs['signup_token']
        verification_type = kwargs['type']
        invite_token = self.request.params['invite_token']\
          if 'invite_token' in self.request.params\
          else None

        self.handle_verification(self,user_id,signup_token,verification_type,invite_token)

class RegisterApnsToken(BaseHandler):
  @api_login_required
  def post(self):
    """
    Register the token against current user
    Params:
    token: string: the token
    kind: string: platform - one of iOS, Android, WinPhone
    :return:
    """
    token = str(self.request.params['token']).translate(None, '< >')
    device_kind_str = self.request.params['kind'].lower()
    device_kind = ndb_models.NotificationToken.ios
    if device_kind_str == 'android':
      device_kind = ndb_models.NotificationToken.android
    if device_kind_str == 'winphone':
      device_kind = ndb_models.NotificationToken.winPhone
    tr = ndb_models.NotificationToken.query(
      ndb_models.NotificationToken.userId == self.user_id,
      ndb_models.NotificationToken.kind == device_kind).get()
    if not tr:
      tr = ndb_models.NotificationToken()
      tr.kind = device_kind
      tr.userId = self.user_id
    tr.token = token
    tr.put()


class FbRedirect (BaseHandler):
  def get(self):
    con = {"email": Category.query()}
    tok_list = ",".join(self.request.GET)
    logging_ext.info('FbRedirect: Params '+tok_list)
    try:
      # get the token
      token = self.request.params["access_token"]

      # is the email a user?
      # email not known

      # check if token is registered for user
      # if not, store it
      # log the user
      logging.info('FbRedirect: Logged in')
      con['message'] = "Logged in using facebook"
      self.render_template("oauth-fb.html", con)
    except:
      logging_ext.error("Unable to read data", exc_info=True)
      con['message'] = "Unable to read data"
      self.render_template("oauth-fb.html", con)

class WebServer(BaseHandler):
  def get(self):
    self.render_template("www-index.html")

class CommentsUpdatesHandler(BaseHandler):
  @api_login_required
  def get(self):
    """
    Get any updates on my comments
    :return: list of vote ids
    """
    author = self.user_id
    since = datetime.datetime.strptime(
              self.request.params['since'],
              config['DATETIME_FORMAT']) - \
                config['TIMING_DELTA']
    from ndb_models import  Change
    results = {}
    votesQ = Change.query(
        Change.kind == Change.CHANGE_COMMENT,
        Change.subscriberId == str(author),
        Change.when > since)
    for v in votesQ:
        results[v.recordId]= v.when
    json.dump({"changed_votes":results},
              self.response.out,
              default=json_serial)

class CommentsHandler(BaseHandler):
  @api_login_required
  def get(self):
    """
    Get all comments for a vote
    param: Vote: int
    :return: list of json comments
    """
    vote_id = self.request.get("vote")
    vote = Vote.get_by_id(int(vote_id))
    list = []
    if vote:
      comments_q = Comment.query(Comment.vote == vote.key)
      for c in comments_q:
        list.append(c.get_json())
    json.dump({"comments":list},
              self.response.out)

  @api_login_required
  def post(self):
    """
    Put a single comment, update or insert
    params:
    vote: int
    author: int
    comment: string
    when: datetime
    :return:
    """
    when = datetime.datetime.strptime(
            self.request.params['when'],
            config['DATETIME_FORMAT'])
    author = int(self.request.get('author'))
    vote_id  = int(self.request.get('vote'))
    if vote_id:
      vote_key = ndb.Key(Vote,vote_id)
      comment = Comment.query(
          Comment.author == author,
          Comment.when == when,
          Comment.vote == vote_key
      ).get()
      if not comment:
        comment = Comment()
        comment.author = author
        comment.vote = vote_key
      comment.when = when
      comment.comment = self.request.get('comment')
      comment.put()
      vote_record = vote_key.get()
      vote_record.put()
      change_record = ndb_models.Change()
      change_record.kind = ndb_models.Change.CHANGE_COMMENT
      change_record.when = when
      change_record.subscriberId = str(vote_record.voter)
      change_record.recordId = str(vote_id)
      change_record.put()
      self.response.out.write('OK')
    else:
      self.abort(500)

class FeedbackHandler(BaseHandler):
  @api_login_required
  def get(self):
    """
    Get all feedback for a user
    :return: list of json feedbacks
    """
    # get feedbacks
    try:
      feedbacksQ = Feedback.query(Feedback.user == self.request.userId)
      feedbacks = []
      for f in feedbacksQ:
        feedbacks.append(f.to_json())
      json.dump({"comments":list},
              self.response.out)
    except Exception, e:
      logging.error("FeedbackHandler.get",e)

  @api_login_required
  def post(self):
    """
    Write a feedback for a user
    Params:
    ReplyTo: int: 0 if a new item
    Comment: string
    """
    try:
      feedbackId = int(self.request.get('ReplyTo'))
      fb = None
      if feedbackId>0:
        #find item
        fb = Feedback.get_by_id(feedbackId)
      if not fb:
        # new item
        fb = Feedback()
        fb.user = self.user_id
      fb.comment = self.request.get('Comment')
      fb.admin_response = self.user.profile().is_admin
      fb.put()
      self.response.out.write("OK")
    except Exception, e:
      logging.error("FeedbackHandler.post",e)

