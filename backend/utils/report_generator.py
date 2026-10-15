"""
Report Generator — Excel (openpyxl) + PDF (reportlab)
Generates Daily, Weekly, and Monthly reports for:
  - Attendance (contractor-wise, gate-wise, shift-wise)
  - PPE Violations (type-wise, gate-wise, person-wise)
"""

import logging
import io
from datetime import date, datetime, timedelta
from pathlib import Path
from backend.config import REPORTS_DIR, REPORT_COMPANY_NAME

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# EXCEL REPORT
# ══════════════════════════════════════════════════════════════════════════════
def generate_excel_report(report_type: str, start_date: str, end_date: str,
                           attendance_data: list, violation_data: list,
                           summary: dict) -> bytes:
    """Generate Excel report. Returns bytes for download."""
    from openpyxl import Workbook
    from openpyxl.styles import (Font, PatternFill, Alignment,
                                  Border, Side, GradientFill)
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    # ── Sheet 1: Summary ──────────────────────────────────────────────────────
    ws_sum = wb.active
    ws_sum.title = "Summary"

    header_fill  = PatternFill("solid", fgColor="1A3A5C")
    header_font  = Font(color="FFFFFF", bold=True, size=12)
    title_font   = Font(color="1A3A5C", bold=True, size=16)
    accent_fill  = PatternFill("solid", fgColor="E8F4FD")
    green_fill   = PatternFill("solid", fgColor="D5F5E3")
    red_fill     = PatternFill("solid", fgColor="FADBD8")
    thin_border  = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )

    # Title
    ws_sum["A1"] = REPORT_COMPANY_NAME
    ws_sum["A1"].font = Font(color="1A3A5C", bold=True, size=20)
    ws_sum["A2"] = f"{report_type} Report | {start_date} to {end_date}"
    ws_sum["A2"].font = Font(color="666666", italic=True, size=11)
    ws_sum["A3"] = f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M')}"
    ws_sum.merge_cells("A1:G1")
    ws_sum.merge_cells("A2:G2")
    ws_sum.merge_cells("A3:G3")

    # Summary KPIs
    kpi_row = 5
    kpis = [
        ("Total Present",     summary.get("total_present", 0),     green_fill),
        ("Contract Workers",  summary.get("contract_workers", 0),  accent_fill),
        ("OAS Workers",       summary.get("oas_workers", 0),       accent_fill),
        ("Total Violations",  summary.get("total_violations", 0),  red_fill),
        ("Unresolved",        summary.get("unresolved", 0),        red_fill),
        ("PPE Compliance %",  summary.get("compliance_pct", "N/A"), green_fill),
    ]
    for i, (label, value, fill) in enumerate(kpis):
        col = (i % 3) * 2 + 1
        row = kpi_row + (i // 3) * 3
        ws_sum.cell(row, col, label).font = Font(bold=True, size=10)
        cell = ws_sum.cell(row + 1, col, value)
        cell.font = Font(bold=True, size=18, color="1A3A5C")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center")

    # ── Sheet 2: Attendance ───────────────────────────────────────────────────
    ws_att = wb.create_sheet("Attendance")
    att_headers = ["Date", "Employee Code", "Full Name", "Department",
                   "Employee Type", "Contractor", "Gate", "Shift",
                   "Entry Time", "Exit Time", "Duration (Min)"]
    for col, h in enumerate(att_headers, 1):
        cell = ws_att.cell(1, col, h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    for row_idx, rec in enumerate(attendance_data, 2):
        vals = [
            str(rec.get("AttendanceDate", "")),
            rec.get("EmpCode", ""),
            rec.get("FullName", ""),
            rec.get("Department", ""),
            rec.get("EmployeeType", ""),
            rec.get("ContractorName", ""),
            rec.get("GateName", ""),
            rec.get("ShiftCode", ""),
            str(rec.get("EntryTime", ""))[:16] if rec.get("EntryTime") else "",
            str(rec.get("ExitTime", ""))[:16] if rec.get("ExitTime") else "",
            rec.get("Duration_Mins", ""),
        ]
        fill = accent_fill if row_idx % 2 == 0 else None
        for col, val in enumerate(vals, 1):
            cell = ws_att.cell(row_idx, col, val)
            cell.border = thin_border
            if fill:
                cell.fill = fill

    # Auto-fit columns
    for col in ws_att.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws_att.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 30)

    # ── Sheet 3: Violations ───────────────────────────────────────────────────
    ws_vio = wb.create_sheet("Violations")
    vio_headers = ["Timestamp", "Gate", "Violation Type", "Employee Code",
                   "Employee Name", "Confidence %", "Status"]
    for col, h in enumerate(vio_headers, 1):
        cell = ws_vio.cell(1, col, h)
        cell.fill = PatternFill("solid", fgColor="7B241C")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")

    for row_idx, rec in enumerate(violation_data, 2):
        vals = [
            str(rec.get("Timestamp", ""))[:16],
            rec.get("GateName", ""),
            rec.get("ViolationType", ""),
            rec.get("EmpCode", "Unknown"),
            rec.get("FullName", "Unknown Person"),
            f"{float(rec.get('ConfidenceScore', 0)) * 100:.1f}%" if rec.get("ConfidenceScore") else "",
            "Resolved" if rec.get("IsResolved") else "Open",
        ]
        fill = PatternFill("solid", fgColor="FADBD8") if not rec.get("IsResolved") else PatternFill("solid", fgColor="D5F5E3")
        for col, val in enumerate(vals, 1):
            cell = ws_vio.cell(row_idx, col, val)
            cell.border = thin_border
            if col == 7:
                cell.fill = fill

    for col in ws_vio.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws_vio.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 30)

    # Save to bytes
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════════════════════
# PDF REPORT
# ══════════════════════════════════════════════════════════════════════════════
def generate_pdf_report(report_type: str, start_date: str, end_date: str,
                         attendance_data: list, violation_data: list,
                         summary: dict) -> bytes:
    """Generate PDF report. Returns bytes for download."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                     Paragraph, Spacer, HRFlowable)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                             topMargin=1.5*cm, bottomMargin=1.5*cm,
                             leftMargin=1.5*cm, rightMargin=1.5*cm)

    styles = getSampleStyleSheet()
    navy   = colors.HexColor("#1A3A5C")
    red    = colors.HexColor("#C0392B")
    green  = colors.HexColor("#1E8449")

    title_style = ParagraphStyle("Title", parent=styles["Title"],
                                  textColor=navy, fontSize=22, spaceAfter=6)
    sub_style   = ParagraphStyle("Sub",   parent=styles["Normal"],
                                  textColor=colors.grey, fontSize=10, spaceAfter=16)
    h2_style    = ParagraphStyle("H2",    parent=styles["Heading2"],
                                  textColor=navy, spaceBefore=14)

    content = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    content.append(Paragraph(REPORT_COMPANY_NAME, title_style))
    content.append(Paragraph(
        f"{report_type} | {start_date} to {end_date} | "
        f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M')}", sub_style))
    content.append(HRFlowable(width="100%", thickness=2, color=navy, spaceAfter=12))

    # ── KPI Summary Table ─────────────────────────────────────────────────────
    kpi_data = [
        ["Metric", "Value"],
        ["Total Present Today", str(summary.get("total_present", 0))],
        ["Contract Workers",    str(summary.get("contract_workers", 0))],
        ["OAS Workers",         str(summary.get("oas_workers", 0))],
        ["Total Violations",    str(summary.get("total_violations", 0))],
        ["Unresolved",          str(summary.get("unresolved", 0))],
        ["PPE Compliance %",    str(summary.get("compliance_pct", "N/A"))],
    ]
    kpi_table = Table(kpi_data, colWidths=[8*cm, 4*cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F2F3F4"), colors.white]),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN",      (1, 1), (1, -1), "CENTER"),
        ("FONTNAME",   (1, 1), (1, -1), "Helvetica-Bold"),
    ]))
    content += [Paragraph("Summary", h2_style), kpi_table, Spacer(1, 0.5*cm)]

    # ── Attendance Table ──────────────────────────────────────────────────────
    if attendance_data:
        content.append(Paragraph("Attendance Records", h2_style))
        att_rows = [["Date", "Emp Code", "Name", "Type", "Contractor", "Gate", "Entry", "Exit"]]
        for rec in attendance_data[:100]:  # Limit for PDF
            att_rows.append([
                str(rec.get("AttendanceDate", ""))[:10],
                rec.get("EmpCode", ""),
                rec.get("FullName", "")[:20],
                rec.get("EmployeeType", ""),
                (rec.get("ContractorName", "") or "")[:15],
                rec.get("GateName", ""),
                str(rec.get("EntryTime", ""))[:5],
                str(rec.get("ExitTime", ""))[:5] if rec.get("ExitTime") else "--",
            ])
        att_table = Table(att_rows, repeatRows=1)
        att_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#EBF5FB"), colors.white]),
            ("GRID",       (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ]))
        content += [att_table, Spacer(1, 0.5*cm)]

    # ── Violations Table ──────────────────────────────────────────────────────
    if violation_data:
        content.append(Paragraph("PPE Violations", h2_style))
        vio_rows = [["Timestamp", "Gate", "Violation", "Person", "Status"]]
        for rec in violation_data[:100]:
            status_text = "Resolved" if rec.get("IsResolved") else "Open"
            vio_rows.append([
                str(rec.get("Timestamp", ""))[:16],
                rec.get("GateName", ""),
                rec.get("ViolationType", ""),
                rec.get("FullName", "Unknown"),
                status_text,
            ])
        vio_table = Table(vio_rows, repeatRows=1)
        vio_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), red),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FDEDEC"), colors.white]),
            ("GRID",       (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ]))
        content.append(vio_table)

    doc.build(content)
    buf.seek(0)
    return buf.read()
