"""
PSXpert - Markdown Report to High-Fidelity PDF Converter
Renders Markdown reports with professional academic/executive styling and compiles
them to PDF via headless Google Chrome / Microsoft Edge.
"""

import os
import subprocess
import sys
from markdown_it import MarkdownIt

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  @page {{
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
    @bottom-right {{
      content: counter(page);
    }}
  }}
  *, *::before, *::after {{
    box-sizing: border-box;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background-color: #ffffff;
    font-size: 13.5px;
    line-height: 1.6;
    margin: 0;
    padding: 0;
  }}
  h1 {{
    font-size: 24px;
    font-weight: 700;
    color: #0f172a;
    border-bottom: 2px solid #0284c7;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 12px;
  }}
  h2 {{
    font-size: 18px;
    font-weight: 700;
    color: #0f172a;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 6px;
    margin-top: 24px;
    margin-bottom: 10px;
  }}
  h3 {{
    font-size: 15px;
    font-weight: 600;
    color: #1e293b;
    margin-top: 18px;
    margin-bottom: 8px;
  }}
  p {{
    margin-top: 0;
    margin-bottom: 10px;
  }}
  hr {{
    border: none;
    border-top: 1px solid #cbd5e1;
    margin: 18px 0;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 14px 0 18px 0;
    font-size: 12px;
    page-break-inside: avoid;
  }}
  th, td {{
    border: 1px solid #cbd5e1;
    padding: 7px 10px;
    text-align: left;
  }}
  th {{
    background-color: #f1f5f9;
    color: #0f172a;
    font-weight: 600;
  }}
  tr:nth-child(even) {{
    background-color: #f8fafc;
  }}
  code {{
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    background-color: #f1f5f9;
    color: #0369a1;
    padding: 2px 5px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
  }}
  pre {{
    background-color: #0f172a;
    color: #f8fafc;
    padding: 12px 14px;
    border-radius: 6px;
    font-size: 11.5px;
    line-height: 1.45;
    overflow-x: auto;
    page-break-inside: avoid;
  }}
  pre code {{
    background: none;
    color: inherit;
    border: none;
    padding: 0;
  }}
  blockquote {{
    margin: 14px 0;
    padding: 10px 14px;
    background-color: #f0f9ff;
    border-left: 4px solid #0284c7;
    color: #0369a1;
    font-size: 13px;
    page-break-inside: avoid;
  }}
  blockquote p {{
    margin: 0;
  }}
  ul, ol {{
    margin-top: 0;
    margin-bottom: 12px;
    padding-left: 22px;
  }}
  li {{
    margin-bottom: 4px;
  }}
  .badge {{
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }}
  .badge-success {{ background-color: #dcfce7; color: #15803d; }}
  .badge-warning {{ background-color: #fef9c3; color: #a16207; }}
  .badge-danger  {{ background-color: #fee2e2; color: #b91c1c; }}
  .badge-info    {{ background-color: #e0f2fe; color: #0369a1; }}
  .print-footer {{
    margin-top: 30px;
    border-top: 1px solid #e2e8f0;
    padding-top: 8px;
    font-size: 11px;
    color: #64748b;
    text-align: center;
  }}
</style>
</head>
<body>
{content}
<div class="print-footer">
  PSXpert Quantitative Stock Analysis & Prediction Platform — Confidential Evaluation Report
</div>
</body>
</html>
"""


def find_browser():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def convert_md_to_pdf(md_path: str, pdf_path: str):
    if not os.path.exists(md_path):
        print(f"Error: Source Markdown file not found: {md_path}")
        return False

    browser = find_browser()
    if not browser:
        print("Error: Chrome or Edge executable not found for headless PDF generation.")
        return False

    print(f"-> Reading markdown from {md_path}...")
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    title = "PSXpert Evaluation Report"
    for line in md_text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # Parse Markdown using markdown-it
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    html_body = md.render(md_text)

    # Style blockquotes with GitHub-style alerts if present
    html_body = html_body.replace("<blockquote>\n<p>[!NOTE]", "<blockquote class='alert-note'><p><strong>NOTE:</strong>")
    html_body = html_body.replace("<blockquote>\n<p>[!IMPORTANT]", "<blockquote class='alert-important'><p><strong>IMPORTANT:</strong>")
    html_body = html_body.replace("<blockquote>\n<p>[!WARNING]", "<blockquote class='alert-warning'><p><strong>WARNING:</strong>")

    full_html = HTML_TEMPLATE.format(title=title, content=html_body)

    temp_html = md_path.replace(".md", "_temp.html")
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(full_html)

    abs_html = os.path.abspath(temp_html)
    abs_pdf = os.path.abspath(pdf_path)

    print(f"-> Rendering to PDF using {os.path.basename(browser)}...")
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={abs_pdf}",
        f"file:///{abs_html.replace(os.sep, '/')}"
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if os.path.exists(temp_html):
        try:
            os.remove(temp_html)
        except Exception:
            pass

    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000:
        size_kb = os.path.getsize(pdf_path) / 1024
        print(f"[OK] Generated PDF successfully ({size_kb:.1f} KB): {pdf_path}")
        return True
    else:
        print(f"Failed to generate PDF. Subprocess output: {res.stderr}")
        return False


if __name__ == "__main__":
    targets = [
        (
            os.path.join("reports", "model_evaluation", "model_accuracy_maximization_report.md"),
            os.path.join("reports", "model_evaluation", "model_accuracy_maximization_report.pdf"),
        ),
        (
            os.path.join("reports", "model_evaluation", "psxpert_model_accuracy_verification_and_news_integration_report.md"),
            os.path.join("reports", "model_evaluation", "psxpert_model_accuracy_verification_and_news_integration_report.pdf"),
        )
    ]

    for md, pdf in targets:
        if os.path.exists(md):
            convert_md_to_pdf(md, pdf)
