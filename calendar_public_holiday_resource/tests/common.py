# Copyright 2026 glueckkanja AG
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestPublicHolidayResourceCommon(TransactionCase):
    """Fixtures for the synchronisation.

    Which regions a working schedule covers comes from the work addresses of
    its employees, and `resource` has no notion of either -- that is supplied
    by `hr_holidays_public_resource`. These tests therefore stub the hook and
    cover the mechanics; the derivation itself is tested where it lives.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        # Regional public holidays are resolved to the resources of the people
        # working in the region, which `resource` knows nothing about; the
        # resolution lives in `hr_holidays_public_resource` and is tested there.
        cls._states_by_calendar = {}

        def _get_public_holiday_resource_targets(lines, calendars):
            targets = []
            for calendar in calendars:
                states = cls._states_by_calendar.get(calendar.id)
                if not states:
                    continue
                for company in calendar._public_holiday_companies():
                    for line in lines.filtered("state_ids"):
                        if not line.state_ids & states:
                            continue
                        if not calendar._matches_public_holiday_country(line, company):
                            continue
                        for resource in cls._resources_by_calendar.get(calendar.id, []):
                            targets.append((line, resource, calendar, company))
            return targets

        patcher = patch.object(
            type(cls.env["calendar.public.holiday.line"]),
            "_get_public_holiday_resource_targets",
            _get_public_holiday_resource_targets,
        )
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        cls._resources_by_calendar = {}
        # The sync floor is the current year, so every fixture uses it.
        cls.year = date.today().year
        cls.holiday_model = cls.env["calendar.public.holiday"]
        cls.line_model = cls.env["calendar.public.holiday.line"]
        cls.leave_model = cls.env["resource.calendar.leaves"]

        # Start from a clean slate: other modules ship demo public holidays and
        # global time off that would otherwise collide with the fixtures.
        cls.line_model.search([]).unlink()
        cls.holiday_model.search([]).unlink()
        cls.leave_model.search([("resource_id", "=", False)]).with_context(
            public_holiday_sync=True
        ).unlink()

        cls.country = cls.env.ref("base.de")
        cls.state_by = cls.env["res.country.state"].create(
            {"name": "Test Bayern", "code": "TBY", "country_id": cls.country.id}
        )
        cls.state_nw = cls.env["res.country.state"].create(
            {"name": "Test Nordrhein", "code": "TNW", "country_id": cls.country.id}
        )
        cls.other_country = cls.env.ref("base.fr")

        # Nationwide public holidays are generated for every company whose
        # country matches -- and for companies without a country, which cannot
        # be ruled out. Pinning the pre-existing companies to an unrelated
        # country keeps them out of the fixtures' way.
        cls.bystander_country = cls.env.ref("base.it")
        cls.env["res.company"].sudo().search([]).write(
            {"country_id": cls.bystander_country.id}
        )

        cls.company = cls.env["res.company"].create(
            {"name": "Public Holiday Co", "country_id": cls.country.id}
        )
        cls.company_2 = cls.env["res.company"].create(
            {"name": "Public Holiday Co 2", "country_id": cls.country.id}
        )
        cls.env.user.company_ids |= cls.company | cls.company_2

        # Creating a company also creates its default working schedule, so the
        # sweep has to happen once every company exists. Only the fixture
        # schedules below take part in the assertions.
        cls.env["resource.calendar"].sudo().with_context(active_test=False).search(
            []
        ).write({"public_holiday_employee_sync": False})

        cls.cal_national = cls._create_calendar("National", cls.company)
        cls.cal_by = cls._create_calendar("Bayern", cls.company, cls.state_by)
        cls.cal_tokyo = cls._create_calendar("Tokyo", cls.company, tz="Asia/Tokyo")
        # The company-wide records span the day in the timezone of the main
        # schedule of the company, so the fixtures make that deterministic.
        cls.company.resource_calendar_id = cls.cal_national
        cls.cal_company_2 = cls._create_calendar("Company 2", cls.company_2)
        cls.company_2.resource_calendar_id = cls.cal_company_2

        cls.holiday = cls.holiday_model.create(
            {"year": cls.year, "country_id": cls.country.id}
        )
        # The stub outlives a single test, so each one starts from the fixtures.
        cls._states_baseline = dict(cls._states_by_calendar)
        cls._resources_baseline = dict(cls._resources_by_calendar)

    def setUp(self):
        super().setUp()
        self._states_by_calendar.clear()
        self._states_by_calendar.update(self._states_baseline)
        self._resources_by_calendar.clear()
        self._resources_by_calendar.update(self._resources_baseline)

    @classmethod
    def _create_calendar(cls, name, company, state=None, tz="Europe/Berlin"):
        calendar = cls.env["resource.calendar"].create(
            {
                "name": name,
                "company_id": company.id if company else False,
                "tz": tz,
            }
        )
        if state:
            cls._set_calendar_states(calendar, state)
        return calendar

    @classmethod
    def _set_calendar_states(cls, calendar, states):
        """Stand in for people working in a region on this schedule."""
        cls._states_by_calendar[calendar.id] = states
        cls._resources_by_calendar.setdefault(
            calendar.id,
            cls.env["resource.resource"].create(
                {
                    "name": f"{calendar.name} resource",
                    "calendar_id": calendar.id,
                    "company_id": calendar.company_id.id or cls.company.id,
                }
            ),
        )

    @classmethod
    def _create_line(
        cls, day, name="Holiday", states=None, holiday=None, calendars=None
    ):
        return cls.line_model.create(
            {
                "name": name,
                "date": day,
                "public_holiday_id": (holiday or cls.holiday).id,
                "state_ids": [(6, 0, states.ids)] if states else False,
                "additional_resource_calendar_ids": (
                    [(6, 0, calendars.ids)] if calendars else False
                ),
            }
        )

    def _mirrors(self, line, calendar=None, company=None):
        domain = [("public_holiday_line_id", "=", line.id)]
        if calendar is not None:
            domain.append(("calendar_id", "=", calendar.id))
        if company is not None:
            domain.append(("company_id", "=", company.id))
        return self.leave_model.search(domain)

    def _company_mirror(self, line, company=None):
        """The company-wide record of a nationwide line."""
        return self.leave_model.search(
            [
                ("public_holiday_line_id", "=", line.id),
                ("calendar_id", "=", False),
                ("resource_id", "=", False),
                ("company_id", "=", (company or self.company).id),
            ]
        )
