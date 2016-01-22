import json
import logging
import datetime
import re
from google.appengine.api import images, memcache
from google.appengine.api.images import CORRECT_ORIENTATION
import time
import auth_model
import geohash
from settings import config
import settings
from google.appengine.ext import ndb

__author__ = 'Will'


def getProp(obj, propName, falseValue=False):
  try:
    if hasattr(obj, propName):
      return getattr(obj, propName, falseValue)
    return obj[propName]
  except:
    return falseValue


# #####################################################################################
class Audit(ndb.Model):
  # who is logged on
  usr = ndb.IntegerProperty(required=False)
  # timestanp
  dt = ndb.DateTimeProperty(auto_now=True)
  # JSON object with data values - if NULL then only TextProperty is used
  values = ndb.TextProperty()
  # action - text
  action = ndb.TextProperty()
  subjectId = ndb.IntegerProperty(required=False)
  #TODO log ip - request.get_host()

  @classmethod
  def write(cls, kind, usr, msg, send_mail=True, subject=None, trace=None):
    if send_mail:
      try:
        if config['online']:  #DEBUG
          if trace:
            pass
            # TODO mail admins
            #mail_admins("Audit", "%s - %s \n %s" % (kind, msg, trace))
          else:
            pass
            # TODO mail admins
            #mail_admins("Audit", "%s - %s" % (kind, msg))
      except Exception as err:
        a = Audit()
        a.usr = None
        a.action = "Exception"
        a.values = "###### Cannot send Audit Mail: %s - %s - %s:%s" % \
                   (kind, msg, type(err), err)
        if subject:
          a.subjectId = subject
        a.put()
    try:
      a = Audit()
      if usr:
        if not usr.id:
          # fight the anonymous userId
          usr = None
      a.usr = usr
      a.action = kind
      a.values = msg
      if subject:
        a.subjectId = subject
      a.put()
    except Exception as err:
      Audit.log(None, "####### AUDIT FAIL. %s:%s" % (type(err), err))

  @classmethod
  def error(cls, usr, msg, send_mail=True, trace=None):
    Audit.write('Error', usr, msg, send_mail, trace=trace)
    try:
      print 'ERROR %s' % msg
    except:
      pass

  @classmethod
  def payment(cls, msg, send_mail=False, item=None):
    Audit.write('Payment', None, msg, send_mail)

  @classmethod
  def security(cls, usr, msg, send_mail=True, item=None):
    Audit.write('Payment', usr, msg, send_mail)

  @classmethod
  def log(cls, usr, msg, send_mail=False, item=None):
    try:
      if item:
        try:
          msg = msg + item.__str__()
        except:
          pass
      Audit.write('Log', usr, msg, send_mail)
    except:
      pass

  @classmethod
  def track(cls, usr, item, kind):
    Audit.write('Track', usr, kind, False, item)

  def __unicode__(self):
    return "%s %s [%s] User:%s" % (self.dt, self.action, self.values, self.usr)


class Address(ndb.Model):
  address = ndb.TextProperty()
  city = ndb.TextProperty()
  state = ndb.TextProperty(required=False)
  postal_code = ndb.TextProperty(required=False)
  country = ndb.TextProperty()


class Category(ndb.Model):
  # id is the slug
  title = ndb.TextProperty()



class DBImage(ndb.Model):
  title = ndb.TextProperty(required=False)
  picture = ndb.BlobProperty()
  thumb = ndb.BlobProperty(required=False)
  owner = ndb.IntegerProperty(required=False)  # key
  remoteURL = ndb.StringProperty(required=False)


  def make_thumb(self):
    window_ratio = 65.0 / 55.0
    height = images.Image(image_data=self.picture).height
    width = images.Image(image_data=self.picture).width
    image_ratio = float(width) / float(height)
    logging.info("thumb " + str(image_ratio))
    if image_ratio > window_ratio:
      # wide
      new_height = 55
      new_width = int(55.0 * image_ratio)
      self.thumb = images.resize(self.picture,
                                 new_width,
                                 new_height,
                                 output_encoding=images.JPEG,
                                 quality=55,
                                 correct_orientation=CORRECT_ORIENTATION)
      self.thumb = images.crop(self.thumb,
                               left_x=0.5 - 32.0 / new_width,
                               top_y=0.0,
                               right_x=0.5 + 32.0 / new_width,
                               bottom_y=1.0)
    else:
      new_width = 65
      new_height = int(65.0 / image_ratio)
      self.thumb = images.resize(self.picture,
                                 new_width, new_height,
                                 output_encoding=images.JPEG,
                                 quality=55,
                                 correct_orientation=CORRECT_ORIENTATION)
      self.thumb = images.crop(self.thumb,
                               left_x=0.0,
                               top_y=0.5 - 27.0 / new_height,
                               right_x=1.0,
                               bottom_y=0.5 + 27.0 / new_height)

  def get_thumb(self):
    # get or make a thumbnail
    if not self.thumb:
      self.make_thumb()
      self.put()
    return self.thumb


class Item(ndb.Model):
  title = ndb.StringProperty()
  place_name = ndb.StringProperty()
  # TODO how to pass title.max_length?
  owner = ndb.IntegerProperty()  # key
  # descr = db.TextProperty()
  address = ndb.TextProperty()
  active = ndb.IntegerProperty(default=1)
  category = ndb.KeyProperty(kind=Category)
  photo = ndb.KeyProperty(kind=DBImage, required=False)
  # latitude = db.FloatProperty()
  # longitude = db.FloatProperty()
  lat = ndb.FloatProperty()
  # long = db.FloatProperty()
  lng = ndb.FloatProperty()
  telephone = ndb.StringProperty(required=False)
  geo_hash = ndb.StringProperty()
  thumbsUp = ndb.IntegerProperty(default=0)
  googleID = ndb.TextProperty(default="")  #Maps ID
  created = ndb.DateTimeProperty(auto_now_add=True)
  edited = ndb.DateTimeProperty(auto_now=True)
  website = ndb.StringProperty(default='', required=False)
  json = ndb.TextProperty(required=False, default = "")


  def prop(self, name):
    return getProp(self, name)

  def __unicode__(self):
    return self.place_name

  def get_json(self, force_refresh = False):
    if self.json == 'null' or not self.json or force_refresh:
      json_data = self.set_json()
      self.put()
      return json_data
    return json.loads(self.json)

  def get_json_str_with_vote(self, userId):
    self.get_json()
    vote = Vote.query(Vote.item == self.key, Vote.voter == userId).get()
    if vote:
      # if the user has voted for this item, and the user is excluded, next
      myVoteStr = ',"mine": true,"stars":%d,"descr":"%s"'%(vote.stars, vote.comment)
      res = self.json[0:len(self.json)-1]+myVoteStr+'}'
      return res

  def qualified_title(self):
    return self.__unicode__()

  @classmethod
  def json_serial(cls, o):
    """
    JSON serializer for objects not serializable by default json code
       http://stackoverflow.com/questions/11875770/how-to-overcome-
              datetime-datetime-not-json-serializable-in-python
    """
    if type(o) is datetime.date or type(o) is datetime.datetime:
        return o.isoformat()

  def save(self):
    self.set_json()
    self.put()

  def set_json(self):
    json_data = self.to_json(None)
    json_str = json.dumps(
      json_data,
      default=self.json_serial)
    self.json = json_str
    return json_data

  @classmethod
  def id_to_json(cls, id):
    """
    :param id: int ndb id
    :return: dict the json representation
    """
    try:
      # memcache has item entries under Key, and JSON entries under JSON:id
      item = Item.get_by_id(id)
      return item.get_json()
    except Exception:
      logging.exception('id_to_json', exc_info=True)
      return None

  def put(self):
    """
    Saves the object, and updates it's json value
    :return: void
    """
    ndb.Model.put(self)
    self.set_json()
    ndb.Model.put(self)

  def to_json(self, request, uid_for_votes=None):
    """
    create a json object for the web.
    :param request: BaseHandler

    :return: dict - json repr of the place
    """
    try:
      if request:
        base_url = request.url[:request.url.find(request.path)]
      else:
        base_url = ""
      if self.photo:
        if self.photo.get().picture:
          image_url = base_url+'/img/' + str(self.photo.urlsafe())
          thumbnail_url = base_url+'/thumb/' + str(self.photo.urlsafe())
          image_url.replace('https','http')
          thumbnail_url.replace('https','http')
        else:
          image_url = ''
          thumbnail_url = ''
      else:
        image_url = ''
        thumbnail_url = ''
        # image_url = "/static/images/noImage.jpeg"
      edit_time = self.edited
      if edit_time:
        try:
          edit_time_unix = int(time.mktime(edit_time.timetuple())) * 1000
        except:
          edit_time_unix = 0
      else:
        edit_time_unix = 0
      if self.category == None or self.category.get().title == None:
        logging.error("%s has no cuisine"%self.place_name)
      data = {
        'lat': self.lat,
        'lng': self.lng,
        'website': self.website,
        'address': self.address,
        'key': str(self.key.id()) ,
        'place_name': self.place_name,
        'place_id': '',
        'cuisineName': self.category.get().title,
        'telephone': self.telephone,
        'img': image_url,
        'edited': edit_time_unix,
        'thumbnail': thumbnail_url,

        'owner': self.owner,
        # is_map is True if the point came
        # from a google places API search. Default False
        'is_map': False}
      if uid_for_votes:
        vote = Vote.query(Vote.voter == uid_for_votes, Vote.item == self.key).get()
        if vote:
          # if the user has voted for this item, and the user is excluded, next
          data["mine"] = True
          data["vote"] = vote.stars
          data["descr"] = vote.comment
      return data
    except Exception, E:
      logging.exception('to_json %s'%self.key.id(), exc_info=True)



  @classmethod
  def get_unique_place(cls, request, return_existing=True):
    try:
      it = ndb.Key(Item,int(request.get('key'))).get()
    except:
      it = None
    if it:
      logging.debug('get_unique_place exists '+it.place_name)
      return it if return_existing else None
    place_name = request.get('new-title')
    if not place_name:
      place_name = request.get('place_name')
    logging.debug('get_unique_place name '+place_name)
    if 'latitude' in request.params:
      lat = float(request.get('latitude'))
    else:
      lat = float(request.get('lat'))
    if 'longitude' in request.params:
      lng = float(request.get('longitude'))
    else:
      lng = float(request.get('lng'))
    geo_code = geohash.encode(lat, lng, precision=6)
    local_results = Item.query().\
      filter(Item.geo_hash >geo_code).\
      filter(Item.geo_hash < geo_code + "{")
    lower_name = place_name.lower()
    for place in local_results:
      if lower_name in place.place_name.lower():
        logging.debug('get_unique_place Found "%s"@[%f.4,%f.4]'%
                      (place_name,lat,lng))
        return place if return_existing else None
    it = Item(place_name=place_name)
    it.lat = lat
    it.lng = lng
    it.geo_hash = geohash.encode(lat, lng)
    logging.debug("get_unique_place - create item %s@[%f.4,%f.4]"%
                 (it.place_name, it.lat, it.lng))
    return it

  def vote_from(self, user_id):
    """
    return the text & score from the user's vote
    @param user_id:
    @return user's comment, user's vote score:
    """
    users_vote = Vote.query(Vote.voter == user_id).get()
    if users_vote:
      return users_vote.comment, users_vote.stars, users_vote.untried
    else:
      return "", 0, False

  def closest_vote_from(self, user_id):
    """
    return the text & score from the owners vote
    @param user_id:
    @return user's comment, user's vote score:
    """
    users_vote = Vote.query().\
      filter(Vote.voter == user_id).\
      filter(Vote.item == self.key).\
      get()
    if users_vote:
      return users_vote


    # first one
    user_profile = auth_model.UserProfile.query(
      auth_model.UserProfile.user == ndb.Key(auth_model.User, int(user_id)))
    for friend in user_profile.friends:
      users_vote = Vote.query(Vote.voter == friend.key.integer_id()).get()
      logging.debug("friend " + str(friend.key.integer_id()))
      if users_vote:
        return users_vote
    logging.debug("closest_vote_from " + str(user_id))
    logging.debug("num friends " + str(len(user_profile.friends)))
    return None



class PlaceStyle:
  STYLE_QUICK = 1
  STYLE_RELAXED = 2
  STYLE_FANCY = 3

class MealKind:
  KIND_BREAKFAST = 1
  KIND_LUNCH = 2
  KIND_DINNER = 4
  KIND_COFFEE = 8
  KIND_BAR = 16

  @classmethod
  def KIND_ALL(cls):
    return cls.KIND_BREAKFAST +cls.KIND_LUNCH +cls.KIND_DINNER +cls.KIND_COFFEE +cls.KIND_BAR

class VoteValue:
  VOTE_NONE = 0
  VOTE_LIKED = 1
  VOTE_DISLIKED = -1
  VOTE_UNTRIED = 2

def datetime_parser(dct):
    for k, v in dct.items():
        if isinstance(v, basestring) and re.search("\ UTC", v):
            try:
                dct[k] = datetime.datetime.strptime(v, config['DATETIME_FORMAT'])
            except:
                pass
    return dct



"""
A vote for an item
"""
class Vote(ndb.Model):
  item = ndb.KeyProperty(kind=Item)
  voter = ndb.IntegerProperty()
  vote = ndb.IntegerProperty()
  stars = ndb.IntegerProperty(required=True, default=0)
  untried = ndb.BooleanProperty(default=False)
  comment = ndb.TextProperty()
  when = ndb.DateTimeProperty(auto_now=True)
  place_style = ndb.IntegerProperty(default=PlaceStyle.STYLE_RELAXED)
  meal_kind = ndb.IntegerProperty(default=MealKind.KIND_ALL())
  cuisine = ndb.KeyProperty(kind=Category)
  replies = ndb.IntegerProperty(default=0)
  json = ndb.StringProperty(default="")

  @classmethod
  def json_serial(cls, o):
    """
    JSON serializer for objects not serializable by default json code
       http://stackoverflow.com/questions/11875770/how-to-overcome-
              datetime-datetime-not-json-serializable-in-python
    """
    if type(o) is datetime.date or type(o) is datetime.datetime:
        return o.isoformat()

  def put(self):
    # override put to set the json
    if self.key and self.key.id() == 6507171000877056:
      logging.debug('sara put')
      # put twice so we have a key
    ndb.Model.put(self)
    self.json = json.dumps(self.to_json(),default=self.json_serial)
    ndb.Model.put(self)
    if self.key.id() == 6507171000877056:
      logging.debug('sara put json %s'%self.json)

  def get_json(self):
    if len(self.json)==0:
      self.put()
    return json.loads(self.json,object_hook=datetime_parser)

  def kind_str(self):
    kinds = []
    if MealKind.KIND_BREAKFAST & self.meal_kind:
      kinds.append("Breakfast")
    if MealKind.KIND_LUNCH & self.meal_kind:
      kinds.append("Lunch")
    if MealKind.KIND_DINNER & self.meal_kind:
      kinds.append("Dinner")
    if MealKind.KIND_COFFEE & self.meal_kind:
      kinds.append("Coffee")
    if MealKind.KIND_BAR & self.meal_kind:
      kinds.append("Bar")
    return ', '.join(kinds)


  @property
  def voter_name(self):
    name = memcache.get('USERNAME' + str(self.voter))
    if name:
      return name
    user = auth_model.User().get_by_id(self.voter)
    name = user.screen_name
    memcache.set('USERNAME' + str(self.voter), name)
    
  def to_json(self):
   if self.key and self.item.id() == 6507171000877056:
    logging.debug('sara to json')
   when =  self.when
   if not when:
     when = datetime.datetime.now()
   replies =  Comment.query(Comment.vote == self.key).count()
   if self.item.id() == 6507171000877056:
     logging.debug("Vote ToJson Sarah %d - %s, %s"%(replies, str(Comment.vote), str(self.key)))
   return {"key": str(self.item.id()),
           "voteId": self.key.id(),
           "vote": self.stars,
           "untried": self.untried,
           "style": self.place_style,
           "kind": self.meal_kind,
           "comment": self.comment,
           "cuisineName": self.cuisine.get().title,
           "voter": self.voter,
           "place_name": self.item.get().place_name,
           "replies": replies,
           # Json date format 1984-10-02T01:00:00
           "when": when.strftime(
             config['DATETIME_FORMAT']),
      }

  @classmethod
  def get_user_votes(cls, user_id):
    """
    Returns the list of votes for a user from the db
    :param user_id string
    :returns dict<place_key,list<Vote>>
    """
    try:
      logging.debug("get_user_votes for %s"%user_id)
      entry = {}
      user_vote_list = Vote.query(Vote.voter == user_id)
      for user_vote in user_vote_list:
        vote_detail = user_vote.json
        place_key = vote_detail['key']
        if place_key in entry:
          entry[place_key].append(vote_detail)
        else:
          entry[place_key] = [vote_detail]
      return entry
    except Exception:
      logging.error("get_user_votes Exception", exc_info=True)
      return {}

"""
A feedback Item
"""

class Feedback(ndb.Model):
  reply_to = ndb.IntegerProperty(default=-1)# -1 means it's not a reply
  user = ndb.IntegerProperty(default=-1)
  admin_response = ndb.BooleanProperty()# True means it's an admin reply - Sprout
  comment = ndb.TextProperty()
  when = ndb.DateTimeProperty(auto_now=True)

  def to_json(self):
    when =  self.when
    if not when:
      when = datetime.datetime.now()
    if not self.key:
      ndb.Model.put(self)
    return {"FeedbackId": str(self.key.id()),
           "Comment": self.comment,
           "UserId": self.user,
           "ReplyTo": self.reply_to,
           "AdminResponse": self.admin_response,
           # Json date format 1984-10-02T01:00:00
           "When": when.strftime(
             config['DATETIME_FORMAT'])
            }

  def get_email(self):
    u = auth_model.User.get_by_id(self.user)
    return u.email_address

"""
A comment on a vote
"""

class Comment(ndb.Model):
  vote = ndb.KeyProperty(kind=Vote)
  author = ndb.IntegerProperty()
  comment = ndb.TextProperty()
  when = ndb.DateTimeProperty(auto_now=True)
  json = ndb.StringProperty(default="")

  def to_json(self):
    when =  self.when
    if not when:
      when = datetime.datetime.now()
    if not self.key:
      ndb.Model.put(self)
    return {"Vote": str(self.vote.id()),
           "Comment": self.comment,
           "CommentId": self.key.id(),
           "Author": self.author,
           # Json date format 1984-10-02T01:00:00
           "When": when.strftime(
             config['DATETIME_FORMAT'])
            }

  def get_json(self):
    if len(self.json)==0:
      self.put()
    return json.loads(self.json,object_hook=datetime_parser)

  @classmethod
  def json_serial(cls, o):
    """
    JSON serializer for objects not serializable by default json code
       http://stackoverflow.com/questions/11875770/how-to-overcome-
              datetime-datetime-not-json-serializable-in-python
    """
    if type(o) is datetime.date or type(o) is datetime.datetime:
        return o.isoformat()

  def put(self):
    # override put to set the json
    self.json = json.dumps(self.to_json(),default=self.json_serial)
    ndb.Model.put(self)

class Trust(ndb.Model):
  # Trust value from first user to second user, where firstId < secondId
  first = ndb.IntegerProperty()
  second = ndb.IntegerProperty()
  trust = ndb.IntegerProperty()

  @classmethod
  def updateTrust(cls, user_a, user_b):
    # get list of common item votes
    user_a_hits = Vote.query(Vote.voter == user_a)
    user_b_hits = Vote.query(Vote.voter == user_b)
    similar = []
    user_a_ids = []
    user_b_ids = []
    for r in user_a_hits:
      user_a_ids.append(r.id())
    for r in user_b_hits:
      user_b_ids.append(r.id())
    for id in user_a_ids:
      if id in user_b_ids:
        similar.append(id)
        #count similarity of votes

#caching

def get_friends_str(user_id):
  friends = []
  left_list = Friends.query(Friends.lower == user_id)
  right_list = Friends.query(Friends.higher == user_id)
  for f in left_list:
    if not f.higher in friends:
      friends.append(f.higher)
  for f in right_list:
    if not f.lower in friends:
      friends.append(f.lower)
  friends_with_name = []
  for f in friends:
    friends_with_name.append("%s:%s"%(f,auth_model.User.get_by_id(f).screen_name))
  if friends_with_name:
    return ",".join(friends_with_name)
  else:
    return ""

# def memcache_get_user_dict(UserId):
#   """
#   memcache enabled get User
#   @param UserId: string
#   @return user:
#   """
#   try:
#     UserId = int(UserId)
#     user_rec = memcache.get(str(UserId))
#     if user_rec:
#       return user_rec
#     user = User().get_by_id(UserId)
#     if user:
#       uprof = user.profile()
#       record = {'u': user,
#                 'p': uprof,
#                 'f': get_friends_str(user.key.id()),
#                 'v': Vote.get_user_votes(UserId),
#                 'd': datetime.datetime.now()}
#       if not memcache.set(str(UserId), record):
#         logging.error("could not memcache Item %d"% UserId)
#       return record
#     else:
#       logging.error('memcache_get_user_dict No User '+str(UserId))
#   except Exception:
#     logging.error('memcache_get_user_dict exception', exc_info=True)


# def memcache_touch_user(id):
#   id = int(id)
#   logging.debug ("memcache_touch_user %d"%id)
#   ur = memcache_get_user_dict(id)
#   ur['p'].last_write = datetime.datetime.now()
#   ur['p'].put()
#   memcache.delete(str(id))

# def memcache_update_user_votes(id):
#   logging.debug("memcache_update_user_votes %d"%id)
#   ur = memcache_get_user_dict(id)
#   ur['p'].last_write = datetime.datetime.now()
#   # ur['p'].put()
#   ur['v'] = Vote.get_user_votes(id)
#   ur['d'] = datetime.datetime.now()
#   if not memcache.set(str(id), ur):
#       logging.error("could not update User Votes %d"% id)
  return ur

# def memcache_touch_place(key_or_item):
#   try:
#     if type(key_or_item) == db.Key:
#       it = db.get(key_or_item)
#       key = key_or_item
#     else:
#       it = key_or_item
#       key = str(it.key())
#     memcache.delete(key)
#     memcache.delete("JSON:" + key)
#     memcache.set(key, it)
#   except Exception:
#     logging.error("failed to memcache place " + str(key_or_item), exc_info=True)


# def memcache_put_user(user):
#   """
#   put user in memcache
#   @param user:
#   """
#   uid = "No UID"
#   try:
#     uid = user.key.id()
#     uprof = user.profile()
#     record = {'u': user,
#               'p': uprof}
#     if not memcache.set(str(id), record):
#       logging.error("could not memcache Item " + str(uid))
#   except Exception:
#     logging.error("failed to memcache user " + str(uid), exc_info=True)


# def memcache_put_user_dict(dict):
#   """
#   put user in memcache
#   @param dict:
#   """
#   uid = "No UID"
#   try:
#     uid = dict['u'].key.id()
#     if not memcache.set(str(uid), dict):
#       logging.error("could not memcache Item " + uid)
#   except Exception:
#     logging.error("failed to memcache Dict " + uid, exc_info=True)

"""
When someone is invited, their email is stored. If they accept they are made
friends with the inviter
"""
class Invite(ndb.Model):
  inviter = ndb.IntegerProperty()
  token = ndb.StringProperty()
  when = ndb.DateTimeProperty(auto_now=True)

  @classmethod
  def getInviteToken(cls, userId):
    invite = Invite()
    invite.inviter = userId
    now = int(time.time())
    token = str(hash(userId + now))
    invite.token = token
    invite.put()
    return token

  @classmethod
  def delInviteToken(cls, token):
    invite = Invite.query(Invite.token == token).get()
    if invite:
      invite.key.delete()
      return True
    return False

  @classmethod
  def checkInviteToken(cls, token):
    # if the invite token exists, return the userId of the inviter
    inv = Invite.query(Invite.token == token).get()
    if inv:
      return inv.inviter
    return None

class Friends(ndb.Model):
  # integer userIds, the lower value always in Lower as it's commutative
  lower = ndb.IntegerProperty(default=0)
  higher = ndb.IntegerProperty(default=0)


  @classmethod
  def addFriends(cls,first, second):
    i1 = int(first)
    i2 = int(second)
    lower = min(i1, i2)
    higher = max(i1, i2)
    f = Friends.query(Friends.lower == lower, Friends.higher == higher).get()
    if f:
      logging.info("addFriends: already friends %s, %s"%(lower, higher))
    else:
      logging.info("addFriends: adding %s, %s"%(lower, higher))
      f = Friends()
      f.higher = higher
      f.lower = lower
      f.put()

  @classmethod
  def getFriendIds(cls,user_id):
    lo = Friends.query(Friends.lower == user_id)
    hi = Friends.query(Friends.higher == user_id)
    result = []
    for f in lo:
      u = f.higher
      if not u in result:
        result.append(u)
    for f in hi:
      u = f.lower
      if not u in result:
        result.append(u)
    return result


""" These are internal invites - both are users
"""
class InviteInternal(ndb.Model):
  inviter = ndb.IntegerProperty(default=0)
  invitee = ndb.IntegerProperty(default=0)
  accepted = ndb.BooleanProperty(default=False)
  when = ndb.DateTimeProperty(auto_now=True)
  name = ndb.StringProperty(default="")

  @classmethod
  def add_invite(cls,from_id, to_id):
    inv = InviteInternal.query().\
      filter(InviteInternal.inviter == from_id).\
      filter(InviteInternal.invitee ==  to_id).\
      get()
    if not inv:
      inv = InviteInternal()
    inv.inviter = from_id
    inv.invitee = to_id
    u = auth_model.User.get_by_id(from_id)
    inv.name = u.screen_name
    inv.put()

  def to_json(self):
    if self.when:
      timestr = self.when.strftime(
              settings.config['DATETIME_FORMAT'])
    else:
      timestr = datetime.datetime.now().strftime(
              settings.config['DATETIME_FORMAT'])
    dict = {
      'inviter':self.inviter,
    'invitee':self.invitee,
    'accepted':self.accepted,
    'name':self.name,
    'when':timestr}
    return dict