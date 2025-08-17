import pytest
from unittest.mock import MagicMock
from pathlib import Path
from src.pages import _markdown_to_notion_blocks, publish_pages_to_notion, _parse_markdown_file

@pytest.fixture
def sample_markdown_text():
    with open('pages/test.md', 'r') as f:
        return f.read()

@pytest.fixture
def sample_markdown_body(sample_markdown_text):
    _, body = _parse_markdown_file('pages/test.md')
    return body

def test_markdown_to_notion_blocks_full(sample_markdown_body):
    # Act
    blocks = _markdown_to_notion_blocks(sample_markdown_body)

    # Assert
    # This is a basic check. A real test would be more thorough.
    assert len(blocks) > 5

def test_publish_pages_to_notion_with_mock(mocker, sample_markdown_text):
    # Arrange
    # Mock the file system read
    mocker.patch('builtins.open', mocker.mock_open(read_data=sample_markdown_text))
    mocker.patch('pathlib.Path.rglob', return_value=[Path('pages/test.md')])

    mock_notion_client = MagicMock()
    # Mock find_page_by_title_and_parent to simulate page not existing
    mocker.patch('src.pages.find_page_by_title_and_parent', return_value=None)

    # Act
    publish_pages_to_notion("pages", mock_notion_client)

    # Assert
    mock_notion_client.pages.create.assert_called_once()
    call_args = mock_notion_client.pages.create.call_args[1]

    # Check front matter parsing
    assert call_args['properties']['title'][0]['text']['content'] == "Enhanced Markdown Test Page"
    assert call_args['icon']['emoji'] == "🚀"
    assert call_args['cover']['external']['url'] == "https://www.notion.so/images/page-cover/solid_red.png"

    # Check block generation
    children = call_args['children']
    assert any(b['type'] == 'heading_1' for b in children)
    assert any(b['type'] == 'code' for b in children)
    assert any(b['type'] == 'table' for b in children)
    assert any(b['type'] == 'image' for b in children)
    assert any(b['type'] == 'callout' for b in children)

    # Check for link
    link_paragraph = [b for b in children if b['type'] == 'paragraph' and 'And a link' in b['paragraph']['rich_text'][0]['text']['content']]
    assert link_paragraph, "Paragraph with link not found"
    link_text_obj = link_paragraph[0]['paragraph']['rich_text'][1]
    assert link_text_obj['text']['content'] == 'Visit my website'
    assert link_text_obj['text']['link']['url'] == 'https://www.example.com'
