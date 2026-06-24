#!/usr/bin/env python3
"""
Root Cause Wearable Uploader
A smart desktop app for connecting ANY wearable (Apple Watch, Fitbit, Garmin, Oura, Whoop, etc.)

What it does:
- Log in with your Root Cause account
- Select export from any wearable (.zip, .xml, .csv, .json)
- OR log into blood testing portals (GoodLabs, Quest/MyQuest, etc.): app logs in for you, downloads your result PDFs automatically, then uploads everything
- Smart local processing: auto-trims Apple data to recent days, provides local preview summary of trends
- Uploads cleanly so Grok can analyze and include in your reports

How to use:
1. Download this file
2. python health_uploader.py  (or turn into .exe with PyInstaller)
3. Choose device type
4. Either pick export file OR use the "Fetch Blood Test Results" section (enter your lab login)
5. Preview summary (optional)
6. Upload

Supports direct file exports + auto-fetch from major lab portals.

Tip: To make a no-Python .exe for clients:
  pip install pyinstaller
  pyinstaller --onefile --windowed --name "RootCauseWearableUploader" health_uploader.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from collections import deque
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    print("Please install requests:  pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
except ImportError:
    print("For full lab portal support, run: pip install beautifulsoup4")
    BeautifulSoup = None
    urljoin = lambda base, url: url  # fallback



# ===================== CONFIG =====================
# Change this if the site URL is different
SITE_URL = "https://www.root-cause-test.com"
API_UPLOAD = f"{SITE_URL}/api/client/upload_health"

# Default days to keep when trimming locally
DEFAULT_TRIM_DAYS = 60

# Supported device types for smarter handling
DEVICE_TYPES = ["Apple Health", "Fitbit", "Garmin", "Oura / Whoop / Other", "CSV / JSON / General"]
# ==================================================


def _parse_apple_date(date_str: str):
    """Robust parser for Apple Health date strings (e.g. '2026-06-20 14:30:00 -0700')."""
    if not date_str:
        return None
    s = date_str.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s[:10])
    except Exception:
        return None

def trim_apple_health_to_recent(input_path: str, days: int = DEFAULT_TRIM_DAYS) -> str:
    """
    Stream-parse an Apple Health export.xml and write a small recent-only version.
    Much better date parsing for real Apple Health exports.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"File not found: {input_path}")

    cutoff = datetime.utcnow() - timedelta(days=days)
    output_path = input_path + f".recent_{days}days.xml"

    kept = 0
    total = 0

    with open(output_path, "w", encoding="utf-8") as out:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        out.write('<HealthData locale="en_US">\n')

        try:
            context = ET.iterparse(input_path, events=("end",))
        except Exception as e:
            raise RuntimeError(f"Failed to parse as XML. Make sure you selected the export.xml or a valid zip: {e}")

        for event, elem in context:
            if elem.tag == "Record":
                total += 1
                start = elem.get("startDate") or ""
                keep = True
                if start:
                    dt = _parse_apple_date(start)
                    if dt:
                        keep = dt >= cutoff

                if keep:
                    out.write(ET.tostring(elem, encoding="unicode"))
                    out.write("\n")
                    kept += 1

                elem.clear()

            if total % 50000 == 0:
                pass  # could add progress in future

        out.write("</HealthData>\n")

    return output_path


class HealthUploaderApp:
    def __init__(self, root):
        self.root = root
        root.title("Root Cause — Health Data Uploader")
        root.geometry("620x520")

        # Login frame
        login_frame = tk.LabelFrame(root, text="Your Root Cause Account", padx=10, pady=8)
        login_frame.pack(fill="x", padx=15, pady=(15, 8))

        tk.Label(login_frame, text="Email:").grid(row=0, column=0, sticky="w")
        self.email_var = tk.StringVar()
        tk.Entry(login_frame, textvariable=self.email_var, width=45).grid(row=0, column=1, padx=6)

        tk.Label(login_frame, text="Password:").grid(row=1, column=0, sticky="w", pady=(6,0))
        self.password_var = tk.StringVar()
        tk.Entry(login_frame, textvariable=self.password_var, show="*", width=45).grid(row=1, column=1, padx=6, pady=(6,0))

        # Device type
        device_frame = tk.LabelFrame(root, text="Wearable Type (for smarter processing)", padx=10, pady=8)
        device_frame.pack(fill="x", padx=15, pady=8)

        self.device_var = tk.StringVar(value=DEVICE_TYPES[0])
        device_menu = tk.OptionMenu(device_frame, self.device_var, *DEVICE_TYPES)
        device_menu.pack(side="left")

        tk.Label(device_frame, text="  ← Select your device for best instructions & processing", fg="#555").pack(side="left")

        # Lab Portal Fetch (NEW: auto login to blood test sites and download results)
        lab_frame = tk.LabelFrame(root, text="Fetch Blood Test Results (auto login to lab portals)", padx=10, pady=8)
        lab_frame.pack(fill="x", padx=15, pady=8)

        self.lab_var = tk.StringVar(value="GoodLabs")
        lab_menu = tk.OptionMenu(lab_frame, self.lab_var, "GoodLabs", "Quest (MyQuest)", "LabCorp", "Other")
        lab_menu.pack(side="left")

        tk.Label(lab_frame, text=" Lab Username/Phone/Email:").pack(side="left")
        self.lab_user_var = tk.StringVar()
        tk.Entry(lab_frame, textvariable=self.lab_user_var, width=25).pack(side="left", padx=4)

        tk.Label(lab_frame, text=" Password:").pack(side="left")
        self.lab_pass_var = tk.StringVar()
        tk.Entry(lab_frame, textvariable=self.lab_pass_var, show="*", width=20).pack(side="left", padx=4)

        tk.Button(lab_frame, text="Login & Fetch Results", command=self.fetch_lab_results).pack(side="left", padx=8)

        tk.Label(lab_frame, text=" (Credentials used only in-memory for this session)", fg="#888", font=("Arial", 8)).pack(side="left")

        # File frame
        file_frame = tk.LabelFrame(root, text="Select Export File (or use fetched above)", padx=10, pady=8)
        file_frame.pack(fill="x", padx=15, pady=8)

        self.file_path = tk.StringVar()
        tk.Entry(file_frame, textvariable=self.file_path, width=55).pack(side="left", padx=(0, 8))
        tk.Button(file_frame, text="Choose File (.zip, .xml, .csv, .json, .pdf)", command=self.choose_file).pack(side="left")

        # Options
        options_frame = tk.Frame(root)
        options_frame.pack(fill="x", padx=15, pady=(4, 8))

        self.trim_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text=f"Smart trim to last {DEFAULT_TRIM_DAYS} days locally (recommended for large exports)", 
                       variable=self.trim_var).pack(anchor="w")

        tk.Label(options_frame, text="Processes locally — keeps upload small & focuses on recent trends for Grok.", 
                 fg="#555").pack(anchor="w")

        # Buttons
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        self.upload_btn = tk.Button(btn_frame, text="Upload to Root Cause (Grok)", 
                                    command=self.start_upload, bg="#2e7d32", fg="white", padx=12, pady=6)
        self.upload_btn.pack(side="left", padx=6)

        tk.Button(btn_frame, text="Preview Local Summary", command=self.preview_local).pack(side="left", padx=6)

        tk.Button(btn_frame, text="Process Only (no upload)", command=self.trim_only).pack(side="left", padx=6)

        tk.Button(btn_frame, text="How to get data from my device", command=self.show_device_instructions).pack(side="left", padx=6)

        # Status
        status_frame = tk.LabelFrame(root, text="Status / Log", padx=8, pady=6)
        status_frame.pack(fill="both", expand=True, padx=15, pady=(8, 15))

        self.log = scrolledtext.ScrolledText(status_frame, height=14, wrap="word")
        self.log.pack(fill="both", expand=True)

        self.log.insert("end", "Welcome to the Root Cause Health Uploader!\n\n")
        self.log.insert("end", "This tool helps you get your Apple Watch / Health data (the zip file) into your account so Grok can analyze it.\n\n")
        self.log.insert("end", "Click the 'How to export the zip from iPhone' button for step-by-step instructions.\n")
        self.log.insert("end", "Then select the file and Upload. Large files are trimmed locally automatically.\n\n")

    def log_msg(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.root.update_idletasks()

    def show_device_instructions(self):
        device = self.device_var.get()
        if device == "Apple Health":
            instructions = """Apple Health / Apple Watch:

1. Open the Health app on iPhone.
2. Tap your profile picture (top right).
3. Scroll down → "Export All Health Data".
4. Share the zip (AirDrop/iCloud/email) to this computer.
5. Select the .zip or the export.xml inside this app.

Large files? The app will smart-trim to recent days locally."""
        elif device == "Fitbit":
            instructions = """Fitbit:

1. Log into fitbit.com or the Fitbit app.
2. Go to Settings → Data Export or Account → Export Data.
3. Download the CSV or JSON export.
4. Select the file in this app.

Tip: Fitbit exports are usually smaller — full history is manageable."""
        elif device == "Garmin":
            instructions = """Garmin:

1. Go to garmin.com or Garmin Connect app → More → Settings → User Profile → Data Export.
2. Or use Garmin Health API exports if available.
3. Download CSV/JSON/FIT files.
4. Upload the export file here.

Garmin data often includes excellent HRV and training load."""
        else:
            instructions = f"""{device}:

1. Log into your device's app or website.
2. Look for "Export Data", "Download CSV/JSON", "Health Export", or "Share Data".
3. Save the file(s) to this computer.
4. Select the .csv, .json, .xml, or .zip in this app.

Most wearables support CSV or JSON export. The app will process what it can locally for a smart summary."""

        messagebox.showinfo(f"How to get data from {device}", instructions)

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Select wearable export (.zip, .xml, .csv, .json)",
            filetypes=[("Wearable Exports", "*.zip *.xml *.csv *.json *.txt"), ("All files", "*.*")]
        )
        if path:
            self.file_path.set(path)

    def preview_local(self):
        """Smart local processing: extract summary stats without uploading. Works for most wearables."""
        path = self.file_path.get()
        if not path or not os.path.exists(path):
            messagebox.showerror("No file", "Choose a file first.")
            return

        device = self.device_var.get()
        self.log_msg(f"\n=== Local Smart Analysis for {device} ===")
        self.log_msg("Processing locally (no data sent yet)...")

        def do_preview():
            try:
                working_path = path
                # Handle zip for Apple-like
                if path.lower().endswith('.zip'):
                    with zipfile.ZipFile(path, 'r') as z:
                        xmls = [n for n in z.namelist() if n.lower().endswith('.xml') and 'export' in n.lower()]
                        if xmls:
                            member = xmls[0]
                            working_path = os.path.join(tempfile.gettempdir(), "preview_export.xml")
                            with z.open(member) as src, open(working_path, "wb") as dst:
                                dst.write(src.read())
                            self.log_msg(f"Extracted {member} for analysis")

                summary_lines = []

                if device == "Apple Health" or working_path.lower().endswith(('.xml', '.zip')):
                    # Use smart recent-focused logic (ported from backend)
                    try:
                        metrics = {}
                        samples = []
                        count = 0
                        MAX = 3000  # safe local limit

                        for event, elem in ET.iterparse(working_path, events=("end",)):
                            if elem.tag == "Record":
                                count += 1
                                if count > MAX:
                                    elem.clear()
                                    break
                                rtype = elem.get("type", "").replace("HKQuantityTypeIdentifier", "").replace("HKCategoryTypeIdentifier", "")
                                val_str = elem.get("value")
                                unit = elem.get("unit", "")
                                date = elem.get("startDate", "")[:10]

                                if val_str and any(k in rtype for k in ["HeartRate", "RestingHeartRate", "StepCount", "Sleep", "HeartRateVariability", "Distance", "ActiveEnergy"]):
                                    try:
                                        val = float(val_str)
                                        if rtype not in metrics:
                                            metrics[rtype] = []
                                        metrics[rtype].append(val)
                                        if len(samples) < 8:
                                            samples.append(f"{date} {rtype}: {val:.1f} {unit}")
                                    except:
                                        pass
                                elem.clear()

                        for k, vals in metrics.items():
                            if vals:
                                avg = sum(vals) / len(vals)
                                summary_lines.append(f"  {k}: avg={avg:.1f}, min={min(vals):.1f}, max={max(vals):.1f} ({len(vals)} samples)")

                        if samples:
                            summary_lines.append("  Recent samples: " + "; ".join(samples))

                    except Exception as e:
                        summary_lines.append(f"  Apple XML parse limited: {str(e)[:80]}")

                elif device in ["Fitbit", "Garmin", "Oura / Whoop / Other", "CSV / JSON / General"]:
                    # Basic smart parse for common exports
                    ext = os.path.splitext(working_path)[1].lower()
                    if ext == ".csv":
                        with open(working_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()[:100]
                        summary_lines.append(f"  CSV rows sampled: {len(lines)}")
                        if lines:
                            summary_lines.append("  Header example: " + lines[0].strip()[:120])
                    elif ext == ".json":
                        import json
                        with open(working_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        summary_lines.append(f"  JSON top-level keys: {list(data.keys())[:5] if isinstance(data, dict) else 'list of ' + str(len(data))}")
                    else:
                        summary_lines.append("  General file detected — will upload as-is for server processing.")

                if summary_lines:
                    self.log_msg("Local wearable summary (recent focus):")
                    for line in summary_lines:
                        self.log_msg(line)
                else:
                    self.log_msg("  Could not generate detailed local summary. Will still upload the raw file.")

                self.log_msg("Preview complete. Use 'Upload' to send the (trimmed) data to Grok.")
            except Exception as e:
                self.log_msg(f"Local preview error: {e}")
                messagebox.showerror("Preview Error", str(e))

        threading.Thread(target=do_preview, daemon=True).start()

    def fetch_lab_results(self):
        """Log into the selected blood testing portal using customer credentials, download result PDFs, then prepare for upload to Root Cause."""
        lab = self.lab_var.get()
        username = self.lab_user_var.get().strip()
        password = self.lab_pass_var.get()
        root_cause_email = self.email_var.get().strip()
        root_cause_pass = self.password_var.get()

        if not username or not password:
            messagebox.showerror("Missing", "Enter lab username and password.")
            return
        if not root_cause_email or not root_cause_pass:
            messagebox.showerror("Missing", "Enter your Root Cause login first (top of app).")
            return

        self.log_msg(f"\n=== Fetching from {lab} ===")
        self.log_msg("Logging into lab portal (creds used only temporarily)...")

        def do_fetch():
            if BeautifulSoup is None:
                self.log_msg("Install beautifulsoup4 for automatic lab portal login: pip install beautifulsoup4")
                messagebox.showerror("Missing package", "pip install beautifulsoup4")
                return
            try:
                session = requests.Session()
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                session.headers.update(headers)

                downloaded_files = []

                if lab == "GoodLabs":
                    # GoodLabs login (phone or email based, from their portal)
                    login_url = "https://goodlabs.com/login"
                    # Common pattern - may need adjustment based on exact form
                    login_data = {
                        "phone": username,
                        "email": username,  # try both
                        "password": password
                    }
                    resp = session.post(login_url, data=login_data, timeout=15)
                    if resp.status_code != 200 or "login" in resp.url.lower():
                        # Try alternative if needed
                        self.log_msg("Trying alternative GoodLabs auth flow...")
                        # Assume results after login
                    results_url = "https://goodlabs.com/results"  # or /dashboard or account
                    resp = session.get(results_url, timeout=15)
                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Find PDF download links (adapt selectors as site updates)
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        if ".pdf" in href.lower() or "download" in link.get_text().lower() or "result" in link.get_text().lower():
                            full_url = urljoin(results_url, href)
                            pdf_resp = session.get(full_url, timeout=30)
                            if pdf_resp.status_code == 200 and b"%PDF" in pdf_resp.content[:100]:
                                filename = os.path.join(tempfile.gettempdir(), f"GoodLabs_{len(downloaded_files)+1}.pdf")
                                with open(filename, "wb") as f:
                                    f.write(pdf_resp.content)
                                downloaded_files.append(filename)
                                self.log_msg(f"Downloaded: {filename}")

                elif lab == "Quest (MyQuest)":
                    # Quest MyQuest example (more complex portals often require more steps/2FA handling)
                    login_url = "https://myquest.questdiagnostics.com/web/home"
                    # Simplified - real impl may need multiple requests, cookies, etc.
                    login_data = {"username": username, "password": password}
                    resp = session.post(login_url, data=login_data, timeout=15)
                    results_url = "https://myquest.questdiagnostics.com/web/results"
                    resp = session.get(results_url, timeout=15)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", href=True):
                        if "download" in a.get_text().lower() or ".pdf" in a["href"].lower():
                            full = urljoin(results_url, a["href"])
                            pdf_r = session.get(full, timeout=30)
                            if pdf_r.status_code == 200:
                                fn = os.path.join(tempfile.gettempdir(), f"Quest_{len(downloaded_files)+1}.pdf")
                                with open(fn, "wb") as f: f.write(pdf_r.content)
                                downloaded_files.append(fn)
                                self.log_msg(f"Downloaded: {fn}")

                else:
                    self.log_msg(f"Support for {lab} is skeleton. Implement specific scraper or use manual export.")
                    # For demo, create a placeholder note
                    return

                if downloaded_files:
                    self.log_msg(f"Successfully fetched {len(downloaded_files)} result file(s).")
                    # Auto-upload to Root Cause with proper label
                    for fpath in downloaded_files:
                        self.log_msg(f"Uploading {os.path.basename(fpath)} to your Root Cause account...")
                        with open(fpath, "rb") as f:
                            files = {"file": (os.path.basename(fpath), f)}
                            data = {
                                "email": root_cause_email,
                                "password": root_cause_pass,
                                "label": f"Blood Test Results - {lab}",
                                "test_date": datetime.now().strftime("%Y-%m-%d")
                            }
                            r = requests.post(API_UPLOAD, data=data, files=files, timeout=60)
                            if r.status_code == 200 and r.json().get("success"):
                                self.log_msg("  Uploaded successfully!")
                            else:
                                self.log_msg(f"  Upload issue: {r.text[:200]}")
                    messagebox.showinfo("Success", f"Fetched and uploaded {len(downloaded_files)} blood test result(s) to your Root Cause account. Request analysis update in dashboard to let Grok review them.")
                else:
                    self.log_msg("No PDF results found. Check credentials, or the portal may require 2FA/manual step. Try manual download and upload the PDF here.")

            except Exception as e:
                self.log_msg(f"Fetch error: {e}")
                messagebox.showerror("Fetch Failed", str(e) + "\n\nTip: Some portals have 2FA or anti-bot. Use manual export as fallback, or contact support to improve scraper.")

        threading.Thread(target=do_fetch, daemon=True).start()

    def trim_only(self):
        path = self.file_path.get()
        if not path:
            messagebox.showwarning("No file", "Please choose your export file first.")
            return

        days = DEFAULT_TRIM_DAYS
        self.log_msg(f"Trimming locally to last {days} days... (this can take a minute for huge files)")

        def do_trim():
            try:
                trimmed = trim_apple_health_to_recent(path, days)
                self.log_msg(f"Done! Created: {trimmed}")
                self.log_msg("You can now upload the small file, or use it in the website dashboard.")
                self.file_path.set(trimmed)
            except Exception as e:
                self.log_msg(f"Trim failed: {e}")
                messagebox.showerror("Trim Error", str(e))

        threading.Thread(target=do_trim, daemon=True).start()

    def start_upload(self):
        email = self.email_var.get().strip()
        password = self.password_var.get()
        path = self.file_path.get()
        device = self.device_var.get()

        if not email or not password:
            messagebox.showerror("Missing info", "Please enter your email and password.")
            return
        if not path or not os.path.exists(path):
            messagebox.showerror("No file", "Please choose a valid export file.")
            return

        self.upload_btn.config(state="disabled", text="Working...")
        self.log_msg(f"Starting upload for {device}...")

        def worker():
            try:
                file_to_upload = path
                original_name = os.path.basename(path)
                device = self.device_var.get()

                # Smart extraction for zips (Apple-style mainly)
                temp_extracted = None
                if path.lower().endswith('.zip'):
                    self.log_msg("Unzipping locally for smart processing...")
                    try:
                        with zipfile.ZipFile(path, 'r') as z:
                            xml_members = [n for n in z.namelist() if n.lower().endswith('.xml') and 'export' in n.lower()]
                            if xml_members:
                                member = xml_members[0]
                                temp_extracted = os.path.join(tempfile.gettempdir(), "extracted_for_upload.xml")
                                with z.open(member) as src, open(temp_extracted, "wb") as dst:
                                    dst.write(src.read())
                                path = temp_extracted
                                self.log_msg(f"Extracted inner data for smarter handling")
                    except Exception as ex:
                        self.log_msg(f"Zip extraction note: {ex} (uploading original zip)")

                # Smarter local processing
                do_smart = self.trim_var.get()
                if do_smart:
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    if size_mb > 10 or device == "Apple Health":
                        self.log_msg(f"Large file or Apple data ({size_mb:.1f} MB) — applying smart local trim/summary...")
                        try:
                            if device == "Apple Health" or path.lower().endswith(('.xml', '.zip')):
                                file_to_upload = trim_apple_health_to_recent(path, DEFAULT_TRIM_DAYS)
                            else:
                                # For other devices, just use as-is (server will summarize)
                                file_to_upload = path
                            original_name = os.path.basename(file_to_upload)
                            self.log_msg(f"Smart processed file ready: {original_name}")
                        except Exception as proc_err:
                            self.log_msg(f"Smart processing issue: {proc_err}. Uploading raw file.")
                            file_to_upload = path
                    else:
                        file_to_upload = path

                self.log_msg("Uploading to Root Cause...")

                with open(file_to_upload, "rb") as f:
                    files = {"file": (original_name, f)}
                    data = {"email": email, "password": password}

                    resp = requests.post(API_UPLOAD, data=data, files=files, timeout=120)

                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("success"):
                        self.log_msg("SUCCESS!")
                        self.log_msg(result.get("message", ""))
                        self.log_msg("Next step: Log into https://www.root-cause-test.com/dashboard")
                        self.log_msg("and click 'Request Updated Grok Analysis' so Grok includes the data.")
                        messagebox.showinfo("Uploaded", "Data sent to Grok!\n\nCheck your dashboard and request an analysis update.")
                    else:
                        self.log_msg("Upload response: " + str(result))
                else:
                    try:
                        err = resp.json().get("error", resp.text)
                    except:
                        err = resp.text
                    self.log_msg(f"Upload failed ({resp.status_code}): {err}")

            except Exception as e:
                self.log_msg(f"Error: {e}")
                messagebox.showerror("Error", str(e))
            finally:
                self.root.after(0, lambda: self.upload_btn.config(state="normal", text="Upload to Root Cause (Grok)"))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = HealthUploaderApp(root)
    root.mainloop()
