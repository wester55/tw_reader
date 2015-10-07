from __future__ import absolute_import, print_function

# Go to http://apps.twitter.com and create an app.
# The consumer key and secret will be generated for you after
import json
import mimetypes
from urlparse import parse_qs
import six
import requests
from requests_oauthlib import OAuth1Session, OAuth1

consumer_key="ngyEI20AOXmNDuKA0s1J5Gt2l"
consumer_secret="LzzPeoF5EipYsMwnO5uC1u7pKVrHDatERb9CBTjDJX1dZKcRX7"

# After the step above, you will be redirected to your app's page.
# Create an access token under the the "Your access token" section
access_token="15629921-O5zGhOvfB6w20xjmcDZMcudwzLVG5qn7ckjPqH97Y"
access_token_secret="HdndTCcaPt1bDunZXDwDexMmpbOBkrlGa2zr5hgTXJjyL"

STREAM_VERSION = '1.1'

class Parser(object):

    def parse(self, method, payload):
        """
        Parse the response payload and return the result.
        Returns a tuple that contains the result data and the cursors
        (or None if not present).
        """
        raise NotImplementedError

    def parse_error(self, payload):
        """
        Parse the error message from payload.
        If unable to parse the message, throw an exception
        and default error message will be used.
        """
        raise NotImplementedError


class RawParser(Parser):

    def __init__(self):
        pass

    def parse(self, method, payload):
        return payload

    def parse_error(self, payload):
        return payload


class JSONParser(Parser):

    payload_format = 'json'

    def __init__(self):
        self.json_lib = import_simplejson()

    def parse(self, method, payload):
        try:
            json = self.json_lib.loads(payload)
        except Exception as e:
            raise TweepError('Failed to parse JSON payload: %s' % e)

        needs_cursors = 'cursor' in method.session.params
        if needs_cursors and isinstance(json, dict):
            if 'previous_cursor' in json:
                if 'next_cursor' in json:
                    cursors = json['previous_cursor'], json['next_cursor']
                    return json, cursors
        else:
            return json

    def parse_error(self, payload):
        error = self.json_lib.loads(payload)
        if error.has_key('error'):
            return error['error']
        else:
            return error['errors']


class ModelParser(JSONParser):

    def __init__(self, model_factory=None):
        JSONParser.__init__(self)
        self.model_factory = model_factory or ModelFactory

    def parse(self, method, payload):
        try:
            if method.payload_type is None:
                return
            model = getattr(self.model_factory, method.payload_type)
        except AttributeError:
            raise TweepError('No model for this payload type: '
                             '%s' % method.payload_type)

        json = JSONParser.parse(self, method, payload)
        if isinstance(json, tuple):
            json, cursors = json
        else:
            cursors = None

        if method.payload_list:
            result = model.parse_list(method.api, json)
        else:
            result = model.parse(method.api, json)

        if cursors:
            return result, cursors
        else:
            return result

class API(object):
    """Twitter API"""

    def __init__(self, auth_handler=None,
                 host='api.twitter.com', search_host='search.twitter.com',
                 upload_host='upload.twitter.com', cache=None, api_root='/1.1',
                 search_root='', upload_root='/1.1', retry_count=0,
                 retry_delay=0, retry_errors=None, timeout=60, parser=None,
                 compression=False, wait_on_rate_limit=False,
                 wait_on_rate_limit_notify=False, proxy=''):
        """ Api instance Constructor

        :param auth_handler:
        :param host:  url of the server of the rest api, default:'api.twitter.com'
        :param search_host: url of the search server, default:'search.twitter.com'
        :param upload_host: url of the upload server, default:'upload.twitter.com'
        :param cache: Cache to query if a GET method is used, default:None
        :param api_root: suffix of the api version, default:'/1.1'
        :param search_root: suffix of the search version, default:''
        :param upload_root: suffix of the upload version, default:'/1.1'
        :param retry_count: number of allowed retries, default:0
        :param retry_delay: delay in second between retries, default:0
        :param retry_errors: default:None
        :param timeout: delay before to consider the request as timed out in seconds, default:60
        :param parser: ModelParser instance to parse the responses, default:None
        :param compression: If the response is compressed, default:False
        :param wait_on_rate_limit: If the api wait when it hits the rate limit, default:False
        :param wait_on_rate_limit_notify: If the api print a notification when the rate limit is hit, default:False
        :param proxy: Url to use as proxy during the HTTP request, default:''

        :raise TypeError: If the given parser is not a ModelParser instance.
        """
        self.auth = auth_handler
        self.host = host
        self.search_host = search_host
        self.upload_host = upload_host
        self.api_root = api_root
        self.search_root = search_root
        self.upload_root = upload_root
        self.cache = cache
        self.compression = compression
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.retry_errors = retry_errors
        self.timeout = timeout
        self.wait_on_rate_limit = wait_on_rate_limit
        self.wait_on_rate_limit_notify = wait_on_rate_limit_notify
        self.parser = parser or ModelParser()
        self.proxy = {}
        if proxy:
            self.proxy['https'] = proxy

        # Attempt to explain more clearly the parser argument requirements
        # https://github.com/tweepy/tweepy/issues/421
        #
        parser_type = Parser
        if not isinstance(self.parser, parser_type):
            raise TypeError(
                '"parser" argument has to be an instance of "{required}".'
                ' It is currently a {actual}.'.format(
                    required=parser_type.__name__,
                    actual=type(self.parser)
                )
            )

    @property
    def home_timeline(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/home_timeline
            :allowed_param:'since_id', 'max_id', 'count'
        """
        return bind_api(
            api=self,
            path='/statuses/home_timeline.json',
            payload_type='status', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count'],
            require_auth=True
        )

    def statuses_lookup(self, id_, include_entities=None,
                        trim_user=None, map_=None):
        return self._statuses_lookup(list_to_csv(id_), include_entities,
                                     trim_user, map_)

    @property
    def _statuses_lookup(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/lookup
            :allowed_param:'id', 'include_entities', 'trim_user', 'map'
        """
        return bind_api(
            api=self,
            path='/statuses/lookup.json',
            payload_type='status', payload_list=True,
            allowed_param=['id', 'include_entities', 'trim_user', 'map'],
            require_auth=True
        )

    @property
    def user_timeline(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/user_timeline
            :allowed_param:'id', 'user_id', 'screen_name', 'since_id'
        """
        return bind_api(
            api=self,
            path='/statuses/user_timeline.json',
            payload_type='status', payload_list=True,
            allowed_param=['id', 'user_id', 'screen_name', 'since_id',
                           'max_id', 'count', 'include_rts']
        )

    @property
    def mentions_timeline(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/mentions_timeline
            :allowed_param:'since_id', 'max_id', 'count'
        """
        return bind_api(
            api=self,
            path='/statuses/mentions_timeline.json',
            payload_type='status', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count'],
            require_auth=True
        )

    @property
    def related_results(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/related_results/show/%3id.format
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/related_results/show/{id}.json',
            payload_type='relation', payload_list=True,
            allowed_param=['id'],
            require_auth=False
        )

    @property
    def retweets_of_me(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/retweets_of_me
            :allowed_param:'since_id', 'max_id', 'count'
        """
        return bind_api(
            api=self,
            path='/statuses/retweets_of_me.json',
            payload_type='status', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count'],
            require_auth=True
        )

    @property
    def get_status(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/show/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/statuses/show.json',
            payload_type='status',
            allowed_param=['id']
        )

    def update_status(self, media_ids=None, *args, **kwargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/statuses/update
            :allowed_param:'status', 'in_reply_to_status_id', 'lat', 'long', 'source', 'place_id', 'display_coordinates', 'media_ids'
        """
        post_data = {}
        if media_ids is not None:
            post_data["media_ids"] = list_to_csv(media_ids)

        return bind_api(
            api=self,
            path='/statuses/update.json',
            method='POST',
            payload_type='status',
            allowed_param=['status', 'in_reply_to_status_id', 'lat', 'long', 'source', 'place_id', 'display_coordinates'],
            require_auth=True
        )(post_data=post_data, *args, **kwargs)

    def media_upload(self, filename, *args, **kwargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/media/upload
            :allowed_param:
        """
        f = kwargs.pop('file', None)
        headers, post_data = API._pack_image(filename, 3072, form_field='media', f=f)
        kwargs.update({'headers': headers, 'post_data': post_data})

        return bind_api(
            api=self,
            path='/media/upload.json',
            method='POST',
            payload_type='media',
            allowed_param=[],
            require_auth=True,
            upload_api=True
        )(*args, **kwargs)

    def update_with_media(self, filename, *args, **kwargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/statuses/update_with_media
            :allowed_param:'status', 'possibly_sensitive', 'in_reply_to_status_id', 'lat', 'long', 'place_id', 'display_coordinates'
        """
        f = kwargs.pop('file', None)
        headers, post_data = API._pack_image(filename, 3072, form_field='media[]', f=f)
        kwargs.update({'headers': headers, 'post_data': post_data})

        return bind_api(
            api=self,
            path='/statuses/update_with_media.json',
            method='POST',
            payload_type='status',
            allowed_param=[
                'status', 'possibly_sensitive', 'in_reply_to_status_id', 'lat', 'long',
                'place_id', 'display_coordinates'
            ],
            require_auth=True
        )(*args, **kwargs)

    @property
    def destroy_status(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/statuses/destroy/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/statuses/destroy/{id}.json',
            method='POST',
            payload_type='status',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def retweet(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/statuses/retweet/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/statuses/retweet/{id}.json',
            method='POST',
            payload_type='status',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def retweets(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/retweets/%3Aid
            :allowed_param:'id', 'count'
        """
        return bind_api(
            api=self,
            path='/statuses/retweets/{id}.json',
            payload_type='status', payload_list=True,
            allowed_param=['id', 'count'],
            require_auth=True
        )

    @property
    def retweeters(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/retweeters/ids
            :allowed_param:'id', 'cursor', 'stringify_ids
        """
        return bind_api(
            api=self,
            path='/statuses/retweeters/ids.json',
            payload_type='ids',
            allowed_param=['id', 'cursor', 'stringify_ids']
        )

    @property
    def get_user(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/show
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/users/show.json',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name']
        )

    @property
    def get_oembed(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/oembed
            :allowed_param:'id', 'url', 'maxwidth', 'hide_media', 'omit_script', 'align', 'related', 'lang'
        """
        return bind_api(
            api=self,
            path='/statuses/oembed.json',
            payload_type='json',
            allowed_param=['id', 'url', 'maxwidth', 'hide_media', 'omit_script', 'align', 'related', 'lang']
        )

    def lookup_users(self, user_ids=None, screen_names=None, include_entities=None):
        """ Perform bulk look up of users from user ID or screenname """
        post_data = {}
        if include_entities is not None:
            include_entities = 'true' if include_entities else 'false'
            post_data['include_entities'] = include_entities
        if user_ids:
            post_data['user_id'] = list_to_csv(user_ids)
        if screen_names:
            post_data['screen_name'] = list_to_csv(screen_names)

        return self._lookup_users(post_data=post_data)

    @property
    def _lookup_users(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/lookup
            allowed_param='user_id', 'screen_name', 'include_entities'
        """
        return bind_api(
            api=self,
            path='/users/lookup.json',
            payload_type='user', payload_list=True,
            method='POST',
        )

    def me(self):
        """ Get the authenticated user """
        return self.get_user(screen_name=self.auth.get_username())

    @property
    def search_users(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/search
            :allowed_param:'q', 'count', 'page'
        """
        return bind_api(
            api=self,
            path='/users/search.json',
            payload_type='user', payload_list=True,
            require_auth=True,
            allowed_param=['q', 'count', 'page']
        )

    @property
    def suggested_users(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/suggestions/%3Aslug
            :allowed_param:'slug', 'lang'
        """
        return bind_api(
            api=self,
            path='/users/suggestions/{slug}.json',
            payload_type='user', payload_list=True,
            require_auth=True,
            allowed_param=['slug', 'lang']
        )

    @property
    def suggested_categories(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/suggestions
            :allowed_param:'lang'
        """
        return bind_api(
            api=self,
            path='/users/suggestions.json',
            payload_type='category', payload_list=True,
            allowed_param=['lang'],
            require_auth=True
        )

    @property
    def suggested_users_tweets(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/suggestions/%3Aslug/members
            :allowed_param:'slug'
        """
        return bind_api(
            api=self,
            path='/users/suggestions/{slug}/members.json',
            payload_type='status', payload_list=True,
            allowed_param=['slug'],
            require_auth=True
        )

    @property
    def direct_messages(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/direct_messages
            :allowed_param:'since_id', 'max_id', 'count'
        """
        return bind_api(
            api=self,
            path='/direct_messages.json',
            payload_type='direct_message', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count'],
            require_auth=True
        )

    @property
    def get_direct_message(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/direct_messages/show
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/direct_messages/show/{id}.json',
            payload_type='direct_message',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def sent_direct_messages(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/direct_messages/sent
            :allowed_param:'since_id', 'max_id', 'count', 'page'
        """
        return bind_api(
            api=self,
            path='/direct_messages/sent.json',
            payload_type='direct_message', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count', 'page'],
            require_auth=True
        )

    @property
    def send_direct_message(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/direct_messages/new
            :allowed_param:'user', 'screen_name', 'user_id', 'text'
        """
        return bind_api(
            api=self,
            path='/direct_messages/new.json',
            method='POST',
            payload_type='direct_message',
            allowed_param=['user', 'screen_name', 'user_id', 'text'],
            require_auth=True
        )

    @property
    def destroy_direct_message(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/direct_messages/destroy
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/direct_messages/destroy.json',
            method='POST',
            payload_type='direct_message',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def create_friendship(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/friendships/create
            :allowed_param:'id', 'user_id', 'screen_name', 'follow'
        """
        return bind_api(
            api=self,
            path='/friendships/create.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name', 'follow'],
            require_auth=True
        )

    @property
    def destroy_friendship(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/friendships/destroy
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/friendships/destroy.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def show_friendship(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friendships/show
            :allowed_param:'source_id', 'source_screen_name'
        """
        return bind_api(
            api=self,
            path='/friendships/show.json',
            payload_type='friendship',
            allowed_param=['source_id', 'source_screen_name',
                           'target_id', 'target_screen_name']
        )

    def lookup_friendships(self, user_ids=None, screen_names=None):
        """ Perform bulk look up of friendships from user ID or screenname """
        return self._lookup_friendships(list_to_csv(user_ids), list_to_csv(screen_names))

    @property
    def _lookup_friendships(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friendships/lookup
            :allowed_param:'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/friendships/lookup.json',
            payload_type='relationship', payload_list=True,
            allowed_param=['user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def friends_ids(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friends/ids
            :allowed_param:'id', 'user_id', 'screen_name', 'cursor'
        """
        return bind_api(
            api=self,
            path='/friends/ids.json',
            payload_type='ids',
            allowed_param=['id', 'user_id', 'screen_name', 'cursor']
        )

    @property
    def friends(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friends/list
            :allowed_param:'id', 'user_id', 'screen_name', 'cursor', 'skip_status', 'include_user_entities'
        """
        return bind_api(
            api=self,
            path='/friends/list.json',
            payload_type='user', payload_list=True,
            allowed_param=['id', 'user_id', 'screen_name', 'cursor', 'skip_status', 'include_user_entities']
        )

    @property
    def friendships_incoming(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friendships/incoming
            :allowed_param:'cursor'
        """
        return bind_api(
            api=self,
            path='/friendships/incoming.json',
            payload_type='ids',
            allowed_param=['cursor']
        )

    @property
    def friendships_outgoing(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friendships/outgoing
            :allowed_param:'cursor'
        """
        return bind_api(
            api=self,
            path='/friendships/outgoing.json',
            payload_type='ids',
            allowed_param=['cursor']
        )

    @property
    def followers_ids(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/followers/ids
            :allowed_param:'id', 'user_id', 'screen_name', 'cursor', 'count'
        """
        return bind_api(
            api=self,
            path='/followers/ids.json',
            payload_type='ids',
            allowed_param=['id', 'user_id', 'screen_name', 'cursor', 'count']
        )

    @property
    def followers(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/followers/list
            :allowed_param:'id', 'user_id', 'screen_name', 'cursor', 'count', 'skip_status', 'include_user_entities'
        """
        return bind_api(
            api=self,
            path='/followers/list.json',
            payload_type='user', payload_list=True,
            allowed_param=['id', 'user_id', 'screen_name', 'cursor', 'count',
                           'skip_status', 'include_user_entities']
        )

    @property
    def get_settings(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/account/settings
        """
        return bind_api(
            api=self,
            path='/account/settings.json',
            payload_type='json',
            use_cache=False
        )

    @property
    def set_settings(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/settings
            :allowed_param:'sleep_time_enabled', 'start_sleep_time',
            'end_sleep_time', 'time_zone', 'trend_location_woeid',
            'allow_contributor_request', 'lang'
        """
        return bind_api(
            api=self,
            path='/account/settings.json',
            method='POST',
            payload_type='json',
            allowed_param=['sleep_time_enabled', 'start_sleep_time',
                           'end_sleep_time', 'time_zone',
                           'trend_location_woeid', 'allow_contributor_request',
                           'lang'],
            use_cache=False
        )

    def verify_credentials(self, **kargs):
        """ :reference: https://dev.twitter.com/rest/reference/get/account/verify_credentials
            :allowed_param:'include_entities', 'skip_status', 'include_email'
        """
        try:
            return bind_api(
                api=self,
                path='/account/verify_credentials.json',
                payload_type='user',
                require_auth=True,
                allowed_param=['include_entities', 'skip_status', 'include_email'],
            )(**kargs)
        except TweepError as e:
            if e.response and e.response.status == 401:
                return False
            raise

    @property
    def rate_limit_status(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/application/rate_limit_status
            :allowed_param:'resources'
        """
        return bind_api(
            api=self,
            path='/application/rate_limit_status.json',
            payload_type='json',
            allowed_param=['resources'],
            use_cache=False
        )

    @property
    def set_delivery_device(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_delivery_device
            :allowed_param:'device'
        """
        return bind_api(
            api=self,
            path='/account/update_delivery_device.json',
            method='POST',
            allowed_param=['device'],
            payload_type='user',
            require_auth=True
        )

    @property
    def update_profile_colors(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/account/update_profile_colors
            :allowed_param:'profile_background_color', 'profile_text_color',
             'profile_link_color', 'profile_sidebar_fill_color',
             'profile_sidebar_border_color'],
        """
        return bind_api(
            api=self,
            path='/account/update_profile_colors.json',
            method='POST',
            payload_type='user',
            allowed_param=['profile_background_color', 'profile_text_color',
                           'profile_link_color', 'profile_sidebar_fill_color',
                           'profile_sidebar_border_color'],
            require_auth=True
        )

    def update_profile_image(self, filename, file_=None):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_profile_image
            :allowed_param:'include_entities', 'skip_status'
        """
        headers, post_data = API._pack_image(filename, 700, f=file_)
        return bind_api(
            api=self,
            path='/account/update_profile_image.json',
            method='POST',
            payload_type='user',
            allowed_param=['include_entities', 'skip_status'],
            require_auth=True
        )(self, post_data=post_data, headers=headers)

    def update_profile_background_image(self, filename, **kargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_profile_background_image
            :allowed_param:'tile', 'include_entities', 'skip_status', 'use'
        """
        f = kargs.pop('file', None)
        headers, post_data = API._pack_image(filename, 800, f=f)
        bind_api(
            api=self,
            path='/account/update_profile_background_image.json',
            method='POST',
            payload_type='user',
            allowed_param=['tile', 'include_entities', 'skip_status', 'use'],
            require_auth=True
        )(post_data=post_data, headers=headers)

    def update_profile_banner(self, filename, **kargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_profile_banner
            :allowed_param:'width', 'height', 'offset_left', 'offset_right'
        """
        f = kargs.pop('file', None)
        headers, post_data = API._pack_image(filename, 700, form_field="banner", f=f)
        bind_api(
            api=self,
            path='/account/update_profile_banner.json',
            method='POST',
            allowed_param=['width', 'height', 'offset_left', 'offset_right'],
            require_auth=True
        )(post_data=post_data, headers=headers)

    @property
    def update_profile(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_profile
            :allowed_param:'name', 'url', 'location', 'description'
        """
        return bind_api(
            api=self,
            path='/account/update_profile.json',
            method='POST',
            payload_type='user',
            allowed_param=['name', 'url', 'location', 'description'],
            require_auth=True
        )

    @property
    def favorites(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/favorites/list
            :allowed_param:'screen_name', 'user_id', 'max_id', 'count', 'since_id', 'max_id'
        """
        return bind_api(
            api=self,
            path='/favorites/list.json',
            payload_type='status', payload_list=True,
            allowed_param=['screen_name', 'user_id', 'max_id', 'count', 'since_id', 'max_id']
        )

    @property
    def create_favorite(self):
        """ :reference:https://dev.twitter.com/rest/reference/post/favorites/create
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/favorites/create.json',
            method='POST',
            payload_type='status',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def destroy_favorite(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/favorites/destroy
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/favorites/destroy.json',
            method='POST',
            payload_type='status',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def create_block(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/blocks/create
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/blocks/create.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def destroy_block(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/blocks/destroy
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/blocks/destroy.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def blocks(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/blocks/list
            :allowed_param:'cursor'
        """
        return bind_api(
            api=self,
            path='/blocks/list.json',
            payload_type='user', payload_list=True,
            allowed_param=['cursor'],
            require_auth=True
        )

    @property
    def blocks_ids(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/blocks/ids """
        return bind_api(
            api=self,
            path='/blocks/ids.json',
            payload_type='json',
            require_auth=True
        )

    @property
    def report_spam(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/users/report_spam
            :allowed_param:'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/users/report_spam.json',
            method='POST',
            payload_type='user',
            allowed_param=['user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def saved_searches(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/saved_searches/show/%3Aid """
        return bind_api(
            api=self,
            path='/saved_searches/list.json',
            payload_type='saved_search', payload_list=True,
            require_auth=True
        )

    @property
    def get_saved_search(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/saved_searches/show/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/saved_searches/show/{id}.json',
            payload_type='saved_search',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def create_saved_search(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/saved_searches/create
            :allowed_param:'query'
        """
        return bind_api(
            api=self,
            path='/saved_searches/create.json',
            method='POST',
            payload_type='saved_search',
            allowed_param=['query'],
            require_auth=True
        )

    @property
    def destroy_saved_search(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/saved_searches/destroy/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/saved_searches/destroy/{id}.json',
            method='POST',
            payload_type='saved_search',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def create_list(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/lists/create
            :allowed_param:'name', 'mode', 'description'
        """
        return bind_api(
            api=self,
            path='/lists/create.json',
            method='POST',
            payload_type='list',
            allowed_param=['name', 'mode', 'description'],
            require_auth=True
        )

    @property
    def destroy_list(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/lists/destroy
            :allowed_param:'owner_screen_name', 'owner_id', 'list_id', 'slug'
        """
        return bind_api(
            api=self,
            path='/lists/destroy.json',
            method='POST',
            payload_type='list',
            allowed_param=['owner_screen_name', 'owner_id', 'list_id', 'slug'],
            require_auth=True
        )

    @property
    def update_list(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/lists/update
            :allowed_param: list_id', 'slug', 'name', 'mode', 'description', 'owner_screen_name', 'owner_id'
        """
        return bind_api(
            api=self,
            path='/lists/update.json',
            method='POST',
            payload_type='list',
            allowed_param=['list_id', 'slug', 'name', 'mode', 'description', 'owner_screen_name', 'owner_id'],
            require_auth=True
        )

    @property
    def lists_all(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/lists/list
            :allowed_param:'screen_name', 'user_id'
        """
        return bind_api(
            api=self,
            path='/lists/list.json',
            payload_type='list', payload_list=True,
            allowed_param=['screen_name', 'user_id'],
            require_auth=True
        )

    @property
    def lists_memberships(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/lists/memberships
            :allowed_param:'screen_name', 'user_id', 'filter_to_owned_lists', 'cursor'
        """
        return bind_api(
            api=self,
            path='/lists/memberships.json',
            payload_type='list', payload_list=True,
            allowed_param=['screen_name', 'user_id', 'filter_to_owned_lists', 'cursor'],
            require_auth=True
        )

    @property
    def lists_subscriptions(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/lists/subscriptions
            :allowed_param:'screen_name', 'user_id', 'cursor'
        """
        return bind_api(
            api=self,
            path='/lists/subscriptions.json',
            payload_type='list', payload_list=True,
            allowed_param=['screen_name', 'user_id', 'cursor'],
            require_auth=True
        )

    @property
    def list_timeline(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/statuses
            :allowed_param:'owner_screen_name', 'slug', 'owner_id', 'list_id',
             'since_id', 'max_id', 'count', 'include_rts
        """
        return bind_api(
            api=self,
            path='/lists/statuses.json',
            payload_type='status', payload_list=True,
            allowed_param=['owner_screen_name', 'slug', 'owner_id',
                           'list_id', 'since_id', 'max_id', 'count',
                           'include_rts']
        )

    @property
    def get_list(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/lists/show
            :allowed_param:'owner_screen_name', 'owner_id', 'slug', 'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/show.json',
            payload_type='list',
            allowed_param=['owner_screen_name', 'owner_id', 'slug', 'list_id']
        )

    @property
    def add_list_member(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/members/create
            :allowed_param:'screen_name', 'user_id', 'owner_screen_name',
             'owner_id', 'slug', 'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/members/create.json',
            method='POST',
            payload_type='list',
            allowed_param=['screen_name', 'user_id', 'owner_screen_name',
                           'owner_id', 'slug', 'list_id'],
            require_auth=True
        )

    @property
    def remove_list_member(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/members/destroy
            :allowed_param:'screen_name', 'user_id', 'owner_screen_name',
             'owner_id', 'slug', 'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/members/destroy.json',
            method='POST',
            payload_type='list',
            allowed_param=['screen_name', 'user_id', 'owner_screen_name',
                           'owner_id', 'slug', 'list_id'],
            require_auth=True
        )

    def add_list_members(self, screen_name=None, user_id=None, slug=None,
                         list_id=None, owner_id=None, owner_screen_name=None):
        """ Perform bulk add of list members from user ID or screenname """
        return self._add_list_members(list_to_csv(screen_name),
                                      list_to_csv(user_id),
                                      slug, list_id, owner_id,
                                      owner_screen_name)

    @property
    def _add_list_members(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/members/create_all
            :allowed_param:'screen_name', 'user_id', 'slug', 'list_id',
            'owner_id', 'owner_screen_name'

        """
        return bind_api(
            api=self,
            path='/lists/members/create_all.json',
            method='POST',
            payload_type='list',
            allowed_param=['screen_name', 'user_id', 'slug', 'list_id',
                           'owner_id', 'owner_screen_name'],
            require_auth=True
        )

    def remove_list_members(self, screen_name=None, user_id=None, slug=None,
                            list_id=None, owner_id=None, owner_screen_name=None):
        """ Perform bulk remove of list members from user ID or screenname """
        return self._remove_list_members(list_to_csv(screen_name),
                                         list_to_csv(user_id),
                                         slug, list_id, owner_id,
                                         owner_screen_name)

    @property
    def _remove_list_members(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/members/destroy_all
            :allowed_param:'screen_name', 'user_id', 'slug', 'list_id',
            'owner_id', 'owner_screen_name'

        """
        return bind_api(
            api=self,
            path='/lists/members/destroy_all.json',
            method='POST',
            payload_type='list',
            allowed_param=['screen_name', 'user_id', 'slug', 'list_id',
                           'owner_id', 'owner_screen_name'],
            require_auth=True
        )

    @property
    def list_members(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/members
            :allowed_param:'owner_screen_name', 'slug', 'list_id',
             'owner_id', 'cursor
        """
        return bind_api(
            api=self,
            path='/lists/members.json',
            payload_type='user', payload_list=True,
            allowed_param=['owner_screen_name', 'slug', 'list_id',
                           'owner_id', 'cursor']
        )

    @property
    def show_list_member(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/members/show
            :allowed_param:'list_id', 'slug', 'user_id', 'screen_name',
             'owner_screen_name', 'owner_id
        """
        return bind_api(
            api=self,
            path='/lists/members/show.json',
            payload_type='user',
            allowed_param=['list_id', 'slug', 'user_id', 'screen_name',
                           'owner_screen_name', 'owner_id']
        )

    @property
    def subscribe_list(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/subscribers/create
            :allowed_param:'owner_screen_name', 'slug', 'owner_id',
            'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/subscribers/create.json',
            method='POST',
            payload_type='list',
            allowed_param=['owner_screen_name', 'slug', 'owner_id',
                           'list_id'],
            require_auth=True
        )

    @property
    def unsubscribe_list(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/subscribers/destroy
            :allowed_param:'owner_screen_name', 'slug', 'owner_id',
            'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/subscribers/destroy.json',
            method='POST',
            payload_type='list',
            allowed_param=['owner_screen_name', 'slug', 'owner_id',
                           'list_id'],
            require_auth=True
        )

    @property
    def list_subscribers(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/subscribers
            :allowed_param:'owner_screen_name', 'slug', 'owner_id',
             'list_id', 'cursor
        """
        return bind_api(
            api=self,
            path='/lists/subscribers.json',
            payload_type='user', payload_list=True,
            allowed_param=['owner_screen_name', 'slug', 'owner_id',
                           'list_id', 'cursor']
        )

    @property
    def show_list_subscriber(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/subscribers/show
            :allowed_param:'owner_screen_name', 'slug', 'screen_name',
             'owner_id', 'list_id', 'user_id
        """
        return bind_api(
            api=self,
            path='/lists/subscribers/show.json',
            payload_type='user',
            allowed_param=['owner_screen_name', 'slug', 'screen_name',
                           'owner_id', 'list_id', 'user_id']
        )

    @property
    def trends_available(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/trends/available """
        return bind_api(
            api=self,
            path='/trends/available.json',
            payload_type='json'
        )

    @property
    def trends_place(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/trends/place
            :allowed_param:'id', 'exclude'
        """
        return bind_api(
            api=self,
            path='/trends/place.json',
            payload_type='json',
            allowed_param=['id', 'exclude']
        )

    @property
    def trends_closest(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/trends/closest
            :allowed_param:'lat', 'long'
        """
        return bind_api(
            api=self,
            path='/trends/closest.json',
            payload_type='json',
            allowed_param=['lat', 'long']
        )

    @property
    def search(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/search/tweets
            :allowed_param:'q', 'lang', 'locale', 'since_id', 'geocode',
             'max_id', 'since', 'until', 'result_type', 'count',
              'include_entities', 'from', 'to', 'source']
        """
        return bind_api(
            api=self,
            path='/search/tweets.json',
            payload_type='search_results',
            allowed_param=['q', 'lang', 'locale', 'since_id', 'geocode',
                           'max_id', 'since', 'until', 'result_type',
                           'count', 'include_entities', 'from',
                           'to', 'source']
        )

    @property
    def reverse_geocode(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/geo/reverse_geocode
            :allowed_param:'lat', 'long', 'accuracy', 'granularity', 'max_results'
        """
        return bind_api(
            api=self,
            path='/geo/reverse_geocode.json',
            payload_type='place', payload_list=True,
            allowed_param=['lat', 'long', 'accuracy', 'granularity',
                           'max_results']
        )

    @property
    def geo_id(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/geo/id/%3Aplace_id
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/geo/id/{id}.json',
            payload_type='place',
            allowed_param=['id']
        )

    @property
    def geo_search(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/geo/search
            :allowed_param:'lat', 'long', 'query', 'ip', 'granularity',
             'accuracy', 'max_results', 'contained_within

        """
        return bind_api(
            api=self,
            path='/geo/search.json',
            payload_type='place', payload_list=True,
            allowed_param=['lat', 'long', 'query', 'ip', 'granularity',
                           'accuracy', 'max_results', 'contained_within']
        )

    @property
    def geo_similar_places(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/geo/similar_places
            :allowed_param:'lat', 'long', 'name', 'contained_within'
        """
        return bind_api(
            api=self,
            path='/geo/similar_places.json',
            payload_type='place', payload_list=True,
            allowed_param=['lat', 'long', 'name', 'contained_within']
        )

    @property
    def supported_languages(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/help/languages """
        return bind_api(
            api=self,
            path='/help/languages.json',
            payload_type='json',
            require_auth=True
        )

    @property
    def configuration(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/help/configuration """
        return bind_api(
            api=self,
            path='/help/configuration.json',
            payload_type='json',
            require_auth=True
        )

    """ Internal use only """

    @staticmethod
    def _pack_image(filename, max_size, form_field="image", f=None):
        """Pack image from file into multipart-formdata post body"""
        # image must be less than 700kb in size
        if f is None:
            try:
                if os.path.getsize(filename) > (max_size * 1024):
                    raise TweepError('File is too big, must be less than %skb.' % max_size)
            except os.error as e:
                raise TweepError('Unable to access file: %s' % e.strerror)

            # build the mulitpart-formdata body
            fp = open(filename, 'rb')
        else:
            f.seek(0, 2)  # Seek to end of file
            if f.tell() > (max_size * 1024):
                raise TweepError('File is too big, must be less than %skb.' % max_size)
            f.seek(0)  # Reset to beginning of file
            fp = f

        # image must be gif, jpeg, or png
        file_type = mimetypes.guess_type(filename)
        if file_type is None:
            raise TweepError('Could not determine file type')
        file_type = file_type[0]
        if file_type not in ['image/gif', 'image/jpeg', 'image/png']:
            raise TweepError('Invalid file type for image: %s' % file_type)

        if isinstance(filename, six.text_type):
            filename = filename.encode("utf-8")

        BOUNDARY = b'Tw3ePy'
        body = list()
        body.append(b'--' + BOUNDARY)
        body.append('Content-Disposition: form-data; name="{0}";'
                    ' filename="{1}"'.format(form_field, filename)
                    .encode('utf-8'))
        body.append('Content-Type: {0}'.format(file_type).encode('utf-8'))
        body.append(b'')
        body.append(fp.read())
        body.append(b'--' + BOUNDARY + b'--')
        body.append(b'')
        fp.close()
        body = b'\r\n'.join(body)

        # build headers
        headers = {
            'Content-Type': 'multipart/form-data; boundary=Tw3ePy',
            'Content-Length': str(len(body))
        }

        return headers, body

class StreamListener(object):

    def __init__(self, api=None):
        self.api = api or API()

    def on_connect(self):
        """Called once connected to streaming server.

        This will be invoked once a successful response
        is received from the server. Allows the listener
        to perform some work prior to entering the read loop.
        """
        pass

    def on_data(self, raw_data):
        """Called when raw data is received from connection.

        Override this method if you wish to manually handle
        the stream data. Return False to stop stream and close connection.
        """
        data = json.loads(raw_data)

        if 'in_reply_to_status_id' in data:
            status = Status.parse(self.api, data)
            if self.on_status(status) is False:
                return False
        elif 'delete' in data:
            delete = data['delete']['status']
            if self.on_delete(delete['id'], delete['user_id']) is False:
                return False
        elif 'event' in data:
            status = Status.parse(self.api, data)
            if self.on_event(status) is False:
                return False
        elif 'direct_message' in data:
            status = Status.parse(self.api, data)
            if self.on_direct_message(status) is False:
                return False
        elif 'friends' in data:
            if self.on_friends(data['friends']) is False:
                return False
        elif 'limit' in data:
            if self.on_limit(data['limit']['track']) is False:
                return False
        elif 'disconnect' in data:
            if self.on_disconnect(data['disconnect']) is False:
                return False
        elif 'warning' in data:
            if self.on_warning(data['warning']) is False:
                return False
        else:
            logging.error("Unknown message type: " + str(raw_data))

    def keep_alive(self):
        """Called when a keep-alive arrived"""
        return

    def on_status(self, status):
        """Called when a new status arrives"""
        return

    def on_exception(self, exception):
        """Called when an unhandled exception occurs."""
        return

    def on_delete(self, status_id, user_id):
        """Called when a delete notice arrives for a status"""
        return

    def on_event(self, status):
        """Called when a new event arrives"""
        return

    def on_direct_message(self, status):
        """Called when a new direct message arrives"""
        return

    def on_friends(self, friends):
        """Called when a friends list arrives.

        friends is a list that contains user_id
        """
        return

    def on_limit(self, track):
        """Called when a limitation notice arrives"""
        return

    def on_error(self, status_code):
        """Called when a non-200 status code is returned"""
        return False

    def on_timeout(self):
        """Called when stream connection times out"""
        return

    def on_disconnect(self, notice):
        """Called when twitter sends a disconnect notice

        Disconnect codes are listed here:
        https://dev.twitter.com/docs/streaming-apis/messages#Disconnect_messages_disconnect
        """
        return

    def on_warning(self, notice):
        """Called when a disconnection warning message arrives"""
        return

class Stream(object):

    host = 'stream.twitter.com'

    def __init__(self, auth, listener, **options):
        self.auth = auth
        self.listener = listener
        self.running = False
        self.timeout = options.get("timeout", 300.0)
        self.retry_count = options.get("retry_count")
        # values according to
        # https://dev.twitter.com/docs/streaming-apis/connecting#Reconnecting
        self.retry_time_start = options.get("retry_time", 5.0)
        self.retry_420_start = options.get("retry_420", 60.0)
        self.retry_time_cap = options.get("retry_time_cap", 320.0)
        self.snooze_time_step = options.get("snooze_time", 0.25)
        self.snooze_time_cap = options.get("snooze_time_cap", 16)

        # The default socket.read size. Default to less than half the size of
        # a tweet so that it reads tweets with the minimal latency of 2 reads
        # per tweet. Values higher than ~1kb will increase latency by waiting
        # for more data to arrive but may also increase throughput by doing
        # fewer socket read calls.
        self.chunk_size = options.get("chunk_size",  512)

        self.verify = options.get("verify", True)

        self.api = API()
        self.headers = options.get("headers") or {}
        self.new_session()
        self.body = None
        self.retry_time = self.retry_time_start
        self.snooze_time = self.snooze_time_step

    def new_session(self):
        self.session = requests.Session()
        self.session.headers = self.headers
        self.session.params = None

    def _run(self):
        # Authenticate
        url = "https://%s%s" % (self.host, self.url)

        # Connect and process the stream
        error_counter = 0
        resp = None
        exception = None
        while self.running:
            if self.retry_count is not None:
                if error_counter > self.retry_count:
                    # quit if error count greater than retry count
                    break
            try:
                auth = self.auth.apply_auth()
                resp = self.session.request('POST',
                                            url,
                                            data=self.body,
                                            timeout=self.timeout,
                                            stream=True,
                                            auth=auth,
                                            verify=self.verify)
                if resp.status_code != 200:
                    if self.listener.on_error(resp.status_code) is False:
                        break
                    error_counter += 1
                    if resp.status_code == 420:
                        self.retry_time = max(self.retry_420_start,
                                              self.retry_time)
                    sleep(self.retry_time)
                    self.retry_time = min(self.retry_time * 2,
                                          self.retry_time_cap)
                else:
                    error_counter = 0
                    self.retry_time = self.retry_time_start
                    self.snooze_time = self.snooze_time_step
                    self.listener.on_connect()
                    self._read_loop(resp)
            except (Timeout, ssl.SSLError) as exc:
                # This is still necessary, as a SSLError can actually be
                # thrown when using Requests
                # If it's not time out treat it like any other exception
                if isinstance(exc, ssl.SSLError):
                    if not (exc.args and 'timed out' in str(exc.args[0])):
                        exception = exc
                        break
                if self.listener.on_timeout() is False:
                    break
                if self.running is False:
                    break
                sleep(self.snooze_time)
                self.snooze_time = min(self.snooze_time + self.snooze_time_step,
                                       self.snooze_time_cap)
            except Exception as exc:
                exception = exc
                # any other exception is fatal, so kill loop
                break

        # cleanup
        self.running = False
        if resp:
            resp.close()

        self.new_session()

        if exception:
            # call a handler first so that the exception can be logged.
            self.listener.on_exception(exception)
            raise exception

    def _data(self, data):
        if self.listener.on_data(data) is False:
            self.running = False

    def _read_loop(self, resp):
        buf = ReadBuffer(resp.raw, self.chunk_size)

        while self.running and not resp.raw.closed:
            length = 0
            while not resp.raw.closed:
                line = buf.read_line().strip()
                if not line:
                    self.listener.keep_alive()  # keep-alive new lines are expected
                elif line.isdigit():
                    length = int(line)
                    break
                else:
                    raise TweepError('Expecting length, unexpected value found')

            next_status_obj = buf.read_len(length)
            if self.running:
                self._data(next_status_obj)

            # # Note: keep-alive newlines might be inserted before each length value.
            # # read until we get a digit...
            # c = b'\n'
            # for c in resp.iter_content(decode_unicode=True):
            #     if c == b'\n':
            #         continue
            #     break
            #
            # delimited_string = c
            #
            # # read rest of delimiter length..
            # d = b''
            # for d in resp.iter_content(decode_unicode=True):
            #     if d != b'\n':
            #         delimited_string += d
            #         continue
            #     break
            #
            # # read the next twitter status object
            # if delimited_string.decode('utf-8').strip().isdigit():
            #     status_id = int(delimited_string)
            #     next_status_obj = resp.raw.read(status_id)
            #     if self.running:
            #         self._data(next_status_obj.decode('utf-8'))


        if resp.raw.closed:
            self.on_closed(resp)

    def _start(self, async):
        self.running = True
        if async:
            self._thread = Thread(target=self._run)
            self._thread.start()
        else:
            self._run()

    def on_closed(self, resp):
        """ Called when the response has been closed by Twitter """
        pass

    def userstream(self,
                   stall_warnings=False,
                   _with=None,
                   replies=None,
                   track=None,
                   locations=None,
                   async=False,
                   encoding='utf8'):
        self.session.params = {'delimited': 'length'}
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%s/user.json' % STREAM_VERSION
        self.host = 'userstream.twitter.com'
        if stall_warnings:
            self.session.params['stall_warnings'] = stall_warnings
        if _with:
            self.session.params['with'] = _with
        if replies:
            self.session.params['replies'] = replies
        if locations and len(locations) > 0:
            if len(locations) % 4 != 0:
                raise TweepError("Wrong number of locations points, "
                                 "it has to be a multiple of 4")
            self.session.params['locations'] = ','.join(['%.2f' % l for l in locations])
        if track:
            self.session.params['track'] = u','.join(track).encode(encoding)

        self._start(async)

    def firehose(self, count=None, async=False):
        self.session.params = {'delimited': 'length'}
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%s/statuses/firehose.json' % STREAM_VERSION
        if count:
            self.url += '&count=%s' % count
        self._start(async)

    def retweet(self, async=False):
        self.session.params = {'delimited': 'length'}
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%s/statuses/retweet.json' % STREAM_VERSION
        self._start(async)

    def sample(self, async=False, languages=None):
        self.session.params = {'delimited': 'length'}
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%s/statuses/sample.json' % STREAM_VERSION
        if languages:
            self.session.params['language'] = ','.join(map(str, languages))
        self._start(async)

    def filter(self, follow=None, track=None, async=False, locations=None,
               stall_warnings=False, languages=None, encoding='utf8', filter_level=None):
        self.body = {}
        self.session.headers['Content-type'] = "application/x-www-form-urlencoded"
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%s/statuses/filter.json' % STREAM_VERSION
        if follow:
            self.body['follow'] = u','.join(follow).encode(encoding)
        if track:
            self.body['track'] = u','.join(track).encode(encoding)
        if locations and len(locations) > 0:
            if len(locations) % 4 != 0:
                raise TweepError("Wrong number of locations points, "
                                 "it has to be a multiple of 4")
            self.body['locations'] = u','.join(['%.4f' % l for l in locations])
        if stall_warnings:
            self.body['stall_warnings'] = stall_warnings
        if languages:
            self.body['language'] = u','.join(map(str, languages))
        if filter_level:
            self.body['filter_level'] = unicode(filter_level, encoding)
        self.session.params = {'delimited': 'length'}
        self.host = 'stream.twitter.com'
        self._start(async)

    def sitestream(self, follow, stall_warnings=False,
                   with_='user', replies=False, async=False):
        self.body = {}
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%s/site.json' % STREAM_VERSION
        self.body['follow'] = u','.join(map(six.text_type, follow))
        self.body['delimited'] = 'length'
        if stall_warnings:
            self.body['stall_warnings'] = stall_warnings
        if with_:
            self.body['with'] = with_
        if replies:
            self.body['replies'] = replies
        self._start(async)

    def disconnect(self):
        if self.running is False:
            return
        self.running = False

class AuthHandler(object):

    def apply_auth(self, url, method, headers, parameters):
        """Apply authentication headers to request"""
        raise NotImplementedError

    def get_username(self):
        """Return the username of the authenticated user"""
        raise NotImplementedError

class OAuthHandler(AuthHandler):
    """OAuth authentication handler"""
    OAUTH_HOST = 'api.twitter.com'
    OAUTH_ROOT = '/oauth/'

    def __init__(self, consumer_key, consumer_secret, callback=None):
        if type(consumer_key) == six.text_type:
            consumer_key = consumer_key.encode('ascii')

        if type(consumer_secret) == six.text_type:
            consumer_secret = consumer_secret.encode('ascii')

        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token = None
        self.access_token_secret = None
        self.callback = callback
        self.username = None
        self.oauth = OAuth1Session(consumer_key,
                                   client_secret=consumer_secret,
                                   callback_uri=self.callback)

    def _get_oauth_url(self, endpoint):
        return 'https://' + self.OAUTH_HOST + self.OAUTH_ROOT + endpoint

    def apply_auth(self):
        return OAuth1(self.consumer_key,
                      client_secret=self.consumer_secret,
                      resource_owner_key=self.access_token,
                      resource_owner_secret=self.access_token_secret,
                      decoding=None)

    def _get_request_token(self, access_type=None):
        try:
            url = self._get_oauth_url('request_token')
            if access_type:
                url += '?x_auth_access_type=%s' % access_type
            return self.oauth.fetch_request_token(url)
        except Exception as e:
            raise TweepError(e)

    def set_access_token(self, key, secret):
        self.access_token = key
        self.access_token_secret = secret

    def get_authorization_url(self,
                              signin_with_twitter=False,
                              access_type=None):
        """Get the authorization URL to redirect the user"""
        try:
            if signin_with_twitter:
                url = self._get_oauth_url('authenticate')
                if access_type:
                    logging.warning(WARNING_MESSAGE)
            else:
                url = self._get_oauth_url('authorize')
            self.request_token = self._get_request_token(access_type=access_type)
            return self.oauth.authorization_url(url)
        except Exception as e:
            raise
            raise TweepError(e)

    def get_access_token(self, verifier=None):
        """
        After user has authorized the request token, get access token
        with user supplied verifier.
        """
        try:
            url = self._get_oauth_url('access_token')
            self.oauth = OAuth1Session(self.consumer_key,
                                       client_secret=self.consumer_secret,
                                       resource_owner_key=self.request_token['oauth_token'],
                                       resource_owner_secret=self.request_token['oauth_token_secret'],
                                       verifier=verifier, callback_uri=self.callback)
            resp = self.oauth.fetch_access_token(url)
            self.access_token = resp['oauth_token']
            self.access_token_secret = resp['oauth_token_secret']
            return self.access_token, self.access_token_secret
        except Exception as e:
            raise TweepError(e)

    def get_xauth_access_token(self, username, password):
        """
        Get an access token from an username and password combination.
        In order to get this working you need to create an app at
        http://twitter.com/apps, after that send a mail to api@twitter.com
        and request activation of xAuth for it.
        """
        try:
            url = self._get_oauth_url('access_token')
            oauth = OAuth1(self.consumer_key,
                           client_secret=self.consumer_secret)
            r = requests.post(url=url,
                              auth=oauth,
                              headers={'x_auth_mode': 'client_auth',
                                       'x_auth_username': username,
                                       'x_auth_password': password})

            print(r.content)
            credentials = parse_qs(r.content)
            return credentials.get('oauth_token')[0], credentials.get('oauth_token_secret')[0]
        except Exception as e:
            raise TweepError(e)

    def get_username(self):
        if self.username is None:
            api = API(self)
            user = api.verify_credentials()
            if user:
                self.username = user.screen_name
            else:
                raise TweepError('Unable to get username,'
                                 ' invalid oauth token!')
        return self.username

class TweepError(Exception):
    """Tweepy exception"""

    def __init__(self, reason, response=None):
        self.reason = six.text_type(reason)
        self.response = response
        Exception.__init__(self, reason)

    def __str__(self):
        return self.reason

def is_rate_limit_error_message(message):
    """Check if the supplied error message belongs to a rate limit error."""
    return isinstance(message, list) \
        and len(message) > 0 \
        and 'code' in message[0] \
        and message[0]['code'] == 88

class RateLimitError(TweepError):
    """Exception for Tweepy hitting the rate limit."""
    # RateLimitError has the exact same properties and inner workings
    # as TweepError for backwards compatibility reasons.
    pass

def import_simplejson():
    try:
        import simplejson as json
    except ImportError:
        try:
            import json  # Python 2.6+
        except ImportError:
            try:
                # Google App Engine
                from django.utils import simplejson as json
            except ImportError:
                raise ImportError("Can't load a json library")

    return json


def list_to_csv(item_list):
    if item_list:
        return ','.join([str(i) for i in item_list])

class ResultSet(list):
    """A list like object that holds results from a Twitter API query."""
    def __init__(self, max_id=None, since_id=None):
        super(ResultSet, self).__init__()
        self._max_id = max_id
        self._since_id = since_id

    @property
    def max_id(self):
        if self._max_id:
            return self._max_id
        ids = self.ids()
        # Max_id is always set to the *smallest* id, minus one, in the set
        return (min(ids) - 1) if ids else None

    @property
    def since_id(self):
        if self._since_id:
            return self._since_id
        ids = self.ids()
        # Since_id is always set to the *greatest* id in the set
        return max(ids) if ids else None

    def ids(self):
        return [item.id for item in self if hasattr(item, 'id')]


class Model(object):

    def __init__(self, api=None):
        self._api = api

    def __getstate__(self):
        # pickle
        pickle = dict(self.__dict__)
        try:
            del pickle['_api']  # do not pickle the API reference
        except KeyError:
            pass
        return pickle

    @classmethod
    def parse(cls, api, json):
        """Parse a JSON object into a model instance."""
        raise NotImplementedError

    @classmethod
    def parse_list(cls, api, json_list):
        """
            Parse a list of JSON objects into
            a result set of model instances.
        """
        results = ResultSet()
        for obj in json_list:
            if obj:
                results.append(cls.parse(api, obj))
        return results

    def __repr__(self):
        state = ['%s=%s' % (k, repr(v)) for (k, v) in vars(self).items()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(state))


class Status(Model):

    @classmethod
    def parse(cls, api, json):
        status = cls(api)
        setattr(status, '_json', json)
        for k, v in json.items():
            if k == 'user':
                user_model = getattr(api.parser.model_factory, 'user') if api else User
                user = user_model.parse(api, v)
                setattr(status, 'author', user)
                setattr(status, 'user', user)  # DEPRECIATED
            elif k == 'created_at':
                setattr(status, k, parse_datetime(v))
            elif k == 'source':
                if '<' in v:
                    setattr(status, k, parse_html_value(v))
                    setattr(status, 'source_url', parse_a_href(v))
                else:
                    setattr(status, k, v)
                    setattr(status, 'source_url', None)
            elif k == 'retweeted_status':
                setattr(status, k, Status.parse(api, v))
            elif k == 'place':
                if v is not None:
                    setattr(status, k, Place.parse(api, v))
                else:
                    setattr(status, k, None)
            else:
                setattr(status, k, v)
        return status

    def destroy(self):
        return self._api.destroy_status(self.id)

    def retweet(self):
        return self._api.retweet(self.id)

    def retweets(self):
        return self._api.retweets(self.id)

    def favorite(self):
        return self._api.create_favorite(self.id)

    def __eq__(self, other):
        if isinstance(other, Status):
            return self.id == other.id

        return NotImplemented

    def __ne__(self, other):
        result = self == other

        if result is NotImplemented:
            return result

        return not result


class User(Model):

    @classmethod
    def parse(cls, api, json):
        user = cls(api)
        setattr(user, '_json', json)
        for k, v in json.items():
            if k == 'created_at':
                setattr(user, k, parse_datetime(v))
            elif k == 'status':
                setattr(user, k, Status.parse(api, v))
            elif k == 'following':
                # twitter sets this to null if it is false
                if v is True:
                    setattr(user, k, True)
                else:
                    setattr(user, k, False)
            else:
                setattr(user, k, v)
        return user

    @classmethod
    def parse_list(cls, api, json_list):
        if isinstance(json_list, list):
            item_list = json_list
        else:
            item_list = json_list['users']

        results = ResultSet()
        for obj in item_list:
            results.append(cls.parse(api, obj))
        return results

    def timeline(self, **kargs):
        return self._api.user_timeline(user_id=self.id, **kargs)

    def friends(self, **kargs):
        return self._api.friends(user_id=self.id, **kargs)

    def followers(self, **kargs):
        return self._api.followers(user_id=self.id, **kargs)

    def follow(self):
        self._api.create_friendship(user_id=self.id)
        self.following = True

    def unfollow(self):
        self._api.destroy_friendship(user_id=self.id)
        self.following = False

    def lists_memberships(self, *args, **kargs):
        return self._api.lists_memberships(user=self.screen_name,
                                           *args,
                                           **kargs)

    def lists_subscriptions(self, *args, **kargs):
        return self._api.lists_subscriptions(user=self.screen_name,
                                             *args,
                                             **kargs)

    def lists(self, *args, **kargs):
        return self._api.lists_all(user=self.screen_name,
                                   *args,
                                   **kargs)

    def followers_ids(self, *args, **kargs):
        return self._api.followers_ids(user_id=self.id,
                                       *args,
                                       **kargs)


class DirectMessage(Model):

    @classmethod
    def parse(cls, api, json):
        dm = cls(api)
        for k, v in json.items():
            if k == 'sender' or k == 'recipient':
                setattr(dm, k, User.parse(api, v))
            elif k == 'created_at':
                setattr(dm, k, parse_datetime(v))
            else:
                setattr(dm, k, v)
        return dm

    def destroy(self):
        return self._api.destroy_direct_message(self.id)


class Friendship(Model):

    @classmethod
    def parse(cls, api, json):
        relationship = json['relationship']

        # parse source
        source = cls(api)
        for k, v in relationship['source'].items():
            setattr(source, k, v)

        # parse target
        target = cls(api)
        for k, v in relationship['target'].items():
            setattr(target, k, v)

        return source, target


class Category(Model):

    @classmethod
    def parse(cls, api, json):
        category = cls(api)
        for k, v in json.items():
            setattr(category, k, v)
        return category


class SavedSearch(Model):

    @classmethod
    def parse(cls, api, json):
        ss = cls(api)
        for k, v in json.items():
            if k == 'created_at':
                setattr(ss, k, parse_datetime(v))
            else:
                setattr(ss, k, v)
        return ss

    def destroy(self):
        return self._api.destroy_saved_search(self.id)


class SearchResults(ResultSet):

    @classmethod
    def parse(cls, api, json):
        metadata = json['search_metadata']
        results = SearchResults()
        results.refresh_url = metadata.get('refresh_url')
        results.completed_in = metadata.get('completed_in')
        results.query = metadata.get('query')
        results.count = metadata.get('count')
        results.next_results = metadata.get('next_results')

        status_model = getattr(api.parser.model_factory, 'status') if api else Status

        for status in json['statuses']:
            results.append(status_model.parse(api, status))
        return results


class List(Model):

    @classmethod
    def parse(cls, api, json):
        lst = List(api)
        for k, v in json.items():
            if k == 'user':
                setattr(lst, k, User.parse(api, v))
            elif k == 'created_at':
                setattr(lst, k, parse_datetime(v))
            else:
                setattr(lst, k, v)
        return lst

    @classmethod
    def parse_list(cls, api, json_list, result_set=None):
        results = ResultSet()
        if isinstance(json_list, dict):
            json_list = json_list['lists']
        for obj in json_list:
            results.append(cls.parse(api, obj))
        return results

    def update(self, **kargs):
        return self._api.update_list(self.slug, **kargs)

    def destroy(self):
        return self._api.destroy_list(self.slug)

    def timeline(self, **kargs):
        return self._api.list_timeline(self.user.screen_name,
                                       self.slug,
                                       **kargs)

    def add_member(self, id):
        return self._api.add_list_member(self.slug, id)

    def remove_member(self, id):
        return self._api.remove_list_member(self.slug, id)

    def members(self, **kargs):
        return self._api.list_members(self.user.screen_name,
                                      self.slug,
                                      **kargs)

    def is_member(self, id):
        return self._api.is_list_member(self.user.screen_name,
                                        self.slug,
                                        id)

    def subscribe(self):
        return self._api.subscribe_list(self.user.screen_name, self.slug)

    def unsubscribe(self):
        return self._api.unsubscribe_list(self.user.screen_name, self.slug)

    def subscribers(self, **kargs):
        return self._api.list_subscribers(self.user.screen_name,
                                          self.slug,
                                          **kargs)

    def is_subscribed(self, id):
        return self._api.is_subscribed_list(self.user.screen_name,
                                            self.slug,
                                            id)


class Relation(Model):
    @classmethod
    def parse(cls, api, json):
        result = cls(api)
        for k, v in json.items():
            if k == 'value' and json['kind'] in ['Tweet', 'LookedupStatus']:
                setattr(result, k, Status.parse(api, v))
            elif k == 'results':
                setattr(result, k, Relation.parse_list(api, v))
            else:
                setattr(result, k, v)
        return result


class Relationship(Model):
    @classmethod
    def parse(cls, api, json):
        result = cls(api)
        for k, v in json.items():
            if k == 'connections':
                setattr(result, 'is_following', 'following' in v)
                setattr(result, 'is_followed_by', 'followed_by' in v)
            else:
                setattr(result, k, v)
        return result


class JSONModel(Model):

    @classmethod
    def parse(cls, api, json):
        return json


class IDModel(Model):

    @classmethod
    def parse(cls, api, json):
        if isinstance(json, list):
            return json
        else:
            return json['ids']


class BoundingBox(Model):

    @classmethod
    def parse(cls, api, json):
        result = cls(api)
        if json is not None:
            for k, v in json.items():
                setattr(result, k, v)
        return result

    def origin(self):
        """
        Return longitude, latitude of southwest (bottom, left) corner of
        bounding box, as a tuple.

        This assumes that bounding box is always a rectangle, which
        appears to be the case at present.
        """
        return tuple(self.coordinates[0][0])

    def corner(self):
        """
        Return longitude, latitude of northeast (top, right) corner of
        bounding box, as a tuple.

        This assumes that bounding box is always a rectangle, which
        appears to be the case at present.
        """
        return tuple(self.coordinates[0][2])


class Place(Model):

    @classmethod
    def parse(cls, api, json):
        place = cls(api)
        for k, v in json.items():
            if k == 'bounding_box':
                # bounding_box value may be null (None.)
                # Example: "United States" (id=96683cc9126741d1)
                if v is not None:
                    t = BoundingBox.parse(api, v)
                else:
                    t = v
                setattr(place, k, t)
            elif k == 'contained_within':
                # contained_within is a list of Places.
                setattr(place, k, Place.parse_list(api, v))
            else:
                setattr(place, k, v)
        return place

    @classmethod
    def parse_list(cls, api, json_list):
        if isinstance(json_list, list):
            item_list = json_list
        else:
            item_list = json_list['result']['places']

        results = ResultSet()
        for obj in item_list:
            results.append(cls.parse(api, obj))
        return results


class Media(Model):

    @classmethod
    def parse(cls, api, json):
        media = cls(api)
        for k, v in json.items():
            setattr(media, k, v)
        return media

class ModelFactory(object):
    """
    Used by parsers for creating instances
    of models. You may subclass this factory
    to add your own extended models.
    """

    status = Status
    user = User
    direct_message = DirectMessage
    friendship = Friendship
    saved_search = SavedSearch
    search_results = SearchResults
    category = Category
    list = List
    relation = Relation
    relationship = Relationship
    media = Media

    json = JSONModel
    ids = IDModel
    place = Place
    bounding_box = BoundingBox


class StdOutListener(StreamListener):
    """ A listener handles tweets are the received from the stream.
    This is a basic listener that just prints received tweets to stdout.

    """
    def on_data(self, data):
        print(data)
        return True

    def on_error(self, status):
        print(status)

if __name__ == '__main__':
    l = StdOutListener()
    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    stream = Stream(auth, l)
    stream.filter(track=['basketball'])