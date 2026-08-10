# Copyright 2026 glueckkanja AG
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, datetime

from .common import TestPublicHolidayResourceCommon


class TestDisplayName(TestPublicHolidayResourceCommon):
    """Generated time off names the public holiday calendar it comes from."""

    def test_generated_time_off_names_its_source(self):
        line = self._create_line(date(self.year, 10, 3), name="Tag der Einheit")
        mirror = self._company_mirror(line)
        self.assertEqual(
            mirror.display_name,
            f"[{self.holiday.display_name}] Tag der Einheit",
        )

    def test_the_name_is_not_repeated(self):
        line = self._create_line(date(self.year, 10, 3), name="Tag der Einheit")
        mirror = self._company_mirror(line)
        self.assertEqual(mirror.display_name.count("Tag der Einheit"), 1)

    def test_display_name_follows_a_rename(self):
        line = self._create_line(date(self.year, 10, 3), name="Before")
        mirror = self._company_mirror(line)
        line.name = "After"
        mirror.invalidate_recordset(["display_name"])
        self.assertEqual(mirror.display_name, f"[{self.holiday.display_name}] After")

    def test_hand_made_time_off_is_left_alone(self):
        manual = self.leave_model.create(
            {
                "name": "Company outing",
                "calendar_id": self.cal_national.id,
                "date_from": datetime(self.year, 5, 2, 0, 0, 0),
                "date_to": datetime(self.year, 5, 2, 23, 59, 59),
            }
        )
        self.assertEqual(manual.display_name, "Company outing")

    def test_line_tells_years_apart(self):
        next_year = self.holiday_model.create(
            {"year": self.year + 1, "country_id": self.country.id}
        )
        this_one = self._create_line(date(self.year, 10, 3), name="Tag der Einheit")
        next_one = self._create_line(
            date(self.year + 1, 10, 3), name="Tag der Einheit", holiday=next_year
        )
        self.assertNotEqual(this_one.display_name, next_one.display_name)
        self.assertIn(str(self.year), this_one.display_name)
        self.assertIn(str(self.year + 1), next_one.display_name)

    def test_line_names_year_and_country(self):
        line = self._create_line(date(self.year, 10, 3), name="Tag der Einheit")
        self.assertEqual(
            line.display_name,
            f"Tag der Einheit ({self.year} - {self.country.name})",
        )

    def test_line_without_a_country_names_the_year_only(self):
        holiday = self.holiday_model.create({"year": self.year + 2})
        line = self._create_line(
            date(self.year + 2, 10, 3), name="Plain", holiday=holiday
        )
        self.assertEqual(line.display_name, f"Plain ({self.year + 2})")

    def test_line_name_does_not_nest_brackets(self):
        line = self._create_line(date(self.year, 10, 3), name="Tag der Einheit")
        self.assertNotIn("((", line.display_name)
