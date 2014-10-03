from datetime import datetime, timedelta
from webapp2_extras import auth
import views

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
  'template_filename_function': views.get_template_file,
  'mobile': False,
  'how_old_is_new': timedelta(days=1),
  'ALLOWED_INCLUDE_ROOTS': "/templates",
  'google_api_key': 'AIzaSyDiTThta8R7EFuFo8cGfPHxIGYoFkc77Bw',
  'all_are_friends': True
}

auth.default_config['token_max_age'] = 86400 * 7 * 8  # 8 weeks login auth token timeout

ALLOWED_APP_IDS = ('shout-about', 'rayv-prod')

API_TARGET_APP_ID = 'rayv-prod'
