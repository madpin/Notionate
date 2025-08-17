import pytest
from unittest.mock import MagicMock, patch

from src.ingestion import ingest_data_to_notion

@pytest.fixture
def mock_notion_client():
    """Pytest fixture for a mocked Notion client."""
    client = MagicMock()
    # Mock the find_database_by_title to return a mock db
    client.search.return_value = {
        'results': [{
            'id': 'test_db_id',
            'title': [{'plain_text': 'customers'}],
            'properties': {
                'external_id': {'type': 'rich_text'},
                'Name': {'type': 'title'},
                'Status': {'type': 'select', 'select': {'options': [{'name': 'Active'}]}}
            }
        }]
    }
    return client

@pytest.fixture
def yaml_data():
    """Sample YAML data for testing."""
    return {
        "defaults": {
            "match_on": "external_id",
            "create_missing_select_options": True
        },
        "data": {
            "customers": [
                {"external_id": "cust-001", "Name": "New Corp", "Status": "Prospect"}
            ]
        }
    }

def test_ingest_yaml_create_page(mock_notion_client, yaml_data):
    """
    Tests that a new page is created from YAML data.
    """
    # Arrange: Simulate that the page does not exist
    mock_notion_client.databases.query.return_value = {"results": []}

    # Act
    ingest_data_to_notion(yaml_data, mock_notion_client, dry_run=False)

    # Assert
    mock_notion_client.pages.create.assert_called_once()
    mock_notion_client.pages.update.assert_not_called()

def test_ingest_yaml_update_page(mock_notion_client, yaml_data):
    """
    Tests that an existing page is updated from YAML data.
    """
    # Arrange: Simulate that the page exists
    existing_page = {"id": "existing_page_id"}
    mock_notion_client.databases.query.return_value = {"results": [existing_page]}

    # Act
    ingest_data_to_notion(yaml_data, mock_notion_client, dry_run=False)

    # Assert
    mock_notion_client.pages.create.assert_not_called()
    mock_notion_client.pages.update.assert_called_once()
    update_args = mock_notion_client.pages.update.call_args
    assert update_args.kwargs['page_id'] == 'existing_page_id'

def test_ingest_creates_new_select_option(mock_notion_client, yaml_data):
    """
    Tests that a new select option is created if it doesn't exist.
    """
    # Arrange
    mock_notion_client.databases.query.return_value = {"results": []} # Create mode

    # Act
    ingest_data_to_notion(yaml_data, mock_notion_client, dry_run=False)

    # Assert
    # It should be called once to update the database with the new option
    mock_notion_client.databases.update.assert_called_once()
    update_args = mock_notion_client.databases.update.call_args
    assert update_args.kwargs['database_id'] == 'test_db_id'

    # Check that the new option "Prospect" is being added
    options = update_args.kwargs['properties']['Status']['select']['options']
    assert {'name': 'Active'} in options
    assert {'name': 'Prospect'} in options

@pytest.fixture
def csv_data():
    """Sample CSV data for testing."""
    return [
        {"ID": "cust-002", "Company Name": "CSV Corp"}
    ]

@pytest.fixture
def map_config():
    """Sample map config for testing."""
    return {
        "target_db": "customers",
        "defaults": {"match_on": "external_id"},
        "columns": {
            "ID": {"as": "external_id"},
            "Company Name": {"as": "Name"}
        }
    }

def test_ingest_csv_data(mock_notion_client, csv_data, map_config):
    """
    Tests that data from a CSV is ingested correctly using a map file.
    """
    # Arrange
    mock_notion_client.databases.query.return_value = {"results": []}

    # Act
    ingest_data_to_notion(csv_data, mock_notion_client, map_config, dry_run=False)

    # Assert
    mock_notion_client.pages.create.assert_called_once()
    create_args = mock_notion_client.pages.create.call_args
    properties = create_args.kwargs['properties']
    assert 'Name' in properties
    assert properties['Name']['title'][0]['text']['content'] == "CSV Corp"
    assert 'external_id' in properties
    assert properties['external_id']['rich_text'][0]['text']['content'] == "cust-002"

def test_ingest_csv_requires_map(mock_notion_client, csv_data):
    """
    Tests that CSV ingestion raises an error if no map file is provided.
    """
    with pytest.raises(ValueError, match="A map file is required for CSV ingestion."):
        ingest_data_to_notion(csv_data, mock_notion_client)
