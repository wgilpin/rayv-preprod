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
  blocked = model.BooleanProperty(default=False)
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
      res = db.GqlQuery(
        "SELECT * FROM UserProfile WHERE userId = :1", self.key.id()).get()
      if res:
        return res
      raise LookupError
    except:
      logging.info("Create user profile")
      new_profile = UserProfile()
      # put this User's UserId in the profile to link them
      new_profile.userId = self.key.id()
      new_profile.friends = []
      # last_write set when a change is made to your book
      new_profile.last_write = datetime.datetime.now()
      # last_read set when we load this so we can check vs write
      new_profile.last_read = datetime.datetime.now()
      new_profile.put()
      return new_profile

