from app.database import Base
from app import models  # noqa: F401


def test_expected_tables_are_registered() -> None:
    expected = {
        "organizations",
        "installations",
        "servers",
        "agents",
        "products",
        "product_modules",
        "scripts",
        "script_versions",
        "jobs",
        "executions",
        "events",
        "audit_records",
    }

    assert expected == set(Base.metadata.tables)


def test_primary_keys_use_single_id_column() -> None:
    for table in Base.metadata.sorted_tables:
        assert [column.name for column in table.primary_key.columns] == ["id"]
