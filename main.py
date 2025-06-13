import io
import os
import re
import requests
from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel
from docx import Document
from docx.shared import Pt
from docx.table import _Cell

# Initialize the FastAPI app
app = FastAPI(
    title="Markdown to DOCX Converter",
    description="An API that receives Markdown text, creates a .docx file, uploads it, and returns a download link.",
    version="1.2.0",
)

# Pydantic models for API request and response
class MarkdownRequest(BaseModel):
    markdown_text: str
    filename: str = "document.docx"

class ConversionResponse(BaseModel):
    status: str
    download_url: str


def parse_and_add_paragraph(paragraph_text: str, document: Document):
    """
    Parses a line of text for inline markdown (bold, italic) and adds
    it to the document with appropriate formatting.
    """
    p = document.add_paragraph()
    # This pattern finds ***text*** (bold/italic), **text** (bold), or *text* (italic)
    pattern = r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)'
    parts = re.split(pattern, paragraph_text)
    
    for part in parts:
        if part.startswith('***') and part.endswith('***'):
            run = p.add_run(part[3:-3])
            run.bold = True
            run.italic = True
        elif part.startswith('**') and part.endswith('**'):
            run = p.add_run(part[2:-2])
            run.bold = True
        elif part.startswith('*') and part.endswith('*'):
            run = p.add_run(part[1:-1])
            run.italic = True
        elif part:
            p.add_run(part)

@app.post("/convert/markdown-to-docx", 
          response_model=ConversionResponse,
          summary="Convert Markdown to a DOCX Download Link",
          description="Takes Markdown text, creates a .docx file using 'template.docx' if available, uploads it, and returns a public download link.")
async def convert_markdown_to_docx(request: MarkdownRequest):
    """
    This endpoint processes incoming Markdown, creates a DOCX file,
    uploads it to a temporary hosting service, and returns a download link.
    """
    markdown_text = request.markdown_text
    template_path = 'template.docx'

    # --- TEMPLATE HANDLING ---
    if os.path.exists(template_path):
        document = Document(template_path)
        document.add_paragraph() 
    else:
        document = Document()
        style = document.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)

    # --- PARSING LOGIC ---
    lines = markdown_text.split('\n')
    in_table = False
    table_data = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # (Table, Heading, and List parsing logic remains the same)
        if line.startswith('|') and line.endswith('|'):
            if not in_table: in_table = True
            table_data.append([cell.strip() for cell in line.strip('|').split('|')])
            i += 1
            continue
        elif in_table:
            in_table = False
            if table_data:
                headers = table_data[0]
                records = table_data[2:] if len(table_data) > 1 and '---' in table_data[1][0] else table_data[1:]
                table = document.add_table(rows=1, cols=len(headers))
                table.style = 'Table Grid'
                hdr_cells = table.rows[0].cells
                for j, header in enumerate(headers):
                    hdr_cells[j].text = header
                    hdr_cells[j].paragraphs[0].runs[0].bold = True
                for record in records:
                    row_cells = table.add_row().cells
                    for j, cell_text in enumerate(record):
                        row_cells[j].text = cell_text
            table_data = []
        
        if i < len(lines) and lines[i].strip().startswith('|'):
             continue
        if line.startswith('# '): document.add_heading(line[2:], level=1)
        elif line.startswith('## '): document.add_heading(line[3:], level=2)
        elif line.startswith('### '): document.add_heading(line[4:], level=3)
        elif line.startswith('* '):
            parse_and_add_paragraph(line[2:], document)
            document.paragraphs[-1].style = 'List Bullet'
        elif line.strip() == '---': document.add_page_break()
        elif line.strip(): parse_and_add_paragraph(line, document)
        i += 1

    # --- FILE PREPARATION & UPLOAD ---
    file_stream = io.BytesIO()
    document.save(file_stream)
    file_stream.seek(0)

    # --- UPLOAD TO GOFILE.IO ---
    try:
        # Step 1: Get the best available server from GoFile's API
        server_response = requests.get('https://api.gofile.io/getServer', timeout=10)
        server_response.raise_for_status()
        server = server_response.json()['data']['server']
        
        # Step 2: Upload the in-memory file to the server
        upload_url = f'https://{server}.gofile.io/uploadFile'
        files = {
            'file': (request.filename, file_stream.read(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        }
        upload_response = requests.post(upload_url, files=files, timeout=30)
        upload_response.raise_for_status()
        
        upload_data = upload_response.json()

        if upload_data.get("status") == "ok":
            download_link = upload_data['data']['downloadPage']
            return {"status": "success", "download_url": download_link}
        else:
            # If GoFile reports an error, relay it.
            raise HTTPException(status_code=500, detail=f"File hosting service failed: {upload_data.get('status')}")

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error communicating with file hosting service: {e}")
    except Exception as e:
        # Catch any other unexpected errors.
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during file upload: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
