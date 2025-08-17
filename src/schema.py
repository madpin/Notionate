import yaml

def load_schema(schema_file):
    """
    Loads a schema from a YAML file.
    """
    with open(schema_file, 'r') as f:
        return yaml.safe_load(f)

from src.notion_utils import find_database_by_title

def _create_database(notion_client, parent_page_id, db_config):
    """
    Creates a new database in Notion.
    """
    title = db_config.get('title')
    properties = _build_properties(db_config.get('properties', {}))

    return notion_client.databases.create(
        parent={"page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": title}}],
        properties=properties,
    )

def _build_properties(schema_properties):
    """
    Builds the properties object for the Notion API from the schema.
    """
    notion_properties = {}
    for name, prop in schema_properties.items():
        prop_type = prop.get('type')
        if prop_type not in notion_properties:
            notion_properties[name] = {}

        if prop_type == 'title':
            notion_properties[name] = {"title": {}}
        elif prop_type == 'rich_text':
            notion_properties[name] = {"rich_text": {}}
        elif prop_type == 'number':
            format_value = prop.get('format', 'number')
            # Validate number format values for Notion API
            valid_formats = [
                'number', 'number_with_commas', 'percent', 'dollar', 'australian_dollar',
                'canadian_dollar', 'singapore_dollar', 'euro', 'pound', 'yen', 'ruble',
                'rupee', 'won', 'yuan', 'real', 'lira', 'rupiah', 'franc', 'hong_kong_dollar',
                'new_zealand_dollar', 'krona', 'norwegian_krone', 'mexican_peso', 'rand',
                'new_taiwan_dollar', 'danish_krone', 'zloty', 'baht', 'forint', 'koruna',
                'shekel', 'chilean_peso', 'philippine_peso', 'dirham', 'colombian_peso',
                'riyal', 'ringgit', 'leu', 'argentine_peso', 'uruguayan_peso', 'peruvian_sol'
            ]
            if format_value not in valid_formats:
                raise ValueError(f"Invalid number format '{format_value}' for property '{name}'. Valid formats are: {', '.join(valid_formats)}")
            notion_properties[name] = {"number": {"format": format_value}}
        elif prop_type == 'select':
            notion_properties[name] = {"select": {"options": prop.get('options', [])}}
        elif prop_type == 'multi_select':
            notion_properties[name] = {"multi_select": {"options": prop.get('options', [])}}
        elif prop_type == 'date':
            notion_properties[name] = {"date": {}}
        elif prop_type == 'files':
            notion_properties[name] = {"files": {}}
        elif prop_type == 'url':
            notion_properties[name] = {"url": {}}
        elif prop_type == 'email':
            notion_properties[name] = {"email": {}}
        elif prop_type == 'phone_number':
            notion_properties[name] = {"phone_number": {}}
        elif prop_type == 'checkbox':
            notion_properties[name] = {"checkbox": {}}

    return notion_properties

def _update_database(notion_client, existing_db, db_config, update_mode):
    """
    Updates an existing database in Notion.
    """
    db_id = existing_db['id']
    schema_properties = _build_properties(db_config.get('properties', {}))

    if update_mode == 'replace':
        # Replace mode: All existing properties are removed and replaced with the schema properties
        # The Notion API doesn't allow removing all properties at once, so we set them to the new schema.
        # Properties not in the new schema will be removed by the API if they are not required.
        # Note: The 'title' property cannot be deleted.
        properties_to_update = schema_properties

    elif update_mode == 'merge':
        # Merge mode: Add new properties and update existing ones.
        existing_properties = existing_db.get('properties', {})
        properties_to_update = existing_properties.copy()
        properties_to_update.update(schema_properties)

    else:
        print(f"Unknown update mode: {update_mode}. Skipping update.")
        return

    notion_client.databases.update(database_id=db_id, properties=properties_to_update)
    print(f"Successfully updated database '{db_config.get('title')}'.")


def apply_schema_to_notion(schema, notion_client, dry_run=False):
    """
    Applies a schema to a Notion workspace.
    If dry_run is True, it returns a plan of changes instead of applying them.
    """
    plan = []
    workspace_config = schema.get('workspace', {})
    parent_page_id = workspace_config.get('parent_page_id')
    db_key_to_id_map = {}

    if not parent_page_id:
        raise ValueError("A `parent_page_id` must be defined under `workspace` in your schema.")

    for db_config in schema.get('databases', []):
        db_title = db_config.get('title')
        match_rule = db_config.get('match', {'by': 'title', 'value': db_title})

        existing_db = None
        if match_rule.get('by') == 'title':
            if dry_run:
                plan.append(f"[DRY RUN] Would search for database with title: '{match_rule.get('value')}'")
                # In dry run, we assume it doesn't exist to show creation plan
                existing_db = None
            else:
                existing_db = find_database_by_title(notion_client, match_rule.get('value'))

        db_key = db_config.get('db_key')
        if not db_key:
            raise ValueError(f"Database '{db_title}' is missing a `db_key`.")

        if existing_db:
            db_key_to_id_map[db_key] = existing_db['id']
            update_mode = db_config.get('update_mode', 'merge')
            if dry_run:
                plan.append(f"  - Plan to UPDATE database: '{db_title}' (mode: {update_mode})")
            else:
                print(f"Updating database: '{db_title}' (mode: {update_mode})...")
                _update_database(notion_client, existing_db, db_config, update_mode)
        else:
            if dry_run:
                plan.append(f"  - Plan to CREATE database: '{db_title}'")
                # In dry run, we don't have an ID, so we use a placeholder
                db_key_to_id_map[db_key] = f"new_db_for_{db_key}"
            else:
                print(f"Creating database: '{db_title}'...")
                created_db = _create_database(notion_client, parent_page_id, db_config)
                db_id = created_db['id']
                db_key_to_id_map[db_key] = db_id
                print(f"Successfully created database '{db_title}' with ID: {db_id}")

    # Handle relations after all databases are processed
    for relation_config in schema.get('relations', []):
        from_db_key = relation_config.get('from_db')
        to_db_key = relation_config.get('to_db')
        property_name = relation_config.get('property_name')

        from_db_id = db_key_to_id_map.get(from_db_key)
        to_db_id = db_key_to_id_map.get(to_db_key)

        if not from_db_id or not to_db_id:
            on_missing = relation_config.get('on_missing', 'skip')
            if on_missing == 'error':
                raise ValueError(f"Could not find one or both databases for relation: '{from_db_key}' -> '{to_db_key}'")
            else:
                print(f"Skipping relation '{from_db_key}' -> '{to_db_key}' because one or both databases were not found.")
                continue

        relation_property = {
            "type": "relation",
            "relation": {
                "database_id": to_db_id,
                "single_property": {}  # Use single_property for one-way relations
            }
        }

        synced_property_name = relation_config.get('synced_property_name')
        if synced_property_name:
            # If we have a synced property name, it's a dual relation
            relation_property['relation'] = {
                "database_id": to_db_id,
                "dual_property": {
                    "synced_property_name": synced_property_name
                }
            }

        if dry_run:
            plan.append(f"  - Plan to CREATE RELATION '{property_name}' on '{from_db_key}' to '{to_db_key}'")
        else:
            print(f"Creating relation '{property_name}' on '{from_db_key}'...")
            notion_client.databases.update(
                database_id=from_db_id,
                properties={
                    property_name: relation_property
                }
            )
            print(f"Successfully created relation on '{from_db_key}'.")

    if dry_run:
        return plan
