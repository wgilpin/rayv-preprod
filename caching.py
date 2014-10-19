import logging
import datetime
from google.appengine.api import memcache
from google.appengine.ext import db
from auth_model import User

__author__ = 'Will'


def memcache_get_user_dict(UserId):
  """
  memcache enabled get User
  @param UserId:
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
                'p': uprof}
      if not memcache.set(str(UserId), record):
        logging.error("could not memcache Item " + UserId)
      return record
    else:
      logging.error('memcache_get_user_dict No User '+str(UserId))
  except:
    logging.error('memcache_get_user_dict', exc_info=True)


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
  except Exception:
    logging.error("failed to memcache place " + str(key_or_item), exc_info=True)


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
  except Exception:
    logging.error("failed to memcache user " + uid, exc_info=True)


def memcache_put_user_dict(dict):
  """
  put user in memcache
  @param dict:
  """
  try:
    uid = dict['u'].key.id()
    if not memcache.set(str(uid), dict):
      logging.error("could not memcache Item " + uid)
  except Exception:
    logging.error("failed to memcache Dict " + uid, exc_info=True)
