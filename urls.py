import webapp2
from webapp2_extras.routes import RedirectRoute
import admin
from auth_logic import SignupHandler, SetPasswordHandler, \
  ForgotPasswordHandler, AuthenticatedHandler
import auth_logic
import geo
import migrate
import ndb_models
import profiler
import views

__author__ = 'Will'

urls = [
  webapp2.Route('/', views.WebServer ),
  webapp2.Route('/signup', SignupHandler),
  webapp2.Route('/<type:v|p>/<user_id:\d+>-<signup_token:.+>',
                handler=views.passwordVerificationHandler, name='verification'),
  webapp2.Route('/password', SetPasswordHandler),
  webapp2.Route('/login', views.login, name='login'),
  webapp2.Route('/forgot', ForgotPasswordHandler, name='forgot'),
  webapp2.Route('/authenticated', AuthenticatedHandler, name='authenticated'),
  webapp2.Route('/register', views.register, name='register'),
  webapp2.Route('/logout', views.logout),
  webapp2.Route('/api/login', views.loginAPI),
  webapp2.Route('/api/invite', views.InviteUserAPI),
  webapp2.Route('/api/register', auth_logic.RegisterInOne),
  webapp2.Route('/api/password', auth_logic.ChangePasswordAPIHandler),
  webapp2.Route('/api/profile', views.profileAPI),
  webapp2.Route('/api/items/all', ndb_models.getStrangerPlaces),
  webapp2.Route('/api/items', views.itemsAPI),
  webapp2.Route('/api/friends', views.FriendsApi),
  webapp2.Route('/api/friends/accept', views.FriendsApiAccept),
  webapp2.Route('/api/friends/reject', views.FriendsApiReject),
  webapp2.Route('/api/friends/remove', views.FriendsApiRemove),
  webapp2.Route('/api/friend/<id:\d+>/votes', views.FriendsVotesApi),
  webapp2.Route('/api/log',views.api_log),
  webapp2.Route('/api/delete',views.api_delete),
  webapp2.Route('/api/geocode',geo.geoCodeAddressMultiple),
  webapp2.Route('/api/place_details',views.getPlaceDetailsApi),
  webapp2.Route('/api/friend/invite',views.AddUserAsFriend),
  webapp2.Route('/api/email_friend',views.emailInviteFriend),
  webapp2.Route('/api/UpdateVote',ndb_models.AddVoteChangesWorker),
  webapp2.Route('/api/UpdatePlace',ndb_models.AddPlaceChangesWorker),
  webapp2.Route('/api/ClearUserChanges',ndb_models.ClearUserChangesWorker),
  webapp2.Route('/api/vote',views.UpdateVote),
  webapp2.Route('/api/comment',views.CommentsHandler),
  webapp2.Route('/api/comments/updates',views.CommentsUpdatesHandler),
  webapp2.Route('/api/comments',views.CommentsHandler),
  webapp2.Route('/api/feedback',views.FeedbackHandler),
  webapp2.Route('/apns/register',views.RegisterApnsToken),


  webapp2.Route('/clear_user_updates',ndb_models.ClearUserUpdates),
  webapp2.Route('/task/batch_update_items',migrate.BatchUpdateItemsHandler),
  webapp2.Route('/task/batch_update_votes',migrate.BatchUpdateVotesHandler),
  webapp2.Route('/GetItemsAjax', views.GetItemsAjax, name='GetItemsAjax'),
  webapp2.Route('/getMapList_Ajax', views.getMapList_Ajax),
  webapp2.Route('/getAddresses_ajax', views.getAddresses_ajax),
  webapp2.Route('/getCuisines_ajax', views.getCuisines_ajax),
  webapp2.Route('/getFullUserRecord', ndb_models.getUserRecordFastViaWorkers),
  webapp2.Route('/addVote_Ajax', views.addVote_ajax),
  webapp2.Route('/getItem/<key:\S+>', views.getItem_ajax),
  webapp2.Route('/getVotes/<key:\S+>', views.getItemVotes_ajax),
  webapp2.Route('/imageSave_Ajax', views.imageEdit_Ajax),

  webapp2.Route('/item/del/<key:\S+>', views.deleteItem),
  # webapp2.Route('/item/<key:\S+>', views.updateItem),
  webapp2.Route('/item', views.newOrUpdateItem, name='newOrUpdateItem'),
  #webapp2.Route('/updateItem', views.updateItem),
  webapp2.Route('/geoLookup', views.geoLookup),
  webapp2.Route('/img/<key:\S+>', views.ImageHandler),
  webapp2.Route('/thumb/<key:\S+>', views.ThumbHandler),
  webapp2.Route('/search', views.search),

  webapp2.Route('/user_profile', views.user_profile),
  webapp2.Route('/profile', profiler.Report),
  webapp2.Route('/profile_reset', profiler.profile_reset),

  webapp2.Route('/ping', views.ping),
  webapp2.Route('/migrate_datastore', migrate.migrate),
  webapp2.Route('/load', views.loadTestData, name='load'),
  webapp2.Route('/full_load', views.wipeAndLoadTestData),
  webapp2.Route('/admin', admin.Main),
  webapp2.Route('/admin/sync_to_prod', admin.SyncToProd),
  webapp2.Route('/admin/update_photos', admin.updatePhotoFromGoogle),
  webapp2.Route('/admin/put_place_api', views.UpdateItemFromAnotherAppAPI),
  webapp2.Route('/admin/update_vote', admin.UpdateAdminVote),
  webapp2.Route('/admin/broadcast', admin.NotificationBroadcast),
  webapp2.Route('/admin/password', admin.ResetUserPassword),
  webapp2.Route('/admin/feedback', admin.FeedbackList),

  webapp2.Route('/oauth/fb', views.FbRedirect),
  webapp2.Route('/www', views.WebServer),
  webapp2.Route('/index.html', views.WebServer),
  RedirectRoute('/admin/cleanup_votes', redirect_to='/migrate_datastore?no=12'),

]