# Copyright (C) 2010-2023 by the Free Software Foundation, Inc.
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

"""REST web form validation."""

import re

from lazr.config import as_boolean
from mailman.interfaces.address import IEmailValidator
from mailman.interfaces.errors import MailmanError
from mailman.interfaces.languages import ILanguageManager
from mailman.rest.helpers import get_request_params
from public import public
from zope.component import getUtility


COMMASPACE = ', '


@public
class RESTError(MailmanError):
    """Base class for REST API errors."""


@public
class UnknownPATCHRequestError(RESTError):
    """A PATCH request contained an unknown attribute."""

    def __init__(self, attribute):
        self.attribute = attribute


@public
class ReadOnlyPATCHRequestError(RESTError):
    """A PATCH request contained a read-only attribute."""

    def __init__(self, attribute):
        self.attribute = attribute


@public
class enum_validator:
    """Convert an enum value name into an enum value."""

    def __init__(self, enum_class, *, allow_blank=False):
        self._enum_class = enum_class
        self._allow_blank = allow_blank

    def __call__(self, enum_value):
        # This will raise a KeyError if the enum value is unknown.  The
        # Validator API requires turning this into a ValueError.
        if not enum_value and self._allow_blank:
            return None
        try:
            return self._enum_class[enum_value]
        except KeyError:
            # Retain the error message.
            err_msg = 'Accepted Values are: {}'.format(self._accepted_values)
            raise ValueError(err_msg)

    @property
    def _accepted_values(self):
        """Joined comma separated self._enum_class values"""
        return ', '.join(item._name_ for item in self._enum_class)


@public
def subscriber_validator(api):
    """Convert an email-or-(int|hex) to an email-or-UUID."""
    def _inner(subscriber):
        try:
            return api.to_uuid(subscriber)
        except ValueError:
            # It must be an email address.
            if getUtility(IEmailValidator).is_valid(subscriber):
                return subscriber
            raise ValueError
    return _inner


@public
def language_validator(code):
    """Convert a language code to a Language object."""
    return getUtility(ILanguageManager)[code]


@public
def list_of_strings_validator(values):
    """Turn a list of things, or a single thing, into a list of unicodes."""
    # There is no good way to pass around an empty list through HTTP API, so,
    # we consider an empty string as an empty list, which can easily be passed
    # around. This is a contract between Core and Postorius. This also fixes a
    # bug where an empty string ('') would be interpreted as a valid value ['']
    # to create a singleton list, instead of empty list, which in later stages
    # would create other problems.
    if values == '':
        return []
    if not isinstance(values, (list, tuple)):
        values = [values]
    for value in values:
        if not isinstance(value, str):
            raise ValueError('Expected str, got {!r}'.format(value))
    return values


@public
def list_of_emails_validator(values):
    """Turn a list of things, or a single thing, into a list of emails."""
    if not isinstance(values, (list, tuple)):
        if getUtility(IEmailValidator).is_valid(values):
            return [values]
        raise ValueError('Bad email address format: {}'.format(values))
    for value in values:
        if not getUtility(IEmailValidator).is_valid(value):
            raise ValueError('Expected email address, got {!r}'.format(value))
    return values


@public
def list_of_emails_or_regexp_validator(values):
    if values == '':
        return []
    if not isinstance(values, (list, tuple)):
        values = [values]
    for value in values:
        email_or_regexp_validator(value)
    return values


@public
def list_of_emails_or_regexp_or_atlist_validator(values):
    if values == '':
        return []
    if not isinstance(values, (list, tuple)):
        values = [values]
    for value in values:
        email_or_regexp_or_atlist_validator(value)
    return values


@public
def integer_ge_zero_validator(value):
    """Validate that the value is a non-negative integer."""
    value = int(value)
    if value < 0:
        raise ValueError('Expected a non-negative integer: {}'.format(value))
    return value


@public
def regexp_validator(value):                           # pragma: missed
    """Validate that the value is a valid regexp."""
    # This code is covered as proven by the fact that the tests
    # test_add_bad_regexp and test_patch_bad_regexp in
    # mailman/rest/tests/test_header_matches.py fail with AssertionError:
    # HTTPError not raised if the code is bypassed, but coverage says it's
    # not covered so work around it for now.
    try:
        re.compile(value)
    except re.error:
        raise ValueError('Expected a valid regexp, got {}'.format(value))
    return value


@public
def email_or_regexp_validator(value):
    """ Email or regular expression validator

    Validate that the value is not null and is a valid regular expression or
     email.
    """
    if not value:
        raise ValueError(
            'Expected a valid email address or regular expression, got empty')
    valid = True
    # A string starts with ^ will be regarded as regex.
    if value.startswith('^'):
        try:
            regexp_validator(value)
        except ValueError:
            valid = False
    else:
        valid = getUtility(IEmailValidator).is_valid(value)

    if valid:
        return value
    else:
        raise ValueError(
            'Expected a valid email address or regular expression,'
            ' got {}'.format(value))


@public
def email_or_regexp_or_atlist_validator(value):
    """ Email or regular expression or @list validator

    Validate that the value is not null and is a valid regular expression or
     email or @fqdn_listname.
    """
    if not value:
        raise ValueError(
            'Expected a valid email address, regular expression or '
            '@fqdn_listname, got empty')
    valid = True
    # A string starts with ^ will be regarded as regex.
    if value.startswith('^'):
        try:
            regexp_validator(value)
        except ValueError:
            valid = False
    # A string starting with @ is a list posting address.
    elif value.startswith('@'):
        # Just validate the posting address as an email.
        valid = getUtility(IEmailValidator).is_valid(value[1:])
    else:
        valid = getUtility(IEmailValidator).is_valid(value)

    if valid:
        return value
    else:
        raise ValueError(
            'Expected a valid email address, regular expression or '
            '@fqdn_listname, got {}'.format(value))


@public
def email_validator(value):
    """Validate the value is a valid email."""
    if not getUtility(IEmailValidator).is_valid(value):
        raise ValueError(
            'Expected a valid email address, got {}'.format(value))
    return value


@public
class Validator:
    """A validator of parameter input."""

    def __init__(self, **kws):
        if '_optional' in kws:
            self._optional = set(kws.pop('_optional'))
        else:
            self._optional = set()
        self._converters = kws.copy()

    def __call__(self, request):
        values = {}
        extras = set()
        cannot_convert = set()
        form_data = {}
        # All keys which show up only once in the form data get a scalar value
        # in the pre-converted dictionary.  All keys which show up more than
        # once get a list value.
        missing = object()
        # Parse the items from request depending on the content type.
        items = get_request_params(request)

        for key, new_value in items.items():
            old_value = form_data.get(key, missing)
            if old_value is missing:
                form_data[key] = new_value
            elif isinstance(old_value, list):
                old_value.append(new_value)
            else:
                form_data[key] = [old_value, new_value]
        # Now do all the conversions.
        for key, value in form_data.items():
            try:
                if (self._converters[key] is as_boolean and
                        isinstance(value, bool)):
                    values[key] = value
                else:
                    values[key] = self._converters[key](value)
            except KeyError:
                extras.add(key)
            except (TypeError, ValueError) as e:
                cannot_convert.add((key, str(e)))
        # Make sure there are no unexpected values.
        if len(extras) != 0:
            extras = COMMASPACE.join(sorted(extras))
            raise ValueError('Unexpected parameters: {}'.format(extras))
            # raise BadRequestError(
            #     description='Unexpected parameters: {}'.format(extras))
        # Make sure everything could be converted.
        if len(cannot_convert) != 0:
            invalid_msg = []
            for param in sorted(cannot_convert):
                invalid_msg.append(
                    'Invalid Parameter "{0}": {1}.'.format(*param))
            raise ValueError(' '.join(invalid_msg))
            # raise InvalidParamError(param_name=bad, msg=invalid_msg)
        # Make sure nothing's missing.
        value_keys = set(values)
        required_keys = set(self._converters) - self._optional
        if value_keys & required_keys != required_keys:
            missing = COMMASPACE.join(sorted(required_keys - value_keys))
            raise ValueError('Missing Parameter: {}'.format(missing))
            # raise MissingParamError(param_name=missing)
        return values

    def update(self, obj, request):
        """Update the object with the values in the request.

        This first validates and converts the attributes in the request, then
        updates the given object with the newly converted values.

        :param obj: The object to update.
        :type obj: object
        :param request: The HTTP request.
        :raises ValueError: if conversion failed for some attribute, including
            if the API version mismatches.
        """
        for key, value in self.__call__(request).items():
            self._converters[key].put(obj, key, value)


@public
class PatchValidator(Validator):
    """Create a special validator for PATCH requests.

    PATCH is different than PUT because with the latter, you're changing the
    entire resource, so all expected attributes must exist.  With the former,
    you're only changing a subset of the attributes, so you only validate the
    ones that exist in the request.
    """

    def __init__(self, request, converters):
        """Create a validator for the PATCH request.

        :param request: The request object, which must have a .PATCH
            attribute.
        :param converters: A mapping of attribute names to the converter for
            that attribute's type.  Generally, this will be a GetterSetter
            instance, but it might be something more specific for custom data
            types (e.g. non-basic types like unicodes).
        :raises UnknownPATCHRequestError: if the request contains an unknown
            attribute, i.e. one that is not in the `attributes` mapping.
        :raises ReadOnlyPATCHRequest: if the requests contains an attribute
            that is defined as read-only.
        """
        validationators = {}
        # Parse the items from request depending on the content type.
        items = get_request_params(request)
        for attribute in items:
            if attribute not in converters:
                raise UnknownPATCHRequestError(attribute)
            if converters[attribute].decoder is None:
                raise ReadOnlyPATCHRequestError(attribute)
            validationators[attribute] = converters[attribute]
        super().__init__(**validationators)
