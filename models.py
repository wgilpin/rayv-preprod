import logging
from google.appengine.api import images, memcache
from google.appengine.api.images import CORRECT_ORIENTATION
from google.appengine.ext import db
from google.appengine.ext.db import BadKeyError, BadRequestError
from auth_model import User
import geohash
from settings import config
import settings

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

  def prop(self, name):
    return getProp(self, name)

  def __unicode__(self):
    return self.place_name

  def qualified_title(self):
    return self.__unicode__()

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
    @param user_id:
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

  @classmethod
  def get_user_votes(cls, user_id, since=None):
    try:
      entry = {}
      user_vote_list = Vote.all().filter("voter =", user_id)
      if since:
        user_vote_list = user_vote_list.filter("when >", since)
      for user_vote in user_vote_list:
        vote_detail = {"key": str(user_vote.item.key()),
                       "vote": user_vote.vote,
                       "untried": user_vote.untried,
                       "comment": user_vote.comment,
                       "place_name": user_vote.item.place_name,
                       # Json date format 1984-10-02T01:00:00
                       "when": user_vote.when.strftime(
                         settings.config['DATETIME_FORMAT']),
        }
        entry[str(user_vote.item.key())] = vote_detail
      return entry
    except Exception:
      logging.error("get_user_votes Exception", exc_info=True)

class Trust(db.Model):
  # Trust value from first user to second user, where firstId < secondId
  first = db.IntegerProperty()
  second = db.IntegerProperty()
  trust = db.IntegerProperty()

  @classmethod
  def updateTrust(user_a, user_b):
    if user_a < user_b:
      first = user_a
      second = user_b
    else:
      first = user_b
      second = user_a
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

