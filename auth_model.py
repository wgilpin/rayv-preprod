import datetime
import logging
from google.appengine.ext.ndb import model

__author__ = 'Will'

import time
import webapp2_extras.appengine.auth.models

from google.appengine.ext import ndb

from webapp2_extras import security
import models





class User(webapp2_extras.appengine.auth.models.User):
  screen_name = model.StringProperty()
  blocked = model.BooleanProperty(default=False)
  friends = model.KeyProperty(kind='User',repeated=True)

  def set_friends(self):
    f_list = models.Friends.getFriendIds(self.key.integer_id())
    self.friends = [ndb.Key(User,f) for f in f_list]
    self.put()

  def get_friends_key_list(self):
    # if len(self.friends)==0:
    self.set_friends()
    return self.friends

  @classmethod
  def get_by_email(cls, email):
      """Returns a user object based on a email addr.

      :param email:
          String representing a email addr for the user
      :returns:
          A user object.
      """
      return ndb.gql("select * from User where email_address = :1",email).get()

  def set_password(self, raw_password):
    """Sets the password for the current userId

    :param raw_password:
        The raw password which will be hashed and stored
    """
    self.password = security.generate_password_hash(raw_password, length=12)

  def to_custom_dict(self):
    return {
      'screen_name': self.screen_name,
      'blocked': self.blocked
    }

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

  @classmethod
  def get_by_auth_token_and_username(cls, token, username):
    """Returns a userId object based on a userId ID and token.

    :param token:
        The token string to be verified.
    :returns:
        A tuple ``(User, timestamp)``, with a userId object and
        the token timestamp, or ``(None, None)`` if both were not found.
    """
    try:
      rec = cls.token_model.query(cls.token_model.token==token)
      if rec:
        user = cls.get_by_id(int(rec.get().user))
        if user and user.auth_ids[0]==username:
          return user
    except Exception, e:
      logging.error('get_by_auth_token_and_username',exc_info=True)
    return None

  def profile(self):
    try:
      res = UserProfile.query(UserProfile.user == self.key).get()
      if res:
        return res
      raise LookupError
    except:
      logging.info("Create user profile for %s"%self.key.id())
      new_profile = UserProfile()
      # put this User's UserId in the profile to link them
      new_profile.user = self.key
      new_profile.friends = []
      # last_write set when a change is made to your book
      new_profile.last_write = datetime.datetime.now()
      # last_read set when we load this so we can check vs write
      new_profile.last_read = datetime.datetime.now()
      new_profile.put()
      return new_profile

class UserProfile(ndb.Model):
  user = ndb.KeyProperty(kind=User)
  count_posted = ndb.IntegerProperty()
  count_read = ndb.IntegerProperty()
  last_write = ndb.DateTimeProperty()
  last_read = ndb.DateTimeProperty()
  # list of key ids
  is_admin = ndb.BooleanProperty(default=False)
  sex = ndb.StringProperty(default="")