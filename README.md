# Notionate: Notion Resource Management Automation

This tool automates Notion workspace configuration and content management using simple, human-readable files.

## Overview

This document defines three portable standards to configure a workspace: Schema Map (YAML), Content (YAML/CSV), and Markdown Pages. You can use them via a command line tool. All standards are idempotent; re-running the same files updates what exists without creating duplicates.

### Who this is for

*   **Non-technical users** who want a simple, readable format to manage Notion content.
*   **Technical users** who want a stable contract for automating Notion workflows.

## Core Concepts

*   **`db_key`**: A short, stable ID you assign to each database (e.g., `customers`). It is used to reference databases in other files.
*   **`external_id`**: A stable ID you assign to each row/record in a database. This is used to safely update records without creating duplicates.
*   **`match` rules**: Rules for how to find existing objects when updating. For databases, matching is done by title. For records, matching is done by `external_id` or another property you specify.

## Interface (CLI)

The tool is run via the command line.

**CLI examples:**

```bash
# Apply the schema to create/update databases
./scripts/tool apply-schema schema.yaml

# Ingest data from a YAML file
./scripts/tool ingest data.yaml

# Ingest data from a CSV file (requires a mapping file)
./scripts/tool ingest data.csv --map map.yaml

# Publish a directory of Markdown files as Notion pages
./scripts/tool publish-pages pages/

# Perform a dry run to see what changes would be made
./scripts/tool plan --schema schema.yaml --data data.yaml
```

---

## Standard 1: Schema Map (YAML)

### Purpose

Define databases, their properties, and relations in a single YAML file. This allows you to create or update your workspace schema safely and repeatably.

*   **File name**: Any `.yaml` file (e.g., `schema.yaml`).

### Top-level keys

*   **`version`**: The semantic version of the spec.
*   **`workspace`**: Global settings. Currently, only `parent_page_id` is supported, which defines the Notion page where new databases will be created.
*   **`databases`**: A list of database definitions.
*   **`relations`**: A list of relation properties to create after all databases exist.

### Database Definition

*   **`db_key`**: (Required) A stable identifier for the database (e.g., `customers`, `orders`).
*   **`title`**: (Required) The display name users will see in Notion.
*   **`match`**: (Optional) How to find an existing database to update.
    *   `by`: `title` (this is the only supported value).
    *   `value`: The exact title to match against.
*   **`update_mode`**: (Optional) `merge` (default) or `replace`.
    *   `merge`: Add missing properties/options and keep existing ones.
    *   `replace`: Make the database schema match the file exactly. Properties not in the file will be removed.
*   **`properties`**: (Required) A map of `property_name` to its definition.

### Property Types

The following property types are supported:

*   `title`
*   `rich_text`
*   `number` (can include a `format` key: `number`, `percent`, or specific currency formats like `dollar`, `euro`, `pound`, etc.)
*   `select` (must include an `options` list of `{name, color?}` objects)
*   `multi_select` (must include an `options` list of `{name, color?}` objects)
*   `date`
*   `files`
*   `url`
*   `email`
*   `phone_number`
*   `checkbox`
*   `relation` (Note: These are defined in the top-level `relations` section, not inline).

### Relations Section

*   **`from_db`**: The `db_key` of the source database.
*   **`property_name`**: The name of the relation property to create on the source database.
*   **`to_db`**: The `db_key` of the target database.
*   **`synced_property_name`**: (Optional) The name of the corresponding property created on the target database for bi-directional links.
*   **`on_missing`**: `skip` (default) or `error`. What to do if one of the databases in the relation is not found.

### Schema Example

```yaml
version: "1.0"
workspace:
  parent_page_id: "YOUR_NOTION_PARENT_PAGE_ID"

databases:
  - db_key: customers
    title: "Customers"
    match: { by: title, value: "Customers" }
    update_mode: merge
    properties:
      Name: { type: title }
      Email: { type: email }
      Status:
        type: select
        options:
          - { name: "Active" }
          - { name: "Prospect" }
      Created At: { type: date }

  - db_key: orders
    title: "Orders"
    properties:
      Order Number: { type: title }
      Amount: { type: number, format: dollar }
      Paid: { type: checkbox }

relations:
  - from_db: orders
    property_name: "Customer"
    to_db: customers
    synced_property_name: "Orders"
```

---

## Standard 2: Content Ingestion (YAML and CSV)

### Purpose

Add or update records in your Notion databases from human-friendly YAML or CSV files.

### Common Settings (YAML `defaults`)

*   **`match_on`**: The property to use for matching existing records. Defaults to `external_id`. Can be set to the name of any property.
*   **`create_missing_select_options`**: `true` or `false` (default `true`). If true, new options will be added to `select` and `multi_select` properties if they appear in the data.

### YAML Structure (`data.yaml`)

*   **`data`**: A map of `db_key` to a list of records.
*   Each record is a map of property names to values. An `external_id` property is strongly recommended for stable updates.

### Supported Value Shapes

*   **`title`, `rich_text`, `url`, `email`, `phone_number`**: "A string"
*   **`number`**: 123 or 45.6
*   **`select`**: "Option Name"
*   **`multi_select`**: ["Option A", "Option B"]
*   **`date`**: "YYYY-MM-DD" or `{ "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" }`
*   **`checkbox`**: `true` or `false`
*   **`files`**: `["https://example.com/a.pdf"]` or `[{ "url": "https://...", "name": "..." }]`
*   **`relation`**: **NOTE: Ingesting relation values is not currently supported.**

### YAML Data Example

```yaml
version: "1.0"
defaults:
  match_on: external_id
  create_missing_select_options: true

data:
  customers:
    - external_id: "cust-001"
      Name: "Acme Corp"
      Email: "info@acme.com"
      Status: "Active"
      Created At: "2025-01-10"

  orders:
    - external_id: "ord-1001"
      "Order Number": "SO-1001"
      Amount: 1250.50
      Paid: true
      # The 'Customer' relation field cannot be set via ingestion yet.
```

### CSV Ingestion (`data.csv` + `map.yaml`)

For CSV files, a `map.yaml` file is required to specify the target database and map CSV columns to Notion properties.

**`map.yaml` Example:**

```yaml
version: "1.0"
target_db: customers # The db_key of the target database
defaults:
  match_on: external_id
columns:
  # Maps CSV column header to a Notion Property
  external_id: { as: external_id }
  Name: { as: Name } # 'as' is the property name in Notion
  Email: { as: Email }
```

**`orders.csv` Example:**

```csv
external_id,Name,Email
cust-002,Beta Corp,contact@beta.corp
```

---

## Standard 3: Markdown Pages

### Purpose

Author pages in Markdown and publish them to your Notion workspace.

### Front Matter (YAML)

Each `.md` file can contain a YAML front matter block for configuration.

*   **`title`**: (Required) The title of the Notion page.
*   **`parent_page_id`**: (Required) The ID of the parent page in Notion.
*   **`icon`**: (Optional) An emoji for the page icon.
*   **`cover_url`**: (Optional) A URL for the page cover image.

### Supported Markdown to Page Blocks

The conversion from Markdown to Notion blocks is currently limited. The following are supported:

*   `#`, `##`, `###` → Headings 1–3
*   Paragraphs → Paragraph blocks

**NOTE**: Other Markdown features like lists, dividers, callouts, and links are **not yet supported**.

### Data Linking and Embedding

**NOTE**: Linking to databases, records, or queries (`[[db:...]]`, `[[record:...]]`) and embedding live data views are **not yet implemented**.

### Example Page (`my-page.md`)

```markdown
---
title: "Account Overview"
icon: "📊"
parent_page_id: "YOUR_NOTION_PARENT_PAGE_ID"
---

# Team Dashboard

This is the single source of truth for our team.

## Key Accounts

This section provides an overview of our most important accounts.
```

## Operational Workflow

1.  **Apply Schema**: Run `apply-schema` to create or update your database structures.
2.  **Ingest Data**: Run `ingest` to populate your databases with records.
3.  **Publish Pages**: Run `publish-pages` to create or update your workspace pages from Markdown files.
4.  **Plan**: Use the `plan` command at any time to preview changes without modifying your workspace.
