"""Column types that render on both PostgreSQL and SQLite.

The schema was written against PostgreSQL and used `ARRAY(Text)` and the
dialect-specific `UUID`. Neither renders on SQLite, which the default
zero-configuration deployment uses. These variants keep the native PostgreSQL
types where they are available and fall back to portable equivalents
elsewhere, so the same models serve both.
"""

from sqlalchemy import JSON, Text, Uuid
from sqlalchemy import ARRAY as _ARRAY

# Native text[] on PostgreSQL, a JSON list on SQLite. Both round-trip a Python
# list of strings, so model and seeding code is unchanged.
StringArray = _ARRAY(Text).with_variant(JSON(), "sqlite")

# SQLAlchemy 2.0's portable Uuid: renders as native UUID on PostgreSQL and as
# CHAR(32) elsewhere, returning uuid.UUID objects either way.
GUID = Uuid(as_uuid=True)
