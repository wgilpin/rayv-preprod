import urllib2
from google.appengine.ext import db
from google.appengine.ext.db import ReferencePropertyResolveError
from auth_logic import BaseHandler
import geohash
from models import Item, Vote, DBImage
from views import logged_in, getPlaceDetailFromGoogle

__author__ = 'Will'


class migrate(BaseHandler):
  def get(self):
    if logged_in():
      if self.request.get("no") == '1':
        items = Item.all()
        for it in items:
          dirty = False
          try:
            if not it.votesUp > 0:
              it.votesUp = 0
              dirty = True
          except:
            it.votesUp = 0
            dirty = True
          try:
            if not it.votesDown > 0:
              it.votesDown = 0
              dirty = True
          except:
            it.votesDown = 0
            dirty = True
          if dirty:
            it.put()
        self.response.out.write("1-items OK")
        votes = Vote.all()
        for v in votes:
          dirty = False
          try:
            if v.vote == True:
              v.vote = 1
              dirty = True
          except:
            v.vote = 1
            dirty = True
          if dirty:
            v.put()

        self.response.out.write("1-votes OK")
        return
      elif self.request.get("no") == '2':
        # move item comment from the item to the vote
        items = Item.all()
        for it in items:
          vote = it.votes.filter("voter =", it.owner).get()
          if vote and it.descr and len(it.descr) > 0:
            # don't overwrite a comment with a blank
            vote.comment = it.descr
            vote.put()
        self.response.out.write("2-vote comments OK")
      elif self.request.get("no") == '3':
        # make sure each item has 1 vote
        items = Item.all()
        for it in items:
          vote = it.votes.filter("voter =", it.owner).get()
          if not vote:
            vote = Vote()
            vote.item = it
            vote.vote = 1
            vote.voter = it.owner
            vote.comment = "blah"
            it.upVotes = 1
            vote.put()
            it.put()
          if it.votesUp == it.votesDown == 0:
            if vote.vote > 0:
              it.votesUp = vote.vote
            else:
              it.votesDown = abs(vote.vote)
            it.put()
        self.response.out.write("3-vote totals OK")
      elif self.request.get("no") == '4':
        # make sure each item has 1 vote
        items = Item.all()
        for it in items:
          try:
            it.lat = it.latitude
          except:
            pass
          try:
            it.lng = it.long
          except:
            pass
          it.put()
        self.response.out.write("4-latLng OK")
      elif self.request.get("no") == '5':
        # make sure votesDown is +ve (abs())
        items = Item.all()
        for it in items:
          if it.votesDown < 0:
            it.votesDown = abs(it.votesDown)
            it.put()
        self.response.out.write("5-+ve votes OK")
      elif self.request.get("no") == "6":
        # add GeoHash
        for it in Item().all():
          it.geo_hash = geohash.encode(it.lat, it.lng)
          it.put()
        self.response.out.write("6 - geohash added OK")
      elif self.request.get("no") == "7":
        # recalc vote totals
        items = Item.all()
        for it in items:
          up = 0
          down = 0
          for v in it.votes:
            if v.vote > 0:
              up += v.vote
            else:
              down += abs(v.vote)
          it.votesUp = up
          it.votesDown = down
          it.put()
        self.response.out.write("7 - votes re-totaled OK")
      elif self.request.get("no") == "8":
        # add google img where missing
        items = Item.all()
        for it in items:
          try:
            if it.photo and it.photo.thumb:
              self.response.out.write("photo %s<br>" % it.title)
              continue
            if it.photo.remoteURL and len(it.photo.remoteURL) > 0:
              self.response.out.write("googled %s<br>" % it.title)
              continue
            img = DBImage()
            img.remoteURL = getPlaceDetailFromGoogle(it)['photo']
            img.put()
            it.photo = img
            self.response.out.write("Added <a href='%s'>%s</a><br>" %
                                    (img.remoteURL, it.title))
            it.put()
          except Exception, e:
            self.response.out.write("FAIL %s<br>" % it.title)
            self.response.out.write("FAIL %s-%s<br>" % (it.title, str(e)))
            pass
        self.response.out.write("8 - images got from google OK")
      elif self.request.get("no") == "9":
        # add phone nos
        items = Item.all()
        for it in items:
          try:
            if it.telephone:
              self.response.out.write("%s has phone<br>" % it.title)
              continue
            detail = getPlaceDetailFromGoogle(it)
            if 'telephone' in detail:
              it.telephone = getPlaceDetailFromGoogle(it)['telephone']
            else:
              self.response.out.write("%s no phone<br>" % it.title)
            it.put()
            self.response.out.write("%s is %s<br>" % (it.title, it.telephone))
          except Exception, e:
            self.response.out.write("FAIL %s<br>" % it.title)
            self.response.out.write("FAIL %s-%s<br>" % (it.title, str(e)))
            pass
        self.response.out.write("9 - phone nos got from google OK")
      elif self.request.get("no") == "10":

        # change Item title property to a StringProp not a textProp (place_name)
        items = Item.all()
        for it in items:
          it.place_name = it.title
          it.put()
        self.response.out.write("10 - title becomes place_name StringProp OK")
      elif self.request.get("no") == "11":
        # add convert remote urls to blobs
        items = Item.all()
        for it in items:
          try:
            if it.photo and it.photo.thumb:
              self.response.out.write("photo %s<br>" % it.place_name)
              continue
            if it.photo.remoteURL and len(it.photo.remoteURL) > 0:
              self.response.out.write("url %s: '%s'<br>" %
                                      (it.place_name, it.photo.remoteURL))
              main_url = it.photo.remoteURL % 250
              data = urllib2.urlopen(main_url)
              it.photo.picture = db.Blob(data.read())
              thumb_url = it.photo.remoteURL % 65
              thumb_data = urllib2.urlopen(thumb_url)
              it.photo.thumb = db.Blob(thumb_data.read())
              it.photo.remoteURL = None
              it.photo.put()
            self.response.out.write("skipped %s" % it.place_name)
          except Exception, e:
            self.response.out.write("FAIL %s<br>" % it.place_name)
            self.response.out.write("FAIL %s-%s<br>" % (it.place_name, str(e)))
            pass
        self.response.out.write("11 - images got from google into db OK")
      elif self.request.get("no") == "12":
        # remove orphan votes
        votes = Vote.all()
        for v in votes:
          try:
            it = v.item.place_name
          except ReferencePropertyResolveError:
            db.delete(v)
            self.response.out.write('Delete 1')
          except Exception:
            self.response.out.write("FAIL ", exc_info=True)
        self.response.out.write("12 - votes clean - MEMCACHE")
      elif self.request.get("no") == "13":
        # add websites
        items = Item.all()
        for it in items:
          try:
            if it.website:
              self.response.out.write("%s has website<br>" % it.place_name)
              continue
            detail = getPlaceDetailFromGoogle(it)
            if 'website' in detail:
              it.website = getPlaceDetailFromGoogle(it)['website']
            else:
              self.response.out.write("%s no website<br>" % it.place_name)
            it.put()
            self.response.out.write("%s is %s<br>" % (it.place_name, it.website))
          except Exception, e:
            self.response.out.write("FAIL %s<br>" % it.place_name)
            self.response.out.write("FAIL %s-%s<br>" % (it.place_name, str(e)))
            pass
        self.response.out.write("13 - websites got from google OK")
      else:
        self.response.out.write("No Migration")
    else:
      self.response.out.write("Log In")