# Markdown to DOCX Converter API

An API service that converts Markdown text to formatted DOCX files, uploads them, and returns download links.

## Features

- Convert Markdown text to properly formatted DOCX documents
- Support for headings, bold, italic, tables, and lists
- Optional template support (use your own letterhead)
- Automatic file hosting and shareable download links

## API Endpoints

### `/convert/markdown-to-docx` (POST)

Converts Markdown text to a DOCX file, uploads it, and returns a download link.

#### Request Body

```json
{
  "markdown_text": "# Your Markdown Here\n\nThis is **bold** and *italic* text.",
  "filename": "document.docx"
}
```

#### Response

```json
{
  "status": "success",
  "download_url": "https://gofile.io/d/abcdef"
}
```

## Setup and Deployment

### Local Development

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the server:
   ```
   uvicorn main:app --reload
   ```

3. Access the API documentation at `http://localhost:8000/docs`

### Docker Deployment

1. Build the Docker image:
   ```
   docker build -t sow-api-service .
   ```

2. Run the container:
   ```
   docker run -p 8000:8000 sow-api-service
   ```

## Template Support

Place a DOCX file named `template.docx` in the same directory as the application to use it as a template/letterhead for all generated documents.
