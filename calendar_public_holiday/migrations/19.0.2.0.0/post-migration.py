# Copyright 2026 glueckkanja AG
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

from odoo.addons.calendar_public_holiday.hooks import migrate_states_to_regions


@openupgrade.migrate()
def migrate(env, version):
    # The lines are scoped to regions instead of states from this version
    # on: every state a line was scoped to becomes a region of that name.
    migrate_states_to_regions(env)
