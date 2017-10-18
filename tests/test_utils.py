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

"""Test utils."""

from __future__ import absolute_import, print_function

import sys

import pytest
from flask_security.confirmable import _security
from helpers import check_csrf_disabled
from invenio_db import db

from invenio_oauthclient.errors import AlreadyLinkedError
from invenio_oauthclient.models import RemoteAccount, RemoteToken
from invenio_oauthclient.utils import _get_external_id, \
    create_csrf_disabled_registrationform, create_csrf_free_registrationform, \
    fill_form, oauth_authenticate, oauth_get_user, oauth_link_external_id, \
    oauth_unlink_external_id, obj_or_import_string, rebuild_access_tokens


def test_utilities(models_fixture):
    """Test utilities."""
    app = models_fixture
    datastore = app.extensions['invenio-accounts'].datastore
    assert obj_or_import_string('invenio_oauthclient.errors')

    # User
    existing_email = 'existing@inveniosoftware.org'
    user = datastore.find_user(email=existing_email)

    # Authenticate
    assert not _get_external_id({})
    assert not oauth_authenticate('dev', user, require_existing_link=True)

    _security.confirmable = True
    _security.login_without_confirmation = False
    user.confirmed_at = None
    assert not oauth_authenticate('dev', user)

    # Tokens
    t = RemoteToken.create(user.id, 'dev', 'mytoken', 'mysecret')
    assert \
        RemoteToken.get(user.id, 'dev', access_token='mytoken') == \
        RemoteToken.get_by_token('dev', 'mytoken')

    assert oauth_get_user('dev', access_token=t.access_token) == user
    assert \
        oauth_get_user('dev', account_info={'user': {'email': existing_email}}) == user

    # Link user to external id
    external_id = {'id': '123', 'method': 'test_method'}
    oauth_link_external_id(user, external_id)

    with pytest.raises(AlreadyLinkedError):
        oauth_link_external_id(user, external_id)

    assert oauth_get_user('dev',
                          account_info={
                              'external_id': external_id['id'],
                              'external_method': external_id['method']
                          }) == user

    # Cleanup
    oauth_unlink_external_id(external_id)
    acc = RemoteAccount.get(user.id, 'dev')
    acc.delete()


def test_rebuilding_access_tokens(models_fixture):
    """Test rebuilding access tokens with random new SECRET_KEY."""
    app = models_fixture
    old_secret_key = app.secret_key

    datastore = app.extensions['invenio-accounts'].datastore
    existing_email = 'existing@inveniosoftware.org'
    user = datastore.find_user(email=existing_email)

    # Creating a new remote token and commiting to the db
    test_token = 'mytoken'
    token_type = 'testing'
    with db.session.begin_nested():
        rt = RemoteToken.create(user.id, 'testkey', test_token,
                                app.secret_key, token_type)
        db.session.add(rt)
    db.session.commit()

    # Changing application SECRET_KEY
    app.secret_key = 'NEW_SECRET_KEY'
    db.session.expunge_all()

    # Asserting the decoding error occurs with the stale SECRET_KEY
    if sys.version_info[0] < 3:  # python 2
        remote_token = RemoteToken.query.first()
        assert remote_token.access_token != test_token
    else:  # python 3
        with pytest.raises(UnicodeDecodeError):
            RemoteToken.query.first()

    db.session.expunge_all()
    rebuild_access_tokens(old_secret_key)
    remote_token = RemoteToken.query.filter_by(token_type=token_type).first()

    # Asserting the access_token is not changed after rebuilding
    assert remote_token.access_token == test_token


def test_csrf_disabled_form_old(userprofiles_withcsrf_app, user_dict):
    """Test disabling CSRF in registration form."""
    app = userprofiles_withcsrf_app
    with app.test_request_context():
        form = create_csrf_disabled_registrationform()

        form = fill_form(
            form,
            user_dict,
        )

        assert form.validate()
        check_csrf_disabled(form)


def test_csrf_disabled_form_updated(userprofiles_withcsrf_app, user_dict):
    """Test disabling CSRF in registration form with updated function."""
    app = userprofiles_withcsrf_app
    with app.test_request_context():
        form = create_csrf_free_registrationform()

        form = fill_form(
            form,
            user_dict,
        )

        assert form.validate()
        check_csrf_disabled(form)
