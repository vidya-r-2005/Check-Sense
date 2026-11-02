"""Script to insert all seven figures, update captions, and modify Table 1 in CheckSense_IEEE_Report.docx."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.shared import Inches
from docx.text.paragraph import Paragraph

REPO_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = REPO_ROOT / "reports" / "figures"

INPUT_DOCX = Path(r"C:\Users\2005v\OneDrive\Desktop\CheckSense_IEEE_Report.docx")
OUTPUT_DESKTOP_DOCX = Path(r"C:\Users\2005v\OneDrive\Desktop\CheckSense_IEEE_Report_Completed.docx")
OUTPUT_DOCS_DOCX = REPO_ROOT / "docs" / "CheckSense_IEEE_Report.docx"
OUTPUT_DESKTOP_PDF = Path(r"C:\Users\2005v\OneDrive\Desktop\CheckSense_IEEE_Report_Completed.pdf")
OUTPUT_DOCS_PDF = REPO_ROOT / "docs" / "CheckSense_IEEE_Report.pdf"

CAPTIONS = {
    1: "Fig. 1.  Detailed end-to-end CheckSense software engineering architecture: multi-format specification ingestion (PDF, DOCX, TXT), structural normalization and normative modal gating, spaCy 7-tuple semantic frame extraction, specialized tri-head defect detection (Head 4a ambiguity, Head 4b incompleteness, Head 4c implicit constraints), candidate-level MLP fusion and token Jaccard deduplication, grounded clarification formulating syntactic contract questions, stakeholder domain input, and governed refinement with 100% strict numeric preservation and ISO/IEC/IEEE 29148 evaluation.",
    2: "Fig. 2.  Specialised multi-head model architecture: Head 4a (lexicon regexes, TF-IDF logistic regression smell classifier, and token BIO tagger), Head 4b (dependency slot completeness rules), Head 4c (8-class domain ontology matrix), 24-dimensional dense feature representation, candidate-level MLP fusion scorer, and syntactic/numeric guardrails.",
    3: "Fig. 3.  Authentic CheckSense interactive studio interface: (a) document overview metrics and defect distribution; (b) requirement explorer with localized span highlighting; (c) clarification workspace with grounded questions and stakeholder input; and (d) governed refinement gate with numeric audit verification.",
    4: "Fig. 4.  Dataset composition and corpus filtering funnel: (a) deterministic preprocessing funnel for 13,394 raw sentences from the PURE corpus; (b) requirement counts across project benchmarks (ARTA, PURE, QuRE, sequestered test pool, and pilot sample).",
    5: "Fig. 5.  Comparative defect detection performance across baselines and ablation studies (macro-F1). Hatched bars denote in-sample resubstitution on the training pilot; solid bars indicate genuine evaluated pipelines and ablations; dashed reference line indicates genuine out-of-fold generalization (0.650).",
    6: "Fig. 6.  Reliability and probability calibration of the Phase 5 MLP fusion scorer: (a) 10-bin reliability diagram with empirical accuracy vs. mean predicted confidence (ECE = 38.3%); (b) sample count distribution across confidence bins.",
    7: "Fig. 7.  Authentic step-by-step worked example: requirement extraction, localized span detection ('quickly'), grounded clarification formulation, stakeholder answer integration, governed rewrite, and 100% verified numeric preservation audit.",
}

FIGURE_FILES = {
    1: FIGURES_DIR / "fig1_system_architecture.png",
    2: FIGURES_DIR / "fig2_model_architecture.png",
    3: FIGURES_DIR / "fig3_application_screenshots.png",
    4: FIGURES_DIR / "fig4_dataset_statistics.png",
    5: FIGURES_DIR / "fig5_model_performance.png",
    6: FIGURES_DIR / "fig6_model_reliability.png",
    7: FIGURES_DIR / "fig7_worked_example.png",
}


def complete_report():
    print(f"[*] Opening {INPUT_DOCX}...")
    doc = docx.Document(str(INPUT_DOCX))

    # 1. Update outdated dependency description in Section IV-D
    for p in doc.paragraphs:
        if "written in Python 3.12 with PyTorch 2.3.1" in p.text:
            print("[*] Updating outdated dependency text in Section IV-D...")
            old_str = "with PyTorch 2.3.1, transformers 4.41.2, spaCy 3.7.5 and scikit-learn 1.5.0"
            new_str = "with spaCy 3.8, scikit-learn 1.5.0, NumPy 1.26.4, SciPy 1.13.1, and Ollama HTTP endpoints"
            for run in p.runs:
                if old_str in run.text:
                    run.text = run.text.replace(old_str, new_str)
                    print(f"[+] Replaced: {run.text[:80]}...")
            if old_str in p.text and old_str not in "".join(r.text for r in p.runs):
                p.text = p.text.replace(old_str, new_str)

    # 2. Modify Table 1: Remove "Main limitation" column
    table1_modified = False
    for t_idx, t in enumerate(doc.tables):
        if len(t.rows) >= 9 and len(t.rows[0].cells) >= 6:
            header_texts = [c.text.strip().lower() for c in t.rows[0].cells]
            if "ref." in header_texts[0] and "limitation" in header_texts[5]:
                print(f"[*] Modifying Table 1 (Table index {t_idx}): Removing 'Main limitation' column...")
                for row in t.rows:
                    tc = row.cells[5]._tc
                    row._tr.remove(tc)
                
                # Proportional column widths for 5 remaining columns spanning full two-column table (7.00 inches)
                col_widths = [Inches(0.45), Inches(1.55), Inches(1.90), Inches(1.30), Inches(1.80)]
                for row in t.rows:
                    for idx, width in enumerate(col_widths):
                        row.cells[idx].width = width
                
                new_headers = [c.text.strip().replace('\n', ' ') for c in t.rows[0].cells]
                print(f"[+] Successfully updated Table 1! Remaining columns: {new_headers}")
                table1_modified = True
                break

    if not table1_modified:
        print("[!] Warning: Table 1 with 'Main limitation' column was not found by exact criteria.")

    # 3. Map and replace each placeholder table with the corresponding figure
    tables_to_remove = []
    
    for t_idx, t in enumerate(doc.tables):
        text_content = " ".join(c.text for row in t.rows for c in row.cells)
        for fig_num in range(1, 8):
            if f"[ INSERT FIGURE {fig_num} HERE ]" in text_content:
                print(f"[*] Found placeholder Table for Figure {fig_num} (Table index {t_idx})")
                img_path = FIGURE_FILES[fig_num]
                if not img_path.exists():
                    print(f"[-] Image file missing: {img_path}")
                    sys.exit(1)

                # Insert a new paragraph immediately before the table
                new_p_elm = OxmlElement("w:p")
                t._element.addprevious(new_p_elm)
                p = Paragraph(new_p_elm, doc)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run()
                
                # Image width: single column width 3.35 inches
                run.add_picture(str(img_path), width=Inches(3.35))
                print(f"[+] Inserted Figure {fig_num} ({img_path.name}) at width 3.35in")

                tables_to_remove.append(t)
                break

    # Remove the placeholder tables
    for t in tables_to_remove:
        parent = t._element.getparent()
        if parent is not None:
            parent.remove(t._element)
    print(f"[+] Removed {len(tables_to_remove)} placeholder tables from document.")

    # 4. Update the figure captions
    updated_captions = 0
    for p in doc.paragraphs:
        txt = p.text.strip()
        for fig_num in range(1, 8):
            prefix = f"Fig. {fig_num}."
            if txt.startswith(prefix) and ("[Add caption]" in txt or len(txt) < 25):
                print(f"[*] Updating caption for Figure {fig_num}...")
                p.text = CAPTIONS[fig_num]
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                updated_captions += 1
                break

    print(f"[+] Successfully updated {updated_captions} figure captions.")

    # 5. Save completed DOCX documents
    doc.save(str(OUTPUT_DESKTOP_DOCX))
    print(f"[+] Saved completed document to Desktop: {OUTPUT_DESKTOP_DOCX}")

    try:
        doc.save(str(OUTPUT_DOCS_DOCX))
        print(f"[+] Saved completed document to: {OUTPUT_DOCS_DOCX}")
    except Exception as e:
        print(f"[!] Note: {OUTPUT_DOCS_DOCX.name} currently locked by sync ({e}). Will attempt copy after rendering.")

    # 6. Render to PDF via PowerShell Word COM
    render_pdf(OUTPUT_DESKTOP_DOCX, OUTPUT_DESKTOP_PDF)

    if OUTPUT_DESKTOP_PDF.exists():
        try:
            import shutil
            shutil.copy2(str(OUTPUT_DESKTOP_PDF), str(OUTPUT_DOCS_PDF))
            print(f"[+] Copied completed PDF to: {OUTPUT_DOCS_PDF}")
        except Exception as e:
            print(f"[!] Note on PDF copy to docs: {e}")

    try:
        import shutil
        shutil.copy2(str(OUTPUT_DESKTOP_DOCX), str(OUTPUT_DOCS_DOCX))
        print(f"[+] Synced completed DOCX to: {OUTPUT_DOCS_DOCX}")
    except Exception as e:
        pass

    print("[SUCCESS] Report completion and PDF generation finished successfully!")


def render_pdf(docx_path: Path, pdf_path: Path):
    print(f"[*] Converting {docx_path.name} to PDF using Microsoft Word COM...")
    ps_cmd = f"""
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    try {{
        $doc = $word.Documents.Open('{str(docx_path)}')
        $doc.SaveAs([ref]'{str(pdf_path)}', [ref]17)
        $doc.Close()
        Write-Host "PDF export succeeded."
    }} finally {{
        $word.Quit()
    }}
    """
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    if pdf_path.exists():
        print(f"[+] PDF generated successfully: {pdf_path} ({pdf_path.stat().st_size:,} bytes)")
    else:
        print(f"[-] PDF conversion warning/output: {res.stdout}\n{res.stderr}")


if __name__ == "__main__":
    complete_report()
