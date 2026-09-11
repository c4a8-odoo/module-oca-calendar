## 19.0.2.0.0

- Public holiday lines are scoped to public holiday regions instead of
  country states. Regions are only created for the places people work at
  (see `hr_holidays_public`); upgrading assigns every line that was scoped
  to states the regions lying in those states, and disables a line no
  region stands for yet.
- A region names its country, which selects the public holiday calendars
  applying to it, and the state it lies in.
- A public holiday line can be disabled.
