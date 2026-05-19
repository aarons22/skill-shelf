from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, Text

metadata = MetaData()

marketplaces = Table(
    "marketplaces",
    metadata,
    Column("slug", Text, primary_key=True),
    Column("display_name", Text, nullable=False),
    Column("owner_name", Text, nullable=False),
    Column("owner_email", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
)

skills = Table(
    "skills",
    metadata,
    Column("marketplace_slug", Text, ForeignKey("marketplaces.slug", ondelete="CASCADE"), nullable=False),
    Column("slug", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("version", Text, nullable=False, default="1.0.0"),
    Column("content", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    Column("last_commit", Text, nullable=True),
)
