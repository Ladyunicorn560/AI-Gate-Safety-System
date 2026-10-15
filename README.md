# 🏗️ AI Gate Safety System

An intelligent gate access control and workplace safety monitoring system powered by computer vision. It combines **face recognition** for employee authentication with **PPE (Personal Protective Equipment) detection** to enforce safety compliance at entry gates — all managed through a real-time web dashboard.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎭 **Face Recognition** | Recognizes registered employees via live camera feed |
| 🦺 **PPE Detection** | Detects hard hats, safety vests, gloves, goggles using YOLO |
| 🚪 **Gate Access Control** | Auto-opens gates for compliant employees |
| 📸 **Violation Snapshots** | Saves images of PPE violations with timestamps |
| 📊 **Live Dashboard** | Real-time WebSocket-powered monitoring UI |
| 📋 **Attendance Tracking** | Automatic attendance logging per gate/shift |
| 📁 **Reports & Exports** | Generate PDF/Excel compliance and attendance reports |
| ⚙️ **Settings Panel** | Configure RTSP camera URLs and system parameters in-browser |

---

## 🗂️ Project Structure

```
AI-Gate-Safety-System/
├── backend/
│   ├── ai/                  # Face recognition & PPE detection modules
│   ├── api/                 # Flask REST API routes
│   ├── database/            # SQL Server models & queries
│   ├── utils/               # Snapshot helpers, utilities
│   ├── app.py               # Flask + SocketIO entry point
│   └── config.py            # App configuration loader
├── frontend/
│   ├── index.html           # Main dashboard
│   ├── pages/               # Settings, attendance, reports pages
│   ├── js/                  # Dashboard, attendance, API client scripts
│   └── css/                 # Styling
├── data/
│   ├── employee_faces/      # (gitignored) Registered face images
│   ├── uploads/             # (gitignored) Uploaded images
│   ├── violations/          # (gitignored) Violation snapshots
│   └── reports/             # (gitignored) Generated reports
├── models/                  # ML model weights (see setup below)
├── logs/                    # (gitignored) Runtime logs
├── scripts/                 # Utility / setup scripts
├── requirements.txt
├── .env.example             # ← Copy to .env and fill in your values
└── start.bat                # Windows one-click launcher
```

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.10+
- Microsoft SQL Server (with Windows Authentication)
- ODBC Driver 18 for SQL Server ([download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server))
- IP/USB cameras with RTSP streams (or webcam for testing)

### 1. Clone the repository

```bash
git clone https://github.com/Ladyunicorn560/AI-Gate-Safety-System.git
cd AI-Gate-Safety-System
```

### 2. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
copy .env.example .env       # Windows
# cp .env.example .env       # Linux / macOS
```

Edit `.env` and set:
- `DB_SERVER` — your SQL Server instance name
- `SECRET_KEY` — a strong random secret (see comment in `.env.example`)
- `GATE1_RTSP` … `GATE4_RTSP` — RTSP URLs for your cameras

### 5. Download ML Models

The model weights are **not included** in the repository due to file size.

| File | Purpose | Download / Notes |
|------|---------|-----------------|
| `models/ppe_model.pt` | PPE detection (YOLO) | Train your own or use the provided script |
| `yolov8n.pt` / `yolov8m.pt` | Base YOLO weights | Auto-downloaded by Ultralytics on first run |

### 6. Set up the database

Run the SQL schema script:

```bash
# Open SQL Server Management Studio and run:
# scripts/create_database.sql
```

### 7. Start the application

```bash
# Windows (one-click)
start.bat

# Or manually
venv\Scripts\python backend\app.py
```

Open your browser at **http://localhost:5000**

---

## 🛡️ Security Notes

- **Never commit `.env`** — it's in `.gitignore`
- Rotate `SECRET_KEY` before deploying to production
- RTSP credentials are stored only in `.env`, not in the database
- Employee face images are stored locally and excluded from the repo

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.
