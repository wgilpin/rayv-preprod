import json
import logging
import urllib2
from google.appengine.ext import ndb
from auth_logic import BaseHandler
from webapp2_extras import auth
from auth_model import User
from models import Item, DBImage, VoteValue, Vote, \
  Category
import urllib
from google.appengine.api import urlfetch
import geo
import ndb_models

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
      con['items'] = Item.query()
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
            seed_user = u.key
            break
        if seed_user:
          logging.info("SyncToProd seed user")
          url = 'https://rayv-app.appspot.com/admin/put_place_api'
          place_list = json.loads(self.request.params['list'])
          for place in place_list:
            it = Item.get_by_id(place)
            logging.info("SyncToProd sending " + it.place_name)
            form_fields = place.urlsafe_key_to_json()
            vote = Vote.query(Vote.voter == seed_user, Vote.item == it.key).get()
            if vote:
              form_fields['myComment'] = vote.comment
              form_fields['voteScore'] = vote.vote
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
          it = ndb.Key(Item, place).get()
          if not it.photo:
            it.photo = DBImage()
          detail = geo.getPlaceDetailFromGoogle(it)
          remoteURL = detail['photo']
          if remoteURL:
            main_url = remoteURL % 250
            data = urllib2.urlopen(main_url)
            it.photo.picture = str(data.read())
            it.photo.remoteURL = None
            thumb_url = remoteURL % 65
            thumb_data = urllib2.urlopen(thumb_url)
            it.photo.thumb = str(thumb_data.read())
            it.photo.put()
      except:
        logging.error('updatePhotoFromGoogle', exc_info=True)

class UpdateAdminVote(BaseHandler):
  def post(self):
    vote_key = ndb.Key(urlsafe=self.request.get('vote_key'))
    item_key = ndb.Key(urlsafe=self.request.get('item_key'))
    vote = Vote.get_by_id(vote_key)
    it = Item.get_by_id(item_key)
    if it:
      try:
        old_votes = Vote.query(Vote.voter == vote.voter, Vote.item == item_key)
        for v in old_votes:
          if v.key.urlsafe() != vote_key:
            v.key.delete()
        vote = Vote.get_by_id(vote_key)
        vote.meal_kind =  int(self.request.get('kind'))
        vote.place_style=  int(self.request.get('style'))
        cuisine = self.request.get('cuisine')
        if cuisine:
          vote.cuisine = Category.get_by_id(cuisine)
        if not vote.cuisine:
          vote.cuisine = vote.item.category
        vote.put()
        it.set_json()
        ndb_models.mark_vote_as_updated(vote.key.urlsafe(), vote.voter)
        logging.info ('UpdateAdminVote for %s, %s'%(it.place_name,vote_key))
      except Exception, ex:
        logging.error("UpdateAdminVote votes exception", exc_info=True)
        raise

      # mark user as dirty
      self.response.out.write('OK')
      logging.debug("UpdateAdminVote OK")
      return
    logging.error("UpdateAdminVote 404 for %s"%vote_key)
    self.abort(404)
