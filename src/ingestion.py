import yaml
import csv

def load_data(data_file):
    """
    Loads data from a YAML or CSV file.
    """
    if data_file.endswith('.yaml') or data_file.endswith('.yml'):
        with open(data_file, 'r') as f:
            return yaml.safe_load(f)
    elif data_file.endswith('.csv'):
        with open(data_file, 'r') as f:
            return list(csv.DictReader(f))
    else:
        raise ValueError("Unsupported file type. Please use .yaml, .yml, or .csv")

from src.notion_utils import find_database_by_title

def _find_page_by_property(notion_client, db_id, property_name, property_value, property_type='rich_text'):
    """
    Finds a page in a database by a property's value.
    Note: This is a simplified implementation. A robust solution would handle different property types.
    """
    filter_conditions = {
        "property": property_name,
        property_type: {
            "equals": property_value
        }
    }

    response = notion_client.databases.query(database_id=db_id, filter=filter_conditions)
    return response.get('results')[0] if response.get('results') else None

def _ensure_select_options(notion_client, db_id, prop_name, prop_definition, options_to_ensure, prop_type):
    """
    Ensures that the given options exist for a select or multi-select property.
    If not, it updates the database to add them.
    """
    existing_options = {opt['name'] for opt in prop_definition.get('options', [])}
    new_options = [opt for opt in options_to_ensure if opt not in existing_options]

    if new_options:
        print(f"Adding new options to '{prop_name}': {new_options}")
        updated_options = prop_definition.get('options', []) + [{'name': name} for name in new_options]

        notion_client.databases.update(
            database_id=db_id,
            properties={
                prop_name: {
                    prop_type: {
                        "options": updated_options
                    }
                }
            }
        )
        # Update the local definition to avoid re-fetching
        prop_definition['options'] = updated_options

def _build_page_properties(record, db_id, db_properties, notion_client, create_missing_select_options):
    """
    Builds the page properties for the Notion API from a record.
    """
    page_properties = {}
    for key, value in record.items():
        prop_info = db_properties.get(key)
        if not prop_info:
            if key != 'external_id':
                print(f"Warning: Property '{key}' not found in database schema. Skipping.")
            continue

        prop_type = prop_info['type']

        if key == 'external_id':
             page_properties[key] = {'rich_text': [{'text': {'content': str(value)}}]}
        elif prop_type == 'title':
            page_properties[key] = {'title': [{'text': {'content': str(value)}}]}
        elif prop_type == 'rich_text':
            page_properties[key] = {'rich_text': [{'text': {'content': str(value)}}]}
        elif prop_type == 'number':
            page_properties[key] = {'number': value}
        elif prop_type == 'checkbox':
            page_properties[key] = {'checkbox': value}
        elif prop_type == 'url':
            page_properties[key] = {'url': value}
        elif prop_type == 'email':
            page_properties[key] = {'email': value}
        elif prop_type == 'phone_number':
            page_properties[key] = {'phone_number': value}
        elif prop_type == 'date':
            if isinstance(value, str):
                page_properties[key] = {'date': {'start': value}}
            elif isinstance(value, dict):
                page_properties[key] = {'date': value}
        elif prop_type == 'files':
            files_list = []
            for item in value:
                if isinstance(item, str):
                    files_list.append({'name': item.split('/')[-1], 'external': {'url': item}})
                elif isinstance(item, dict) and 'url' in item:
                    files_list.append({'name': item.get('name', item['url'].split('/')[-1]), 'external': {'url': item['url']}})
            page_properties[key] = {'files': files_list}
        elif prop_type == 'select':
            if create_missing_select_options:
                _ensure_select_options(notion_client, db_id, key, prop_info['select'], [value], prop_type)
            page_properties[key] = {'select': {'name': value}}
        elif prop_type == 'multi_select':
            if create_missing_select_options:
                _ensure_select_options(notion_client, db_id, key, prop_info['multi_select'], value, prop_type)
            page_properties[key] = {'multi_select': [{'name': v} for v in value]}
        elif prop_type == 'relation':
            related_pages_ids = []
            values = value if isinstance(value, list) else [value]

            for v in values:
                # For now, we only support finding related page by title (string value)
                if isinstance(v, str):
                    # To find by title, we need to know the related database's title property name.
                    # This requires an extra API call and makes things complex.
                    # For this implementation, we assume a simple search can find it.
                    # This is a simplification and may not be robust.
                    related_db_id = prop_info['relation']['database_id']

                    # This is a hack: we don't know the title property name of the other db.
                    # We are assuming a simple query on the string value will work, which is not guaranteed.
                    # A proper implementation would retrieve the related DB schema to find its title property.

                    # For now, this part is too complex to implement fully without more info.
                    # We will just show a warning.
                    print(f"Warning: Relation property '{key}' is not fully supported yet. Skipping.")

    return page_properties

def _update_page(notion_client, page_id, properties):
    """
    Updates a page in Notion.
    """
    notion_client.pages.update(page_id=page_id, properties=properties)

def _transform_csv_row(row, map_config):
    """
    Transforms a CSV row into a standard record format using a map config.
    """
    record = {}
    column_map = map_config.get('columns', {})
    for csv_header, mapping in column_map.items():
        if csv_header in row:
            value = row[csv_header]
            target_key = mapping.get('as', csv_header)

            # Here we just copy the value. The property building logic will handle types.
            record[target_key] = value

    return record

def ingest_data_to_notion(data, notion_client, map_config=None, dry_run=False):
    """
    Ingests data into Notion.
    If dry_run is True, it returns a plan of changes instead of applying them.
    """
    plan = []

    # Handle YAML data
    if isinstance(data, dict):
        defaults = data.get('defaults', {})
        data_items = data.get('data', {})
    # Handle CSV data
    elif isinstance(data, list):
        if not map_config:
            raise ValueError("A map file is required for CSV ingestion.")
        defaults = map_config.get('defaults', {})
        target_db = map_config.get('target_db')
        if not target_db:
            raise ValueError("Map file must specify a `target_db`.")

        transformed_records = [_transform_csv_row(row, map_config) for row in data]
        data_items = {target_db: transformed_records}
    else:
        raise ValueError("Unsupported data format.")

    match_on = defaults.get('match_on', 'external_id')
    create_missing_select_options = defaults.get('create_missing_select_options', True)

    for db_key, records in data_items.items():
        if dry_run:
            plan.append(f"[DRY RUN] Plan to find database with title: '{db_key}'")
            db = {"id": f"fake_id_for_{db_key}", "properties": {}} # Fake db for planning
        else:
            print(f"Finding database '{db_key}'...")
            db = find_database_by_title(notion_client, db_key)

        if not db:
            message = f"Database with key '{db_key}' not found. Skipping."
            if dry_run:
                plan.append(f"  - {message}")
            else:
                print(message)
            continue

        db_id = db['id']
        db_properties = db.get('properties', {})

        for record in records:
            match_value = record.get(match_on)
            if not match_value:
                print(f"Warning: Record is missing match key '{match_on}'. Skipping.")
                continue

            existing_page = None
            if not dry_run:
                prop_type = 'title' if match_on == 'title' else 'rich_text'
                existing_page = _find_page_by_property(notion_client, db_id, match_on, match_value, prop_type)

            if dry_run:
                # In dry-run, we don't build properties as it might try to update a schema
                page_properties = {}
            else:
                page_properties = _build_page_properties(record, db_id, db_properties, notion_client, create_missing_select_options)

            if existing_page:
                if dry_run:
                    plan.append(f"  - Plan to UPDATE page in '{db_key}' (matched on {match_on}: {match_value})")
                else:
                    print(f"Updating page in '{db_key}' (matched on {match_on}: {match_value})...")
                    _update_page(notion_client, existing_page['id'], page_properties)
                    print(f"Successfully updated page.")
            else:
                if dry_run:
                    plan.append(f"  - Plan to CREATE page in '{db_key}' ({match_on}: {match_value})")
                else:
                    print(f"Creating page in '{db_key}' ({match_on}: {match_value})...")
                    notion_client.pages.create(parent={"database_id": db_id}, properties=page_properties)
                    print(f"Successfully created page.")

    if dry_run:
        return plan
