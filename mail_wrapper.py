import os
from google.appengine.api import mail

__author__ = 'Will'

def send_mail(sender, to, subject, body):
  server = os.environ['SERVER_NAME']
  if server == 'localhost' or server.find('192.')== 0:
    print "SEND EMAIL"
    print 'to: '+str(to)
    print 'Re: '+subject
    print body
  else:
    mail.send_mail(sender, to, subject, body)
