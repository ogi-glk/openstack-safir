#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Initial migration

Revision ID: 77508df731b2
Revises: None
Create Date: 2021-08-22 21:08:00

"""

from alembic import op
import sqlalchemy as sa

from oslo_db.sqlalchemy import types as oslo_db_types

# revision identifiers, used by Alembic.
revision = '77508df731b2'
down_revision = None


def upgrade():
    op.create_table(
        'licence',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted', oslo_db_types.SoftDeleteInteger(), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('licence_key', sa.String(length=255)),
        sa.Column('notification_address', sa.String(length=255)),
        sa.Column('notification_counter', sa.String(length=255)),
        sa.Column('last_notification_time', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'deleted', name='uniq_cluster0id0deleted')
    )
