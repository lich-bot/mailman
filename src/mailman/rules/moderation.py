# Copyright (C) 2007-2023 by the Free Software Foundation, Inc.
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

"""Membership related rules."""

import re
import logging

from contextlib import suppress
from mailman.core.i18n import _
from mailman.interfaces.action import Action
from mailman.interfaces.address import InvalidEmailAddressError
from mailman.interfaces.bans import IBanManager
from mailman.interfaces.listmanager import IListManager
from mailman.interfaces.member import MemberRole
from mailman.interfaces.rules import IRule
from mailman.interfaces.usermanager import IUserManager
from public import public
from zope.component import getUtility
from zope.interface import implementer


log = logging.getLogger('mailman.error')


def _find_sender_member(mlist, msg):
    # For every sender email in the message, try to find a member associated
    # with that email.
    #
    # First, check the sender email directly.  If it's a member, we're done.
    #
    # Next, check to see if the sender email is linked to an existing user,
    # and if so, check to see if any of the addresses linked to that user is a
    # member.
    user_manager = getUtility(IUserManager)
    for sender in msg.senders:
        member = mlist.members.get_member(sender)
        if member is not None:
            return member
        user = user_manager.get_user(sender)
        if user is not None:
            for address in user.addresses:
                member = mlist.members.get_member(address.email)
                if member is not None:
                    return member
    return None


@public
@implementer(IRule)
class MemberModeration:
    """The member moderation rule."""

    name = 'member-moderation'
    description = _('Match messages sent by moderated members.')
    record = True

    def check(self, mlist, msg, msgdata):
        """See `IRule`."""
        # The MemberModeration rule misses unconditionally if any of the
        # senders are banned.
        ban_manager = IBanManager(mlist)
        for sender in msg.senders:
            if ban_manager.is_banned(sender):
                return False
        member = _find_sender_member(mlist, msg)
        if member is None:
            return False
        action = (mlist.default_member_action
                  if member.moderation_action is None
                  else member.moderation_action)
        if action is Action.defer:
            # The regular moderation rules apply.
            return False
        elif action is not None:
            # We must stringify the moderation action so that it can be
            # stored in the pending request table.
            msgdata['member_moderation_action'] = action.name
            msgdata['moderation_sender'] = sender
            with _.defer_translation():
                # This will be translated at the point of use.
                msgdata.setdefault('moderation_reasons', []).append(
                    _('The message comes from a moderated member'))
            return True
        # The sender is not a member so this rule does not match.
        return False


def _do_action(msgdata, action, sender):
    if action is Action.defer:
        # The regular moderation rules apply.
        return False
    else:
        # We must stringify the moderation action so that it can be
        # stored in the pending request table.
        with _.defer_translation():
            # This will be translated at the point of use.
            reason = _('The message is not from a list member')
        _record_action(msgdata, action.name, sender, reason)
        return True


def _record_action(msgdata, action, sender, reason):
    msgdata['member_moderation_action'] = action
    msgdata['moderation_sender'] = sender
    msgdata.setdefault('moderation_reasons', []).append(reason)


@public
@implementer(IRule)
class NonmemberModeration:
    """The nonmember moderation rule."""

    name = 'nonmember-moderation'
    description = _('Match messages sent by nonmembers.')
    record = True

    def check(self, mlist, msg, msgdata):
        """See `IRule`."""
        ban_manager = IBanManager(mlist)
        user_manager = getUtility(IUserManager)
        # The NonmemberModeration rule misses unconditionally if any of the
        # senders are banned.
        for sender in msg.senders:
            if ban_manager.is_banned(sender):
                return False
        if len(msg.senders) == 0:
            with _.defer_translation():
                # This will be translated at the point of use.
                reason = _('No sender was found in the message.')
            _record_action(
                msgdata, mlist.default_nonmember_action, 'No sender', reason)
            return True
        # Every sender email must be a member or nonmember directly.  If it is
        # neither, make the email a nonmembers.
        for sender in msg.senders:
            if (mlist.members.get_member(sender) is None
                    and mlist.nonmembers.get_member(sender) is None):   # noqa
                # The email must already be registered, since this happens in
                # the incoming runner itself.
                address = user_manager.get_address(sender)
                assert address is not None, (
                    'Posting address is not registered: {}'.format(sender))
                with suppress(InvalidEmailAddressError):
                    # This might be a list posting address in Reply-To: or
                    # some other invalid address.  In any case, ignore it.
                    mlist.subscribe(address, MemberRole.nonmember)
        # If this message is gated from usenet the rule misses.
        if msgdata.get('fromusenet', False):
            return False
        # Check to see if any of the sender emails is already a member.  If
        # so, then this rule misses.
        member = _find_sender_member(mlist, msg)
        if member is not None:
            return False
        # Do nonmember moderation check.
        for sender in msg.senders:
            nonmember = mlist.nonmembers.get_member(sender)
            assert nonmember is not None, (
                "sender {} didn't get subscribed as a nonmember".format(sender)
                )
            action = nonmember.moderation_action
            if action is not None:
                # Do this first so a specific nonmember.moderation_action
                # trumps the legacy settings.
                return _do_action(msgdata, action, sender)
            # nonmember has no moderation action so check the
            # '*_these_nonmembers' properties.  XXX These are
            # legacy attributes from MM2.1; their database type is 'pickle' and
            # they should eventually get replaced.
            for action_name in ('accept', 'hold', 'reject', 'discard'):
                legacy_attribute_name = '{}_these_nonmembers'.format(
                    action_name)
                checklist = getattr(mlist, legacy_attribute_name)
                for addr in checklist:
                    try:
                        if ((addr.startswith('^') and re.match(addr, sender))
                                or _at_list(mlist, action_name, addr, sender)
                                or addr == sender):     # noqa: W503
                            # accept_these_nonmembers should 'defer'.
                            if action_name == 'accept':
                                return False
                            with _.defer_translation():
                                # This will be translated at the point of use.
                                reason = (_(
                                    'The sender is in the nonmember {} list'
                                    ), action_name)
                            _record_action(msgdata,
                                           action_name, sender, reason)
                            return True
                    except re.error as error:
                        # The pattern is a malformed regular expression.
                        # Log and continue with the next pattern.
                        log.error("Invalid regexp '{}' in "
                                  '{}_these_nonmembers for {}: {}'
                                  .format(addr, action_name, mlist.list_id,
                                          error.msg))
                        continue
            # No nonmember.moderation.action and no legacy hits for this
            # sender - continue
        action = mlist.default_nonmember_action
        return _do_action(msgdata, action, sender)


def _at_list(mlist, action_name, addr, sender):
    # Check for the @fqdn_listname in accept_these_nonmembers.
    if action_name != 'accept':
        # at_list is only for accept_these_nonmembers.
        return False
    if not addr.startswith('@'):
        # Not an at_list
        return False
    if addr[1:] == mlist.fqdn_listname:
        msg = "Can't reference own list."
    else:
        olist = getUtility(IListManager).get_by_fqdn(addr[1:])
        if olist is None:
            msg = 'No such list'
        else:
            if sender in [member.address.email for
                          member in olist.members.members]:
                return True
            else:
                return False
    log.error("Bad at_list '{}' in "
              '{}_these_nonmembers for {}: {}'
              .format(addr, action_name, mlist.list_id, msg))
    return False
