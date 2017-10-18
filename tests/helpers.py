# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016, 2017 CERN.
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

"""OAuth client test utility functions."""

from inspect import isfunction

import six
from mock import MagicMock
from wtforms.fields.core import FormField

from invenio_oauthclient._compat import _create_identifier
from invenio_oauthclient.views.client import serializer


def get_state(app='test'):
    """Get state."""
    return serializer.dumps({'app': app, 'sid': _create_identifier(),
                             'next': None, })


def mock_response(oauth, remote_app='test', data=None):
    """Mock the oauth response to use the remote."""
    oauth.remote_apps[remote_app].handle_oauth2_response = MagicMock(
        return_value=data
    )


def mock_remote_get(oauth, remote_app='test', data=None):
    """Mock the oauth remote get response."""
    oauth.remote_apps[remote_app].get = MagicMock(
        return_value=data
    )


def check_redirect_location(resp, loc):
    """Check response redirect location."""
    assert resp._status_code == 302
    if isinstance(loc, six.string_types):
        assert resp.headers['Location'] == loc
    elif isfunction(loc):
        assert loc(resp.headers['Location'])


def check_csrf_disabled(form):
    """Check if csrf is disabled in form."""
    import flask_wtf
    from pkg_resources import parse_version
    if parse_version(flask_wtf.__version__) >= parse_version("0.14.0"):
        assert form.meta.csrf is False
        if hasattr(form, 'csrf_token'):
            assert not form.csrf_token
        for f in form:
            if isinstance(f, FormField):
                check_csrf_disabled(f)
    else:
        assert form.csrf_enabled is False
        for f in form:
            if isinstance(f, FormField):
                check_csrf_disabled(f)
