# Most of the exception related stuff is based on the pyscrobbler package.
# Some fixups to run under app engine.
import datetime, logging, locale, md5, re, site, sys, time, urllib
from google.appengine.api import urlfetch

enc = 'utf8'

# AudioScrobblerQuery configuration settings
audioscrobbler_request_version = '1.0'
audioscrobbler_request_host = 'ws.audioscrobbler.com'

# AudioScrobblerPost configuration settings
audioscrobbler_post_host = 'post.audioscrobbler.com:80'
client_name = u'tst'
client_version = u'1.0' # If using a client_name of 'tst', use 1.0

class AudioScrobblerError(Exception):

    """
    The base AudioScrobbler error from which all our other exceptions derive
    """

    def __init__(self, message):
        """ Create a new AudioScrobblerError.

            :Parameters:
                - `message`: The message that will be displayed to the user
        """
        self.message = message

    def __repr__(self):
        msg = "%s: %s"
        return msg % (self.__class__.__name__, self.message,)

    def __str__(self):
        return self.__repr__()

class AudioScrobblerConnectionError(AudioScrobblerError):

    """
    The base network error, raise by invalid HTTP responses or failures to
    connect to the server specified (DNS, timeouts, etc.)
    """

    def __init__(self, type, code, message):
        self.type = type
        self.code = code
        self.message = message

    def __repr__(self):
        msg = "AudioScrobblerConnectionError: %s: %s %s"
        return msg % (self.type.upper(), self.code, self.message,)

class AudioScrobblerTypeError(AudioScrobblerError):

    """
    If we would normally raise a TypeError we raise this instead
    """
    pass

class AudioScrobblerHandshakeError(AudioScrobblerError):

    """
    If we fail the handshake this is raised.  If you're running in a long
    running process you should pass on this error, as the system keeps a
    cache which ``flushcache()`` will clear for you when the server is back.
    """
    pass

class AudioScrobblerPostBanned(AudioScrobblerHandshakeError):
    """
    If the POST server returns a ``BANNED`` message we raise this exception.
    """

    def __repr__(self):
        msg = "Sadly this library has been banned. Do not use this library, " \
            + "and look for updates."

        return msg

class AudioScrobblerPostBadAuth(AudioScrobblerHandshakeError):
    """
    If the POST server returns a "BADAUTH" message we raise this exception
    """
    def __repr__(self):
        return "The provided user authentication data is no good! Did you typo?"

class AudioScrobblerPostBadTime(AudioScrobblerHandshakeError):
    """
    If the POST server returns a "BADTIME" message we raise this exception
    """
    def __repr__(self):
        return "The system clock seems to be terribly wrong. Please correct " \
            + "the time and try again later"

class AudioScrobblerPostFailed(AudioScrobblerError):
    """
    If the POST server returns an ``FAILED`` message we raise this exception.
    """

    def __repr__(self):
        msg = "Posting track to AudioScrobbler failed.  Reason given: %s"
        return msg % (self.message,)

class AudioScrobblerPost:
    """
    Provides a happy interface to post tracks played to a user's Last.fm account
    """

    def __init__(self,
                 username = u'',
                 password = u'',
                 password_is_md5 = False,
                 client_name = client_name,
                 client_version = client_version,
                 protocol_version = u'1.2',
                 host = audioscrobbler_post_host,
                 verbose = False):
        """
        Constructor for AudioScrobbler
        """
        self.params = dict(username=username,
                           password=password,
                           client_name=client_name,
                           client_version=client_version,
                           protocol_version=protocol_version,
                           host=host)
        if not(password_is_md5):
            self.params['password'] = md5.md5(self.params['password']).hexdigest()
        self.verbose = verbose

        self.authenticated = False
        self.session_id = None
        self.now_playing_url = None
        self.submission_url = None
        self.submission_queue = []

    def auth(self, force = False):
        """
        Authenticate against the server
        If force is True, will always authenticate, otherwise will only
        authenticate if there is not an existing session.
        """
        if self.authenticated and not(force):
            return True

        # Actually can authenticate now!
        # set up request
        now = datetime.datetime.now()
        p = { 'hs' : 'true',
              'u' : self.params['username'],
              'a' : md5.md5(self.params['password']
                                + str(int(now.strftime('%s')))).hexdigest(),
              'c' : self.params['client_name'],
              'v' : self.params['client_version'],
              'p' : self.params['protocol_version'],
              't' : str(int(now.strftime('%s'))) }
        url = 'http://%s/?%s' % (self.params['host'], urllib.urlencode(p))

        # submit request
        response = urlfetch.fetch(url)

        # process response
        response_body = response.content
        if response_body.startswith('OK'):
            self.log("Handshake success: ")

            status, self.session_id, self.now_playing_url, self.submission_url \
                = response_body.splitlines()

            self.log("Session ID: %s" % self.session_id)
            self.log("Now playing: %s" % self.now_playing_url)
            self.log("Submission: %s" % self.submission_url)

            self.authenticated = True
            return True
        else:
            self.log("Handshake failure! ")
            self.log(response_body)

            if response_body.startswith('BANNED'):
                raise AudioScrobblerPostBanned(response_body)
            elif response_body.startswith('BADAUTH'):
                raise AudioScrobblerPostBadAuth(response_body)
            elif response_body.startswith('BADTIME'):
                raise AudioScrobblerPostBadTime(response_body)
            elif response_body.startswith('FAILED'):
                raise AudioScrobblerPostFailed(response_body)
            return False

    def post_track(self,
                   artist_name = '',
                   song_title = '',
                   length = '',
                   date_played = '',
                   album = '',
                   track_number = '',
                   mbid = ''):
        self.add_track(artist_name, song_title, length, date_played, album,
                       track_number, mbid)
        return self.post()

    def add_track(self,
                  artist_name = '',
                  song_title = '',
                  length = '',
                  date_played = '',
                  album = '',
                  track_number = '',
                  mbid = ''):
        length = str(length)
        date_played = str(date_played)
        self.submission_queue.append((artist_name, song_title, length,
                                      date_played, album, track_number, mbid))

    def post(self):
        if not self.authenticated:
            self.auth()
            return self.post() # authenticate and try again

        tracks = self.submission_queue[0:50]

        params = { 's' : self.session_id }

        # create query params
        for i in xrange(0, len(tracks)):
            params['a[%d]' % i], params['t[%d]' % i], params['l[%d]' % i], \
                params['i[%d]' % i], params['b[%d]' % i], params['n[%d]' % i], \
                params['m[%d]' % i] = tracks[i]
            params['o[%d]' % i] = 'P'
            params['r[%d]' % i] = ''

        post = urllib.urlencode(params, True)

        # execute post
        response = urlfetch.fetch(self.submission_url, method='POST', payload=post)

        # process response
        response_body = response.content
        if response_body.startswith('OK'):
            self.log('Successfully submitted %d tracks' % len(tracks))
            submitted = len(tracks)
            self.submission_queue = self.submission_queue[50:]
            return submitted
        else:
            self.log('ZOMG FAILURE')
            self.log(response_body)
            raise AudioScrobblerPostFailed('not sure what happened here sir')

    def flush_cache(self):
        num_submitted = 0

        self.log('Flushing Cache (size: %d)' % len(self.submission_queue))
        while len(self.submission_queue) > 0:
            num_submitted += self.post()

        return num_submitted

    def log(self, msg, force = False):
        """
        Logs a string to console (if self.verbose is True)
        """
        if self.verbose or force:
            time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            logging.info("%s: %s" % (time, msg))
