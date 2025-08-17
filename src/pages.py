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

def _md_token_to_rich_text(token):
    """
    Converts a markdown-it inline token to a list of Notion rich_text objects,
    correctly handling nested annotations and links.
    """
    rich_text_objects = []
    if not token.children:
        return []

    active_annotations = {}
    link_url = None

    for child in token.children:
        if child.type == 'text':
            if not child.content:
                continue

            text_obj = {"type": "text", "text": {"content": child.content}}
            annotations = active_annotations.copy()
            if link_url:
                text_obj['text']['link'] = {"url": link_url}

            if annotations:
                text_obj['annotations'] = annotations

            rich_text_objects.append(text_obj)

        elif child.type == 'strong_open':
            active_annotations['bold'] = True
        elif child.type == 'strong_close':
            active_annotations.pop('bold', None)

        elif child.type == 'em_open':
            active_annotations['italic'] = True
        elif child.type == 'em_close':
            active_annotations.pop('italic', None)

        elif child.type == 'code_inline':
            # code is not a stacked annotation
            text_obj = {"type": "text", "text": {"content": child.content}}
            text_obj['annotations'] = {'code': True}
            rich_text_objects.append(text_obj)

        elif child.type == 'link_open':
            link_url = child.attrs['href']
        elif child.type == 'link_close':
            link_url = None

    return rich_text_objects

def _markdown_to_notion_blocks(md_body):
    """
    Converts a markdown string into a list of Notion block objects.
    This version has enhanced support for various markdown features.
    """
    md = MarkdownIt("gfm-like")
    tokens = md.parse(md_body)

    blocks = []
    current_list = None

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Headings
        if token.type == 'heading_open':
            heading_level = int(token.tag[1])
            inline_token = tokens[i+1]
            blocks.append({
                "object": "block",
                "type": f"heading_{heading_level}",
                f"heading_{heading_level}": {"rich_text": _md_token_to_rich_text(inline_token)}
            })
            i += 3 # Skip inline and heading_close
            continue

        # Paragraphs and Images
        if token.type == 'paragraph_open':
            inline_token = tokens[i+1]

            is_image_block = False
            if inline_token.children:
                significant_children = [child for child in inline_token.children if child.type != 'text' or child.content.strip()]
                if len(significant_children) == 1 and significant_children[0].type == 'image':
                    is_image_block = True

            if is_image_block:
                image_token = [c for c in inline_token.children if c.type == 'image'][0]
                blocks.append({
                    "object": "block",
                    "type": "image",
                    "image": {
                        "type": "external",
                        "external": {"url": image_token.attrs['src']}
                    }
                })
            else:
                rich_text = _md_token_to_rich_text(inline_token)
                if rich_text: # Avoid creating empty paragraph blocks
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": rich_text}
                    })
            i += 3 # Skip inline and paragraph_close
            continue

        # Lists
        if token.type in ['bullet_list_open', 'ordered_list_open']:
            list_type = 'bulleted_list_item' if token.type == 'bullet_list_open' else 'numbered_list_item'

            j = i + 1
            while j < len(tokens) and tokens[j].type not in ['bullet_list_close', 'ordered_list_close']:
                if tokens[j].type == 'list_item_open':
                    inline_token = tokens[j+2] # list_item_open, paragraph_open, inline
                    blocks.append({
                        "object": "block",
                        "type": list_type,
                        list_type: {"rich_text": _md_token_to_rich_text(inline_token)}
                    })
                j += 1
            i = j + 1
            continue

        # Code blocks
        if token.type == 'fence':
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": token.content}}],
                    "language": token.info or "plain text"
                }
            })
            i += 1
            continue

        # Blockquotes and Callouts
        if token.type == 'blockquote_open':
            # A blockquote can contain multiple paragraphs. We'll check the first one.
            inline_token = tokens[i+2] # blockquote_open, paragraph_open, inline
            rich_text = _md_token_to_rich_text(inline_token)

            if rich_text and rich_text[0]['text']['content'].strip().startswith('[!'):
                 blocks.append({
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": rich_text,
                        "icon": {"type": "emoji", "emoji": "💡"}
                    }
                })
            else:
                blocks.append({
                    "object": "block",
                    "type": "quote",
                    "quote": {"rich_text": rich_text}
                })

            j = i + 1
            while j < len(tokens) and tokens[j].type != 'blockquote_close':
                j += 1
            i = j + 1
            continue

        # Horizontal rule
        if token.type == 'hr':
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue


        # Tables
        if token.type == 'table_open':
            table_block = {"object": "block", "type": "table", "table": {"table_width": 0, "has_column_header": False, "has_row_header": False, "children": []}}

            j = i + 1
            while j < len(tokens) and tokens[j].type != 'table_close':
                if tokens[j].type == 'thead_open':
                    table_block['table']['has_column_header'] = True
                elif tokens[j].type == 'tbody_open':
                    pass # Default
                elif tokens[j].type == 'tr_open':
                    row_block = {"type": "table_row", "table_row": {"cells": []}}

                    k = j + 1
                    while k < len(tokens) and tokens[k].type != 'tr_close':
                        if tokens[k].type in ['th_open', 'td_open']:
                            cell_token = tokens[k+1]
                            cell_content = _md_token_to_rich_text(cell_token)
                            row_block['table_row']['cells'].append(cell_content)
                        k += 1

                    table_block['table']['children'].append(row_block)
                    if not table_block['table']['table_width']:
                        table_block['table']['table_width'] = len(row_block['table_row']['cells'])

                j += 1
            blocks.append(table_block)
            i = j + 1
            continue

        i += 1

    return blocks


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
