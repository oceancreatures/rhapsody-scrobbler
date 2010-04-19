#!/usr/bin/env python

import datetime
import logging

from models.user import User
from lib import scrobbler

time_cutoff = datetime.datetime.now() - datetime.timedelta(minutes=20)
users = User.all().filter('last_updated <', time_cutoff).order('-last_updated')

print "Lets do this!\n"
for user in users:
    print "pinging: %s" % user.username
    try:
        scrobbler.update(user)
    except Exception, inst:
        logging.exception(inst)
print "-- done!"
