from auth_logic import BaseHandler
from webapp2_extras import auth
from models import Item

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
