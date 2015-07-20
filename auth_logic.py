import base64
from google.appengine.api import mail
import google.appengine.ext.ndb

from auth_model import User
import settings

__author__ = 'Will'

# !/usr/bin/env python

# see https://github.com/abahgat/webapp2-userId-accounts/ where I got this fro,

import logging
from base_handler import BaseHandler

from webapp2_extras.auth import InvalidAuthIdError
from webapp2_extras.auth import InvalidPasswordError


def user_required(handler):
  """
    Decorator that checks if there's a userId associated with the current session.
    Will also fail if there's no session present.
  """

  def check_login(self, *args, **kwargs):
    auth = self.auth
    if not auth.get_user_by_session():
      self.redirect(self.uri_for('login'), abort=True)
    else:
      return handler(self, *args, **kwargs)

  return check_login

def CheckAPILogin(handler):
  username = ""
  logging.debug("Login headers " + str(handler.request.headers.environ))
  token = None
  if 'HTTP_AUTHORIZATION' in handler.request.headers.environ:
    token = handler.request.headers.environ['HTTP_AUTHORIZATION']
  elif 'Authorization' in handler.request.headers:
    token = handler.request.headers['Authorization']
  if token:
    (username, password) = base64.b64decode(token.split(' ')[1]).split(':')
    user = handler.user_model.get_by_auth_id(username)
    if user and user.blocked:
      logging.info('views.loginAPI: Blocked user ' + username)
      handler.abort(403)
    handler.auth.get_user_by_password(username, password, remember=True,
                                   save_session=True)
    logging.info('LoginAPI: Logged in')
    # tok = user.create_auth_token(handler.user_id)
    # handler.response.out.write('{"auth":"%s"}'%tok)
  else:
    logging.warning('LoginAPI no auth header')
    handler.abort(401)
  return username, True

def api_login_required(handler):
  """
    Decorator that checks if there's a userId associated with the current session.
    Will also fail if there's no session present.
  """

  def check_login(self, *args, **kwargs):
    auth = self.auth
    if not auth.get_user_by_session():
      try:
        username, isOk = CheckAPILogin(self)
        if not isOk:
          self.abort(401)
      except InvalidPasswordError:
        self.abort(401)
    return handler(self, *args, **kwargs)

  return check_login

class RegisterInOne(BaseHandler):
  def post(self):
    username = self.request.get('username')
    user = self.user_model.get_by_auth_id(username)
    if user and user.blocked:
      logging.info('SignupHandler: Blocked user ' + username)
      self.response.out.write("BLOCKED")
    email = self.request.get('email')
    name = self.request.get('name')
    password = self.request.get('password')
    last_name = self.request.get('lastname')

    unique_properties = ['email_address']
    user_data = self.user_model.create_user(username,
                                            unique_properties,
                                            email_address=email, name=name,
                                            password_raw=password,
                                            last_name=last_name, verified=False)
    if not user_data[0]:  #user_data is a tuple
      self.response.out.write("BAD_USERNAME")

    user = user_data[1]
    user.screen_name = self.request.get('screenname')
    user.put()

    # store userId data in the session
    self.auth.set_session(self.auth.store.user_to_dict(user), remember=True)

    if not user.verified:
      user.verified = True
      user.put()
    self.response.out.write("OK")


class SignupHandler(BaseHandler):
  def get(self):
    self.render_template('signup.html')

  def post(self):
    logging.info('SignupHandler: In')
    email = self.request.get('email')
    username = email
    user = self.user_model.get_by_auth_id(username)
    if user and user.blocked:
      logging.info('SignupHandler: Blocked user ' + username)
      return self.display_message('Unable to sign up')
    name = self.request.get('name')
    password = self.request.get('password')
    last_name = self.request.get('lastname')

    unique_properties = ['email_address']
    logging.info('SignupHandler: Create User '+email)
    user_data = self.user_model.create_user(username,
                                            unique_properties,
                                            email_address=email, name=name,
                                            password_raw=password,
                                            last_name=last_name, verified=False)
    if not user_data[0]:  #user_data is a tuple
      logging.warning('SignupHandler: ERROR dup for '+email)
      self.display_message(
        'Unable to create account for %s.\n That email is already registered' %
        (username))
      return

    user = user_data[1]
    user_id = user.get_id()

    user.screen_name = self.request.get('screenname')
    logging.info('SignupHandler: Put...')
    user.put()
    logging.info('SignupHandler: Put done')

    token = self.user_model.create_signup_token(user_id)

    verification_url = self.uri_for('verification', type='v', user_id=user_id,
                                    signup_token=token, _full=True)

    msg = 'Click on this link to confirm your address and complete the sign-up process \n'+\
            verification_url
    logging.info('SignupHandler: Send msg %s, token %s'%(verification_url, token))
    mail.send_mail(sender=settings.config['system_email'],
                     to=[email, 'wgilpin+taste5@gmail.com'],
                     subject="Welcome to Taste 5",
                     body=msg)
    #self.display_message(msg.format(url=verification_url))
    logging.info('SignupHandler: Sent')
    params = {
      'email':email,
      'password':password
    }
    self.render_template('signup-verify.html', params)


class ForgotPasswordHandler(BaseHandler):
  def get(self):
    self._serve_page()

  def post(self):
    username = self.request.get('username')
    user = User.query(google.appengine.ext.ndb.GenericProperty('email_address') == username).get()
    # #user = self.user_model.get_by_auth_id(username)
    if not user:
      logging.info('Could not find any userId entry for username %s', username)
    else:
      try:
        if user.blocked:
          logging.info('ForgotPasswordHandler: Blocked user ' + username)
          self.abort(403)
      except:
        pass
      user_id = user.get_id()
      token = self.user_model.create_signup_token(user_id)

      verification_url = self.uri_for('verification', type='p', user_id=user_id,
                                      signup_token=token, _full=True)

      msg = 'Please visit this link to reset your password\n%s'%verification_url
      mail.send_mail(sender=settings.config['system_email'],
                     to=[user.email_address, 'wgilpin+taste5@gmail.com'],
                     subject="Password Reset",
                     body=msg)
      logging.info("Reset email sent to %s"%user.email_address)

    params = {
      'message2': "If that account exists, an email was sent. "
                  "Please read it for instructions"
    }
    self.render_template('login.html', params)

  def _serve_page(self, not_found=False):
    username = self.request.get('username')
    params = {
      'username': username,
      'not_found': not_found
    }
    self.render_template('forgot.html', params)


class VerificationHandler(BaseHandler):
  def get(self, *args, **kwargs):
    user = None
    user_id = kwargs['user_id']
    signup_token = kwargs['signup_token']
    verification_type = kwargs['type']

    # it should be something more concise like
    # self.auth.get_user_by_token(user_id, signup_token)
    # unfortunately the auth interface does not (yet) allow to manipulate
    # signup tokens concisely
    user, ts = self.user_model.get_by_auth_token(int(user_id), signup_token,
                                                 'signup')

    if user:
      if user.blocked:
        logging.info('VerificationHandler: Blocked user ')
        self.abort(403)
      else:
        logging.info('VerificationHandler: Good user ')

    else:
      logging.info('Could not find any userId with id "%s" signup token "%s"',
                   user_id, signup_token)
      self.abort(404)

    # store userId data in the session
    self.auth.set_session(self.auth.store.user_to_dict(user), remember=True)

    if verification_type == 'v':
      # remove signup token, we don't want users to come back with an old link
      self.user_model.delete_signup_token(user.get_id(), signup_token)

      if not user.verified:
        user.verified = True
        user.put()

      self.display_message('User email address has been verified.')
      return
    elif verification_type == 'p':
      # supply userId to the page
      params = {
        'userId': user,
        'token': signup_token
      }
      self.render_template('resetpassword.html', params)
    else:
      logging.info('verification type not supported')
      self.abort(404)


class SetPasswordHandler(BaseHandler):
  @user_required
  def post(self):
    password = self.request.get('password')
    old_token = self.request.get('t')

    if not password or password != self.request.get('confirm_password'):
      logging.debug(
        "Reset fail: " + self.request.get('password') + '/' + self.request.get(
          'confirm_password'))
      self.display_message('passwords do not match')
      return

    user = self.user
    user.set_password(password)
    user.put()

    # remove signup token, we don't want users to come back with an old link
    self.user_model.delete_signup_token(user.get_id(), old_token)

    self.display_message('Password updated')


class LoginHandler(BaseHandler):
  def get(self):
    self._serve_page()

  def post(self):
    username = self.request.get('username')
    user = self.user_model.get_by_auth_id(username)
    if user and user.blocked:
      logging.info('LoginHandler: Blocked user ' + username)
      self._serve_page(True)
    password = self.request.get('password')
    try:
      u = self.auth.get_user_by_password(username, password, remember=True,
                                         save_session=True)
      self.redirect('/index.html')
    except (InvalidAuthIdError, InvalidPasswordError) as e:
      logging.info('Login failed for userId %s because of %s', username,
                   type(e))
      self._serve_page(True)

  def _serve_page(self, failed=False):
    username = self.request.get('username')
    params = {
      'username': username,
      'failed': failed
    }
    self.redirect('/login.html', params)


class LogoutHandler(BaseHandler):
  def get(self):
    self.auth.unset_session()
    self.redirect(self.uri_for('home'))


class AuthenticatedHandler(BaseHandler):
  @user_required
  def get(self):
    self.render_template('authenticated.html')


"""
app = webapp2.WSGIApplication([
    webapp2.Route('/', MainHandler, name='home'),
    webapp2.Route('/signup', SignupHandler),
    webapp2.Route('/<type:v|p>/<user_id:\d+>-<signup_token:.+>',
      handler=VerificationHandler, name='verification'),
    webapp2.Route('/password', SetPasswordHandler),
    webapp2.Route('/login', LoginHandler, name='login'),
    webapp2.Route('/logout', LogoutHandler, name='logout'),
    webapp2.Route('/forgot', ForgotPasswordHandler, name='forgot'),
    webapp2.Route('/authenticated', AuthenticatedHandler, name='authenticated')
], debug=True, config=config)

logging.getLogger().setLevel(logging.DEBUG)
"""
