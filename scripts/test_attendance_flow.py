"""
Attendance Monitoring System — Automated Test Script
Tests DB model logging, cooldown, manual exit, and attendance reports.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
from backend.database.db import initialize_db, get_db
from backend.database.models import EmployeeModel, AttendanceModel, ContractorModel, GateModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def test_attendance_pipeline():
    print("=" * 60)
    print("  AI GATE SAFETY SYSTEM — ATTENDANCE TEST SUITE")
    print("=" * 60)

    # 1. Initialize Database
    logger.info("[1/5] Initializing Database Connection Pool...")
    initialize_db()

    # 2. Check or Create Test Contractor & Gate
    logger.info("[2/5] Setting up Test Contractor and Gate...")
    with get_db() as cur:
        cur.execute("SELECT TOP 1 GateID, GateName FROM dbo.Gates")
        gate = cur.fetchone()
        if not gate:
            logger.error("No gates found. Run schema setup first.")
            return
        gate_id, gate_name = gate[0], gate[1]
        logger.info(f"Using Gate: ID={gate_id}, Name='{gate_name}'")

    # 3. Create or Fetch Test Employee
    logger.info("[3/5] Creating / Loading Test Employee...")
    test_emp_code = "TEST_EMP_99"
    with get_db() as cur:
        cur.execute("SELECT EmployeeID FROM dbo.Employees WHERE EmpCode = ?", (test_emp_code,))
        row = cur.fetchone()
        if row:
            emp_id = row[0]
            logger.info(f"Found existing test employee ID: {emp_id}")
        else:
            emp_id = EmployeeModel.create({
                "emp_code": test_emp_code,
                "full_name": "Test Worker Alex",
                "department": "Safety Testing",
                "designation": "Safety Inspector",
                "employee_type": "Staff",
                "shift_code": "G"
            })
            logger.info(f"Created new test employee ID: {emp_id}")

    # 4. Test Attendance Entry Logging
    logger.info("[4/5] Testing Attendance Entry Logging...")
    att_id = AttendanceModel.log_entry(
        employee_id=emp_id,
        gate_id=gate_id,
        confidence=0.925,
        shift_code="G"
    )
    logger.info(f"✅ Entry logged successfully! Attendance ID: {att_id}")

    # Test Duplicate Entry Guard (Today's Entry Already Exists)
    att_id_repeat = AttendanceModel.log_entry(
        employee_id=emp_id,
        gate_id=gate_id,
        confidence=0.950,
        shift_code="G"
    )
    assert att_id == att_id_repeat, "Duplicate entry guard failed!"
    logger.info("✅ Duplicate entry guard verified (returns existing today's AttendanceID).")

    # 5. Test Attendance Today Retrieval & Manual Exit
    logger.info("[5/5] Testing Today's Attendance Query & Exit Logging...")
    today_records = AttendanceModel.get_today(gate_id=gate_id)
    matching = [r for r in today_records if r["EmpCode"] == test_emp_code]
    assert len(matching) > 0, "Log entry not found in today's attendance records!"
    logger.info(f"Found recorded entry: {matching[0]['FullName']} @ {matching[0]['GateName']} - Entry: {matching[0]['EntryTime']}")

    # Log Exit
    AttendanceModel.log_exit(emp_id)
    today_after_exit = AttendanceModel.get_today(gate_id=gate_id)
    exit_matching = [r for r in today_after_exit if r["EmpCode"] == test_emp_code]
    logger.info(f"✅ Exit logged! Exit time: {exit_matching[0]['ExitTime']}, Duration: {exit_matching[0]['Duration_Mins']} mins")

    print("\n" + "=" * 60)
    print(" [OK] ALL ATTENDANCE MONITORING TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_attendance_pipeline()
