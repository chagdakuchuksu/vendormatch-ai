"""Duration normalization through days, with exact rational arithmetic.

Conversion strategy (deterministic, no rounding, no tolerance):

    1 week  = 7 days
    1 month = 364 / 12 = 30 1/3 days   (1/12 of a 52-week planning year)

So whole quarters line up exactly with weeks: 3 months = 13 weeks = 91 days,
6 months = 26 weeks = 182 days, 12 months = 52 weeks = 364 days. A real calendar month
averages ~30.44 days; the 364-day planning year is used because project timelines are
planned in whole weeks, and a fixed factor such as 4.345 weeks/month would make 6 months
"26.07 weeks" and fail a 26-week strict deadline by a fraction of a day.

Values are converted with `fractions.Fraction`, so e.g. 6 months -> exactly 182 days ->
exactly 26 weeks; there is no floating-point drift to absorb. Same-unit values are never
converted.
"""

from fractions import Fraction

from app.schemas.enums import DurationUnit

DAYS_PER_UNIT: dict[DurationUnit, Fraction] = {
    DurationUnit.WEEKS: Fraction(7),
    DurationUnit.MONTHS: Fraction(364, 12),
}


def to_days(value: float, unit: DurationUnit) -> Fraction:
    return Fraction(value) * DAYS_PER_UNIT[unit]


def convert_duration(value: float, from_unit: DurationUnit, to_unit: DurationUnit) -> float:
    """Convert via days; returns `value` unchanged when the units are equal."""
    if from_unit == to_unit:
        return value
    return float(to_days(value, from_unit) / DAYS_PER_UNIT[to_unit])
