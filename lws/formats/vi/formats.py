# The Vietnamese UI keeps the number style the bank's forms use (1,500,000.5) and
# dd/mm/yyyy dates, the same as the English UI (lws/formats/en).
from lws.formats.en.formats import *  # noqa: F401,F403

DECIMAL_SEPARATOR = '.'
THOUSAND_SEPARATOR = ','
NUMBER_GROUPING = 3
