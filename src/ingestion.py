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

def ingest_data_to_notion(data, notion_client, map_config=None, dry_run=False):
    """
    Ingests data into Notion.
    If dry_run is True, it returns a plan of changes instead of applying them.
    """
    plan = []
    if dry_run:
        plan.append("[DRY RUN] Planning data ingestion...")

        # Handle YAML structure
        if 'data' in data:
            data_items = data.get('data', {})
            if not data_items:
                plan.append("  - No data found to ingest.")
            for db_key, records in data_items.items():
                plan.append(f"  - Plan to ingest {len(records)} record(s) into '{db_key}'")
        # Handle CSV structure (list of dicts)
        elif isinstance(data, list):
            plan.append(f"  - Plan to ingest {len(data)} record(s) from CSV.")

        return plan
    else:
        print("Ingesting data...")
        # In the future, this will contain the logic to interact with the Notion API.
        pass
