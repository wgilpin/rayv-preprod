import json
import logging
import urllib2
from datetime import datetime
from google.appengine.api import memcache
from google.appengine.api.taskqueue import taskqueue
from google.appengine.ext import db
from google.appengine.ext import ndb

from google.appengine.ext.db import ReferencePropertyResolveError
from google.appengine.ext.deferred import deferred
from auth_logic import BaseHandler, user_required
from auth_model import User
import geohash
import logging_ext
from models import Item, Vote, DBImage, Category, VoteValue, MealKind, PlaceStyle
import geo

__author__ = 'Will'

"""
         URL is /migrate_datastore?no=XXXX
"""

class migrate(BaseHandler):


  @user_required
  def add_addresses(self):
    #add address to any that don't have one
    try:
      items = Item.query()
      count = 0
      for it in items:
        if not it.address:
          google_data = geo.getPlaceDetailFromGoogle(it)
          if 'address' in google_data:
            it.address = google_data['address']
          if not it.address:
            it.address = geo.geoCodeLatLng(it.lat, it.lng)
          if it.address:
            it.save()
            count += 1
          else:
            self.response.out.write('No address for \s'%it.place_name)

      self.response.out.write('Added %d addresses \n'%count)
    except Exception, e:
      self.response.out.write("FAIL ")
      logging.error("Migration add-addresses FAIL", exc_info=True)



  @user_required
  def remove_orphan_votes(self):
    # remove orphan votes after an item is deleted
    votes = Vote.query()
    for v in votes:
      try:
        it = v.item.get().place_name
      except ReferencePropertyResolveError:
        v.key.delete()
        self.response.out.write('Delete 1')
      except Exception:
        self.response.out.write("FAIL ")
    memcache.flush_all()

  @user_required
  def add_cuisines(self):
    try:
      new_cat = self.request.params['cuisine']
      new_cat = Category(id=new_cat)
      new_cat.title = new_cat
      new_cat.put()
      self.response.out.write('Added Category %s<br>'%new_cat)
    except Exception, ex:
      self.response.out.write('Adding categories failed %s'%ex)
      
  @user_required
  def add_new_cuisine(self):
    try:
      new_cat_name = self.request.params['cuisine']
      if new_cat_name:
        new_cat = Category(id=new_cat_name)
        new_cat.title = new_cat_name
        new_cat.put()
        self.response.out.write('Added Cuisine %s<br>'%new_cat_name)
    except Exception, ex:
      self.response.out.write('Adding cuisine failed %s'%ex)

  @user_required
  def add_websites(self):
    # add websites
    items = Item.query()
    for it in items:
      try:
        if it.website:
          self.response.out.write("%s has website<br>" % it.place_name)
          continue
        detail = geo.getPlaceDetailFromGoogle(it)
        if 'website' in detail:
          it.website = geo.getPlaceDetailFromGoogle(it)['website']
        else:
          self.response.out.write("%s no website<br>" % it.place_name)
        it.save()
        self.response.out.write("%s is %s<br>" % (it.place_name, it.website))
      except Exception, e:
        self.response.out.write("FAIL %s<br>" % it.place_name)
        self.response.out.write("FAIL %s-%s<br>" % (it.place_name, str(e)))
        pass

  @user_required
  def remote_urls_to_blobs(self):
    # add convert remote urls to blobs
    items = Item.query()
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

  @user_required
  def add_phone_numbers(self):
    # add phone nos
    items = Item.query()
    for it in items:
      try:
        if it.telephone:
          self.response.out.write("%s has phone<br>" % it.title)
          continue
        detail = geo.getPlaceDetailFromGoogle(it)
        if 'telephone' in detail:
          it.telephone = geo.getPlaceDetailFromGoogle(it)['telephone']
        else:
          self.response.out.write("%s no phone<br>" % it.title)
        it.save()
        self.response.out.write("%s is %s<br>" % (it.title, it.telephone))
      except Exception, e:
        self.response.out.write("FAIL %s<br>" % it.title)
        self.response.out.write("FAIL %s-%s<br>" % (it.title, str(e)))
        pass

  @user_required
  def add_google_img_if_missing(self):
    # add google img where missing
    items = Item.query()
    for it in items:
      try:
        if it.photo and it.photo.thumb:
          self.response.out.write("photo %s<br>" % it.title)
          continue
        if it.photo.remoteURL and len(it.photo.remoteURL) > 0:
          self.response.out.write("googled %s<br>" % it.title)
          continue
        img = DBImage()
        img.remoteURL = geo.getPlaceDetailFromGoogle(it)['photo']
        img.put()
        it.photo = img
        self.response.out.write("Added <a href='%s'>%s</a><br>" %
                                (img.remoteURL, it.title))
        it.save()
      except Exception, e:
        self.response.out.write("FAIL %s<br>" % it.title)
        self.response.out.write("FAIL %s-%s<br>" % (it.title, str(e)))
        pass

  @user_required
  def recalc_votes_totals(self):
    # recalc vote totals
    items = Item.query()
    for it in items:
      up = 0
      down = 0
      for v in it.votes:
        if v.vote == VoteValue.VOTE_LIKED:
          up += 1
        elif v.vote == VoteValue.VOTE_DISLIKED:
          down -= 1
      it.votesUp = up
      it.votesDown = down
      it.save()

  @user_required
  def add_geohash(self):
    # add GeoHash
    for it in Item.query():
      it.geo_hash = geohash.encode(it.lat, it.lng)
      it.save()

  @user_required
  def votes_down_to_abs(self):
    # make sure votesDown is +ve (abs())
    items = Item.query()
    for it in items:
      if it.votesDown < 0:
        it.votesDown = abs(it.votesDown)
        it.save()

  @user_required
  def one_vote_per_item(self):
    # make sure each item has 1 vote
    items = Item.query()
    for it in items:
      try:
        it.lat = it.latitude
      except:
        pass
      try:
        it.lng = it.long
      except:
        pass
      it.save()

  @user_required
  def at_least_one_vote_per_item(self):
    # make sure each item has 1 vote
    items = Item.query()
    for it in items:
      vote = it.votes.filter("voter =", it.owner).get()
      if not vote:
        vote = Vote()
        vote.item = it
        vote.vote = VoteValue.VOTE_LIKED
        vote.voter = it.owner
        vote.comment = "blah"
        it.upVotes = 1
        vote.put()
        it.save()
      if it.votesUp == it.votesDown == 0:
        if vote.vote == VoteValue.VOTE_LIKED:
          it.votesUp = 1
        elif vote.vote == VoteValue.VOTE_DISLIKED:
          it.votesDown = -1
        it.save()

  @user_required
  def only_one_vote_per_user_per_item(self):
    # make sure each item has 1 vote
    items = Item.query()
    for it in items:
      votes_per_voter = {}
      for v in it.votes:
        if v.voter in votes_per_voter:
          v.key.delete()
        else:
          votes_per_voter[v.voter] = True

  @user_required
  def item_title_to_StringProperty(self):
    # change Item title property to a StringProp not a textProp (place_name)
    items = Item.query()
    for it in items:
      it.place_name = it.title
      it.save()

  @user_required
  def move_comment_to_vote(self):
    # move item comment from the item to the vote
    items = Item.query()
    for it in items:
      vote = it.votes.filter("voter =", it.owner).get()
      if vote and it.descr and len(it.descr) > 0:
        # don't overwrite a comment with a blank
        vote.comment = it.descr
        vote.put()

  @user_required
  def set_vote_time_to_now(self):
    votes = Vote.query()
    for v in votes:
      v.when = datetime.now()
      v.put()

  @user_required
  def set_votes_up_down(self):
    items = Item.query()
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
        it.save()

  @user_required
  def wipe_item_json(self):
    n = 0
    for p in Item.query():
      p.set_json()
      p.put()
      n += 1
    memcache.flush_all()
    self.response.out.write("\n%d "%n)

  @user_required
  def wipe_votes_json(self):
    #reset all votes json
    taskqueue.add(url='/task/batch_update_votes',
                    params={'migration':'reset-votes-json'})
    self.response.out.write("Batch job started<br/>")

  @user_required
  def rename_category(self):
    #change the name of a cat
    old_cat = self.request.params["old_cat"]
    new_cat = self.request.params["new_cat"]
    if Category.get_by_id(new_cat) == None:
      new_cat_instance = Category(id=new_cat)
      new_cat_instance.title = new_cat
      new_cat_instance.put()
    taskqueue.add(url='/task/batch_update_items',
                    params={
                      'migration':'rename_category',
                      'p1': old_cat,
                      'p2': new_cat})
    taskqueue.add(url='/task/batch_update_votes',
                    params={
                      'migration':'rename_category',
                      'p1': old_cat,
                      'p2': new_cat})
    self.response.out.write("Batch job started")

  @user_required
  def change_votes_to_votevalue(self):
    n=0
    votes = Vote.query()
    for v in votes:
      if v.vote == 1:
        v.vote = VoteValue.VOTE_LIKED
      elif v.vote == -1:
        v.vote = VoteValue.VOTE_DISLIKED
      elif v.untried:
        v.vote = VoteValue.VOTE_UNTRIED
      else:
        v.vote = VoteValue.VOTE_NONE
      v.cuisine = v.item.category
      if v.cuisine.title in ["Burger","Cafe","Fast food","Deli","Fish and chips"]:
        v.place_style = PlaceStyle.STYLE_QUICK
      v.put()
      n += 1
    memcache.flush_all()
    self.response.out.write("\n%d "%n)

  @user_required
  def change_votes_to_4_dot(self):
    n=0
    votes = Vote.query()
    for v in votes:
      if v.untried:
        v.vote = VoteValue.VOTE_UNTRIED
      v.cuisine = v.item.category
      v.put()
      n += 1
    memcache.flush_all()
    self.response.out.write("\n%d "%n)

  @user_required
  def add_google_data_if_missing(self):
    # add google img where missing
    items = Item.query()
    for it in items:
      try:
        good = True
        if not it.address:
          good=False
        if not it.photo:
          good = False
        else:
          if not it.photo.thumb:
            good = False
        if good:
          self.response.out.write("photo %s<br>\n" % it.title)
          continue
        goog = geo.getPlaceDetailFromGoogle(it)
        remoteURL = goog['photo']
        if remoteURL:
          main_url = remoteURL % 250
          data = urllib2.urlopen(main_url)
          it.photo.picture = db.Blob(data.read())
          it.photo.remoteURL = None
          thumb_url = remoteURL % 65
          thumb_data = urllib2.urlopen(thumb_url)
          it.photo.thumb = db.Blob(thumb_data.read())
          it.photo.put()
        if 'address' in goog:
            it.address = goog['address']
        if not it.address:
          it.address = geo.geoCodeLatLng(it.lat, it.lng)
        it.set_json()
        it.put()
        self.response.out.write("Added %s"%it.title)
      except Exception, e:
        self.response.out.write("FAIL %s<br>" % it.title)
        self.response.out.write("FAIL %s-%s<br>" % (it.title, str(e)))
    memcache.flush_all()

  @user_required
  def remove_brunch(self):
    items = Item.query()
    for it in items:
      if it.category.title == 'Brunch':
        v = it.votes
        if v:
          first = v.get()
          it.category = first.cuisine
          it.put()
          self.response.out.write("Set %s to %s<br>"%(it.place_name, first.cuisine.title))
    for v in Vote.query():
      if v.cuisine.title == 'Brunch':
        self.response.out.write("BRUNCH: %s for %s<br>"%(v.key(), v.item.place_name))

  @user_required
  def votes_to_5_star(self):
    votes = Vote.query() #.filter("vote =",0)
    for v in votes:
      if v.vote == VoteValue.VOTE_UNTRIED:
        v.untried = True
        v.stars = 0
      elif v.vote == VoteValue.VOTE_DISLIKED:
        v.stars = 1
        v.untried = False
      elif v.vote == VoteValue.VOTE_LIKED:
        if v.stars == 0:
          v.stars = 5
          v.untried = False
      else:
        self.response.out.write("ERROR on vote %s - %s vote is %s<BR>"%(
          str(v.key()),
          v.item.place_name,
          str(v.vote))
                                )
      v.put()
    memcache.flush_all()





  @user_required
  def get(self):
    migration_name = self.request.get("m")
    if migration_name == '1':
      self.set_votes_up_down()
      self.response.out.write("1-items OK")
      votes = Vote.query()
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
    elif migration_name == '2':
      self.move_comment_to_vote()
      self.response.out.write("2-vote comments OK")
    elif migration_name == '3':
      self.at_least_one_vote_per_item()
      self.response.out.write("3-vote totals OK")
    elif migration_name == '4':
      self.one_vote_per_item()
      self.response.out.write("4-latLng OK")
    elif migration_name == '5':
      self.votes_down_to_abs()
      self.response.out.write("5-+ve votes OK")
    elif migration_name == "6":
      self.add_geohash()
      self.response.out.write("6 - geohash added OK")
    elif migration_name == "7":
      self.recalc_votes_totals()
      self.response.out.write("7 - votes re-totaled OK")
    elif migration_name == "8":
      self.add_google_img_if_missing()
      self.response.out.write("8 - images got from google OK")
    elif migration_name == "9":
      self.add_phone_numbers()
      self.response.out.write("9 - phone nos got from google OK")
    elif migration_name == "10":
      self.item_title_to_StringProperty()
      self.response.out.write("10 - title becomes place_name StringProp OK")
    elif migration_name == "11":
      self.remote_urls_to_blobs()
      self.response.out.write("11 - images got from google into db OK")
    elif migration_name == "remove_orphan_votes":
      self.remove_orphan_votes()
      self.response.out.write(json.dumps({
        'status':'OK',
        'detail':'12 - votes clean'}))
    elif migration_name == "13":
      self.add_websites()
      self.response.out.write("13 - websites got from google OK")
    elif migration_name == "14":
      self.add_edited()
      self.response.out.write("14 - last edit times added")
    elif migration_name == "add-blocked":
      self.add_blocked_to_user()
      self.response.out.write("User blocked - added")
    elif migration_name == "reset-vote-times":
      self.set_vote_time_to_now()
      self.response.out.write("Vote Times Reset")
    elif migration_name == "add-cuisines":
      self.add_cuisines()
      self.response.out.write("Vote Times Reset")
    elif migration_name == "add-addresses":
      self.add_addresses()
      self.response.out.write("Addresses Added")
    elif migration_name == "add-cuisine":
      self.add_new_cuisine()
      self.response.out.write("Cuisine added")
    elif migration_name == "set-vote-value":
      self.change_votes_to_votevalue()
      self.response.out.write("Vote values added")
    elif migration_name == "reset-items-json":
      self.wipe_item_json()
      self.response.out.write("Places reset")
    elif migration_name == "change-votes-to-4-dot":
      self.change_votes_to_4_dot()
      self.response.out.write("Places reset")
    elif migration_name == "add_google_data":
      self.add_google_data_if_missing()
      self.response.out.write("Google data added")
    elif migration_name == "dedup_votes":
      self.only_one_vote_per_user_per_item()
      self.response.out.write("Votes Deduplicated")
    elif migration_name == "remove_brunch":
      self.remove_brunch()
      self.response.out.write("Brunch removed")
    elif migration_name == "five_star":
      self.votes_to_5_star()
      self.response.out.write("Stars set")
    elif migration_name == "reset-votes-json":
      self.wipe_votes_json()
      self.response.out.write("Json Wiped")
    elif migration_name == "rename-category":
      self.rename_category()
      self.response.out.write("Cat renamed")
    elif migration_name == "single-change-queue-places":
      self.single_change_queue_places()
      self.response.out.write("Queues merged")
    elif migration_name == "single-change-queue-votes":
      self.single_change_queue_votes()
      self.response.out.write("Queues merged")
    else:
      logging_ext.logging_ext.error("No Migration - %s"%migration_name)
      self.response.out.write("No Migration - %s"%migration_name)


  @user_required
  def add_edited(self):
    # add the last edited field to each
    items = Item.query()
    stamp = datetime.now()
    dirty = False
    for it in items:
      try:
        it.edited = stamp
        it.save()
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
        it.save()

  @user_required
  def add_blocked_to_user(self):
    users = User.query()
    for u in users:
      if not u.blocked:
        u.blocked = False
        u.put()

  def single_change_queue_places(self):
    from ndb_models import Change
    Change.migrate_old_places_to_changes()

  def single_change_queue_votes(self):
    from ndb_models import Change
    Change.migrate_old_votes_to_changes()



def batch_rename_category_items(item, old_cat, new_cat, nothing=None):
  if item.category.get().title == old_cat:
    item.category = Category.get_by_id(new_cat).key

def batch_rename_category_votes(vote, old_cat, new_cat, nothing=None):
  if vote.cuisine.get().title == old_cat:
    vote.cuisine = Category.get_by_id(new_cat).key

BATCH_SIZE=100
def BatchUpdateItems(update_fn_name, cursor=None, num_updated=0, p1=None, p2=None):
  query = Item.query()
  to_put = []
  q, cursor, more  = query.fetch_page(BATCH_SIZE, start_cursor=cursor)
  for it in q:
    if update_fn_name == "rename_category":
      batch_rename_category_items(it, p1, p2)
    else:
      continue
    to_put.append(it)

  if to_put:
    ndb.put_multi(to_put)
    num_updated += len(to_put)
    logging.debug(
        'Put %d items to Datastore for a total of %d',
        len(to_put), num_updated)
    deferred.defer(
      BatchUpdateItems,
      update_fn_name=update_fn_name,
      cursor=cursor,
      num_updated=num_updated,
      p1=p1,
      p2=p2)
  else:
    logging.debug(
        'BatchUpdateItems complete with %d updates!', num_updated)



class BatchUpdateItemsHandler(BaseHandler):
  def post(self):
    p1 = self.request.get('p1',None)
    p2 = self.request.get('p2',None)
    migration = self.request.get('migration','')
    deferred.defer(BatchUpdateItems,
                   update_fn_name=migration,
                   cursor=None,
                   num_updated=0,
                   p1=p1,
                   p2=p2)
    self.response.out.write('Batch update successfully initiated.')


def batch_reset_vote_json(vote):
  # no put as the put is done in the batch handler
  vote.json = json.dumps(vote.to_json(),default=vote.json_serial)

def BatchUpdateVotes(update_fn_name, cursor=None, num_updated=0, p1=None, p2=None):
  logging_ext.logging_ext.info("BatchUpdateVotes %s %d"%(update_fn_name,num_updated))
  query = Vote.query()
  to_put = []
  q, cursor, more  = query.fetch_page(BATCH_SIZE, start_cursor=cursor)
  for vote in q:
    if update_fn_name == "rename_category":
      batch_rename_category_votes(vote, p1, p2)
    elif update_fn_name == "reset-votes-json":
      batch_reset_vote_json(vote)
    else:
      continue
    to_put.append(vote)

  if to_put:
    ndb.put_multi(to_put)
    num_updated += len(to_put)
    logging.debug(
        'Put %d votes to Datastore for a total of %d',
        len(to_put), num_updated)
    deferred.defer(
      BatchUpdateVotes,
      update_fn_name=update_fn_name,
      cursor=cursor,
      num_updated=num_updated,
      p1=p1,
      p2=p2)
  else:
    logging_ext.logging_ext.info(
        'BatchUpdateVotes complete with %d updates!'% num_updated)

class BatchUpdateVotesHandler(BaseHandler):
  def post(self):
    p1 = self.request.get('p1',None)
    p2 = self.request.get('p2',None)
    migration = self.request.get('migration','')
    deferred.defer(BatchUpdateVotes,
                   update_fn_name=migration,
                   cursor=None,
                   num_updated=0,
                   p1=p1,
                   p2=p2)
    self.response.out.write('Batch update votes successfully initiated.')