from google.appengine.api import mail
import settings

__author__ = 'Will'

def send_mail(sender, to, subject, body):
  if settings.running_on_test_server():
    print "SEND EMAIL"
    print 'to: '+str(to)
    print 'Re: '+subject
    print body
  else:
    mail.send_mail(sender, to, subject, body)
