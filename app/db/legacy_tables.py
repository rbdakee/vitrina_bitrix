from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, MetaData, String, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY

legacy_metadata = MetaData()

parsed_properties = Table(
    "parsed_properties",
    legacy_metadata,
    Column("vitrina_id", BigInteger, primary_key=True),
    Column("rbd_id", BigInteger),
    Column("krisha_id", String(64)),
    Column("krisha_date", DateTime(timezone=True)),
    Column("object_type", String(255)),
    Column("address", Text),
    Column("complex", String(255)),
    Column("builder", String(255)),
    Column("flat_type", String(255)),
    Column("property_class", String(255)),
    Column("condition", String(255)),
    Column("sell_price", Float),
    Column("sell_price_per_m2", Float),
    Column("house_num", String(255)),
    Column("floor_num", Integer),
    Column("floor_count", Integer),
    Column("room_count", Integer),
    Column("phones", String(255)),
    Column("description", Text),
    Column("ceiling_height", Float),
    Column("area", Float),
    Column("year_built", Integer),
    Column("wall_type", String(255)),
    Column("stats_agent_given", String(255)),
    Column("stats_time_given", DateTime(timezone=True)),
    Column("stats_object_status", String(255)),
    Column("stats_recall_time", DateTime(timezone=True)),
    Column("stats_description", Text),
    Column("stats_object_category", String(10)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

vitrina_agents = Table(
    "vitrina_agents",
    legacy_metadata,
    Column("agent_phone", String(255), primary_key=True),
    Column("full_name", Text),
    Column("chat_ids", ARRAY(Text())),
    Column("role", String(50)),
    Column("property_classes", ARRAY(Text())),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)
