#!/usr/bin/env python

import hashlib
import logging
import os
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

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
    def post(self):
        def md5_string(string):
            return hashlib.md5(string).hexdigest()

        username = self.request.get('username')
        user = User.get_or_insert(
            username,
            **self.build_params(username=str,
                                password=md5_string,
                                rss_url=str))
        if self.request.get('old_password') and user.password == self.request.get('old_password'):
            user.password = md5_string(self.request.get('password'))
            user.rss_url = self.request.get('rss_url')
            user.put
            self.render('user', user=user, success='Your info was updated!')
        elif user.password == md5_string(self.request.get('password')):
            self.render('user', user=user)
        else:
            self.error(500)
            self.render('frontpage', error="Username/password not recognized!")

class SubmitHandler(BaseHandler):
    def get(self, username):
        # redirect to tick or error image.
        pass

application = webapp.WSGIApplication(
    [('/', FrontpageHandler),
     ('/submit/(.+)', SubmitHandler),
     ('/users', UsersHandler)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
