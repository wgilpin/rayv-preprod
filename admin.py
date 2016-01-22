import json
import logging
import urllib2

from datetime import datetime, timedelta, time
from time import sleep

from google.appengine.ext import ndb
from apns import APNs, Payload
from auth_logic import BaseHandler
from webapp2_extras import auth
from auth_model import User
from models import Item, DBImage, VoteValue, Vote, \
  Category, Feedback
import urllib
from google.appengine.api import urlfetch
import geo
import ndb_models
from settings import config

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
            form_fields = place.id_to_json()
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
    vote_key = ndb.Key(Vote,int(self.request.get('vote_key')))
    item_key = ndb.Key(Item,int(self.request.get('item_key')))
    vote = vote_key.get()
    it = item_key.get()
    if it:
      try:
        old_votes = Vote.query(Vote.voter == vote.voter, Vote.item == item_key)
        for v in old_votes:
          if v.key.id() != vote_key:
            v.key.delete()
        vote.meal_kind =  int(self.request.get('kind'))
        vote.place_style=  int(self.request.get('style'))
        cuisine = self.request.get('cuisine')
        if cuisine:
          vote.cuisine = Category.get_by_id(cuisine)
        if not vote.cuisine:
          vote.cuisine = vote.item.category
        vote.put()
        it.set_json()
        ndb_models.mark_vote_as_updated(vote.key.id(), vote.voter)
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

class NotificationBroadcast(BaseHandler):
  def get(self):
    if not is_administrator():
      self.abort(403)
    self.render_template("admin-apns.html")

  def post(self):
    if not is_administrator():
      self.abort(403)
    message = self.request.params["message"]
    use_sandbox = 'use_sandbox' in self.request.params
    certFile = 'RayvIosCerts.pem'
    logging.info("NotificationBroadcast with cert %s & sandbox %s"%(certFile, str(use_sandbox)))
    apns = APNs(use_sandbox=use_sandbox,
        cert_file= certFile
    )
    payload = Payload(alert=message, sound="default", badge=1,custom={})
    count = 0
    for registered_user in ndb_models.NotificationToken.query():
      token = str(registered_user.token)
      hex_token = token.translate(None, '< >')
      try:
        apns.gateway_server.send_notification(hex_token, payload, expiry = (datetime.utcnow() + timedelta(300)))
        for (token_hex, fail_time) in apns.feedback_server.items():
            logging.info(token_hex)
            logging.info(fail_time)
        count += 1
        self.response.out.write('User %s<br>'%registered_user.userId)
      except:
        logging.warning("NotificationBroadcast error for %d tok:%s"%(
          registered_user.userId,
          registered_user.token),
                        exc_info=True)
    self.response.out.write('Sent %d messages, sandbox:%s'%(count, str(use_sandbox)))

class ResetUserPassword(BaseHandler):
  def get(self):
    if not is_administrator():
      self.abort(404)
    self.render_template("admin-password.html")

  def post(self):
    if not is_administrator():
      self.abort(404)
    pwd = self.request.get("pwd")
    pwd2 = self.request.get("pwd2")
    if pwd != pwd2:
      self.render_template("admin-password.html",{'message':'Passwords don\'t match'})
      return
    try:
      email = self.request.get('email')
      user = User.get_by_email(email)
      if not user:
        self.render_template("admin-password.html",{'message':'User not found'})
        return
      user.set_password(pwd)
      user.put()
      if config['log_passwords']:
        self.response.out.write("Password has been reset to %s"%pwd)
      else:
        self.response.out.write("Password has been reset ")
    except Exception, e:
      self.response.out.write(e)


class FeedbackList(BaseHandler):
  def get(self):
    if not is_administrator():
      self.redirect('/login')
    feedbacks = Feedback.query().order(Feedback.when)
    con = {'feedback':feedbacks}
    self.render_template("admin-feedback.html", con)
