# Copyright (C) 2014-2023 by the Free Software Foundation, Inc.
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

"""Test the decorate handler."""

import os
import re
import email
import unittest

from importlib.resources import open_binary as resource_open
from mailman.app.lifecycle import create_list
from mailman.config import config
from mailman.email.message import Message
from mailman.handlers import decorate
from mailman.interfaces.archiver import IArchiver
from mailman.interfaces.member import MemberRole
from mailman.interfaces.template import ITemplateManager
from mailman.interfaces.usermanager import IUserManager
from mailman.model.member import Member
from mailman.model.preferences import Preferences
from mailman.testing.helpers import (
    configuration,
    LogFileMark,
    specialized_message_from_string as mfs,
)
from mailman.testing.layers import ConfigLayer
from tempfile import TemporaryDirectory
from zope.component import getUtility
from zope.interface import implementer


@implementer(IArchiver)
class TestArchiver:
    """A test archiver"""

    name = 'testarchiver'
    is_enabled = False

    @staticmethod
    def permalink(mlist, msg):
        return 'http://example.com/link_to_message'


@implementer(IArchiver)
class BrokenArchiver:
    name = 'broken'
    is_enabled = True

    @staticmethod
    def permalink(mlist, msg):
        raise RuntimeError('Cannot get permalink')


class TestDecorate(unittest.TestCase):
    """Test the cook_headers handler."""

    layer = ConfigLayer

    def setUp(self):
        self._mlist = create_list('ant@example.com')
        self._msg = mfs("""\
To: ant@example.com
From: aperson@example.com
Message-ID: <alpha>
Content-Type: text/plain;

This is a test message.
""")
        self._mpm = mfs("""\
To: ant@example.com
From: aperson@example.com
Message-ID: <alpha>
Content-Type: multipart/mixed; boundary="aaaaaa"

--aaaaaa
Content-Type: text/plain;

This is a test message.
--aaaaaa
Content-Type: text/plain;

This is part 2
--aaaaaa--
""")
        self._mpa = mfs("""\
To: ant@example.com
From: aperson@example.com
Message-ID: <alpha>
Content-Type: multipart/alternative; boundary="aaaaaa"

--aaaaaa
Content-Type: text/plain;

This is a test message.
--aaaaaa
Content-Type: text/html;

This is a test message.
--aaaaaa--
""")
        # We need to get this message the way lmtp runner gets it.
        with resource_open(
                'mailman.handlers.tests.data',
                'html_non_ascii.eml') as fp:
            self._htmlna = email.message_from_binary_file(fp, Message)
        temporary_dir = TemporaryDirectory()
        self.addCleanup(temporary_dir.cleanup)
        template_dir = temporary_dir.name
        config.push('archiver', """\
        [paths.testing]
        template_dir: {}
        [archiver.testarchiver]
        class: mailman.handlers.tests.test_decorate.TestArchiver
        enable: yes
        """.format(template_dir))
        self.addCleanup(config.pop, 'archiver')

    def test_decorate_footer_with_archive_url(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('${testarchiver_url}', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        self._mlist.preferred_language = 'en'
        decorate.process(self._mlist, self._msg, {})
        self.assertIn('http://example.com/link_to_message',
                      self._msg.as_string())

    def test_trailing_space_not_removed(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('-- \r\nMy sig', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        self._mlist.preferred_language = 'en'
        decorate.process(self._mlist, self._msg, {})
        self.assertTrue(self._msg.as_string().endswith('-- \nMy sig\n'))

    def test_decorate_member_as_address(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('$member', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        self._mlist.preferred_language = 'en'
        address = getUtility(IUserManager).create_address(
            'aperson@example.com', 'Anne Person')
        member = Member(MemberRole.member, self._mlist.list_id, address)
        member.preferences = Preferences()
        member.preferences.preferred_language = 'en'
        msgdata = dict(member=member)
        decorate.process(self._mlist, self._msg, msgdata)
        self.assertIn('Anne Person <aperson@example.com>',
                      self._msg.as_string())

    def test_decorate_member_as_user(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('$member', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        self._mlist.preferred_language = 'en'
        user = getUtility(IUserManager).make_user(
            'aperson@example.com', 'Anne Person')
        member = Member(MemberRole.member, self._mlist.list_id, user)
        member.preferences = Preferences()
        member.preferences.preferred_language = 'en'
        msgdata = dict(member=member)
        decorate.process(self._mlist, self._msg, msgdata)
        self.assertIn('Anne Person <aperson@example.com>',
                      self._msg.as_string())

    def test_decorate_user_name_or_address_as_user_name(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('$user_name_or_address', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        self._mlist.preferred_language = 'en'
        user = getUtility(IUserManager).make_user(
            'aperson@example.com', 'Anne Person')
        member = Member(MemberRole.member, self._mlist.list_id, user)
        member.preferences = Preferences()
        member.preferences.preferred_language = 'en'
        msgdata = dict(member=member)
        decorate.process(self._mlist, self._msg, msgdata)
        self.assertIn('\nAnne Person',
                      self._msg.as_string())

    def test_decorate_user_name_or_address_as_address(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('$user_name_or_address', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        self._mlist.preferred_language = 'en'
        user = getUtility(IUserManager).make_user(
            'aperson@example.com')
        member = Member(MemberRole.member, self._mlist.list_id, user)
        member.preferences = Preferences()
        member.preferences.preferred_language = 'en'
        msgdata = dict(member=member)
        decorate.process(self._mlist, self._msg, msgdata)
        self.assertIn('\naperson@example.com',
                      self._msg.as_string())

    def test_decorate_user_name_or_email_as_user_name(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('$user_name_or_email', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        self._mlist.preferred_language = 'en'
        user = getUtility(IUserManager).make_user(
            'aperson@example.com', 'Anne Person')
        member = Member(MemberRole.member, self._mlist.list_id, user)
        member.preferences = Preferences()
        member.preferences.preferred_language = 'en'
        msgdata = dict(member=member)
        decorate.process(self._mlist, self._msg, msgdata)
        self.assertIn('\nAnne Person',
                      self._msg.as_string())

    def test_decorate_user_name_or_email_as_address(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('$user_name_or_email', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        self._mlist.preferred_language = 'en'
        user = getUtility(IUserManager).make_user(
            'aperson@example.com')
        member = Member(MemberRole.member, self._mlist.list_id, user)
        member.preferences = Preferences()
        member.preferences.preferred_language = 'en'
        msgdata = dict(member=member)
        decorate.process(self._mlist, self._msg, msgdata)
        self.assertIn('\naperson@example.com',
                      self._msg.as_string())

    def test_decorate_header_footer_with_bad_character_mpa(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        header_path = os.path.join(site_dir, 'myheader.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('Foot\xe9r:', file=fp)
        with open(header_path, 'w', encoding='utf-8') as fp:
            print('Head\xe9r:', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        getUtility(ITemplateManager).set(
            'list:member:regular:header', None, 'mailman:///myheader.txt')
        self._mlist.preferred_language = 'en'
        decorate.process(self._mlist, self._mpa, {})
        self.assertIn('Head?r:', self._mpa.get_payload(0).as_string())
        self.assertIn('Foot?r:', self._mpa.get_payload(2).as_string())

    def test_decorate_header_footer_with_bad_character_mpm(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        header_path = os.path.join(site_dir, 'myheader.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('Foot\xe9r:', file=fp)
        with open(header_path, 'w', encoding='utf-8') as fp:
            print('Head\xe9r:', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        getUtility(ITemplateManager).set(
            'list:member:regular:header', None, 'mailman:///myheader.txt')
        self._mlist.preferred_language = 'en'
        decorate.process(self._mlist, self._mpm, {})
        self.assertIn('Head?r:', self._mpm.get_payload(0).as_string())
        self.assertIn('Foot?r:', self._mpm.get_payload(3).as_string())

    def test_decorate_html_nonascii_flattened_as_bytes(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        header_path = os.path.join(site_dir, 'myheader.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('Footer:', file=fp)
        with open(header_path, 'w', encoding='utf-8') as fp:
            print('Header:', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        getUtility(ITemplateManager).set(
            'list:member:regular:header', None, 'mailman:///myheader.txt')
        self._mlist.preferred_language = 'en'
        decorate.process(self._mlist, self._htmlna, {})
        # This should raise no exception
        bytes = self._htmlna.as_bytes()
        self.assertIn('Header:', self._htmlna.get_payload(0).as_string())
        self.assertIn('Footer:', self._htmlna.get_payload(2).as_string())
        self.assertRegex(bytes, b"""\
To: ant@example.com
From: aperson@example.com
Message-ID: <alpha>
Content-Type: multipart/mixed; boundary="([^"]*)"

--\\1
Content-Type: text/plain; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: inline

Header:

--\\1
Content-Type: text/html; charset=UTF-8
Content-Transfer-Encoding: 8bit

<html>
  <head>

    <meta http-equiv="content-type" content="text/html; charset=UTF-8">
  </head>
  <body>
    <p>HTML form\xc3\xa1t zpr\xc3\xa1vy</p>
    <p>Hahaha<br>
    </p>
  </body>
</html>

--\\1
Content-Type: text/plain; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: inline

Footer:

--\\1--
""")

    def test_decorate_html_nonascii_flattened_as_string(self):
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        header_path = os.path.join(site_dir, 'myheader.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('Footer:', file=fp)
        with open(header_path, 'w', encoding='utf-8') as fp:
            print('Header:', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', None, 'mailman:///myfooter.txt')
        getUtility(ITemplateManager).set(
            'list:member:regular:header', None, 'mailman:///myheader.txt')
        self._mlist.preferred_language = 'en'
        decorate.process(self._mlist, self._htmlna, {})
        self.assertIn('Header:', self._htmlna.get_payload(0).as_string())
        self.assertIn('Footer:', self._htmlna.get_payload(2).as_string())
        # there should be no non-ascii in the as_string() rendering.
        self.assertEqual('', re.sub(r'[\x00-\x7f]', '',
                         self._htmlna.as_string()))

    def test_list_id_allowed_in_template_uri(self):
        # Issue #196 - allow the list_id in the template uri expansion.
        list_dir = os.path.join(
            config.TEMPLATE_DIR, 'lists', 'ant.example.com', 'en')
        os.makedirs(list_dir)
        footer_path = os.path.join(list_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('${testarchiver_url}', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', self._mlist.list_id,
            'mailman:///${list_id}/myfooter.txt')
        self._mlist.preferred_language = 'en'
        decorate.process(self._mlist, self._msg, {})
        self.assertIn('http://example.com/link_to_message',
                      self._msg.as_string())

    def test_list_id_and_language_code_allowed_in_template_uri(self):
        # Issue #196 - allow the list_id in the template uri expansion.
        list_dir = os.path.join(
            config.TEMPLATE_DIR, 'lists', 'ant.example.com', 'it')
        os.makedirs(list_dir)
        footer_path = os.path.join(list_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('${testarchiver_url}', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', self._mlist.list_id,
            'mailman:///${list_id}/${language}/myfooter.txt')
        self._mlist.preferred_language = 'it'
        with configuration('language.it', charset='iso-8859-1'):
            # Default charset='utf-8' base64 encodes the message body.
            decorate.process(self._mlist, self._msg, {})
        self.assertIn('http://example.com/link_to_message',
                      self._msg.as_string())


class TestBrokenPermalink(unittest.TestCase):
    layer = ConfigLayer

    def setUp(self):
        self._mlist = create_list('ant@example.com')
        self._msg = mfs("""\
To: ant@example.com
From: aperson@example.com
Message-ID: <alpha>
Content-Type: text/plain;

This is a test message.
""")
        temporary_dir = TemporaryDirectory()
        self.addCleanup(temporary_dir.cleanup)
        template_dir = temporary_dir.name
        config.push('archiver', """\
        [paths.testing]
        template_dir: {}
        [archiver.testarchiver]
        class: mailman.handlers.tests.test_decorate.BrokenArchiver
        enable: yes
        """.format(template_dir))
        self.addCleanup(config.pop, 'archiver')

    def test_broken_permalink(self):
        # GL issue #208 - IArchive messages raise exceptions, breaking the
        # rfc-2369 handler and shunting messages.
        site_dir = os.path.join(config.TEMPLATE_DIR, 'site', 'en')
        os.makedirs(site_dir)
        footer_path = os.path.join(site_dir, 'myfooter.txt')
        with open(footer_path, 'w', encoding='utf-8') as fp:
            print('${broken_url}', file=fp)
        getUtility(ITemplateManager).set(
            'list:member:regular:footer', self._mlist.list_id,
            'mailman:///myfooter.txt')
        self._mlist.preferred_language = 'en'
        mark = LogFileMark('mailman.archiver')
        decorate.process(self._mlist, self._msg, {})
        log_messages = mark.read()
        self.assertNotIn('http:', self._msg.as_string())
        self.assertIn('Exception in "broken" archiver', log_messages)
        self.assertIn('RuntimeError: Cannot get permalink', log_messages)
