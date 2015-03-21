import logging
import datetime
from google.appengine.api import memcache
from google.appengine.ext import db
from auth_model import User
from models import Vote

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
      print "memcache_get_user_dict OK %d"%UserId
      return user_rec
    print "memcache_get_user_dict MISS %d"%UserId
    user = User().get_by_id(UserId)
    if user:
      print "memcache_get_user_dict ADD %d"%UserId
      uprof = user.profile()
      record = {'u': user,
                'p': uprof}
      if not memcache.set(str(UserId), record):
        logging.error("could not memcache Item %d"% UserId)
      return record
    else:
      logging.error('memcache_get_user_dict No User '+str(UserId))
  except Exception:
    logging.error('memcache_get_user_dict', exc_info=True)


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
  ur['p'].put()
  ur['v'] = Vote.get_user_votes(id)
  if not memcache.set(str(id), ur):
      logging.error("could not update User Votes %d"% id)

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
      logging.error("could not memcache Item " + str(uid))
  except Exception:
    logging.error("failed to memcache user " + str(uid), exc_info=True)


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

