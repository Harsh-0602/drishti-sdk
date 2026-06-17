"""
End-to-end test for Drishti SDK → Render backend.
Run: python e2e_test.py
"""
import time
import sys

import os

# ── Config ────────────────────────────────────────────────────────────
API_KEY  = os.environ.get("DRISHTI_API_KEY", "REPLACE_WITH_YOUR_KEY")
ENDPOINT = "https://drishti-backend-3fks.onrender.com"  # correct Render URL

# ── Test ──────────────────────────────────────────────────────────────
print(f"[Test] SDK version check...")
import importlib.metadata
try:
    ver = importlib.metadata.version("drishti-ai-sdk")
    print(f"[Test] drishti-ai-sdk version: {ver}")
except Exception:
    print("[Test] WARNING: Could not read package version")

print(f"\n[Test] Initialising Drishti client...")
print(f"[Test] Endpoint: {ENDPOINT}")

from drishti import Drishti

try:
    d = Drishti(api_key=API_KEY, endpoint=ENDPOINT, debug=True)
    print("[Test] ✅ Client initialised successfully\n")
except Exception as e:
    print(f"[Test] ❌ Client init failed: {e}")
    sys.exit(1)

print("[Test] Sending trace 'first_real_trace'...")
try:
    with d.trace("first_real_trace", input="e2e test run") as trace:
        time.sleep(0.3)
        trace.set_output("test passed")
    print("[Test] ✅ Trace sent!\n")
except Exception as e:
    print(f"[Test] ❌ Trace failed: {e}")
    sys.exit(1)

# Give background sender time to flush
print("[Test] Waiting 3s for background sender to flush...")
time.sleep(3)
d.shutdown(wait=True)

print("\n" + "="*50)
print("✅ END-TO-END TEST PASSED!")
print(f"Check your dashboard for trace 'first_real_trace'")
print("="*50)
