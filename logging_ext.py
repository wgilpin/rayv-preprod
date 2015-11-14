import logging
import sys
import settings


class logging_ext:

  @classmethod
  def error(cls, message, exc_info=False):
    if settings.running_on_test_server():
      print message, sys.exc_info()
    else:
      logging.error(message, exc_info=exc_info)

  @classmethod
  def info(cls, message, exc_info=False):
    if settings.running_on_test_server():
      print message, sys.exc_info()
    else:
      logging.info(message, exc_info=exc_info)

  @classmethod
  def log_to_console(cls, message):
    if settings.running_on_test_server():
      print message
