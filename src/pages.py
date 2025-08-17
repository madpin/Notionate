import os
import yaml
from pathlib import Path
from markdown_it import MarkdownIt

from src.notion_utils import find_page_by_title_and_parent

def _parse_markdown_file(file_path):
    """
    Parses a markdown file, separating YAML front matter from the content.
    """
    with open(file_path, 'r') as f:
        content = f.read()

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content # No front matter

    front_matter = yaml.safe_load(parts[1])
    body = parts[2].lstrip()
    return front_matter, body

def _markdown_to_notion_blocks(md_body):
    """
    Converts a markdown string into a list of Notion block objects.
    """
    md = MarkdownIt()
    tokens = md.parse(md_body)

    blocks = []
    for token in tokens:
        if token.type == 'heading_open':
            heading_level = int(token.tag[1])
            if heading_level <= 3:
                blocks.append({
                    "object": "block",
                    "type": f"heading_{heading_level}",
                    f"heading_{heading_level}": {"rich_text": [{"type": "text", "text": {"content": ""}}]}
                })
        elif token.type == 'inline' and blocks:
            # Add content to the last created block
            last_block = blocks[-1]
            block_type = last_block['type']
            last_block[block_type]['rich_text'][0]['text']['content'] = token.content
        elif token.type == 'paragraph_open':
             blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": ""}}]}
            })

    # Filter out empty blocks
    return [b for b in blocks if b[b['type']]['rich_text'][0]['text']['content']]


def publish_pages_to_notion(directory, notion_client):
    """
    Publishes markdown pages from a directory to Notion.
    """
    print(f"Publishing pages from directory: {directory}")
    for file_path in Path(directory).rglob('*.md'):
        print(f"Processing page: {file_path}")
        front_matter, body = _parse_markdown_file(file_path)

        title = front_matter.get('title')
        if not title:
            print(f"Warning: Page '{file_path}' is missing a title. Skipping.")
            continue

        parent_page_id = front_matter.get('parent_page_id')
        if not parent_page_id:
            # In a real tool, this might come from a global config
            print(f"Warning: Page '{title}' is missing a parent_page_id. Skipping.")
            continue

        existing_page = find_page_by_title_and_parent(notion_client, title, parent_page_id)

        blocks = _markdown_to_notion_blocks(body)

        page_payload = {
            "properties": {"title": [{"type": "text", "text": {"content": title}}]},
        }

        if 'icon' in front_matter:
            page_payload['icon'] = {'type': 'emoji', 'emoji': front_matter['icon']}
        if 'cover_url' in front_matter:
            page_payload['cover'] = {'type': 'external', 'external': {'url': front_matter['cover_url']}}

        if existing_page:
            page_id = existing_page['id']
            print(f"Updating page: '{title}' (ID: {page_id})")
            notion_client.pages.update(page_id=page_id, **page_payload)
            _update_page_blocks(notion_client, page_id, blocks)
            print(f"Successfully updated page: '{title}'.")
        else:
            print(f"Creating page: '{title}'")
            page_payload['parent'] = {"page_id": parent_page_id}
            page_payload['children'] = blocks
            notion_client.pages.create(**page_payload)
            print(f"Successfully created page: '{title}'")

def _update_page_blocks(notion_client, page_id, new_blocks):
    """
    Updates the content of a page by replacing all its blocks.
    """
    # First, get all existing blocks
    existing_blocks = notion_client.blocks.children.list(block_id=page_id)['results']

    # Delete all existing blocks
    # Note: The API has a limit of 100 blocks per request for both list and delete.
    # A more robust implementation would handle pagination.
    for block in existing_blocks:
        notion_client.blocks.delete(block_id=block['id'])

    # Add the new blocks
    # Note: The API has a limit of 100 blocks per request for append.
    if new_blocks:
        notion_client.blocks.children.append(block_id=page_id, children=new_blocks)
