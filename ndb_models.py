from datetime import datetime
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.appengine.ext.ndb import model
import webapp2
from auth_model import User
import settings
from logging_ext import logging_ext

__author__ = 'Will'
import json
import logging
import models
from base_handler import BaseHandler
from auth_logic import api_login_required
import views


class VoteChange (ndb.Model):
  voteId = model.StringProperty()
  when = model.DateTimeProperty()
  subscriberId = model.StringProperty()

class PlaceChange (ndb.Model):
  placeId = model.StringProperty()
  when = model.DateTimeProperty()
  subscriberId = model.StringProperty()

class AddVoteChangesWorker(webapp2.RequestHandler):
  def post(self): # should run at most 1/s due to entity group limit
    """
    Task Worker to mark votes as updated
      - deletes all entryies for the vote
      - adds a new one for all friends of voter
    Params:
      voteKey: strin
      userId: string
    """
    vote_key = self.request.get('voteKey')
    if not vote_key:
      logging.error("AddVoteChangesWorker: 0 length voteKey")
      return
    user_id_str = self.request.get('userId')
    if not user_id_str:
      logging.error("AddVoteChangesWorker: 0 length user_id")
      return
    user_id = int(user_id_str)
    time = self.request.get('time')
    # @ndb.transactional
    def update_votes():
      old_votes = VoteChange.\
        query(VoteChange.voteId==vote_key).\
        fetch(keys_only=True)
      ndb.delete_multi(old_votes)
      friends_list = User.get_by_id(user_id).get_friends()
      for u in friends_list:
        change = VoteChange()
        change.voteId = vote_key
        change.subscriberId = str(u.id())
        change.when = datetime.strptime(
          time,
          views.config['DATETIME_FORMAT'])
        change.put()
    update_votes()


class AddPlaceChangesWorker(webapp2.RequestHandler):
  """
  Task worker thread for adding places
  """
  def post(self): # should run at most 1/s due to entity group limit
    """
    Task Worker to mark place as updated
    Params:
      placeKey: string
      userId: string
    """
    logging_ext.log_to_console("AddPlaceChangesWorker")
    place_key_str = self.request.get('placeKey')
    user_id = int(self.request.get('userId'))
    # @ndb.transactional
    def update_place():
      place_entries = PlaceChange.\
        query(PlaceChange.placeId == place_key_str)
      now = datetime.now()
      for p in place_entries:
        if p.when < now:
          p.when = now
          p.put()
      user = User.get_by_id(user_id)
      friends_list = user.get_friends()
      for u in friends_list:
        p = PlaceChange.\
          query(
            PlaceChange.subscriberId == str(u.id()),
            PlaceChange.placeId == place_key_str).get()
        if not p:
          p = PlaceChange()
          p.subscriberId = str(u.id())
          p.placeId = place_key_str
        p.when = now
        p.put()
    update_place()

class ClearUserChangesWorker(webapp2.RequestHandler):
  def post(self): # should run at most 1/s due to entity group limit
    """
    Deletes all records of updated votes & places for the given user
     Params:
        userID: string
    """
    user_id = self.request.get('userId')
    since = datetime.strptime(
            self.request.params['before'],
            views.config['DATETIME_FORMAT'])
    # @ndb.transactional
    old_votes = VoteChange.\
      query(VoteChange.subscriberId==user_id, VoteChange.when < since).\
      fetch(keys_only=True)
    ndb.delete_multi(old_votes)
    old_places = PlaceChange.\
      query(PlaceChange.subscriberId==user_id, PlaceChange.when < since).\
      fetch(keys_only=True)
    ndb.delete_multi(old_places)

class ClearUserUpdates(BaseHandler):
  def post(self):
    user_id = self.request.get('userId')
    before = datetime.now().strftime(
            views.config['DATETIME_FORMAT'])
    taskqueue.add(url='/api/ClearUserChanges',
                  params={
                    'userId': user_id,
                    'before': before})

def mark_place_as_updated(place_key, user_id):
  taskqueue.add(url='/api/UpdatePlace',
                params={'placeKey': place_key, 'userId': user_id})

def mark_vote_as_updated(vote_key, user_id):
  now_str= datetime.now().strftime(
            views.config['DATETIME_FORMAT'])
  taskqueue.add(url='/api/UpdateVote',
                params={'voteKey': vote_key,
                        'userId': user_id,
                        'time': now_str})

def get_updated_places_for_user(user_id, since):
  """
  get the list of change records for a given user
  :param user_id: int
  :param since: datetime
  :return: query object on PlaceChange
  """
  result = PlaceChange.\
    query(PlaceChange.subscriberId==str(user_id), PlaceChange.when < since)
  return result




class getUserRecordFastViaWorkers(BaseHandler):
  def getIncrement(self, my_id, now):
    places = {}
    updated_places = get_updated_places_for_user(str(my_id), now)
    for up in updated_places:
      p = models.Item.get_by_id(int(up.placeId))
      places[up.placeId] =p.get_json()
    updated_votes = VoteChange.query(VoteChange.subscriberId==str(my_id))
    votes=[]
    for uv in updated_votes:
      v = models.Vote.get_by_id(int(uv.voteId))
      if v:
        try:
          votes.append(v.json)
          place_key = v.item.key.id()
          if not place_key in places:
            places[place_key] = v.item.get_json()
        except:
          pass
    return votes, places

  def getFullUserRecord(self, user, now=None):
    places = {}
    votes = []
    if settings.config['all_are_friends']:
      q = User.gql('')
    else:
      # start with me
      q = [user]
      # then get my friends
      for f in user.get_friends():
        q.append(f.get())
    place_json = None
    place_key = None
    for u in q:
      user_votes = models.Vote.query(models.Vote.voter == u.key.integer_id()).fetch()
      for vote in user_votes:
        try:
          place_key = vote.item.id()
          votes.append(vote.get_json())
          if not place_key in places:
            place_json = models.Item.id_to_json(place_key)
            if "cuisineName" in place_json:
              places[place_key] = place_json
        except Exception, e:
          if place_json:
            logging.error("getFullUserRecord Exception 1 %s"%place_json['place_name'], exc_info=True)
          else:
            logging.error("getFullUserRecord Exception %s"%place_key, exc_info=True)
    return votes, places

  @api_login_required
  def get(self):
    """ get the user record, including friends' places """
    try:
      if self.user.blocked:
        raise Exception('Blocked')
      my_id = self.user_id

    except:
      logging.error('getFullUserRecord: User Exception')
      json.dump({'result':'FAIL'},
                  self.response.out,
                  default=views.json_serial)
      return

    if my_id:
        # logged in
        result = {
          "id": my_id,
          "admin": self.user.profile().is_admin,
          "version": settings.config["version"]}
        since = None
        now = datetime.now()
        if 'since' in self.request.params:
          try:
            # move since back in time to allow for error
            since = datetime.strptime(
              self.request.params['since'],
              views.config['DATETIME_FORMAT']) - \
                    views.config['TIMING_DELTA']
            votes, places = self.getIncrement(my_id, now)
          except OverflowError, ex:
            logging.error("getFullUserRecord Time error with %s"%since,
                          exc_info=True)
            #full update
            votes, places = self.getFullUserRecord(self.user)
        else:
          #full update
          votes, places = self.getFullUserRecord(self.user)

        friends_list = []
        if views.config['all_are_friends']:
          q = User.gql('')
          for u in q:
            user_str = {
                "id": u.get_id(),
                # todo is it first_name?
                'name': u.screen_name}
            friends_list.append(user_str)
        else:
            friends = self.user.get_friends()
            for f in friends:
              friend = f.get()
              user_str = {
                  "id": f.id(),
                  # todo is it first_name?
                  'name': friend.screen_name}
              friends_list.append(user_str)

        sentInvites = models.InviteInternal.query(models.InviteInternal.inviter == my_id)
        recdInvites = models.InviteInternal.query(models.InviteInternal.invitee == my_id)
        sent = []
        for i in sentInvites:
          sent.append(i.to_json())
        recd = []
        for i in recdInvites:
          recd.append(i.to_json())
        result["sentInvites"] = sent
        result["receivedInvites"] = recd
        result['votes'] = votes
        result["places"] = places
        result["friendsData"] = friends_list
        json_str = json.dumps(
          result,
          default=views.json_serial)
        try:
          since_str = str(since) if since else ""
          logging.debug("GetFullUserRecord for %s %s P:%d, V:%d, F:%d"%(
            self.user.screen_name,
            since_str,
            len(places),
            len(votes),
            len(friends_list)
          ))
        except:
          pass
        try:
          #logging
          logging.debug("getUserRecordFastViaWorkers done ")
        except:
          pass
        self.response.out.write(json_str)
        #profile_out("getFullUserRecord")
        return
    self.error(401)
