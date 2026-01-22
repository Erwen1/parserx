"""Headless smoke-test for comprehensive PDF export data path.

This does NOT drive the QFileDialog/UI; it validates that the objects used by
`XTIMainWindow.export_comprehensive_pdf_report()` provide the expected APIs.

It also produces a small PDF in the repo root if ReportLab is installed.
"""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    from xti_viewer.validation import ValidationManager
    from xti_viewer.models import FlowTimelineModel

    # Validate expected compatibility APIs
    vm = ValidationManager()
    _ = vm.get_all_issues()

    tl = FlowTimelineModel()
    tl.set_timeline([])
    _ = tl.timeline_items

    # Optional: actually generate a tiny PDF to prove ReportLab works
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
    except Exception as e:
        print(f"ReportLab not available, skipping PDF creation: {e}")
        return 0

    out = Path("_pdf_export_smoke_test.pdf")
    doc = SimpleDocTemplate(str(out), pagesize=letter)
    styles = getSampleStyleSheet()
    doc.build([Paragraph("PDF export smoke test", styles["Normal"])])
    print(f"Wrote {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
