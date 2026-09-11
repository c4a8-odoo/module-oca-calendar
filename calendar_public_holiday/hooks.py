# Copyright 2024 Camptocamp
# Copyright 2026 glueckkanja AG
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)

# The many2many that scoped a public holiday line to country states before
# the lines were scoped to regions instead.
LEGACY_STATE_REL_TABLE = "public_holiday_state_rel"


def migrate_rename_xmlid_event_type_holiday(env):
    if not openupgrade.is_module_installed(env.cr, "hr_holidays_public"):
        return
    xmlid_renames = [
        (
            "hr_holidays_public.event_type_holiday",
            "calendar_public_holiday.event_type_holiday",
        ),
    ]
    openupgrade.rename_xmlids(env.cr, xmlid_renames)


def migrate_rename_field_model_hr_holidays_public_line(env):
    field_renames = [
        (
            "hr.holidays.public.line",
            "hr_holidays_public_line",
            "year_id",
            "public_holiday_id",
        ),
    ]
    openupgrade.rename_fields(env, field_renames, no_deep=True)


def migrate_rename_model_hr_holidays_public_line(env):
    if not openupgrade.table_exists(env.cr, "hr_holidays_public_line"):
        return
    model_renames = [("hr.holidays.public.line", "calendar.public.holiday.line")]
    openupgrade.rename_models(env.cr, model_renames)
    tables_renames = [("hr_holidays_public_line", "calendar_public_holiday_line")]
    openupgrade.rename_tables(env.cr, tables_renames)
    # Rename Many2many relation
    tables_renames = [("hr_holiday_public_state_rel", LEGACY_STATE_REL_TABLE)]
    openupgrade.rename_tables(env.cr, tables_renames)
    column_renames = {
        LEGACY_STATE_REL_TABLE: [("line_id", "public_holiday_line_id")],
    }
    openupgrade.rename_columns(env.cr, column_renames)


def migrate_rename_model_hr_holidays_public(env):
    if not openupgrade.table_exists(env.cr, "hr_holidays_public"):
        return
    model_renames = [
        ("hr.holidays.public", "calendar.public.holiday"),
    ]
    openupgrade.rename_models(env.cr, model_renames)
    tables_renames = [("hr_holidays_public", "calendar_public_holiday")]
    openupgrade.rename_tables(env.cr, tables_renames)


def pre_init_hook(env):
    migrate_rename_xmlid_event_type_holiday(env)
    migrate_rename_field_model_hr_holidays_public_line(env)
    migrate_rename_model_hr_holidays_public_line(env)
    migrate_rename_model_hr_holidays_public(env)


def migrate_states_to_regions(env):
    """Turn the related states of the public holiday lines into regions.

    Public holiday lines used to be scoped to country states; they are
    scoped to public holiday regions now. One shared region is created
    per state that at least one line was scoped to, named after the state
    and carrying its country, and every such line is assigned the regions
    of its former states -- so the configuration keeps meaning the same
    thing, and the modules that know about people can link the people of a
    state to the region standing for it. A line that selected every state
    of its country meant the whole country and stays nationwide.

    Idempotent: the legacy relation is read wherever it still exists, an
    existing shared region of the same name and country is reused, and an
    assignment already made is left alone. Returns the regions standing
    for the states.
    """
    cr = env.cr
    if not openupgrade.table_exists(cr, LEGACY_STATE_REL_TABLE):
        return env["calendar.public.holiday.region"]
    cr.execute(
        """
        SELECT rel.public_holiday_line_id, rel.state_id
        FROM public_holiday_state_rel rel
        JOIN calendar_public_holiday_line line
            ON line.id = rel.public_holiday_line_id
        JOIN calendar_public_holiday holiday
            ON holiday.id = line.public_holiday_id
        JOIN res_country_state state ON state.id = rel.state_id
        WHERE holiday.country_id IS NULL
           OR EXISTS (
               SELECT 1
               FROM res_country_state missing
               WHERE missing.country_id = holiday.country_id
                 AND NOT EXISTS (
                     SELECT 1
                     FROM public_holiday_state_rel r
                     WHERE r.public_holiday_line_id = line.id
                       AND r.state_id = missing.id
                 )
           )
        ORDER BY rel.state_id, rel.public_holiday_line_id
        """
    )
    rows = cr.fetchall()
    if not rows:
        return env["calendar.public.holiday.region"]
    region_model = env["calendar.public.holiday.region"].with_context(active_test=False)
    line_model = env["calendar.public.holiday.line"].with_context(active_test=False)
    states = env["res.country.state"].browse(
        sorted({state_id for _line, state_id in rows})
    )
    regions = {}
    for state in states:
        region = region_model.search(
            [
                ("name", "=", state.name),
                ("country_id", "=", state.country_id.id),
                ("company_id", "=", False),
            ],
            limit=1,
        )
        if not region:
            region = region_model.create(
                {"name": state.name, "country_id": state.country_id.id}
            )
        regions[state.id] = region
    line_ids_by_region = {}
    for line_id, state_id in rows:
        line_ids_by_region.setdefault(regions[state_id], set()).add(line_id)
    for region, line_ids in line_ids_by_region.items():
        lines = line_model.browse(sorted(line_ids)).exists()
        missing = lines.filtered(lambda line, loc=region: loc not in line.region_ids)
        if missing:
            missing.write({"region_ids": [(4, region.id)]})
    _logger.info(
        "calendar_public_holiday: %s public holiday region(s) stand for the "
        "%s state(s) of %s public holiday line(s)",
        len(regions),
        len(states),
        len({line_id for line_id, _state in rows}),
    )
    return region_model.union(*regions.values())


def post_init_hook(env):
    # A database coming from hr_holidays_public still carries the legacy
    # state relation the pre-init hook renamed; the lines are scoped to
    # regions now, so the states are turned into regions right away.
    migrate_states_to_regions(env)
