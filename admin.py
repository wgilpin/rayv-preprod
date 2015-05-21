import json
import logging
import urllib2
from google.appengine.ext import db
from auth_logic import BaseHandler
from webapp2_extras import auth
from auth_model import User
from models import Item, DBImage, VoteValue
import urllib
from google.appengine.api import urlfetch
import geo

__author__ = 'Will'


def is_administrator():
  """ True if logged in
  @return: bool
  """
  # todo: make admins
  return True
  user = session_auth = auth.get_auth()
  if session_auth.get_user_by_session():
    return user.profile().is_admin
  else:
    return False


class Main(BaseHandler):
  def get(self):
    if is_administrator():
      con = {}
      con['items'] = Item.all()
      self.render_template("admin-main.html", con)
    else:
      self.abort(403)


class SyncToProd(BaseHandler):
  def post(self):
    if is_administrator():
      try:
        logging.info("SyncToProd")
        seed_user = None
        for u in User.query():
          if 'pegah' in u.auth_ids:
            seed_user = u.key.id()
            break
        if seed_user:
          logging.info("SyncToProd seed user")
          url = 'https://rayv-app.appspot.com/admin/put_place_api'
          place_list = json.loads(self.request.params['list'])
          for place in place_list:
            it = Item.get(place)
            logging.info("SyncToProd sending " + it.place_name)
            form_fields = place.key_to_json()
            vote = it.votes.filter("voter =", seed_user).get()
            if vote:
              form_fields['myComment'] = vote.comment
              form_fields['voteScore'] = vote.vote_value
            else:
              form_fields['voteScore'] = VoteValue.VOTE_LIKED
              form_fields['myComment'] = ""
            form_data = urllib.urlencode(form_fields)
            result = urlfetch.fetch(url=url,
                                    payload=form_data,
                                    method=urlfetch.POST,
                                    headers={'Content-Type': 'application/x-www-form-urlencoded'})
        else:
          self.response.out.write('No Seed User')
      except Exception:
        logging.error('admin.SyncToProd', exc_info=True)
    logging.info("Sync Done to Prod")
    self.response.out.write("OK")


class updatePhotoFromGoogle(BaseHandler):
  def post(self):
    if is_administrator():
      try:
        logging.info("updatePhotoFromGoogle")
        place_list = json.loads(self.request.params['list'])
        for place in place_list:
          it = Item.get(place)
          if not it.photo:
            it.photo = DBImage()
          detail = geo.getPlaceDetailFromGoogle(it)
          remoteURL = detail['photo']
          if remoteURL:
            main_url = remoteURL % 250
            data = urllib2.urlopen(main_url)
            it.photo.picture = db.Blob(data.read())
            it.photo.remoteURL = None
            thumb_url = remoteURL % 65
            thumb_data = urllib2.urlopen(thumb_url)
            it.photo.thumb = db.Blob(thumb_data.read())
            it.photo.put()
      except:
        logging.error('updatePhotoFromGoogle', exc_info=True)

