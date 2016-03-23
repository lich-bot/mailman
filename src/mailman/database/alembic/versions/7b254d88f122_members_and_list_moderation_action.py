"""Members and list moderation action

Revision ID: 7b254d88f122
Revises: d4fbb4fd34ca
Create Date: 2016-02-10 11:31:04.233619

This is a data-only migration. If a member has the same moderation action as
the mailing list's default, then set its moderation action to None and use the
fallback to the list's default.

"""

# revision identifiers, used by Alembic.
revision = '7b254d88f122'
down_revision = 'd4fbb4fd34ca'

import sqlalchemy as sa
from alembic import op
from mailman.database.types import Enum
from mailman.interfaces.action import Action
from mailman.interfaces.member import MemberRole

mailinglist_table = sa.sql.table(
    'mailinglist',
    sa.sql.column('id', sa.Integer),
    sa.sql.column('list_id', sa.Unicode),
    sa.sql.column('default_member_action', Enum(Action)),
    sa.sql.column('default_nonmember_action', Enum(Action)),
    )

member_table = sa.sql.table(
    'member',
    sa.sql.column('id', sa.Integer),
    sa.sql.column('list_id', sa.Unicode),
    sa.sql.column('role', Enum(MemberRole)),
    sa.sql.column('moderation_action', Enum(Action)),
    )

# This migration only considers members and nonmembers.
members_query = member_table.select().where(sa.or_(
    member_table.c.role == MemberRole.member,
    member_table.c.role == MemberRole.nonmember,
    ))

DEFAULT_ACTION_CACHE = {}

def _get_default_action(connection, member):
    list_id = member['list_id']
    propname = 'default_{}_action'.format(member['role'].name)
    try:
        action = DEFAULT_ACTION_CACHE[list_id][propname]
    except KeyError:
        mailing_list = connection.execute(mailinglist_table.select().where(
            mailinglist_table.c.list_id == list_id)).fetchone()
        action = mailing_list[propname]
        if list_id not in DEFAULT_ACTION_CACHE:
            DEFAULT_ACTION_CACHE[list_id] = {}
        DEFAULT_ACTION_CACHE[list_id][propname] = action
    return action


def upgrade():
    connection = op.get_bind()
    for member in connection.execute(members_query).fetchall():
        default_action = _get_default_action(connection, member)
        # If the (non)member's moderation action is the same as the mailing
        # list's default, then set it to None. The moderation rule will
        # fallback to the list's default.
        if member['moderation_action'] == default_action:
            connection.execute(member_table.update().where(
                member_table.c.id == member['id']
                ).values(moderation_action=None))


def downgrade():
    connection = op.get_bind()
    for member in connection.execute(members_query.where(
            member_table.c.moderation_action == None)).fetchall():
        default_action = _get_default_action(connection, member)
        # Use the mailing list's default action
        connection.execute(member_table.update().where(
            member_table.c.id == member['id']
            ).values(moderation_action=default_action))
