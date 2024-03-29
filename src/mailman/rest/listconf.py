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

"""Mailing list configuration via REST API."""

from lazr.config import as_boolean, as_timedelta
from mailman.config import config
from mailman.interfaces.action import Action, FilterAction
from mailman.interfaces.archiver import ArchivePolicy
from mailman.interfaces.autorespond import ResponseAction
from mailman.interfaces.bounce import UnrecognizedBounceDisposition
from mailman.interfaces.digests import DigestFrequency
from mailman.interfaces.mailinglist import (
    ArchiveRenderingMode,
    DMARCMitigateAction,
    IAcceptableAliasSet,
    IMailingList,
    Personalization,
    ReplyToMunging,
    SubscriptionPolicy,
)
from mailman.interfaces.nntp import NewsgroupModeration
from mailman.interfaces.template import ITemplateManager
from mailman.model.roster import RosterVisibility
from mailman.rest.helpers import (
    bad_request,
    etag,
    GetterSetter,
    no_content,
    not_found,
    okay,
)
from mailman.rest.validator import (
    enum_validator,
    integer_ge_zero_validator,
    language_validator,
    list_of_emails_or_regexp_or_atlist_validator,
    list_of_emails_or_regexp_validator,
    list_of_strings_validator,
    PatchValidator,
    ReadOnlyPATCHRequestError,
    UnknownPATCHRequestError,
    Validator,
)
from public import public
from zope.component import getUtility


class AcceptableAliases(GetterSetter):
    """Resource for the acceptable aliases of a mailing list."""

    def get(self, mlist, attribute):
        """Return the mailing list's acceptable aliases."""
        assert attribute == 'acceptable_aliases', (
            'Unexpected attribute: {}'.format(attribute))   # pragma: nocover
        aliases = IAcceptableAliasSet(mlist)
        return sorted(aliases.aliases)

    def put(self, mlist, attribute, value):
        """Change the acceptable aliases.

        Because this is a PUT operation, all previous aliases are cleared
        first.  Thus, this is an overwrite.  The keys in the request are
        ignored.
        """
        assert attribute == 'acceptable_aliases', (
            'Unexpected attribute: {}'.format(attribute))   # pragma: nocover
        alias_set = IAcceptableAliasSet(mlist)
        alias_set.clear()
        for alias in value:
            alias_set.add(alias)


class LanguageGetterSetter(GetterSetter):

    def get(self, mlist, attribute):
        """Return the language code of the preferred language."""
        assert attribute == 'preferred_language', (
            'Unexpected attribute: {}'.format(attribute))   # pragma: nocover
        return mlist.preferred_language.code

    def put(self, mlist, attribute, value):
        """Set the preferred language of the MailingList."""
        assert attribute == 'preferred_language', (
            'Unexpected attribute: {}'.format(attribute))   # pragma: nocover

        # We can just set the language code as value since the setter takes
        # cares of converting the language code to Language model.
        mlist.preferred_language = value


TEMPLATE_ATTRIBUTES = dict(
    digest_footer_uri='list:digest:footer',
    digest_header_uri='list:digest:header',
    footer_uri='list:regular:footer',
    goodbye_message_uri='list:user:notice:goodbye',
    header_uri='list:regular:header',
    welcome_message_uri='list:user:notice:welcome',
    )


class URIAttributeMapper(GetterSetter):
    """Map old IMailingList uri attributes to the new template manager."""

    def get(self, obj, attribute):
        assert IMailingList.providedBy(obj), obj
        template_name = TEMPLATE_ATTRIBUTES[attribute]
        template = getUtility(ITemplateManager).raw(template_name, obj.list_id)
        return '' if template is None else template.uri

    def put(self, obj, attribute, value):
        assert IMailingList.providedBy(obj), obj
        template_name = TEMPLATE_ATTRIBUTES[attribute]
        getUtility(ITemplateManager).set(template_name, obj.list_id, value)


# Additional validators for converting from web request strings to internal
# data types.  See below for details.

def pipeline_validator(pipeline_name):
    """Convert the pipeline name to a string, but only if it's known."""
    if pipeline_name in config.pipelines:
        return pipeline_name
    raise ValueError('Unknown pipeline: {}'.format(pipeline_name))


def password_bytes_validator(value):
    if value is None or isinstance(value, bytes):
        return value
    return config.password_context.encrypt(value).encode('utf-8')


def no_newlines_validator(value):
    value = str(value)
    if '\n' in value:
        raise ValueError('This value must be a single line: {}'.format(value))
    return value


# This is the list of IMailingList attributes that are exposed through the
# REST API.  The values of the keys are the GetterSetter instance holding the
# decoder used to convert the web request string to an internally valid value.
# The instance also contains the get() and put() methods used to retrieve and
# set the attribute values.  Its .decoder attribute will be None for read-only
# attributes.
#
# The decoder must either return the internal value or raise a ValueError if
# the conversion failed (e.g. trying to turn 'Nope' into a boolean).
#
# Many internal value types can be automatically JSON encoded, but see
# mailman.rest.helpers.ExtendedEncoder for specializations of certain types
# (e.g. datetimes, timedeltas, enums).

ATTRIBUTES = dict(
    acceptable_aliases=AcceptableAliases(list_of_strings_validator),
    accept_these_nonmembers=GetterSetter(
        list_of_emails_or_regexp_or_atlist_validator),
    admin_immed_notify=GetterSetter(as_boolean),
    admin_notify_mchanges=GetterSetter(as_boolean),
    administrivia=GetterSetter(as_boolean),
    advertised=GetterSetter(as_boolean),
    allow_list_posts=GetterSetter(as_boolean),
    anonymous_list=GetterSetter(as_boolean),
    archive_policy=GetterSetter(enum_validator(ArchivePolicy)),
    archive_rendering_mode=GetterSetter(enum_validator(ArchiveRenderingMode)),
    autorespond_owner=GetterSetter(enum_validator(ResponseAction)),
    autorespond_postings=GetterSetter(enum_validator(ResponseAction)),
    autorespond_requests=GetterSetter(enum_validator(ResponseAction)),
    autoresponse_grace_period=GetterSetter(as_timedelta),
    autoresponse_owner_text=GetterSetter(str),
    autoresponse_postings_text=GetterSetter(str),
    autoresponse_request_text=GetterSetter(str),
    bounces_address=GetterSetter(None),
    bounce_info_stale_after=GetterSetter(as_timedelta),
    bounce_notify_owner_on_bounce_increment=GetterSetter(as_boolean),
    bounce_notify_owner_on_disable=GetterSetter(as_boolean),
    bounce_notify_owner_on_removal=GetterSetter(as_boolean),
    bounce_score_threshold=GetterSetter(integer_ge_zero_validator),
    bounce_you_are_disabled_warnings=GetterSetter(integer_ge_zero_validator),
    bounce_you_are_disabled_warnings_interval=GetterSetter(
        as_timedelta),
    collapse_alternatives=GetterSetter(as_boolean),
    convert_html_to_plaintext=GetterSetter(as_boolean),
    created_at=GetterSetter(None),
    default_member_action=GetterSetter(enum_validator(Action)),
    default_nonmember_action=GetterSetter(enum_validator(Action)),
    description=GetterSetter(no_newlines_validator),
    digest_last_sent_at=GetterSetter(None),
    digest_send_periodic=GetterSetter(as_boolean),
    digest_size_threshold=GetterSetter(float),
    digest_volume_frequency=GetterSetter(enum_validator(DigestFrequency)),
    digests_enabled=GetterSetter(as_boolean),
    display_name=GetterSetter(str),
    discard_these_nonmembers=GetterSetter(list_of_emails_or_regexp_validator),
    dmarc_mitigate_action=GetterSetter(enum_validator(DMARCMitigateAction)),
    dmarc_mitigate_unconditionally=GetterSetter(as_boolean),
    dmarc_addresses=GetterSetter(list_of_emails_or_regexp_validator),
    dmarc_moderation_notice=GetterSetter(str),
    dmarc_wrapped_message_text=GetterSetter(str),
    emergency=GetterSetter(as_boolean),
    filter_action=GetterSetter(enum_validator(FilterAction)),
    filter_content=GetterSetter(as_boolean),
    filter_extensions=GetterSetter(list_of_strings_validator),
    filter_types=GetterSetter(list_of_strings_validator),
    first_strip_reply_to=GetterSetter(as_boolean),
    forward_unrecognized_bounces_to=GetterSetter(
        enum_validator(UnrecognizedBounceDisposition)),
    fqdn_listname=GetterSetter(None),
    gateway_to_mail=GetterSetter(as_boolean),
    gateway_to_news=GetterSetter(as_boolean),
    hold_these_nonmembers=GetterSetter(list_of_emails_or_regexp_validator),
    include_rfc2369_headers=GetterSetter(as_boolean),
    info=GetterSetter(str),
    join_address=GetterSetter(None),
    last_post_at=GetterSetter(None),
    leave_address=GetterSetter(None),
    linked_newsgroup=GetterSetter(str),
    list_name=GetterSetter(None),
    mail_host=GetterSetter(None),
    max_message_size=GetterSetter(integer_ge_zero_validator),
    max_num_recipients=GetterSetter(integer_ge_zero_validator),
    max_days_to_hold=GetterSetter(integer_ge_zero_validator),
    member_roster_visibility=GetterSetter(enum_validator(RosterVisibility)),
    moderator_password=GetterSetter(password_bytes_validator),
    newsgroup_moderation=GetterSetter(enum_validator(NewsgroupModeration)),
    next_digest_number=GetterSetter(None),
    nntp_prefix_subject_too=GetterSetter(as_boolean),
    no_reply_address=GetterSetter(None),
    owner_address=GetterSetter(None),
    pass_types=GetterSetter(list_of_strings_validator),
    pass_extensions=GetterSetter(list_of_strings_validator),
    personalize=GetterSetter(enum_validator(Personalization)),
    post_id=GetterSetter(None),
    posting_address=GetterSetter(None),
    posting_pipeline=GetterSetter(pipeline_validator),
    preferred_language=LanguageGetterSetter(language_validator),
    process_bounces=GetterSetter(as_boolean),
    reject_these_nonmembers=GetterSetter(list_of_emails_or_regexp_validator),
    reply_goes_to_list=GetterSetter(enum_validator(ReplyToMunging)),
    reply_to_address=GetterSetter(str),
    request_address=GetterSetter(None),
    require_explicit_destination=GetterSetter(as_boolean),
    respond_to_post_requests=GetterSetter(as_boolean),
    send_goodbye_message=GetterSetter(as_boolean),
    send_welcome_message=GetterSetter(as_boolean),
    subject_prefix=GetterSetter(str),
    subscription_policy=GetterSetter(enum_validator(SubscriptionPolicy)),
    unsubscription_policy=GetterSetter(enum_validator(SubscriptionPolicy)),
    usenet_watermark=GetterSetter(None),
    volume=GetterSetter(None)
    )


VALIDATORS = ATTRIBUTES.copy()
for attribute, gettersetter in list(VALIDATORS.items()):
    if gettersetter.decoder is None:
        del VALIDATORS[attribute]


def api_attributes(api):
    # The list of readable attributes is different depending on the API being
    # requested.  Specifically, in API 3.0 the templates are exposed as list
    # attributes, although we map them to templates.  In API 3.1 and beyond,
    # only the template manager API can be used for these.
    attributes = ATTRIBUTES.copy()
    if api.version_info == (3, 0):
        attributes.update({
            attribute: URIAttributeMapper(str)
            for attribute in TEMPLATE_ATTRIBUTES
            })
    return attributes


@public
class ListConfiguration:
    """A mailing list configuration resource."""

    def __init__(self, mailing_list, attribute):
        self._mlist = mailing_list
        self._attribute = attribute

    def on_get(self, request, response):
        """Get a mailing list configuration."""
        resource = {}
        attributes = api_attributes(self.api)
        if self._attribute is None:
            # This is a request for all the mailing list's configuration
            # variables.  Return all readable attributes.
            for attribute, getter in attributes.items():
                value = getter.get(self._mlist, attribute)
                resource[attribute] = value
        elif self._attribute in attributes:
            # This is a request for a specific attribute.
            value = attributes[self._attribute].get(
                self._mlist, self._attribute)
            resource[self._attribute] = value
        else:
            # This is a request for a specific, nonexistent attribute.
            not_found(
                response, 'Unknown attribute: {}'.format(self._attribute))
            return
        okay(response, etag(resource))

    def on_put(self, request, response):
        """Set a mailing list configuration."""
        attribute = self._attribute
        # The list of required attributes differs between API version.  For
        # backward compatibility, in API 3.0 all of the *_uri attributes are
        # optional.  In API 3.1 none of these are allowed since they are
        # handled by the template manager API.
        validators = VALIDATORS.copy()
        attributes = api_attributes(self.api)
        if self.api.version_info == (3, 0):
            validators.update({
                attribute: URIAttributeMapper(str)
                for attribute in TEMPLATE_ATTRIBUTES
                })
            validators['_optional'] = TEMPLATE_ATTRIBUTES.keys()
        if attribute is None:
            # This is a request to update all the list's writable
            # configuration variables.  All must be provided in the request.
            validator = Validator(**validators)
            try:
                validator.update(self._mlist, request)
            except ValueError as error:
                # Unlike the case where we're PUTting to a specific
                # configuration sub-resource, if we're PUTting to the list's
                # entire configuration, but the request has a bogus attribute,
                # the entire request is considered bad.  We can also get here
                # if one of the attributes is read-only.  The error will
                # contain sufficient details, so just return it as the reason.
                bad_request(response, str(error))
                return
        elif attribute not in attributes:
            # Here we're PUTting to a specific resource, but that attribute is
            # bogus so the URL is considered pointing to a missing resource.
            not_found(response, 'Unknown attribute: {}'.format(attribute))
            return
        elif attributes[attribute].decoder is None:
            bad_request(
                response, 'Read-only attribute: {}'.format(attribute))
            return
        else:
            # We're PUTting to a specific configuration sub-resource.
            validator = Validator(**{attribute: validators[attribute]})
            try:
                validator.update(self._mlist, request)
            except ValueError as error:
                bad_request(response, str(error))
                return
        no_content(response)

    def on_patch(self, request, response):
        """Patch the configuration (i.e. partial update)."""
        attributes = api_attributes(self.api)
        if self._attribute is None:
            # We're PATCHing one or more of the attributes on the list's
            # configuration resource, so all the writable attributes are valid
            # candidates for updating.
            converters = attributes
        else:
            # We're PATCHing a specific list configuration attribute
            # sub-resource.  Because the request data must be a dictionary, we
            # restrict it to containing only a single key, which must match
            # the attribute name.  First, check for any extra attributes in
            # the request.
            keys = [key for key, value in request.params.items()]
            if len(keys) > 1:
                bad_request(response, 'Expected 1 attribute, got {}'.format(
                    len(keys)))
                return
            converter = attributes.get(self._attribute)
            if converter is None:
                # This is the case where the URL points to a nonexisting list
                # configuration attribute sub-resource.
                not_found(response, 'Unknown attribute: {}'.format(
                    self._attribute))
                return
            converters = {self._attribute: converter}
        try:
            validator = PatchValidator(request, converters)
        except UnknownPATCHRequestError as error:
            # This is the case where the URL points to the list's entire
            # configuration resource, but the request dictionary contains a
            # nonexistent attribute.
            bad_request(
                response, 'Unknown attribute: {}'.format(error.attribute))
            return
        except ReadOnlyPATCHRequestError as error:
            bad_request(
                response, 'Read-only attribute: {}'.format(error.attribute))
            return
        try:
            validator.update(self._mlist, request)
        except ValueError as error:
            bad_request(response, str(error))
        else:
            no_content(response)

    def on_delete(self, request, response):
        if self._attribute is None:
            bad_request(
                response, 'Cannot delete the list configuration itself')
            return
        if self._attribute not in VALIDATORS:
            bad_request(
                response, 'Read-only attribute: {}'.format(self._attribute))
            return
        # This kind of sucks because it doesn't scale if the list of attributes
        # which can be deleted grows.  So if we get too many we'll have to use
        # a lookup table.  For now, this is good enough.
        if self._attribute != 'acceptable_aliases':
            bad_request(
                response, 'Attribute cannot be DELETEd: {}'.format(
                    self._attribute))
            return
        IAcceptableAliasSet(self._mlist).clear()
        no_content(response)
