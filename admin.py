import json
import logging
from auth_logic import BaseHandler
from webapp2_extras import auth
from models import Item, itemKeyToJSONPoint
import urllib
from google.appengine.api import urlfetch

__author__ = 'Will'


def administrator():
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
    if administrator():
      con = {}
      con['items'] = Item.all()
      self.render_template("admin-main.html", con)
    else:
      self.abort(403)

class SyncToProd(BaseHandler):
  def post(self):
    if administrator():
      try:
        url = 'https://rayv-app.appspot.com/admin/put_place_api'
        place_list = json.loads(self.request.params['list'])
        for place in place_list:
          form_fields = itemKeyToJSONPoint(place)
          form_data = urllib.urlencode(form_fields)
          result = urlfetch.fetch(url=url,
              payload=form_data,
              method=urlfetch.POST,
              headers={'Content-Type': 'application/x-www-form-urlencoded'})
      except Exception, e:
        logging.error('admin.SyncToProd '+str(e))
    logging.info("Sync Done to Prod")
    self.response.out.write("OK")
