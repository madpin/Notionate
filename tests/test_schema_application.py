import pytest
from unittest.mock import MagicMock, patch

from src.schema import apply_schema_to_notion

@pytest.fixture
def mock_notion_client():
    """Pytest fixture for a mocked Notion client."""
    return MagicMock()

@pytest.fixture
def basic_schema():
    """A basic schema for testing."""
    return {
        "version": "1.0",
        "workspace": {
            "parent_page_id": "test_parent_page_id"
        },
        "databases": [
            {
                "db_key": "customers",
                "title": "Customers",
                "properties": {
                    "Name": {"type": "title"},
                    "Email": {"type": "email"}
                }
            }
        ]
    }

def test_apply_schema_create_database(mock_notion_client, basic_schema):
    """
    Tests that a new database is created when it doesn't exist.
    """
    # Arrange: Simulate that the database does not exist
    mock_notion_client.search.return_value = {"results": []}
    mock_notion_client.databases.create.return_value = {"id": "new_db_id", "title": [{"plain_text": "Customers"}]}

    # Act
    apply_schema_to_notion(basic_schema, mock_notion_client, dry_run=False)

    # Assert
    # It should have searched for the database
    mock_notion_client.search.assert_called_once()
    # It should have created the database
    mock_notion_client.databases.create.assert_called_once()
    # It should not have updated any database
    mock_notion_client.databases.update.assert_not_called()

def test_apply_schema_update_database(mock_notion_client, basic_schema):
    """
    Tests that an existing database is updated.
    """
    # Arrange: Simulate that the database exists
    existing_db = {
        "id": "existing_db_id",
        "title": [{"plain_text": "Customers"}],
        "properties": {
            "Name": {"id": "1", "type": "title", "title": {}}
        }
    }
    mock_notion_client.search.return_value = {"results": [existing_db]}

    # Act
    apply_schema_to_notion(basic_schema, mock_notion_client, dry_run=False)

    # Assert
    mock_notion_client.search.assert_called_once()
    mock_notion_client.databases.create.assert_not_called()
    mock_notion_client.databases.update.assert_called_once()

def test_apply_schema_dry_run(mock_notion_client, basic_schema):
    """
    Tests that dry_run returns a plan and does not call modifying API methods.
    """
    # Arrange
    mock_notion_client.search.return_value = {"results": []}

    # Act
    plan = apply_schema_to_notion(basic_schema, mock_notion_client, dry_run=True)

    # Assert
    assert plan is not None
    assert len(plan) > 0
    assert "Plan to CREATE database" in plan[1]
    mock_notion_client.databases.create.assert_not_called()
    mock_notion_client.databases.update.assert_not_called()

def test_create_relation(mock_notion_client):
    """
    Tests that relations are created correctly.
    """
    # Arrange
    schema = {
        "version": "1.0",
        "workspace": {"parent_page_id": "test_parent_page_id"},
        "databases": [
            {"db_key": "customers", "title": "Customers", "properties": {"Name": {"type": "title"}}},
            {"db_key": "orders", "title": "Orders", "properties": {"Order No": {"type": "title"}}}
        ],
        "relations": [
            {
                "from_db": "orders",
                "property_name": "Customer",
                "to_db": "customers",
                "synced_property_name": "Orders"
            }
        ]
    }
    # Simulate that databases are created and we get their IDs
    mock_notion_client.search.return_value = {"results": []}
    mock_notion_client.databases.create.side_effect = [
        {"id": "customers_db_id"},
        {"id": "orders_db_id"}
    ]

    # Act
    apply_schema_to_notion(schema, mock_notion_client, dry_run=False)

    # Assert
    # Called once for each database, and once for the relation
    assert mock_notion_client.databases.update.call_count == 1

    # Get the arguments of the update call for the relation
    update_args = mock_notion_client.databases.update.call_args
    assert update_args.kwargs['database_id'] == 'orders_db_id'
    assert 'Customer' in update_args.kwargs['properties']
    relation_prop = update_args.kwargs['properties']['Customer']
    assert relation_prop['relation']['database_id'] == 'customers_db_id'
    assert relation_prop['relation']['synced_property_name'] == 'Orders'

def test_missing_parent_page_id_raises_error(mock_notion_client):
    """
    Tests that a ValueError is raised if parent_page_id is missing.
    """
    schema = {"workspace": {}, "databases": []}
    with pytest.raises(ValueError, match="A `parent_page_id` must be defined"):
        apply_schema_to_notion(schema, mock_notion_client)
