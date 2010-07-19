#!/usr/bin/env python

import hashlib
import logging
import os
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from lib import audioscrobbler

from models.user import User

class BaseHandler(webapp.RequestHandler):
    def render(self, filename, **template_values):
        """Renders the template, passing in the appropriate template values."""
        path = os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                '../views/%s.djhtml' % filename))
        self.response.out.write(template.render(path, template_values))

    def build_params(self, **kwargs):
        """Simple request parameter parser.

        Example:
            self.build_params(name=unicode, number=long)
        """
        result = {}

        for name, coercer in kwargs.iteritems():
            result[name] = coercer(self.request.get(name))

        return result

class FrontpageHandler(BaseHandler):
    def get(self):
        # display front page.
        self.render('frontpage')

class UsersHandler(BaseHandler):
    def get(self):
        self.post()

    def post(self):
        def md5_string(string):
            return hashlib.md5(string).hexdigest()

        username = self.request.get('username')
        user = User.get_or_insert(
            username,
            **self.build_params(username=str,
                                password=md5_string,
                                rss_url=str))

        # for edit and delete actions
        if self.request.get('old_password') and user.password == self.request.get('old_password'):
            if self.request.get('delete'):
                if self.request.get('delete') == 'true':
                    user.delete()
                    self.render('frontpage', success='You have been removed!')
                else:
                    self.render('user',
                                user=user,
                                error='Please confirm you want to delete yourself!')
            else:
                if self.request.get('password'):
                    user.password = md5_string(self.request.get('password'))
                user.rss_url = self.request.get('rss_url')
                user.put()
                self.render('user', user=user, success='Your info was updated!')
        # just signed up
        elif user.password == md5_string(self.request.get('password')):
            self.render('user', user=user)
        else:
            self.error(500)
            self.render('frontpage', error="Username/password not recognized!")

class LoginCheckHandler(BaseHandler):
    '''Used by AJAX-y requests to check the validity of lastfm credentials.
    '''

    def get(self, username):
        self.response.headers['Content-Type'] = 'application/json'

        password = self.request.get('password')
        if not password:
            user = User.get_by_key_name(username)
            password = user.password
        else:
            password = hashlib.md5(password).hexdigest()

        poster = audioscrobbler.AudioScrobblerPost(
            username=username,
            password=password,
            password_is_md5=True)
        try:
            poster.auth()
            # Login ok
            self.response.out.write('{"isOk": true}')
        except audioscrobbler.AudioScrobblerPostBadAuth:
            self.response.out.write('{"isOk": false}')

application = webapp.WSGIApplication(
    [('/', FrontpageHandler),
     ('/login_check/(.+)', LoginCheckHandler),
     ('/users', UsersHandler)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
