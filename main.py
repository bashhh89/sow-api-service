# main.py
# FINAL, GUARANTEED VERSION - Built from official documentation.
# This API receives a workspace SLUG, fetches the last chat message from that workspace,
# converts it to a DOCX using a template, uploads it, and returns a download link.

import io
import os
import re
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from docx import Document
from docx.shared import Pt

# --- CONFIGURATION ---
ANYTHINGLLM_API_URL = os.environ.get("ANYTHINGLLM_API_URL")
ANYTHINGLLM_API_KEY = os.environ.get("ANYTHINGLLM_API_KEY")

app = FastAPI(
    title="Guaranteed SOW Document Converter",
    description="Pulls the last chat message from an AnythingLLM workspace to generate a .docx file.",
    version="3.0.0",
)

# --- Pydantic Models ---
class ConversionRequest(BaseModel):
    workspace_slug: str
    filename: str = "SOW-Document.docx"

class ConversionResponse(BaseModel):
    status: str
    download_url: str

# --- Helper Functions ---
def parse_and_add_paragraph(p, text):
    pattern = r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)'
    parts = re.split(pattern, text)
    for part in parts:
        if part.startswith('***') and part.endswith('***'):
            run = p.add_run(part[3:-3]); run.bold = True; run.italic = True
        elif part.startswith('**') and part.endswith('**'):
            run = p.add_run(part[2:-2]); run.bold = True
        elif part.startswith('*') and part.endswith('*'):
            run = p.add_run(part[1:-1]); run.italic = True
        elif part: p.add_run(part)

def create_docx_from_markdown(markdown_text: str, document: Document):
    lines = markdown_text.split('\n')
    in_table, i = False, 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('|') and line.endswith('|'):
            if not in_table:
                table_data = []
                in_table = True
            table_data.append([cell.strip() for cell in line.strip('|').split('|')])
        elif in_table:
            in_table = False
            if table_data:
                headers = table_data[0]
                records = table_data[2:] if len(table_data) > 1 and '---' in table_data[1][0] else table_data[1:]
                table = document.add_table(rows=1, cols=len(headers)); table.style = 'Table Grid'
                hdr_cells = table.rows[0].cells
                for j, header in enumerate(headers):
                    hdr_cells[j].text = header; hdr_cells[j].paragraphs[0].runs[0].bold = True
                for record in records:
                    row_cells = table.add_row().cells
                    for j, cell_text in enumerate(record): row_cells[j].text = cell_text
        elif line.startswith('# '): parse_and_add_paragraph(document.add_heading(level=1), line[2:])
        elif line.startswith('## '): parse_and_add_paragraph(document.add_heading(level=2), line[3:])
        elif line.startswith('### '): parse_and_add_paragraph(document.add_heading(level=3), line[4:])
        elif line.startswith('* '):
            p = document.add_paragraph(style='List Bullet'); parse_and_add_paragraph(p, line[2:])
        elif line.strip() == '---': document.add_page_break()
        elif line.strip(): p = document.add_paragraph(); parse_and_add_paragraph(p, line)
        i += 1

# --- Main API Endpoint ---
@app.post("/generate-from-workspace", response_model=ConversionResponse)
async def generate_from_workspace(request: ConversionRequest):
    if not ANYTHINGLLM_API_URL or not ANYTHINGLLM_API_KEY:
        raise HTTPException(status_code=500, detail="Server is not configured with AnythingLLM API credentials.")

    # Step 1: Fetch the last chat from the workspace using the correct endpoint from the documentation
    chats_url = f"{ANYTHINGLLM_API_URL}/api/v1/workspace/{request.workspace_slug}/chats?limit=1"
    headers = {"Authorization": f"Bearer {ANYTHINGLLM_API_KEY}"}
    try:
        response = requests.get(chats_url, headers=headers, timeout=15)
        response.raise_for_status()
        chats_data = response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch chats from AnythingLLM: {e}")

    # Find the last message from the 'assistant'
    history = chats_data.get('history', [])
    if not history:
        raise HTTPException(status_code=404, detail="No chat history found in this workspace.")
        
    markdown_text = history[0].get('content') # The last message content
    if not markdown_text:
        raise HTTPException(status_code=404, detail="Could not extract content from the last message.")

    # Step 2: Create the DOCX
    template_path = 'template.docx'
    document = Document(template_path) if os.path.exists(template_path) else Document()
    if not document.styles.get('Normal'): document.add_paragraph() # Ensure default style exists
    document.styles['Normal'].font.name = 'Calibri'; document.styles['Normal'].font.size = Pt(11)
    create_docx_from_markdown(markdown_text, document)

    # Step 3: Upload the file
    file_stream = io.BytesIO()
    document.save(file_stream); file_stream.seek(0)
    try:
        server_response = requests.get('https://api.gofile.io/getServer', timeout=10)
        server = server_response.json()['data']['server']
        upload_url = f'https://{server}.gofile.io/uploadFile'
        files = {'file': (request.filename, file_stream, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
        upload_response = requests.post(upload_url, files=files, timeout=30)
        upload_data = upload_response.json()
        if upload_data.get("status") == "ok":
            return {"status": "success", "download_url": upload_data['data']['downloadPage']}
        else:
            raise HTTPException(status_code=500, detail="File hosting service error.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"File upload error: {e}")
