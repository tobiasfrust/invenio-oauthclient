# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016, 2017 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Test handlers."""

from __future__ import absolute_import, print_function

import pytest
from flask import session, url_for
from flask_login import current_user
from flask_oauthlib.client import OAuth as FlaskOAuth
from flask_security import login_user, logout_user
from flask_security.confirmable import _security
from helpers import check_redirect_location
from werkzeug.routing import BuildError

from invenio_oauthclient import InvenioOAuthClient, current_oauthclient
from invenio_oauthclient.errors import AlreadyLinkedError, OAuthResponseError
from invenio_oauthclient.handlers import authorized_signup_handler, \
    disconnect_handler, oauth_error_handler, response_token_setter, \
    signup_handler, token_getter, token_session_key, token_setter
from invenio_oauthclient.models import RemoteToken
from invenio_oauthclient.utils import oauth_authenticate
from invenio_oauthclient.views.client import blueprint as blueprint_client
from invenio_oauthclient.views.settings import blueprint as blueprint_settings


def test_token_setter(app, remote):
    """Test token setter on response from OAuth server."""

    # OAuth1
    resp_oauth1 = {
        'name': 'Josiah Carberry',
        'expires_in': 3599,
        'oauth_token': 'test_access_token',
        'oauth_token_secret': 'test_refresh_token',
        'scope': '/authenticate',
        'token_type': 'bearer',
    }
    assert not response_token_setter(remote, resp_oauth1)

    # Bad request
    resp_bad = {
        'invalid': 'invalid',
    }
    with pytest.raises(OAuthResponseError):
        response_token_setter(remote, resp_bad)


def test_token_getter(remote, models_fixture):
    """Test token getter on response from OAuth server."""
    app = models_fixture
    datastore = app.extensions['invenio-accounts'].datastore
    existing_email = 'existing@inveniosoftware.org'
    user = datastore.find_user(email=existing_email)

    # Missing RemoteToken
    oauth_authenticate('dev', user)
    assert not token_getter(remote)

    # Populated RemoteToken
    RemoteToken.create(user.id, 'testkey', 'mytoken', 'mysecret')
    oauth_authenticate('dev', user)
    assert token_getter(remote) == ('mytoken', 'mysecret')


def test_authorized_signup_handler(remote, models_fixture):
    """Test authorized signup handler."""
    datastore = models_fixture.extensions['invenio-accounts'].datastore
    user = datastore.find_user(email='existing@inveniosoftware.org')

    example_response = {'access_token': 'test_access_token'}

    # Mock remote app's handler
    current_oauthclient.signup_handlers[remote.name] = {
        'setup': lambda token, resp: None
    }

    # Authenticate user
    oauth_authenticate('dev', user)

    # Mock next url
    next_url = '/test/redirect'
    session[token_session_key(remote.name) + '_next_url'] = next_url

    # Check user is redirected to next_url
    resp = authorized_signup_handler(example_response, remote)
    check_redirect_location(resp, next_url)


def test_unauthorized_signup(remote, models_fixture):
    """Test unauthorized redirect on signup callback handler."""
    app = models_fixture
    datastore = app.extensions['invenio-accounts'].datastore
    existing_email = 'existing@inveniosoftware.org'
    user = datastore.find_user(email=existing_email)

    example_response = {'access_token': 'test_access_token'}
    example_account_info = {'user': {
        'email': existing_email,
        'external_id': '1234',
        'external_method': 'test_method'
    }}

    # Mock remote app's handler
    current_oauthclient.signup_handlers[remote.name] = {
        'info': lambda resp: example_account_info,
    }

    _security.confirmable = True
    _security.login_without_confirmation = False
    user.confirmed_at = None
    app.config['OAUTHCLIENT_REMOTE_APPS'][remote.name] = {}

    resp = authorized_signup_handler(example_response, remote)
    check_redirect_location(resp, lambda x: x.startswith('/login/'))


def test_signup_handler(remote, models_fixture):
    """Test signup handler."""
    app = models_fixture
    datastore = app.extensions['invenio-accounts'].datastore
    existing_email = 'existing@inveniosoftware.org'
    user = datastore.find_user(email=existing_email)

    # Already authenticated
    login_user(user)
    assert current_user.is_authenticated
    resp1 = signup_handler(remote)
    check_redirect_location(resp1, '/')
    logout_user()
    assert not current_user.is_authenticated

    # No OAuth token
    resp2 = signup_handler(remote)
    check_redirect_location(resp2, '/')

    # Not coming from authorized request
    token = RemoteToken.create(user.id, 'testkey', 'mytoken', 'mysecret')
    token_setter(remote, token, 'mysecret')
    with pytest.raises(BuildError):
        signup_handler(remote)


def test_already_linked_exception(app):
    """Test error when service is already linked to another account."""

    @oauth_error_handler
    def mock_handler():
        raise AlreadyLinkedError(None, None)

    resp = mock_handler()
    check_redirect_location(resp, '/account/settings/linkedaccounts/')


def test_unauthorized_disconnect(app, remote):
    """Test disconnect handler when user is not authenticated."""
    resp = disconnect_handler(remote)
    check_redirect_location(resp, lambda x: x.startswith('/login/'))


def test_dummy_handler(base_app):
    """Test dummy handler."""

    # Force usage of dummy handlers
    base_app.config['OAUTHCLIENT_REMOTE_APPS']['cern']['signup_handler'] = {}

    # Initialize InvenioOAuth
    FlaskOAuth(base_app)
    InvenioOAuthClient(base_app)
    base_app.register_blueprint(blueprint_client)
    base_app.register_blueprint(blueprint_settings)

    # Try to sign-up client
    base_app.test_client().get(url_for('invenio_oauthclient.signup',
                                       remote_app='cern',
                                       next='/someurl/'))
