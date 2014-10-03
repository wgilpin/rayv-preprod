import datetime
import logging
from google.appengine.api import memcache
from google.appengine.ext.ndb import model

__author__ = 'Will'

import time
import webapp2_extras.appengine.auth.models

from google.appengine.ext import ndb, gql, db

from webapp2_extras import security


class UserProfile(db.Model):
  userId = db.IntegerProperty()
  count_posted = db.IntegerProperty()
  count_read = db.IntegerProperty()
  last_write = db.DateTimeProperty()
  last_read = db.DateTimeProperty()
  # list of key ids
  friends = db.ListProperty(long)
  is_admin = db.BooleanProperty(default=False)


class User(webapp2_extras.appengine.auth.models.User):
  screen_name = model.StringProperty()
  def set_password(self, raw_password):
    """Sets the password for the current userId

    :param raw_password:
        The raw password which will be hashed and stored
    """
    self.password = security.generate_password_hash(raw_password, length=12)

  @classmethod
  def get_by_auth_token(cls, user_id, token, subject='auth'):
    """Returns a userId object based on a userId ID and token.

    :param user_id:
        The user_id of the requesting userId.
    :param token:
        The token string to be verified.
    :returns:
        A tuple ``(User, timestamp)``, with a userId object and
        the token timestamp, or ``(None, None)`` if both were not found.
    """
    token_key = cls.token_model.get_key(user_id, subject, token)
    user_key = ndb.Key(cls, user_id)
    # Use get_multi() to save a RPC call.
    valid_token, user = ndb.get_multi([token_key, user_key])
    if valid_token and user:
      timestamp = int(time.mktime(valid_token.created.timetuple()))
      return user, timestamp

    return None, None

  def profile(self):
    try:
      res = db.GqlQuery("SELECT * FROM UserProfile WHERE userId = :1", self.key.id()).get()
      if res:
        return res
      raise LookupError
    except:
      logging.info("Create user profile")
      new_profile = UserProfile()
      # put this User's UserId in the profile to link them
      new_profile.userId = self.key.id()
      new_profile.friends = []
      new_profile.last_write = datetime.datetime.now()  # set when a change is made to your book
      new_profile.last_read = datetime.datetime.now()  # set when we load this so we can check vs write
      new_profile.put()
      return new_profile


def memcache_get_user_dict(UserId):
  """
  memcache enabled get User
  @param UserId:
  @return user:
  """
  user_rec = memcache.get(str(UserId))
  if user_rec:
    return user_rec
  user = User().get_by_id(UserId)
  if user:
    uprof = user.profile()
    record = {'u': user,
              'p': uprof}
    if not memcache.set(str(UserId), record):
      logging.error("could not memcache Item " + UserId)
  return record


def memcache_touch_user(id):
  ur = memcache_get_user_dict(id)
  ur['p'].last_write = datetime.datetime.now()
  ur['p'].put()
  memcache.delete(str(id))


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
  except Exception, e:
    logging.error("failed to memcache place " + str(key_or_item), e)


def memcache_put_user(user):
  """
  put user in memcache
  @param user:
  """
  try:
    uid = user.key.id()
    uprof = user.profile()
    record = {'u': user,
              'p': uprof}
    if not memcache.set(str(id), record):
      logging.error("could not memcache Item " + uid)
  except Exception, e:
    logging.error("failed to memcache user " + uid, e)


def memcache_put_user_dict(dict):
  """
  put user in memcache
  @param dict:
  """
  try:
    uid = dict['u'].key.id()
    if not memcache.set(str(uid), dict):
      logging.error("could not memcache Item " + uid)
  except Exception, e:
    logging.error("failed to memcache Dict " + uid, e)
