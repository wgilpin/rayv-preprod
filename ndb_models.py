from datetime import datetime, timedelta
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
import places_db
import geo


class NotificationToken(ndb.Model):
  android = 0
  ios = 1
  winPhone = 2

  userId = model.IntegerProperty()
  token = model.StringProperty()
  email = model.StringProperty()
  kind = model.IntegerProperty()

class VoteChange (ndb.Model):
  voteId = model.StringProperty()
  when = model.DateTimeProperty()
  subscriberId = model.StringProperty()

class PlaceChange (ndb.Model):
  placeId = model.StringProperty()
  when = model.DateTimeProperty()
  subscriberId = model.StringProperty()

class Change (ndb.Model):
  recordId = model.StringProperty()
  when = model.DateTimeProperty()
  subscriberId = model.StringProperty()
  kind = model.IntegerProperty()

  CHANGE_VOTE = 1
  CHANGE_PLACE = 2
  CHANGE_COMMENT = 3

  @classmethod
  def migrate_old_votes_to_changes(cls):
    count = 0
    vote_changes = VoteChange.query()
    for v in vote_changes:
      new_change = Change()
      new_change.kind = cls.CHANGE_VOTE
      new_change.subscriberId = v.subscriberId
      new_change.recordId = v.voteId
      new_change.when = v.when
      new_change.put()
      count += 1
    return count

  @classmethod
  def migrate_old_places_to_changes(cls):
    count = 0
    place_changes = PlaceChange.query()
    for p in place_changes:
      new_change = Change()
      new_change.kind = cls.CHANGE_PLACE
      new_change.subscriberId = p.subscriberId
      new_change.recordId = p.placeId
      new_change.when = p.when
      new_change.put()
      count += 1
    return count

class AddVoteChangesWorker(webapp2.RequestHandler):
  def post(self): # should run at most 1/s due to entity group limit
    """
    Task Worker to mark votes as updated
      - deletes all entries for the vote
      - adds a new one for all friends of voter
    Params:
      voteId: string
      userId: string
    """
    try:
      logging_ext.log_to_console('AddVoteChangesWorker IN')
      vote_id_str = self.request.get('voteId')
      if not vote_id_str:
        logging_ext.error("** AddVoteChangesWorker: no vote id")
        return
      user_id_str = self.request.get('userId')
      if not user_id_str:
        logging_ext.error("** AddVoteChangesWorker: no user_id")
        return
      user_id = int(user_id_str)
      me = User.get_by_id(user_id)
      time = self.request.get('time')
      old_votes = Change.\
        query(Change.kind == Change.CHANGE_VOTE, Change.recordId == vote_id_str).\
        fetch(keys_only=True)
      ndb.delete_multi(old_votes)
      friends_list = me.get_friends_key_list()
      for u in friends_list:
        change = Change()
        change.kind = Change.CHANGE_VOTE
        change.recordId = vote_id_str
        change.subscriberId = str(u.id())
        change.when = datetime.strptime(
          time,
          views.config['DATETIME_FORMAT'])
        change.put()
    except Exception:
      logging_ext.error("** AddVoteChangesWorker", exc_info=True)

class AddPlaceChangesWorker(webapp2.RequestHandler):
  """
  Task worker thread for adding places
  """
  def post(self): # should run at most 1/s due to entity group limit
    """
    Task Worker to mark place as updated
    Params:
      placeId: string place Id
      userId: string
    """
    try:
      logging_ext.log_to_console("AddPlaceChangesWorker")
      place_id_str = self.request.get('placeId')
      user_id_str = self.request.get('userId')
      place_entries = Change.\
        query(Change.kind==Change.CHANGE_PLACE, Change.recordId == place_id_str)
      now = datetime.now()
      for p in place_entries:
        if p.when < now:
          p.when = now
          p.put()
      user = User.get_by_id(int(user_id_str))
      friends_key_list = user.get_friends_key_list()
      for user_key in friends_key_list:
        p = Change.\
          query(
          Change.kind == Change.CHANGE_PLACE,
            Change.subscriberId == str(user_key.id()),
            Change.recordId == place_id_str).get()
        if not p:
          p = Change()
          p.kind = Change.CHANGE_PLACE
          p.subscriberId = str(user_key.id())
          p.placeId = place_id_str
        p.when = now
        p.put()
    except:
      logging_ext.error('** AddPlaceChangesWorker', exc_info=True)

class ClearUserChangesWorker(webapp2.RequestHandler):
  def post(self): # should run at most 1/s due to entity group limit
    """
    Deletes all records of updated votes & places for the given user more than
    n days old

    """
    try:
      since = datetime.now() - timedelta(days=settings.config['updates_max_age'])
      # @ndb.transactional
      old_votes = Change.\
        query(Change.kind==Change.CHANGE_VOTE, Change.when < since).\
        fetch(keys_only=True)
      ndb.delete_multi(old_votes)
      old_places = Change.\
        query(Change.kind==Change.CHANGE_VOTE, Change.when < since).\
        fetch(keys_only=True)
      ndb.delete_multi(old_places)
      logging.info("ClearUserChangesWorker")
    except:
      logging_ext.error('** ClearUserChangesWorker', exc_info=True)

class ClearUserUpdates(BaseHandler):
  def post(self):
    try:
      user_id_str = self.request.get('userId')
      before = datetime.now().strftime(
              views.config['DATETIME_FORMAT'])
      taskqueue.add(url='/api/ClearUserChanges',
                    params={})
    except:
      logging_ext.error('** ClearUserUpdates', exc_info=True)

def mark_place_as_updated(place_id_str, user_id_str):
  """
  :param place_id_str: string urlsafe
  :param user_id_str: string urlsafe
  :return:
  """
  try:
    taskqueue.add(url='/api/UpdatePlace',
                  params={'placeId': place_id_str, 'userId': user_id_str})
  except:
      logging_ext.error('** mark_place_as_updated', exc_info=True)

def mark_vote_as_updated(vote_id_str, user_id_str):
  """
  :param vote_id_str: string urlsafe
  :param user_id_str: string urlsafe
  :return:
  """
  try:
    now_str= datetime.now().strftime(
              views.config['DATETIME_FORMAT'])
    taskqueue.add(url='/api/UpdateVote',
                  params={'voteId': vote_id_str,
                          'userId': user_id_str,
                          'time': now_str})
  except:
      logging_ext.error('** mark_vote_as_updated', exc_info=True)

class getStrangerPlaces(BaseHandler):
  @api_login_required
  def get(self):
    try:
      logging.debug('getStrangerPlaces')
      lat = float(self.request.get("lat"))
      lng = float(self.request.get("lng"))
      place_names = []
      results = geo.findDbPlacesNearLoc(
          geo.LatLng(lat=lat, lng=lng),
          place_names=place_names)
      if results:
        results['search'] = {'lat': lat,'lng':lng}
        # check_for_dirty_data(self, results)
        json.dump(results,
                  self.response.out,
                  default=views.json_serial)
      else:
        # logging.info("get_google_db_places near [%f,%f]: %s" %
        # (lat, lng, "none found"))
        logging.debug("getStrangerPlaces - none found ")
        self.error(401)
    except Exception:
      logging_ext.error("getStrangerPlaces",True)


def get_updated_places_for_user(user_id_str, since):
  """
  get the list of change records for a given user
  :param user_id_str: string urlsafe
  :param since: datetime
  :return: query object on PlaceChange
  """
  try:
    result = Change.\
      query(
        Change.kind == Change.CHANGE_PLACE,
        Change.subscriberId==user_id_str,
        Change.when > since)
    return result
  except:
      logging_ext.error('** get_updated_places_for_user', exc_info=True)

class getUserRecordFastViaWorkers(BaseHandler):
  def getIncrement(self, my_id, since):
    try:
      places_id2json = {}
      vote_list=[]
      updated_places = Change.query(
        Change.kind == Change.CHANGE_PLACE,
        Change.subscriberId==str(my_id),
        Change.when > since
      )
      for up in updated_places:
        p = models.Item.get_by_id(int(up.placeId))
        places_id2json[int(up.placeId)] =p.get_json()
      updated_votes = Change.query(
        Change.kind== Change.CHANGE_VOTE,
        Change.subscriberId==str(my_id),
        Change.when > since
      )
      for uv in updated_votes:
        key = ndb.Key('Vote', int(uv.voteId))
        v = key.get()
        if v:
          try:
            vote_list.append(v.json)
            place_id = v.item.id()
            if not place_id in places_id2json:
              places_id2json[place_id] = v.item.get().get_json()
          except Exception, E:
            pass
      return vote_list, places_id2json
    except:
      logging_ext.error('** getIncrement', exc_info=True)

  def getFullUserRecord(self, user, now=None):
    try:
      places_id2json = {}
      vote_list = []
      if settings.config['all_are_friends']:
        q = User.gql('')
      else:
        # start with me
        q = [user]
        # then get my friends
        for f in user.get_friends_key_list():
          q.append(f.get())
      place_json = None
      place_id = None
      for u in q:
        if u:
          user_votes = models.Vote.query(models.Vote.voter == u.key.integer_id()).fetch()
          for vote in user_votes:
            try:
              place_id = vote.item.id()
              vote_list.append(vote.get_json())
              if not place_id in places_id2json:
                place_json = models.Item.id_to_json(place_id)
                if "cuisineName" in place_json:
                  places_id2json[place_id] = place_json
            except Exception, e:
              if place_json:
                logging_ext.error("** getFullUserRecord Exception 1 %s"%place_json['place_name'], exc_info=True)
              else:
                logging_ext.error("** getFullUserRecord Exception %s"%place_id, exc_info=True)
      return vote_list, places_id2json
    except:
      logging_ext.error('** getFullUserRecord', exc_info=True)


  @api_login_required
  def get(self):
    """ get the user record, including friends' places """
    try:
      if self.user.blocked:
        raise Exception('Blocked')
      my_id = self.user_id

    except:
      logging_ext.error('** getFullUserRecord: User Exception')
      json.dump({'result':'FAIL'},
                  self.response.out,
                  default=views.json_serial)
      return

    if my_id:
      try:
        # logged in
        #check if the client version is allowed
        good_version = False
        if 'version' in self.request.params:
          version = float(self.request.params['version'])
          min_version = Config.min_server_version_allowed()
          if version >= float(min_version):
            good_version = True
        if not good_version:
          logging_ext.error("getUserRecordFastViaWorkers BAD VERSION")
          self.response.out.write("BAD_VERSION")
          return

        #good client version if we got here
        result = {
          "id": my_id,
          "admin": self.user.profile().is_admin,
          "version": settings.config["version"],
          "min_version": settings.config['min_version']}
        since = None
        now = datetime.now()
        if 'since' in self.request.params:
          try:
            # move since back in time to allow for error
            since = datetime.strptime(
              self.request.params['since'],
              views.config['DATETIME_FORMAT']) - \
                    views.config['TIMING_DELTA']
            vote_list, place_id2json = self.getIncrement(my_id, since)
          except OverflowError, ex:
            logging_ext.error("** getFullUserRecord Time error with %s"%since,
                          exc_info=True)
            #full update
            vote_list, place_id2json = self.getFullUserRecord(self.user)
        else:
          #full update
          vote_list, place_id2json = self.getFullUserRecord(self.user)

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
            friends = self.user.get_friends_key_list()
            for f in friends:
              friend = f.get()
              try:
                user_str = {
                    "id": f.id(),
                    # todo is it first_name?
                    'name': friend.screen_name}
              except:
                logging.error("getFullUserRecord Friends error")
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
        result['votes'] = vote_list
        result["places"] = place_id2json
        result["friendsData"] = friends_list
        json_str = json.dumps(
          result,
          default=views.json_serial)
        try:
          since_str = str(since) if since else ""
          logging.debug("GetFullUserRecord for %s %s P:%d, V:%d, F:%d"%(
            self.user.screen_name,
            since_str,
            len(place_id2json),
            len(vote_list),
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
      except:
        logging_ext.error('** getFullUserRecord: Main',exc_info=True)
    else:
        logging_ext.error('** getFullUserRecord: No ID')
    self.error(401)

class Config (ndb.Model):
  Name = model.StringProperty()
  Value = model.StringProperty()

  @classmethod
  def min_server_version_allowed(cls):
    kvp = cls.query(cls.Name == 'min_server_version').get()
    if not kvp:
      kvp = cls()
      kvp.Name = 'min_server_version'
      kvp.Value = settings.config['min_version']
      kvp.put()
    if float(kvp.Value) < float(settings.config['min_version']):
      kvp.Value = settings.config['min_version']
      kvp.put()
    return  kvp.Value
