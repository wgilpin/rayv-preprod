import logging
import os.path
import webapp2

from webapp2_extras import auth
from webapp2_extras import sessions

from google.appengine.ext.webapp import template
from settings import config




class BaseHandler(webapp2.RequestHandler):
  @webapp2.cached_property
  def auth(self):
    """Shortcut to access the auth instance as a property."""
    return auth.get_auth()

  @webapp2.cached_property
  def user_info(self):
    """Shortcut to access a subset of the userId attributes that are stored
    in the session.

    The list of attributes to store in the session is specified in
      config['webapp2_extras.auth']['user_attributes'].
    :returns
      A dictionary with most userId information
    """
    return self.auth.get_user_by_session()

  @webapp2.cached_property
  def user_id(self):
    """Shortcut to access the userId ID stored
    in the session.

    """
    return self.auth.get_user_by_session()["user_id"]

  @webapp2.cached_property
  def user(self):
    """Shortcut to access the current logged in userId.

    Unlike user_info, it fetches information from the persistence layer and
    returns an instance of the underlying model.

    :returns
      The instance of the userId model associated to the logged in userId.
    """
    u = self.user_info
    return self.user_model.get_by_id(u['user_id']) if u else None

  @webapp2.cached_property
  def user_model(self):
    """Returns the implementation of the userId model.

    It is consistent with config['webapp2_extras.auth']['user_model'], if set.
    """
    return self.auth.store.user_model

  @webapp2.cached_property
  def session(self):
    """Shortcut to access the current session."""
    return self.session_store.get_session(backend="datastore")

  def render_template(self, view_filename, params=None):
    view_filename = self.get_template_file(view_filename, self, params)
    if not params:
      params = {}
    try:
      user = self.user_info
      params['userId'] = user
    except:
      user = None
    path = os.path.dirname(__file__) + '/' + config["templates_dir"] + view_filename
    logging.debug("render_template path " + path)
    output = template.render(path, params)
    self.response.out.write(output)

  def render_template_to_string(self, view_filename, params=None):
    view_filename = self.get_template_file(view_filename, self, params)
    if not params:
      params = {}
    user = self.user_info
    params['userId'] = user
    path = os.path.dirname(__file__) + '/' + config["templates_dir"] + '/' + view_filename
    output = template.render(path, params)
    return output

  def is_mobile(self, request):
    try:
      if 'm' in request.params:
        return True
      if config["mobile"]:
        return True
      if request.user_agent.find("iPhone") > -1:
        return True
      if request.user_agent.find("iPod") > -1:
        return True
      if request.user_agent.find("Android") > -1:
        return True
      if request.user_agent.find("BlackBerry") > -1:
        return True
      return False
    except:
      return False

  def get_template_file(self, template_file, handler, con=None):
    try:
      logging.debug("get_template_file: " + template_file)
      if con and 'mobile' in con:
        if not con['Mobile']:
          try_file = config["templates_dir"] + template_file
          if os.path.exists(try_file):
            logging.debug("template path 1: " + template_file)
            return template_file
          logging.debug("template path 1 pass")
      tablet = False
      if self.is_mobile(handler.request):
        try_file = config["templates_dir"] + 'mobile/' + template_file
        if os.path.exists(try_file):
          logging.debug("template path 2: " + 'mobile/' + template_file)
          return "mobile/" + template_file
        logging.debug("template path 2 pass " + try_file)
      else:
        if "t" in handler.request.params:
          tablet = True
        if handler.request.user_agent.find("iPad") > -1:
          tablet = True
        if tablet:
          # tablets get the desktop page, unless a tablet one exists
          for tmp in config["template_dirs"]:
            if os.path.exists(tmp + "/tablet/t_" + template_file):
              logging.debug("template path 3: " + 'mobile/' + template_file)
              return "tablet/t_" + template_file
          logging.debug("template path 3 pass")
        else:
          for tmp in config["template_dirs"]:
            try_file = config["templates_dir"] + tmp + '/' + template_file
            if os.path.exists(try_file):
              logging.debug("template path 4: " + tmp + '/' + template_file)
              return tmp + '/' + template_file
          logging.debug("template path 4 pass")
      return template_file
    except Exception:
      logging.exception("get_template_file " , exc_info=True)
      logging.debug("template path 5: " + template_file)
      return template_file

  def global_context(self, request, con):
    return con

  def display_message(self, message):
    """Utility function to display a template with a simple message."""
    params = {
      'message': message
    }
    self.render_template('message.html', params)

  # this is needed for webapp2 sessions to work
  def dispatch(self):
    # Get a session store for this request.
    self.session_store = sessions.get_store(request=self.request)

    try:
      # Dispatch the request.
      webapp2.RequestHandler.dispatch(self)
    finally:
      # Save all sessions.
       self.session_store.save_sessions(self.response)
