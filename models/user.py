#!/usr/bin/env python

from google.appengine.ext import db

class User(db.Model):
  username = db.StringProperty(required=True)
  password = db.StringProperty(required=True, indexed=False)
  rss_url = db.LinkProperty(required=True, indexed=False)
  last_updated = db.DateTimeProperty(auto_now=True)
  num_submitted = db.IntegerProperty(default=0)
  submitted_tracks = db.StringListProperty()
