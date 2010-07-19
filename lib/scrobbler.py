#!/usr/bin/env python

import datetime
import logging
import time
import urllib

from google.appengine.api import urlfetch

from lib import audioscrobbler
from lib import feedparser
from models.user import User

def update(user, auto_save=True):
    logging.debug('Checking in for %s' % user.username)

    poster = audioscrobbler.AudioScrobblerPost(username=user.username,
                                               password=user.password,
                                               password_is_md5=True,
                                               verbose=True)
    poster.auth()

    contents = urlfetch.fetch(user.rss_url).content
    # hack around the namespacing.
    contents = contents.replace('<rhap:', '<').replace('</rhap:', '</')

    tracks_played = feedparser.parse(contents)
    for i in xrange(len(tracks_played['entries']) - 1, -1, -1):
        # skip a track we've already submitted
        # see this date ridiculousness? Bleh.
        played_at = datetime.datetime(*tracks_played['entries'][i]['updated_parsed'][0:6])

        if user.last_updated >= played_at:
            continue

        track = dict(artist_name=tracks_played['entries'][i]['artist'],
                     song_title=tracks_played['entries'][i]['track'],
                     length=tracks_played['entries'][i]['duration'],
                     date_played=int(time.mktime(tracks_played['entries'][i]['updated_parsed'])),
                     album=tracks_played['entries'][i]['album'])
        poster.add_track(**track)
        user.submitted_tracks.insert(0, '%s - %s' % (track['artist_name'], track['song_title']))

    # bulk submit
    num_submitted = poster.flush_cache()
    total_submitted = num_submitted + user.num_submitted
    logging.debug('\tSubmitted %d tracks (%d total)' % (num_submitted, total_submitted))

    user.submitted_tracks = user.submitted_tracks[0:50]
    user.num_submitted = total_submitted

    if auto_save:
        user.put()
