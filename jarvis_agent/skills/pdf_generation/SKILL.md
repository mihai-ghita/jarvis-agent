---
name: pdf-generation
description: Use when the user asks to create, build, or export a PDF file.
---

# PDF generation

Generate PDFs by writing a Python script that uses the `reportlab` library,
then running it with the `run_python_script` tool. `reportlab` is pure
Python — it has no system dependencies (unlike, say, `wkhtmltopdf`), so it
installs cleanly and works reliably inside the sandbox container.

## Minimal working example

```python
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

doc = SimpleDocTemplate("/sandbox/output.pdf", pagesize=letter)
styles = getSampleStyleSheet()

story = [
    Paragraph("Hello, PDF!", styles["Title"]),
    Spacer(1, 12),
    Paragraph(
        "This document was generated inside a sandboxed container.",
        styles["Normal"],
    ),
]

doc.build(story)
```

Adapt the `story` list to whatever content the user actually asked for
(more paragraphs, tables, images, etc.) using other `reportlab.platypus`
flowables as needed.

## Calling the tool

When invoking `run_python_script` for a PDF-generation task:

- Pass `libraries=["reportlab"]` so it gets installed in the container
  before the script runs.
- Write the output to a path under `/sandbox` (e.g. `/sandbox/output.pdf`).
- Put the produced filename (e.g. `"output.pdf"`) in `output_files` so it
  gets copied back to the workspace directory on the host.
