from datetime import datetime, timedelta
import os
from webapp2_extras import auth

__author__ = 'Will'

config = {
  'webapp2_extras.auth': {
    'user_model': 'auth_model.User',
    'user_attributes': ['name']
  },
  'webapp2_extras.sessions': {
    'secret_key': '=r-$b*8hglm+858&9t043hlm6-&6-3d3vfc4((7yd0dbrakhvi'
  },
  'templates_dir': "templates/",
  'template_dirs': ["/", "/mobile"],
  'online': True,
  'mobile': False,
  'place_types': 'food|restaurant|bar|cafe|meal_delivery|meal_takeaway|lodging',
  'ALLOWED_INCLUDE_ROOTS': "/templates",
  'google_api_key': 'AIzaSyDiTThta8R7EFuFo8cGfPHxIGYoFkc77Bw',
  'all_are_friends': False,
  'TIMING_DELTA': timedelta(0,5 * 60), # 5 mins
  'system_email': 'wgilpin+rayv@gmail.com',
  'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S',
  'memcache_life': timedelta(1), #1 day,
  'min_version':"0.7",
  'version':"0.7",
  'updates_max_age':30,
  'log_passwords': False,
}

auth.default_config['token_max_age'] = 86400 * 7 * 8  # 8 weeks login auth token timeout

ALLOWED_APP_IDS = ('shout-about', 'rayv-prod')

API_TARGET_APP_ID = 'rayv-app'

FAKE_ATTR = 'True'

def running_on_test_server():
  server = os.environ['SERVER_NAME']
  return server == 'localhost' or server.find('192.')== 0

