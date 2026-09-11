# Copyright 2026 glueckkanja AG
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

from odoo.addons.calendar_public_holiday.hooks import (
    assign_regions_from_legacy_states,
)


@openupgrade.migrate()
def migrate(env, version):
    # The lines are scoped to regions instead of states from this version
    # on: every line scoped to states is assigned the regions lying in them,
    # or disabled until such a region exists.
    assign_regions_from_legacy_states(env)
