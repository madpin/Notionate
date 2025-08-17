def find_database_by_title(notion_client, title):
    """
    Finds a database by its title.
    Returns the database object if found, otherwise None.
    """
    response = notion_client.search(query=title, filter={"property": "object", "value": "database"})
    for db in response.get('results', []):
        # The search can be broad, so we need to find an exact match for the title
        if db.get('title', [{}])[0].get('plain_text').lower() == title.lower():
            return db
    return None

def find_page_by_title_and_parent(notion_client, title, parent_id):
    """
    Finds a page by its title within a specific parent page.
    This is tricky because search doesn't directly support parent filtering this way.
    We have to search for the title and then filter the results by parent.
    """
    response = notion_client.search(query=title, filter={"property": "object", "value": "page"})
    for page in response.get('results', []):
        page_title = page.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text')
        page_parent_id = page.get('parent', {}).get('page_id')
        if page_title.lower() == title.lower() and page_parent_id == parent_id:
            return page
    return None
