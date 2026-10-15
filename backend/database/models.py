"""
Database Models — All CRUD operations for AI Gate Safety System.
Each class corresponds to a SQL Server table.
"""

import logging
import pickle
import numpy as np
from datetime import date, datetime
from backend.database.db import get_db

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYEES
# ══════════════════════════════════════════════════════════════════════════════
class EmployeeModel:

    @staticmethod
    def create(data: dict) -> int:
        """Insert a new employee. Returns new EmployeeID."""
        sql = """
            INSERT INTO dbo.Employees
                (EmpCode, FullName, ContractorID, Department, Designation,
                 EmployeeType, AssignedGateID, ShiftCode, Phone)
            OUTPUT INSERTED.EmployeeID
            VALUES (?,?,?,?,?,?,?,?,?)
        """
        with get_db() as cur:
            cur.execute(sql, (
                data["emp_code"], data["full_name"], data.get("contractor_id"),
                data.get("department"), data.get("designation"),
                data.get("employee_type", "Contract"), data.get("gate_id"),
                data.get("shift_code", "G"), data.get("phone")
            ))
            return cur.fetchone()[0]

    @staticmethod
    def get_all(active_only=True) -> list:
        sql = """
            SELECT e.EmployeeID, e.EmpCode, e.FullName, e.Department,
                   e.Designation, e.EmployeeType, e.ShiftCode, e.IsEnrolled,
                   e.IsActive, e.Phone, e.PhotoPath,
                   c.ContractorName, g.GateName
            FROM dbo.Employees e
            LEFT JOIN dbo.Contractors c ON e.ContractorID = c.ContractorID
            LEFT JOIN dbo.Gates g ON e.AssignedGateID = g.GateID
        """
        if active_only:
            sql += " WHERE e.IsActive = 1"
        sql += " ORDER BY e.FullName"
        with get_db() as cur:
            cur.execute(sql)
            return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    @staticmethod
    def get_by_id(employee_id: int) -> dict | None:
        sql = """
            SELECT e.*, c.ContractorName, g.GateName
            FROM dbo.Employees e
            LEFT JOIN dbo.Contractors c ON e.ContractorID = c.ContractorID
            LEFT JOIN dbo.Gates g ON e.AssignedGateID = g.GateID
            WHERE e.EmployeeID = ?
        """
        with get_db() as cur:
            cur.execute(sql, employee_id)
            row = cur.fetchone()
            return dict(zip([c[0] for c in cur.description], row)) if row else None

    @staticmethod
    def save_face_embedding(employee_id: int, embedding: np.ndarray, photo_path: str):
        """Store face embedding as binary blob."""
        embedding_bytes = pickle.dumps(embedding.astype(np.float32))
        with get_db() as cur:
            cur.execute("""
                UPDATE dbo.Employees
                SET FaceEmbedding = ?, PhotoPath = ?, IsEnrolled = 1, UpdatedAt = SYSUTCDATETIME()
                WHERE EmployeeID = ?
            """, (embedding_bytes, photo_path, employee_id))

    @staticmethod
    def get_all_enrolled_faces() -> list:
        """Return all enrolled employees with their face embeddings."""
        with get_db() as cur:
            cur.execute("""
                SELECT EmployeeID, EmpCode, FullName, FaceEmbedding, Department, EmployeeType
                FROM dbo.Employees
                WHERE IsEnrolled = 1 AND IsActive = 1 AND FaceEmbedding IS NOT NULL
            """)
            results = []
            for row in cur.fetchall():
                embedding = pickle.loads(row.FaceEmbedding)
                results.append({
                    "employee_id": row.EmployeeID,
                    "emp_code":    row.EmpCode,
                    "full_name":   row.FullName,
                    "department":  row.Department,
                    "emp_type":    row.EmployeeType,
                    "embedding":   embedding,
                })
            return results

    @staticmethod
    def search(query: str) -> list:
        sql = """
            SELECT e.EmployeeID, e.EmpCode, e.FullName, e.Department,
                   e.EmployeeType, e.IsEnrolled, c.ContractorName
            FROM dbo.Employees e
            LEFT JOIN dbo.Contractors c ON e.ContractorID = c.ContractorID
            WHERE e.IsActive = 1
              AND (e.FullName LIKE ? OR e.EmpCode LIKE ? OR c.ContractorName LIKE ?)
        """
        like = f"%{query}%"
        with get_db() as cur:
            cur.execute(sql, (like, like, like))
            return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    @staticmethod
    def deactivate(employee_id: int):
        with get_db() as cur:
            cur.execute("UPDATE dbo.Employees SET IsActive = 0 WHERE EmployeeID = ?", employee_id)


# ══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════════════════════════════════════════
class AttendanceModel:

    @staticmethod
    def log_entry(employee_id: int, gate_id: int, confidence: float, shift_code: str = "G") -> int:
        """Log entry time for an employee. Returns AttendanceID."""
        today = date.today()
        # Check if entry already exists today
        with get_db() as cur:
            cur.execute("""
                SELECT AttendanceID FROM dbo.Attendance
                WHERE EmployeeID = ? AND AttendanceDate = ? AND EntryTime IS NOT NULL
            """, (employee_id, today))
            existing = cur.fetchone()
            if existing:
                return existing[0]  # Already logged today

            cur.execute("""
                INSERT INTO dbo.Attendance (EmployeeID, GateID, AttendanceDate, EntryTime, ShiftCode, ConfidenceScore)
                OUTPUT INSERTED.AttendanceID
                VALUES (?, ?, ?, SYSUTCDATETIME(), ?, ?)
            """, (employee_id, gate_id, today, shift_code, confidence))
            return cur.fetchone()[0]

    @staticmethod
    def log_exit(employee_id: int):
        """Update exit time for today's attendance record."""
        today = date.today()
        with get_db() as cur:
            cur.execute("""
                UPDATE dbo.Attendance
                SET ExitTime = SYSUTCDATETIME()
                WHERE EmployeeID = ? AND AttendanceDate = ? AND ExitTime IS NULL
            """, (employee_id, today))

    @staticmethod
    def get_today(gate_id: int = None, contractor_id: int = None) -> list:
        sql = """
            SELECT a.AttendanceID, a.AttendanceDate, a.EntryTime, a.ExitTime,
                   a.ShiftCode, a.ConfidenceScore, a.Duration_Mins,
                   e.EmpCode, e.FullName, e.Department, e.EmployeeType,
                   c.ContractorName, g.GateName
            FROM dbo.Attendance a
            JOIN dbo.Employees e ON a.EmployeeID = e.EmployeeID
            LEFT JOIN dbo.Contractors c ON e.ContractorID = c.ContractorID
            JOIN dbo.Gates g ON a.GateID = g.GateID
            WHERE a.AttendanceDate = CAST(SYSUTCDATETIME() AS DATE)
        """
        params = []
        if gate_id:
            sql += " AND a.GateID = ?";  params.append(gate_id)
        if contractor_id:
            sql += " AND e.ContractorID = ?"; params.append(contractor_id)
        sql += " ORDER BY a.EntryTime DESC"
        with get_db() as cur:
            cur.execute(sql, params)
            return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    @staticmethod
    def get_by_date_range(start_date: str, end_date: str, gate_id: int = None,
                           contractor_id: int = None, employee_id: int = None) -> list:
        sql = """
            SELECT a.AttendanceID, a.AttendanceDate, a.EntryTime, a.ExitTime,
                   a.ShiftCode, a.Duration_Mins,
                   e.EmpCode, e.FullName, e.Department, e.EmployeeType,
                   c.ContractorName, g.GateName
            FROM dbo.Attendance a
            JOIN dbo.Employees e ON a.EmployeeID = e.EmployeeID
            LEFT JOIN dbo.Contractors c ON e.ContractorID = c.ContractorID
            JOIN dbo.Gates g ON a.GateID = g.GateID
            WHERE a.AttendanceDate BETWEEN ? AND ?
        """
        params = [start_date, end_date]
        if gate_id:
            sql += " AND a.GateID = ?"; params.append(gate_id)
        if contractor_id:
            sql += " AND e.ContractorID = ?"; params.append(contractor_id)
        if employee_id:
            sql += " AND a.EmployeeID = ?"; params.append(employee_id)
        sql += " ORDER BY a.AttendanceDate DESC, a.EntryTime DESC"
        with get_db() as cur:
            cur.execute(sql, params)
            return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    @staticmethod
    def get_summary(date_val: str = None) -> dict:
        if not date_val:
            date_val = str(date.today())
        with get_db() as cur:
            cur.execute("""
                SELECT
                    COUNT(DISTINCT a.EmployeeID) AS TotalPresent,
                    COUNT(DISTINCT CASE WHEN e.EmployeeType = 'Contract' THEN a.EmployeeID END) AS ContractWorkers,
                    COUNT(DISTINCT CASE WHEN e.EmployeeType = 'OAS' THEN a.EmployeeID END) AS OASWorkers,
                    COUNT(DISTINCT a.GateID) AS ActiveGates
                FROM dbo.Attendance a
                JOIN dbo.Employees e ON a.EmployeeID = e.EmployeeID
                WHERE a.AttendanceDate = ?
            """, date_val)
            row = cur.fetchone()
            return {
                "total_present":    row[0],
                "contract_workers": row[1],
                "oas_workers":      row[2],
                "active_gates":     row[3],
                "date":             date_val,
            }


# ══════════════════════════════════════════════════════════════════════════════
# VIOLATIONS
# ══════════════════════════════════════════════════════════════════════════════
class ViolationModel:

    @staticmethod
    def log(gate_id: int, violation_type: str, snapshot_path: str,
            employee_id: int = None, confidence: float = None) -> int:
        """Log a PPE violation. Returns ViolationID."""
        with get_db() as cur:
            cur.execute("""
                INSERT INTO dbo.Violations
                    (EmployeeID, GateID, ViolationType, SnapshotPath, ConfidenceScore)
                OUTPUT INSERTED.ViolationID
                VALUES (?, ?, ?, ?, ?)
            """, (employee_id, gate_id, violation_type, snapshot_path, confidence))
            vid = cur.fetchone()[0]

        # Also create an Alert record
        with get_db() as cur:
            cur.execute("""
                INSERT INTO dbo.Alerts (ViolationID, AlertType) VALUES (?, 'dashboard')
            """, vid)
        return vid

    @staticmethod
    def get_recent(limit: int = 50, gate_id: int = None) -> list:
        sql = """
            SELECT TOP(?) v.ViolationID, v.ViolationType, v.SnapshotPath,
                   v.Timestamp, v.IsResolved, v.ConfidenceScore,
                   e.FullName, e.EmpCode, g.GateName
            FROM dbo.Violations v
            LEFT JOIN dbo.Employees e ON v.EmployeeID = e.EmployeeID
            JOIN dbo.Gates g ON v.GateID = g.GateID
        """
        params = [limit]
        if gate_id:
            sql += " WHERE v.GateID = ?"; params.append(gate_id)
        sql += " ORDER BY v.Timestamp DESC"
        with get_db() as cur:
            cur.execute(sql, params)
            return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    @staticmethod
    def search(query: str = None, gate_id: int = None, violation_type: str = None,
               start_date: str = None, end_date: str = None) -> list:
        sql = """
            SELECT v.ViolationID, v.ViolationType, v.SnapshotPath,
                   v.Timestamp, v.IsResolved, v.ConfidenceScore,
                   e.FullName, e.EmpCode, g.GateName
            FROM dbo.Violations v
            LEFT JOIN dbo.Employees e ON v.EmployeeID = e.EmployeeID
            JOIN dbo.Gates g ON v.GateID = g.GateID
            WHERE 1=1
        """
        params = []
        if query:
            sql += " AND (e.FullName LIKE ? OR e.EmpCode LIKE ?)"; params += [f"%{query}%"]*2
        if gate_id:
            sql += " AND v.GateID = ?"; params.append(gate_id)
        if violation_type:
            sql += " AND v.ViolationType = ?"; params.append(violation_type)
        if start_date:
            sql += " AND CAST(v.Timestamp AS DATE) >= ?"; params.append(start_date)
        if end_date:
            sql += " AND CAST(v.Timestamp AS DATE) <= ?"; params.append(end_date)
        sql += " ORDER BY v.Timestamp DESC"
        with get_db() as cur:
            cur.execute(sql, params)
            return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    @staticmethod
    def get_stats(date_val: str = None) -> dict:
        if not date_val:
            date_val = str(date.today())
        with get_db() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS TotalViolations,
                    COUNT(CASE WHEN ViolationType LIKE 'No-Helmet%' THEN 1 END) AS NoHelmet,
                    COUNT(CASE WHEN ViolationType LIKE 'No-Vest%' THEN 1 END) AS NoVest,
                    COUNT(CASE WHEN ViolationType LIKE 'No-Shoes%' THEN 1 END) AS NoShoes,
                    COUNT(CASE WHEN ViolationType LIKE 'No-Mask%' THEN 1 END) AS NoMask,
                    COUNT(CASE WHEN IsResolved = 1 THEN 1 END) AS Resolved
                FROM dbo.Violations
                WHERE CAST(Timestamp AS DATE) = ?
            """, date_val)
            row = cur.fetchone()
            return {
                "total":      row[0], "no_helmet": row[1],
                "no_vest":    row[2], "no_shoes":  row[3],
                "no_mask":    row[4], "resolved":  row[5],
            }

    @staticmethod
    def resolve(violation_id: int, resolved_by: int = None):
        with get_db() as cur:
            cur.execute("""
                UPDATE dbo.Violations
                SET IsResolved = 1, ResolvedBy = ?, ResolvedAt = SYSUTCDATETIME()
                WHERE ViolationID = ?
            """, (resolved_by, violation_id))


# ══════════════════════════════════════════════════════════════════════════════
# GATES
# ══════════════════════════════════════════════════════════════════════════════
class GateModel:

    @staticmethod
    def get_all() -> list:
        with get_db() as cur:
            cur.execute("SELECT * FROM dbo.Gates WHERE IsActive = 1 ORDER BY GateID")
            return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    @staticmethod
    def update_rtsp(gate_id: int, rtsp_url: str):
        with get_db() as cur:
            cur.execute("UPDATE dbo.Gates SET CameraRTSP = ? WHERE GateID = ?", (rtsp_url, gate_id))


# ══════════════════════════════════════════════════════════════════════════════
# CONTRACTORS
# ══════════════════════════════════════════════════════════════════════════════
class ContractorModel:

    @staticmethod
    def get_all() -> list:
        with get_db() as cur:
            cur.execute("SELECT * FROM dbo.Contractors WHERE IsActive = 1 ORDER BY ContractorName")
            return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    @staticmethod
    def create(data: dict) -> int:
        with get_db() as cur:
            cur.execute("""
                INSERT INTO dbo.Contractors (ContractorName, ContactPerson, ContactPhone, ContactEmail, ContractType)
                OUTPUT INSERTED.ContractorID
                VALUES (?,?,?,?,?)
            """, (data["name"], data.get("contact_person"), data.get("phone"), data.get("email"), data.get("contract_type", "Labour")))
            return cur.fetchone()[0]


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM USERS
# ══════════════════════════════════════════════════════════════════════════════
class UserModel:

    @staticmethod
    def get_by_username(username: str) -> dict | None:
        with get_db() as cur:
            cur.execute("SELECT * FROM dbo.SystemUsers WHERE Username = ? AND IsActive = 1", username)
            row = cur.fetchone()
            return dict(zip([c[0] for c in cur.description], row)) if row else None

    @staticmethod
    def update_last_login(user_id: int):
        with get_db() as cur:
            cur.execute("UPDATE dbo.SystemUsers SET LastLogin = SYSUTCDATETIME() WHERE UserID = ?", user_id)

    @staticmethod
    def get_all() -> list:
        with get_db() as cur:
            cur.execute("SELECT UserID, Username, FullName, Role, Email, IsActive, LastLogin FROM dbo.SystemUsers")
            return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]
