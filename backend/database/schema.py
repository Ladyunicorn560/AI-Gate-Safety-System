"""
SQL Server Database Schema Setup
Creates all tables for AI Gate Safety System.
Run once: python -m backend.database.schema
"""

import logging
from backend.database.db import get_db, initialize_db

logger = logging.getLogger(__name__)

# ─── Complete Schema ──────────────────────────────────────────────────────────
SCHEMA_SQL = """
-- ============================================================
-- AI Gate Safety System Database Schema
-- Server: <YOUR_SERVER> | Database: AI_Gate_Safety_DB
-- ============================================================

-- 1. Contractors table
IF OBJECT_ID(N'dbo.Contractors', N'U') IS NULL
CREATE TABLE dbo.Contractors (
    ContractorID    INT IDENTITY(1,1) PRIMARY KEY,
    ContractorName  NVARCHAR(200) NOT NULL,
    ContactPerson   NVARCHAR(150),
    ContactPhone    NVARCHAR(20),
    ContactEmail    NVARCHAR(150),
    ContractType    NVARCHAR(50),   -- 'Labour', 'Service', 'Maintenance', etc.
    IsActive        BIT NOT NULL DEFAULT 1,
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    UpdatedAt       DATETIME2
);

-- 2. Gates table
IF OBJECT_ID(N'dbo.Gates', N'U') IS NULL
CREATE TABLE dbo.Gates (
    GateID          INT IDENTITY(1,1) PRIMARY KEY,
    GateName        NVARCHAR(100) NOT NULL,
    Location        NVARCHAR(200),
    CameraRTSP      NVARCHAR(500),  -- RTSP stream URL
    IsActive        BIT NOT NULL DEFAULT 1,
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

-- 3. Employees table
IF OBJECT_ID(N'dbo.Employees', N'U') IS NULL
CREATE TABLE dbo.Employees (
    EmployeeID      INT IDENTITY(1,1) PRIMARY KEY,
    EmpCode         NVARCHAR(50) UNIQUE NOT NULL,   -- Employee badge/ID
    FullName        NVARCHAR(200) NOT NULL,
    ContractorID    INT REFERENCES dbo.Contractors(ContractorID),
    Department      NVARCHAR(150),
    Designation     NVARCHAR(150),
    EmployeeType    NVARCHAR(50) NOT NULL DEFAULT 'Contract',  -- 'Contract', 'OAS', 'Staff'
    AssignedGateID  INT REFERENCES dbo.Gates(GateID),
    ShiftCode       NCHAR(1) NOT NULL DEFAULT 'G',  -- A/B/C/G
    PhotoPath       NVARCHAR(500),                  -- Path to enrolled face photo
    FaceEmbedding   VARBINARY(MAX),                 -- Serialized numpy array (512 floats)
    IsEnrolled      BIT NOT NULL DEFAULT 0,         -- Has face been enrolled?
    IsActive        BIT NOT NULL DEFAULT 1,
    Phone           NVARCHAR(20),
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    UpdatedAt       DATETIME2
);

-- 4. Attendance table
IF OBJECT_ID(N'dbo.Attendance', N'U') IS NULL
CREATE TABLE dbo.Attendance (
    AttendanceID    INT IDENTITY(1,1) PRIMARY KEY,
    EmployeeID      INT NOT NULL REFERENCES dbo.Employees(EmployeeID),
    GateID          INT NOT NULL REFERENCES dbo.Gates(GateID),
    AttendanceDate  DATE NOT NULL DEFAULT CAST(SYSUTCDATETIME() AS DATE),
    EntryTime       DATETIME2,
    ExitTime        DATETIME2,
    ShiftCode       NCHAR(1),
    Duration_Mins   AS DATEDIFF(MINUTE, EntryTime, ExitTime),  -- Computed column
    ConfidenceScore FLOAT,  -- Face recognition confidence
    IsManual        BIT NOT NULL DEFAULT 0,
    Remarks         NVARCHAR(500),
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

-- 5. Violations table
IF OBJECT_ID(N'dbo.Violations', N'U') IS NULL
CREATE TABLE dbo.Violations (
    ViolationID     INT IDENTITY(1,1) PRIMARY KEY,
    EmployeeID      INT REFERENCES dbo.Employees(EmployeeID),  -- NULL if unknown person
    GateID          INT NOT NULL REFERENCES dbo.Gates(GateID),
    ViolationType   NVARCHAR(100) NOT NULL,  -- 'No-Helmet', 'No-Vest', etc.
    SnapshotPath    NVARCHAR(500),           -- Path to violation image
    Timestamp       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    ConfidenceScore FLOAT,
    IsResolved      BIT NOT NULL DEFAULT 0,
    ResolvedBy      INT,
    ResolvedAt      DATETIME2,
    Notes           NVARCHAR(500),
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

-- 6. Users (System Login) table
IF OBJECT_ID(N'dbo.SystemUsers', N'U') IS NULL
CREATE TABLE dbo.SystemUsers (
    UserID          INT IDENTITY(1,1) PRIMARY KEY,
    Username        NVARCHAR(100) UNIQUE NOT NULL,
    PasswordHash    NVARCHAR(256) NOT NULL,
    FullName        NVARCHAR(200),
    Role            NVARCHAR(50) NOT NULL DEFAULT 'security',  -- admin/security/hr/safety
    Email           NVARCHAR(200),
    IsActive        BIT NOT NULL DEFAULT 1,
    LastLogin       DATETIME2,
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

-- 7. Alerts table
IF OBJECT_ID(N'dbo.Alerts', N'U') IS NULL
CREATE TABLE dbo.Alerts (
    AlertID         INT IDENTITY(1,1) PRIMARY KEY,
    ViolationID     INT REFERENCES dbo.Violations(ViolationID),
    AlertType       NVARCHAR(50) NOT NULL DEFAULT 'visual',  -- 'audio', 'visual', 'dashboard'
    SentAt          DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    IsAcknowledged  BIT NOT NULL DEFAULT 0,
    AcknowledgedBy  INT,
    AcknowledgedAt  DATETIME2
);

-- ─── Indexes ─────────────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Attendance_Date')
    CREATE INDEX IX_Attendance_Date ON dbo.Attendance(AttendanceDate);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Attendance_Employee')
    CREATE INDEX IX_Attendance_Employee ON dbo.Attendance(EmployeeID, AttendanceDate);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Violations_Timestamp')
    CREATE INDEX IX_Violations_Timestamp ON dbo.Violations(Timestamp);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Violations_Gate')
    CREATE INDEX IX_Violations_Gate ON dbo.Violations(GateID, Timestamp);

-- ─── Seed Data ────────────────────────────────────────────────────────────────
-- 4 Gates
IF NOT EXISTS (SELECT 1 FROM dbo.Gates WHERE GateName = 'Main Gate-1')
BEGIN
    INSERT INTO dbo.Gates (GateName, Location, CameraRTSP) VALUES
        ('Main Gate-1', 'North Entrance', ''),
        ('Main Gate-2', 'South Entrance', ''),
        ('Main Gate-3', 'East Entrance',  ''),
        ('Main Gate-4', 'West Entrance',  '');
END

-- Default admin user — password must be set via first-run setup or the admin panel
-- Do NOT hardcode credentials here. Use: python -m backend.database.create_admin
IF NOT EXISTS (SELECT 1 FROM dbo.SystemUsers WHERE Username = 'admin')
    INSERT INTO dbo.SystemUsers (Username, PasswordHash, FullName, Role)
    VALUES ('admin',
            'PLACEHOLDER_RUN_CREATE_ADMIN_SCRIPT',
            'System Administrator', 'admin');

-- Sample Contractors
IF NOT EXISTS (SELECT 1 FROM dbo.Contractors WHERE ContractorName = 'ABC Labour Contractors')
BEGIN
    INSERT INTO dbo.Contractors (ContractorName, ContractorPhone, ContractType) VALUES
        ('ABC Labour Contractors', '9800000001', 'Labour'),
        ('XYZ Service Agency',     '9800000002', 'Service'),
        ('PQR Maintenance Co.',    '9800000003', 'Maintenance');
END
"""

# Seed SQL with renamed column
SCHEMA_SQL = SCHEMA_SQL.replace("ContractorPhone", "ContactPhone")


def create_database_if_not_exists():
    """Connect to master and create AI_Gate_Safety_DB if it doesn't exist."""
    import pyodbc
    from backend.config import DB_SERVER, DB_DRIVER
    master_conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE=master;"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes;"
    )
    try:
        conn = pyodbc.connect(master_conn_str, timeout=15)
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(
            "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'AI_Gate_Safety_DB') "
            "CREATE DATABASE AI_Gate_Safety_DB;"
        )
        cursor.close()
        conn.close()
        logger.info("✅ AI_Gate_Safety_DB database ensured.")
    except Exception as e:
        logger.error(f"❌ Failed to create database: {e}")
        raise


def run_schema():
    """Execute the full schema SQL against AI_Gate_Safety_DB."""
    # Split blocks by double newline
    blocks = [b.strip() for b in SCHEMA_SQL.split('\n\n') if b.strip()]
    success_count = 0
    with get_db() as cursor:
        for block in blocks:
            # Strip leading SQL comments
            lines = [l for l in block.splitlines() if not l.strip().startswith('--')]
            clean_stmt = "\n".join(lines).strip()
            if clean_stmt:
                try:
                    cursor.execute(clean_stmt)
                    success_count += 1
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Schema statement warning: {e}")
    logger.info(f"[OK] Schema applied: {success_count} statements executed.")


def setup():
    """Full setup: create DB + apply schema."""
    print("[+] Setting up AI Gate Safety System Database...")
    create_database_if_not_exists()
    initialize_db()
    run_schema()
    print("[OK] Database setup complete!")
    print("   Server  : (set DB_SERVER in your .env)")
    print("   Database: AI_Gate_Safety_DB")
    print("   Tables  : Contractors, Gates, Employees, Attendance, Violations, SystemUsers, Alerts")
    print("   Admin   : username=admin | password set via first-run script or env")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
    logging.basicConfig(level=logging.INFO)
    setup()
