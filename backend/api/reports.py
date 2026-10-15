"""Reports API — generate and download Excel/PDF reports."""

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from backend.database.models import AttendanceModel, ViolationModel
from backend.utils.report_generator import generate_excel_report, generate_pdf_report
from datetime import date, timedelta
import io, logging

logger = logging.getLogger(__name__)
reports_bp = Blueprint("reports", __name__)


def _get_report_data(start_date, end_date, gate_id=None, contractor_id=None):
    attendance  = AttendanceModel.get_by_date_range(start_date, end_date, gate_id, contractor_id)
    violations  = ViolationModel.search(gate_id=gate_id, start_date=start_date, end_date=end_date)
    att_summary = AttendanceModel.get_summary(str(date.today()))
    vio_stats   = ViolationModel.get_stats(str(date.today()))

    total = vio_stats.get("total", 0)
    summary = {
        **att_summary,
        "total_violations": total,
        "unresolved":       total - vio_stats.get("resolved", 0),
        "compliance_pct":   f"{max(0, 100 - total)}%",
    }
    return attendance, violations, summary


@reports_bp.route("/excel", methods=["GET"])
@jwt_required()
def download_excel():
    start       = request.args.get("start", str(date.today()))
    end         = request.args.get("end",   str(date.today()))
    report_type = request.args.get("type",  "Daily")
    gate_id     = request.args.get("gate_id", type=int)
    contractor_id = request.args.get("contractor_id", type=int)

    attendance, violations, summary = _get_report_data(start, end, gate_id, contractor_id)
    xlsx_bytes = generate_excel_report(report_type, start, end, attendance, violations, summary)

    filename = f"AI_Gate_Report_{report_type}_{start}.xlsx"
    return send_file(
        io.BytesIO(xlsx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@reports_bp.route("/pdf", methods=["GET"])
@jwt_required()
def download_pdf():
    start       = request.args.get("start", str(date.today()))
    end         = request.args.get("end",   str(date.today()))
    report_type = request.args.get("type",  "Daily")
    gate_id     = request.args.get("gate_id", type=int)
    contractor_id = request.args.get("contractor_id", type=int)

    attendance, violations, summary = _get_report_data(start, end, gate_id, contractor_id)
    pdf_bytes = generate_pdf_report(report_type, start, end, attendance, violations, summary)

    filename = f"AI_Gate_Report_{report_type}_{start}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@reports_bp.route("/preview", methods=["GET"])
@jwt_required()
def preview():
    """Return report data as JSON for dashboard preview."""
    start = request.args.get("start", str(date.today()))
    end   = request.args.get("end",   str(date.today()))
    attendance, violations, summary = _get_report_data(start, end)
    return jsonify({
        "summary":    summary,
        "attendance": attendance[:20],
        "violations": violations[:20],
    })
