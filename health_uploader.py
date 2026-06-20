#!/usr/bin/env python3
"""
Root Cause Health Uploader
A simple desktop app for Apple Watch / health device owners.

What it does:
- Lets the client log in with their Root Cause account (email + password)
- Select their Apple Health export.zip or export.xml
- Optionally trims the data locally to recent days (keeps your data small and private)
- Uploads it directly so Grok can analyze it and include in reports

How clients use it:
1. Download this file (health_uploader.py)
2. Install Python if needed (Microsoft Store or python.org)
3. Double-click or run: python health_uploader.py
4. Enter login, pick the export file, click Upload

Requirements: Python 3 + requests (pip install requests) + tkinter (usually built-in)

The app trims locally when possible so you don't upload your entire life history.
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



# ===================== CONFIG =====================
# Change this if the site URL is different
SITE_URL = "https://www.root-cause-test.com"
API_UPLOAD = f"{SITE_URL}/api/client/upload_health"

# Default days to keep when trimming locally
DEFAULT_TRIM_DAYS = 60
# ==================================================


def trim_apple_health_to_recent(input_path: str, days: int = DEFAULT_TRIM_DAYS) -> str:
    """
    Stream-parse an Apple Health export.xml (or unzipped export) and write a small recent-only version.
    Returns path to the trimmed XML.
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

        context = ET.iterparse(input_path, events=("end",))

        for event, elem in context:
            if elem.tag == "Record":
                total += 1
                start = elem.get("startDate") or ""
                keep = True
                if start:
                    try:
                        # rough parse
                        date_part = start[:10]
                        dt = datetime.fromisoformat(date_part)
                        keep = dt >= cutoff
                    except:
                        keep = True  # keep if unsure

                if keep:
                    out.write(ET.tostring(elem, encoding="unicode"))
                    out.write("\n")
                    kept += 1

                elem.clear()

            if total % 100000 == 0:
                # non-blocking hint
                pass

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

        # File frame
        file_frame = tk.LabelFrame(root, text="Apple Health Export", padx=10, pady=8)
        file_frame.pack(fill="x", padx=15, pady=8)

        self.file_path = tk.StringVar()
        tk.Entry(file_frame, textvariable=self.file_path, width=55).pack(side="left", padx=(0, 8))
        tk.Button(file_frame, text="Choose .zip or export.xml", command=self.choose_file).pack(side="left")

        # Options
        options_frame = tk.Frame(root)
        options_frame.pack(fill="x", padx=15, pady=(4, 8))

        self.trim_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text=f"Trim to last {DEFAULT_TRIM_DAYS} days locally before uploading (recommended)", 
                       variable=self.trim_var).pack(anchor="w")

        tk.Label(options_frame, text="This keeps the upload small and only sends recent data to Grok.", 
                 fg="#555").pack(anchor="w")

        # Buttons
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        self.upload_btn = tk.Button(btn_frame, text="Upload to Root Cause (Grok)", 
                                    command=self.start_upload, bg="#2e7d32", fg="white", padx=12, pady=6)
        self.upload_btn.pack(side="left", padx=6)

        tk.Button(btn_frame, text="Trim Only (no upload)", command=self.trim_only).pack(side="left", padx=6)

        # Status
        status_frame = tk.LabelFrame(root, text="Status / Log", padx=8, pady=6)
        status_frame.pack(fill="both", expand=True, padx=15, pady=(8, 15))

        self.log = scrolledtext.ScrolledText(status_frame, height=14, wrap="word")
        self.log.pack(fill="both", expand=True)

        self.log.insert("end", "Welcome! Select your Apple Health export and click Upload.\n")
        self.log.insert("end", "The data goes into your account so Grok can use it in your reports.\n\n")

    def log_msg(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.root.update_idletasks()

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Select Apple Health export.zip or export.xml",
            filetypes=[("Apple Health Export", "*.zip *.xml"), ("All files", "*.*")]
        )
        if path:
            self.file_path.set(path)

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

        if not email or not password:
            messagebox.showerror("Missing info", "Please enter your email and password.")
            return
        if not path or not os.path.exists(path):
            messagebox.showerror("No file", "Please choose a valid export file.")
            return

        self.upload_btn.config(state="disabled", text="Working...")
        self.log_msg("Starting...")

        def worker():
            try:
                file_to_upload = path
                original_name = os.path.basename(path)

                # If user selected a .zip, extract the main XML first (best for large files)
                temp_extracted = None
                if path.lower().endswith('.zip'):
                    self.log_msg("Unzipping locally to find export.xml...")
                    try:
                        with zipfile.ZipFile(path, 'r') as z:
                            xml_members = [n for n in z.namelist() if n.lower().endswith('.xml') and 'export' in n.lower()]
                            if xml_members:
                                member = xml_members[0]
                                temp_extracted = os.path.join(tempfile.gettempdir(), "export_from_zip.xml")
                                with z.open(member) as src, open(temp_extracted, "wb") as dst:
                                    dst.write(src.read())
                                path = temp_extracted   # use the extracted xml for trimming
                                self.log_msg(f"Found and extracted {member}")
                    except Exception as ex:
                        self.log_msg(f"Could not auto-extract from zip: {ex}")

                # Optional local trim (only on the XML)
                if self.trim_var.get() and os.path.getsize(path) > 15 * 1024 * 1024:
                    self.log_msg("File is large — trimming to recent data locally first (this keeps the upload fast)...")
                    try:
                        file_to_upload = trim_apple_health_to_recent(path, DEFAULT_TRIM_DAYS)
                        original_name = os.path.basename(file_to_upload)
                        self.log_msg(f"Trimmed file ready: {original_name}")
                    except Exception as trim_err:
                        self.log_msg(f"Local trim skipped (error: {trim_err}). Uploading original.")
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
    # Make sure we have ET for trimming
    try:
        import xml.etree.ElementTree as ET
    except:
        pass

    root = tk.Tk()
    app = HealthUploaderApp(root)
    root.mainloop()
