# YAML and Markdown to Notion

This tool provides a suite of utilities to automate Notion resource management, allowing you to synchronize data from local files into your Notion workspace.

## Features

- **Schema Management**: Define and apply database schemas from a YAML file.
- **Data Ingestion**: Ingest data from YAML or CSV files into Notion databases.
- **Markdown Publishing**: Publish Markdown files from a local directory directly into Notion pages.

## Enhanced Markdown Support

The tool now supports a wide range of Markdown features when publishing pages, converting them into native Notion blocks.

### Supported Elements

- **Headings**: `# h1`, `## h2`, `### h3`
- **Rich Text**: **bold**, *italic*, `inline code`
- **Lists**: Numbered and bulleted lists.
- **Code Blocks**: Fenced code blocks with syntax highlighting.
- **Tables**: GFM-style tables.
- **Images**: Images are converted to Notion image blocks.
- **Dividers**: Horizontal rules (`---`) are converted to dividers.
- **Links**: Standard Markdown links.
- **Callouts**: Notion-style callouts.

### Conventions

To ensure proper parsing, please follow these conventions in your Markdown files:

- **Images**: To render an image as a block-level element, it must be in its own paragraph.
  ```markdown
  This is some text.

  ![An image](https://example.com/image.png)

  More text.
  ```

- **Callouts**: Callouts can be created using blockquote syntax with a special `[!NOTE]` marker.
  ```markdown
  > [!NOTE]
  > This is a callout.
  ```

## Usage

The main entry point is the `scripts/tool` command-line utility.

### Prerequisites

- Python 3
- `pip`

### Installation

1.  Clone the repository.
2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Set the `NOTION_API_KEY` environment variable with your Notion integration token.

### Commands

- `apply-schema <schema_file>`: Apply a database schema to Notion.
- `ingest <data_file>`: Ingest data from a YAML or CSV file.
- `publish-pages <pages_directory>`: Publish Markdown files from a directory to Notion.
- `plan`: Show a dry run of the changes that would be made.
