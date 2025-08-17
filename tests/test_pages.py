import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import os

from src.pages import publish_pages_to_notion, _parse_markdown_file

@pytest.fixture
def mock_notion_client():
    """Pytest fixture for a mocked Notion client."""
    return MagicMock()

@pytest.fixture
def pages_dir(tmp_path):
    """Creates a temporary directory with a sample markdown file."""
    pages = tmp_path / "pages"
    pages.mkdir()
    page_file = pages / "test_page.md"
    page_file.write_text(
        "---\n"
        "title: 'Test Page'\n"
        "parent_page_id: 'test_parent_id'\n"
        "icon: '📄'\n"
        "---\n"
        "# Hello\n\n"
        "This is a test."
    )
    return pages

def test_parse_markdown_file(pages_dir):
    """
    Tests that the markdown file is parsed correctly.
    """
    file_path = pages_dir / "test_page.md"
    front_matter, body = _parse_markdown_file(file_path)

    assert front_matter['title'] == 'Test Page'
    assert front_matter['parent_page_id'] == 'test_parent_id'
    assert body == "# Hello\n\nThis is a test."

def test_publish_creates_new_page(mock_notion_client, pages_dir):
    """
    Tests that a new page is created when it doesn't exist.
    """
    # Arrange: Simulate that the page does not exist
    mock_notion_client.search.return_value = {"results": []}

    # Act
    publish_pages_to_notion(pages_dir, mock_notion_client)

    # Assert
    mock_notion_client.pages.create.assert_called_once()
    mock_notion_client.pages.update.assert_not_called()

    create_args = mock_notion_client.pages.create.call_args
    assert create_args.kwargs['parent']['page_id'] == 'test_parent_id'
    assert create_args.kwargs['properties']['title'][0]['text']['content'] == 'Test Page'
    assert create_args.kwargs['icon']['emoji'] == '📄'
    assert len(create_args.kwargs['children']) == 2 # Heading and paragraph

def test_publish_updates_existing_page(mock_notion_client, pages_dir):
    """
    Tests that an existing page is updated.
    """
    # Arrange: Simulate that the page exists
    existing_page = {
        "id": "existing_page_id",
        "parent": {"type": "page_id", "page_id": "test_parent_id"},
        "properties": {
            "title": {
                "id": "title",
                "type": "title",
                "title": [{
                    "type": "text",
                    "text": {"content": "Test Page"},
                    "plain_text": "Test Page"
                }]
            }
        }
    }
    mock_notion_client.search.return_value = {"results": [existing_page]}
    # Mock the block children list and delete
    mock_notion_client.blocks.children.list.return_value = {"results": [{"id": "block1"}]}

    # Act
    publish_pages_to_notion(pages_dir, mock_notion_client)

    # Assert
    mock_notion_client.pages.create.assert_not_called()
    # Called once to update properties
    mock_notion_client.pages.update.assert_called_once()
    # Called to update blocks
    mock_notion_client.blocks.children.list.assert_called_once()
    mock_notion_client.blocks.delete.assert_called_once()
    mock_notion_client.blocks.children.append.assert_called_once()
