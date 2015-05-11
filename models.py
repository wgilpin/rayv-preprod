import json
import logging
import datetime
from google.appengine.api import images, memcache
from google.appengine.api.images import CORRECT_ORIENTATION
from google.appengine.ext import db
from google.appengine.ext.db import BadKeyError, BadRequestError
import time
from auth_model import User
import geohash
from settings import config

__author__ = 'Will'


def getProp(obj, propName, falseValue=False):
  try:
    if hasattr(obj, propName):
      return getattr(obj, propName, falseValue)
    return obj[propName]
  except:
    return falseValue


# #####################################################################################
class Audit(db.Model):
  # who is logged on
  usr = db.IntegerProperty(required=False)
  # timestanp
  dt = db.DateTimeProperty(auto_now=True)
  # JSON object with data values - if NULL then only TextProperty is used
  values = db.TextProperty()
  # action - text
  action = db.TextProperty()
  subjectId = db.IntegerProperty(required=False)
  #TODO log ip - request.get_host()

  @classmethod
  def write(cls, kind, usr, msg, send_mail=True, subject=None, trace=None):
    # print kind+' - '+str(usr)+' - '+msg
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
        a.save()
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
      a.save()
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


class Address(db.Model):
  address = db.TextProperty()
  city = db.TextProperty()
  state = db.TextProperty(required=False)
  postal_code = db.TextProperty(required=False)
  country = db.TextProperty()


"""
The semantic tree for items
"""


class Category(db.Model):
  # key_name is the slug
  title = db.TextProperty()


def get_category(key):
  try:
    cat = memcache.get(key)
    if cat:
      return cat
    cat = Category().get(key)
    return cat
  except:
    logging.info("get_category failed for key " + key, exc_info=True)
    return None


class DBImage(db.Model):
  title = db.TextProperty(required=False)
  picture = db.BlobProperty()
  thumb = db.BlobProperty(required=False)
  owner = db.IntegerProperty(required=False)  # key
  remoteURL = db.StringProperty(required=False)


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


class Item(db.Model):
  title = db.StringProperty()
  place_name = db.StringProperty()
  # TODO how to pass title.max_length?
  owner = db.IntegerProperty()  # key
  # descr = db.TextProperty()
  address = db.TextProperty()
  active = db.IntegerProperty(default=1)
  category = db.ReferenceProperty(Category)
  photo = db.ReferenceProperty(DBImage, required=False)
  # latitude = db.FloatProperty()
  # longitude = db.FloatProperty()
  lat = db.FloatProperty()
  # long = db.FloatProperty()
  lng = db.FloatProperty()
  telephone = db.StringProperty(required=False)
  geo_hash = db.StringProperty()
  thumbsUp = db.IntegerProperty(default=0)
  googleID = db.TextProperty(default="")  #Maps ID
  created = db.DateTimeProperty(auto_now_add=True)
  edited = db.DateTimeProperty(auto_now=True)
  website = db.StringProperty(default='', required=False)
  json = db.TextProperty(required=False, default = "")

  def prop(self, name):
    return getProp(self, name)

  def __unicode__(self):
    return self.place_name

  def get_json(self):
    if self.json == 'null' or not self.json:
      json_data = self.set_json()
      self.put()
      return json_data
    return json.loads(self.json)

  def get_json_str_with_vote(self, userId):
    self.get_json()
    vote = self.votes.filter("voter =", userId).get()
    if vote:
      # if the user has voted for this item, and the user is excluded, next
      myVoteStr = ',"mine": true,"vote":%d,"descr":"%s"'%(int(vote.vote), vote.comment)
      if vote.untried:
        myVoteStr += ',"untried": true'
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
  def key_to_json(cls, key, request=None):
    try:
      # memcache has item entries under Key, and JSON entries under JSON:key
      item = Item.get(key)
      return item.get_json()
    except Exception:
      logging.exception('key_to_json', exc_info=True)
      return None



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
        if self.photo.picture:
          image_url = base_url+'/img/' + str(self.photo.key())
          thumbnail_url = base_url+'/thumb/' + str(self.photo.key())
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
      data = {
        'lat': self.lat,
        'lng': self.lng,
        'website': self.website,
        'address': self.address,
        'key': str(self.key()) ,
        'place_name': self.place_name,
        'place_id': '',
        'category': self.category.title,
        'telephone': self.telephone,
        'untried': False,
        'vote': 'null',
        'img': image_url,
        'edited': edit_time_unix,
        'thumbnail': thumbnail_url,
        'up': self.votes.filter("vote =", 1).count(),
        'down': self.votes.filter("vote =", -1).count(),
        'owner': self.owner,
        # is_map is True if the point came
        # from a google places API search. Default False
        'is_map': False}
      if uid_for_votes:
        vote = self.votes.filter("voter =", uid_for_votes).get()
        if vote:
          # if the user has voted for this item, and the user is excluded, next
          data["mine"] = True
          data["vote"] = int(vote.vote)
          data["descr"] = vote.comment
          if vote.untried:
            data["untried"] = True

      return data
    except Exception, E:
      logging.exception('to_json %s'%self.key(), exc_info=True)



  @classmethod
  def get_unique_place(cls, request, return_existing=True):
    it = Item.get_item(request.get('key'))
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
    local_results = Item.all().\
      filter("geo_hash >", geo_code).\
      filter("geo_hash <", geo_code + "{")
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
    users_vote = self.votes.filter("voter =", user_id).get()
    if users_vote:
      return users_vote.comment, users_vote.vote
    else:
      return "", 0

  def closest_vote_from(self, user_record):
    """
    return the text & score from the owners vote
    @param user_record:
    @return user's comment, user's vote score:
    """
    uid = user_record['p'].userId
    users_vote = self.votes.filter("voter =", uid).get()
    if users_vote:
      return users_vote


    # first one
    for friend_id in user_record['p'].friends:
      users_vote = self.votes.filter("voter =", friend_id).get()
      logging.debug("friend " + str(friend_id))
      if users_vote:
        return users_vote
    logging.debug("closest_vote_from " + str(uid))
    logging.debug("num friends " + str(len(user_record['p'].friends)))
    return None

  @classmethod
  def get_item(cls, key):
    """
    memcache enabled get Item
    @param key:
    @return item:
    """
    try:
      if not key:
        return None
      item = memcache.get(key)
      if item:
        return item
      item = Item().get(key)
      if item:
        if not memcache.set(key, item):
          logging.error("could not memcache Item " + key, exc_info=True)
      return item
    except BadKeyError:
      pass
    except BadRequestError:
      #this happens if we pass the key form another app in - which we do
      logging.info('get_item key Bad Request '+key)
    except Exception, e:
      logging.error("get_item", exc_info=True)
    return None




"""
A vote for an item
"""


class Vote(db.Model):
  item = db.ReferenceProperty(Item, collection_name="votes")
  voter = db.IntegerProperty()
  vote = db.IntegerProperty()
  untried = db.BooleanProperty(default=False)
  comment = db.TextProperty()
  when = db.DateTimeProperty(auto_now=True)

  @property
  def voter_name(self):
    name = memcache.get('USERNAME' + str(self.voter))
    if name:
      return name
    user = User.get_by_id(self.voter)
    name = user.screen_name
    memcache.set('USERNAME' + str(self.voter), name)
    
  def to_json(self, voter_id):
     return {"key": str(self.item.key()),
                       "vote": self.vote,
                       "untried": self.untried,
                       "comment": self.comment,
                       "voter": voter_id,
                       "place_name": self.item.place_name,
                       # Json date format 1984-10-02T01:00:00
                       "when": self.when.strftime(
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
      entry = {}
      user_vote_list = Vote.all().filter("voter =", user_id)
      for user_vote in user_vote_list:
        vote_detail = {"key": str(user_vote.item.key()),
                       "vote": user_vote.vote,
                       "untried": user_vote.untried,
                       "comment": user_vote.comment,
                       "voter": user_id,
                       "place_name": user_vote.item.place_name,
                       # Json date format 1984-10-02T01:00:00
                       "when": user_vote.when.strftime(
                         config['DATETIME_FORMAT']),
        }
        place_key = vote_detail['key']
        if place_key in entry:
          entry[place_key].append(vote_detail)
        else:
          entry[place_key] = [vote_detail]
      return entry
    except Exception:
      logging.error("get_user_votes Exception", exc_info=True)
      return {}

class Trust(db.Model):
  # Trust value from first user to second user, where firstId < secondId
  first = db.IntegerProperty()
  second = db.IntegerProperty()
  trust = db.IntegerProperty()

  @classmethod
  def updateTrust(cls, user_a, user_b):
    # get list of common item votes
    user_a_hits = Vote.all().filter("voter =", user_a)
    user_b_hits = Vote.all().filter("voter =", user_b)
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

def memcache_get_user_dict(UserId):
  """
  memcache enabled get User
  @param UserId: string
  @return user:
  """
  try:
    user_rec = memcache.get(str(UserId))
    if user_rec:
      return user_rec
    user = User().get_by_id(UserId)
    if user:
      uprof = user.profile()
      record = {'u': user,
                'p': uprof,
                'v': Vote.get_user_votes(UserId),
                'd': datetime.datetime.now()}
      if not memcache.set(str(UserId), record):
        logging.error("could not memcache Item %d"% UserId)
      return record
    else:
      logging.error('memcache_get_user_dict No User '+str(UserId))
  except Exception:
    logging.error('memcache_get_user_dict exception', exc_info=True)


def memcache_touch_user(id):
  print "memcache_touch_user %d"%id
  ur = memcache_get_user_dict(id)
  ur['p'].last_write = datetime.datetime.now()
  ur['p'].put()
  memcache.delete(str(id))

def memcache_update_user_votes(id):
  print "memcache_update_user_votes %d"%id
  ur = memcache_get_user_dict(id)
  ur['p'].last_write = datetime.datetime.now()
  # ur['p'].put()
  ur['v'] = Vote.get_user_votes(id)
  ur['d'] = datetime.datetime.now()
  if not memcache.set(str(id), ur):
      logging.error("could not update User Votes %d"% id)
  return ur

def memcache_touch_place(key_or_item):
  try:
    if type(key_or_item) == db.Key:
      it = db.get(key_or_item)
      key = key_or_item
    else:
      it = key_or_item
      key = str(it.key())
    memcache.delete(key)
    memcache.delete("JSON:" + key)
    memcache.set(key, it)
  except Exception:
    logging.error("failed to memcache place " + str(key_or_item), exc_info=True)


def memcache_put_user(user):
  """
  put user in memcache
  @param user:
  """
  uid = "No UID"
  try:
    uid = user.key.id()
    uprof = user.profile()
    record = {'u': user,
              'p': uprof}
    if not memcache.set(str(id), record):
      logging.error("could not memcache Item " + str(uid))
  except Exception:
    logging.error("failed to memcache user " + str(uid), exc_info=True)


def memcache_put_user_dict(dict):
  """
  put user in memcache
  @param dict:
  """
  uid = "No UID"
  try:
    uid = dict['u'].key.id()
    if not memcache.set(str(uid), dict):
      logging.error("could not memcache Item " + uid)
  except Exception:
    logging.error("failed to memcache Dict " + uid, exc_info=True)

#TODO: change to ndb! Then drop the memcache crazies, and do Since properly
def get_user_votes(user_id):
  try:
    user_dict = memcache_get_user_dict(user_id)
    votes = {}
    good_user_dict = True
    if not 'd' in user_dict:
      good_user_dict = False
    if not 'v' in user_dict:
      good_user_dict = False
    if not user_dict['d']:
      good_user_dict = False
    if not good_user_dict:
      user_dict = memcache_update_user_votes(user_id)
    if user_dict['d'] < datetime.datetime.now() - config['memcache_life']:
      user_dict = memcache_update_user_votes(user_id)
    votes = user_dict['v']
    return user_dict, votes
  except Exception, e:
    logging.error("get_user_votes Exception", exc_info=True)
    return None, {}

