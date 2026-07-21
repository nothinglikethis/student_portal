# sheets.py — MOCK MODE (no Google API calls)
# ─────────────────────────────────────────────────────────────────────────────
# Uses hardcoded data so you can run and test the UI locally without
# a credentials.json or a real Google Sheet.
#
# When going live, replace this file with the real gspread implementation.
# Every function signature stays identical — views.py needs zero changes.
# ─────────────────────────────────────────────────────────────────────────────
import csv
import os

MANDATORY_DOCS = [
    "Aadhar_Card",
    "Marksheet_10th",
    "Marksheet_12th",
    "Leaving_Certificate",
]

# ── Test case 1: All documents present → APPROVED ────────────────────────────
# ── Test case 2: Missing Aadhar + Leaving Certificate → HOLD ─────────────────
# ── Test case 3: Missing all documents → HOLD ────────────────────────────────
MOCK_SHEET_DATA = [
    {
        "UG_Number": "26UG01",
        "Name": "Rahul Sharma",
        "Password": "rahul123",
        "Division": "AIML",
        "Aadhar_Card": "https://drive.google.com/file/mock-aadhar-01",
        "Marksheet_10th": "https://drive.google.com/file/mock-10th-01",
        "Marksheet_12th": "https://drive.google.com/file/mock-12th-01",
        "Leaving_Certificate": "https://drive.google.com/file/mock-lc-01",
        "Admission_Status": "APPROVED",
        "Pending_Documents": "",
    },
    {
        "UG_Number": "26UG02",
        "Name": "Priya Mehta",
        "Password": "priya123",
        "Division": "AIRO",
        "Aadhar_Card": "",
        "Marksheet_10th": "https://drive.google.com/file/mock-10th-02",
        "Marksheet_12th": "https://drive.google.com/file/mock-12th-02",
        "Leaving_Certificate": "",
        "Admission_Status": "HOLD",
        "Pending_Documents": "Aadhar_Card, Leaving_Certificate",
    },
    {
        "UG_Number": "26UG03",
        "Name": "Arjun Desai",
        "Password": "arjun123",
        "Division": "AIML",
        "Aadhar_Card": "",
        "Marksheet_10th": "",
        "Marksheet_12th": "",
        "Leaving_Certificate": "",
        "Admission_Status": "HOLD",
        "Pending_Documents": "Aadhar_Card, Marksheet_10th, Marksheet_12th, Leaving_Certificate",
    },
]


def register_student(ug_number: str, name: str, password: str) -> dict:
    """
    Register a new student into MOCK_SHEET_DATA.
    Returns {'ok': True} on success.
    Returns {'ok': False, 'error': '<reason>'} if UG number already exists.
    """
    ug_number = ug_number.strip().upper()
    name      = name.strip()
    password  = password.strip()

    for student in MOCK_SHEET_DATA:
        if student["UG_Number"].strip().upper() == ug_number:
            return {"ok": False, "error": "This UG Number is already registered. Please log in."}

    MOCK_SHEET_DATA.append({
        "UG_Number":          ug_number,
        "Name":               name,
        "Password":           password,
        "Division":           "",
        "Aadhar_Card":        "",
        "Marksheet_10th":     "",
        "Marksheet_12th":     "",
        "Leaving_Certificate": "",
        "Admission_Status":   "PENDING",
        "Pending_Documents":  "Aadhar_Card, Marksheet_10th, Marksheet_12th, Leaving_Certificate",
    })

    # ── Offline CSV backup ────────────────────────────────────────────────────
    CSV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "offline_students_backup.csv")
    CSV_HEADERS = ["UG_Number", "Name", "Password", "Admission_Status"]

    file_is_new = not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if file_is_new:
            writer.writerow(CSV_HEADERS)
        writer.writerow([ug_number, name, password, "PENDING"])
    # ─────────────────────────────────────────────────────────────────────────

    return {"ok": True}


def get_all_students() -> list[dict]:
    """Return all student rows. Called by admin_dashboard view."""
    return MOCK_SHEET_DATA


def find_student(ug_number: str) -> dict | None:
    """
    Find a student by UG_Number (case-insensitive).
    Returns the student dict or None.
    """
    ug_number = ug_number.strip().upper()
    for student in MOCK_SHEET_DATA:
        if student["UG_Number"].strip().upper() == ug_number:
            return student
    return None


def process_admission_status(ug_number: str) -> dict | None:
    """
    Apply business logic for a single student and return their updated record.
    PENDING students are returned as-is — status is set by admin, not auto-computed.
    """
    ug_number = ug_number.strip().upper()
    for student in MOCK_SHEET_DATA:
        if student["UG_Number"].strip().upper() != ug_number:
            continue

        if student.get("Admission_Status") == "PENDING":
            return student

        missing = [doc for doc in MANDATORY_DOCS if not str(student.get(doc, "")).strip()]
        student["Admission_Status"] = "HOLD" if missing else "APPROVED"
        student["Pending_Documents"] = ", ".join(missing)
        return student

    return None


def process_all_students() -> None:
    """Re-compute admission status for every student. Called by admin 'Re-process All'."""
    for student in MOCK_SHEET_DATA:
        if student.get("Admission_Status") == "PENDING":
            continue
        missing = [doc for doc in MANDATORY_DOCS if not str(student.get(doc, "")).strip()]
        student["Admission_Status"] = "HOLD" if missing else "APPROVED"
        student["Pending_Documents"] = ", ".join(missing)
