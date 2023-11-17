# Copyright (C) 2015-2023 by the Free Software Foundation, Inc.
#
# This file is part of GNU Mailman.
#
# GNU Mailman is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# GNU Mailman is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# GNU Mailman.  If not, see <https://www.gnu.org/licenses/>.

"""Test REST validators."""

import unittest

from lazr.config import as_boolean
from mailman.app.lifecycle import create_list
from mailman.core.api import API30, API31
from mailman.database.transaction import transaction
from mailman.interfaces.action import Action
from mailman.interfaces.usermanager import IUserManager
from mailman.rest import helpers
from mailman.rest.validator import (
    email_or_regexp_validator,
    email_validator,
    enum_validator,
    integer_ge_zero_validator,
    list_of_emails_or_regexp_or_atlist_validator,
    list_of_emails_or_regexp_validator,
    list_of_emails_validator,
    list_of_strings_validator,
    subscriber_validator,
    Validator,
)
from mailman.testing.layers import RESTLayer
from zope.component import getUtility


class TestValidators(unittest.TestCase):
    layer = RESTLayer

    def test_list_of_strings_validator_single(self):
        # This validator should turn a single key into a list of keys.
        self.assertEqual(list_of_strings_validator('ant'), ['ant'])

    def test_list_of_strings_validator_multiple(self):
        # This validator should turn a single key into a list of keys.
        self.assertEqual(
            list_of_strings_validator(['ant', 'bee', 'cat']),
            ['ant', 'bee', 'cat'])

    def test_list_of_strings_validator_empty_list(self):
        # This validator should return an empty list for an empty string input.
        self.assertEqual(list_of_strings_validator(''), [])

    def test_list_of_emails_or_regexp_validator_empty_list(self):
        # This validator should return an empty list for an empty string input.
        self.assertEqual(list_of_emails_or_regexp_validator(''), [])

    def test_integer_ge_zero_validator_invalid(self):
        self.assertRaises(ValueError, integer_ge_zero_validator, 'foo')
        self.assertRaises(ValueError, integer_ge_zero_validator, '-1')

    def test_integer_ge_zero_validator_valid(self):
        self.assertEqual(integer_ge_zero_validator('0'), 0)
        self.assertEqual(integer_ge_zero_validator('100'), 100)

    def test_list_of_strings_validator_invalid(self):
        # Strings are required.
        self.assertRaises(ValueError, list_of_strings_validator, 7)
        self.assertRaises(ValueError, list_of_strings_validator, ['ant', 7])

    def test_subscriber_validator_int_uuid(self):
        # Convert from an existing user id to a UUID.
        anne = getUtility(IUserManager).make_user('anne@example.com')
        uuid = subscriber_validator(API30)(str(anne.user_id.int))
        self.assertEqual(anne.user_id, uuid)

    def test_subscriber_validator_hex_uuid(self):
        # Convert from an existing user id to a UUID.
        anne = getUtility(IUserManager).make_user('anne@example.com')
        uuid = subscriber_validator(API31)(anne.user_id.hex)
        self.assertEqual(anne.user_id, uuid)

    def test_subscriber_validator_no_int_uuid(self):
        # API 3.1 does not accept ints as subscriber id's.
        anne = getUtility(IUserManager).make_user('anne@example.com')
        self.assertRaises(ValueError,
                          subscriber_validator(API31), str(anne.user_id.int))

    def test_subscriber_validator_bad_int_uuid(self):
        # In API 3.0, UUIDs are ints.
        self.assertRaises(ValueError,
                          subscriber_validator(API30), 'not-a-thing')

    def test_subscriber_validator_bad_int_hex(self):
        # In API 3.1, UUIDs are hexes.
        self.assertRaises(ValueError,
                          subscriber_validator(API31), 'not-a-thing')

    def test_subscriber_validator_email_address_API30(self):
        self.assertEqual(subscriber_validator(API30)('anne@example.com'),
                         'anne@example.com')

    def test_subscriber_validator_email_address_API31(self):
        self.assertEqual(subscriber_validator(API31)('anne@example.com'),
                         'anne@example.com')

    def test_enum_validator_valid(self):
        self.assertEqual(enum_validator(Action)('hold'), Action.hold)

    def test_enum_validator_invalid(self):
        self.assertRaises(ValueError,
                          enum_validator(Action), 'not-a-thing')

    def test_enum_validator_blank(self):
        self.assertEqual(enum_validator(Action, allow_blank=True)(''), None)

    def test_list_of_emails_validator_valid(self):
        self.assertEqual(
            list_of_emails_validator(['foo@example.com', 'bar@example.com']),
            ['foo@example.com', 'bar@example.com'])
        self.assertEqual(
            list_of_emails_validator('bar@example.com'),
            ['bar@example.com'])

    def test_list_of_emails_validator_invalid(self):
        self.assertRaises(
            ValueError, list_of_emails_validator, 'foo.example.com')
        self.assertRaises(
            ValueError,
            list_of_emails_validator,
            ['foo@example.com', 'bar.example.com'])

    def test_email_or_regexp_validator_valid(self):
        self.assertEqual(
            email_or_regexp_validator('foo@example.com'),
            'foo@example.com')
        self.assertEqual(
            email_or_regexp_validator('^[^@]+'),
            '^[^@]+')

    def test_email_or_regexp_validator_invalid(self):
        self.assertRaises(
            ValueError, email_or_regexp_validator, 'foo.example.com')
        self.assertRaises(
            ValueError, email_or_regexp_validator, '^[^@]+(')
        self.assertRaises(
            ValueError, email_or_regexp_validator, '')

    def test_list_of_emails_or_regexp_validator_valid(self):
        self.assertEqual(
            list_of_emails_or_regexp_validator(
                ['foo@example.com', '^.*@example.com']),
            ['foo@example.com', '^.*@example.com'])
        self.assertEqual(
            list_of_emails_or_regexp_validator([]), [])

    def test_list_of_emails_or_regexp_validator_invalid(self):
        self.assertRaises(
            ValueError, list_of_emails_or_regexp_validator, 'foo.example.com')
        self.assertRaises(
            ValueError, list_of_emails_or_regexp_validator,
            ['foo.example.com', '^.*@example.com'])
        self.assertRaises(
            ValueError, list_of_emails_or_regexp_validator,
            ['foo@example.com', '^*@example.com'])

    def test_list_of_emails_or_regexp_or_atlist_validator_valid(self):
        self.assertEqual(
            list_of_emails_or_regexp_or_atlist_validator(
                ['foo@example.com', '^.*@example.com', '@bar@example.com']),
            ['foo@example.com', '^.*@example.com', '@bar@example.com'])
        self.assertEqual(
            list_of_emails_or_regexp_or_atlist_validator([]), [])
        self.assertEqual(
            list_of_emails_or_regexp_or_atlist_validator(''), [])

    def test_list_of_emails_or_regexp_or_atlist_validator_invalid(self):
        self.assertRaises(
            ValueError, list_of_emails_or_regexp_or_atlist_validator,
            'foo.example.com')
        self.assertRaises(
            ValueError, list_of_emails_or_regexp_or_atlist_validator,
            ['foo@example.com', '^*@example.com'])
        self.assertRaises(
            ValueError, list_of_emails_or_regexp_or_atlist_validator,
            ['foo@example.com', '^.*@example.com', '@bar.example.com'])
        self.assertRaises(
            ValueError, list_of_emails_or_regexp_or_atlist_validator, None)

    def test_email_validator(self):
        self.assertRaises(ValueError,
                          email_validator, 'foo.example.com')
        self.assertEqual('foo@example.com', email_validator('foo@example.com'))

    def test_validator_class_boolean_as_bool(self):

        class RequestTrue:
            params = dict(key=True)
            content_type = 'application/x-www-form-urlencoded'

        class RequestFalse:
            params = dict(key=False)
            content_type = 'application/x-www-form-urlencoded'

        validator = Validator(key=as_boolean)
        self.assertTrue(validator(RequestTrue)['key'])
        self.assertFalse(validator(RequestFalse)['key'])


class TestGetterSetter(unittest.TestCase):
    """Test the GeterSetter class"""

    layer = RESTLayer

    def setUp(self):
        with transaction():
            self._mlist = create_list('test@example.com')
        self.getset = helpers.GetterSetter(list_of_strings_validator)

    def test_get_mailinglist_attribute(self):
        self.assertEqual(self.getset.get(self._mlist, 'pass_types'), [])
        self.assertEqual(self.getset.get(self._mlist, 'pass_extensions'), [])

    def test_set_mailinglist_attribute(self):
        self.getset.put(
            self._mlist, 'pass_types', ['application/octet-stream'])
        self.getset.put(
            self._mlist, 'pass_extensions', ['.pdf'])
        self.assertEqual(list(self._mlist.pass_types),
                         ['application/octet-stream'])
        self.assertEqual(list(self._mlist.pass_extensions),
                         ['.pdf'])

    def test_set_boolean_as_bool(self):
        # Non-pythonic POST data can contain JSON booleans. Ensure we can
        # handle that.
        getset = helpers.GetterSetter(as_boolean)
        self.assertTrue(getset(True))
        self.assertFalse(getset(False))
