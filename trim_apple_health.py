#!/usr/bin/env python3
"""
EASIEST WAY TO TRIM A HUGE APPLE HEALTH EXPORT (for clients)

You usually don't need this — try uploading the normal zip first on the website.

Only use if the upload is too big:

1. Install Python (Microsoft Store → search "Python" → install the latest).
2. Unzip the export.zip you got from your iPhone.
3. Copy this trim_apple_health.py file into the same folder as export.xml.
4. Open PowerShell or Terminal in that folder and type:

   py trim_apple_health.py export.xml

5. It will create a much smaller "export_recent.xml".
6. Upload the small file to the site.

Change CUTOFF_DAYS below if you want fewer days (e.g. 30 or 60).
"""

import sys
import os
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# === EDIT THIS IF YOU WANT A DIFFERENT RANGE ===
CUTOFF_DAYS = 90          # keep only data newer than this many days ago
# ===============================================

def trim_export(input_path: str, output_path: str = None):
    if not os.path.isfile(input_path):
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    if output_path is None:
        base = os.path.dirname(input_path) or "."
        output_path = os.path.join(base, "export_recent.xml")

    cutoff = datetime.utcnow() - timedelta(days=CUTOFF_DAYS)
    cutoff_str = cutoff.isoformat() + "Z"   # Apple uses Z suffix roughly

    print(f"Trimming to last {CUTOFF_DAYS} days (cutoff ~{cutoff.date()})")
    print(f"Reading (streaming): {input_path}")
    print("This is safe even on very large files...")

    kept = 0
    total = 0

    # Write header
    with open(output_path, "w", encoding="utf-8") as out:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        out.write('<HealthData locale="en_US">\n')   # Apple usually includes more attrs but this works for parsing

        # Stream the input
        context = ET.iterparse(input_path, events=("end",))
        for event, elem in context:
            tag = elem.tag

            if tag == "Record":
                total += 1
                start = elem.get("startDate") or ""
                # Apple dates look like 2026-06-10 13:22:55 -0700 or with Z
                # We do a simple string compare first (works because ISO-like), then fallback
                keep = False
                if start:
                    try:
                        # Try common formats
                        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
                            try:
                                dt = datetime.strptime(start[:19] + (start[19:] if len(start) > 19 else ""), fmt.replace("%z", ""))
                                # rough normalize
                                break
                            except:
                                pass
                        else:
                            # fallback: take the date part
                            dt = datetime.fromisoformat(start[:10])
                        keep = dt >= cutoff.replace(tzinfo=None)
                    except Exception:
                        # If we can't parse date, keep it (safer)
                        keep = True

                if keep:
                    # Serialize just this element (no pretty print needed)
                    out.write(ET.tostring(elem, encoding="unicode"))
                    out.write("\n")
                    kept += 1

                elem.clear()

            elif tag in ("ActivitySummary", "Workout", "Correlation", "Audiogram"):
                # Optionally keep some other recent things — for simplicity we mostly keep Records
                # You can extend here if you want workouts etc.
                total += 1
                elem.clear()

            if total > 0 and total % 50000 == 0:
                print(f"  ... scanned {total:,} records, kept {kept:,} so far")

        out.write("</HealthData>\n")

    print(f"\nDone. Kept {kept:,} out of ~{total:,} records.")
    print(f"Saved trimmed file to: {output_path}")
    print("Now upload the small export_recent.xml (or zip it) to the website.")
    print("This small file should upload without causing 502s or restarts.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py trim_apple_health.py export.xml")
        print("   (open PowerShell in the folder with export.xml and run the command above)")
        sys.exit(1)

    inp = sys.argv[1]
    trim_export(inp)