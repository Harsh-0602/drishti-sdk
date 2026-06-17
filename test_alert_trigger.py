"""
Alert trigger test — verifies that the alert email pipeline fires end-to-end.

Usage:
    python test_alert_trigger.py <YOUR_API_KEY>

Expected Render logs after this runs:
  [ALERT] Scheduling alert evaluation for project=...
  [ALERT] evaluate_alerts_for_project: project=... found 1 enabled rule(s)
  [ALERT] Evaluating rule id=... name='Cost Spike' type=cost_spike threshold=0.01 ...
  [ALERT] cost_spike check: ... total_cost_inr=1.000000 threshold=0.010000 exceeded=True
  [ALERT] THRESHOLD EXCEEDED — firing alert for rule id=...
  [ALERT] Calling send_email_alert: to=<your_email> ...
  [ALERT] Resend: using key prefix=re_MXbpp...  from=alerts@drishtiai.dev
  [ALERT] Calling resend.Emails.send() to=<your_email> ...
  [ALERT] Resend API SUCCESS — email_id=<some_id>
"""
import sys
import time
import datetime
import urllib.request
import json
import ssl

# ── Config ─────────────────────────────────────────────────────────────
API_KEY  = sys.argv[1] if len(sys.argv) > 1 else "REPLACE_WITH_YOUR_API_KEY"
ENDPOINT = "https://drishti-backend-3fks.onrender.com"

# ── Send a trace with cost clearly exceeding ₹0.01 ─────────────────────
now = datetime.datetime.now(datetime.timezone.utc)
started = now.isoformat()
ended   = (now + datetime.timedelta(milliseconds=500)).isoformat()

payload = {
    "name": "alert_threshold_test",
    "status": "ok",
    "total_cost_inr": 1.00,        # ₹1.00  >> ₹0.01 threshold
    "total_cost_usd": 0.012,
    "total_latency_ms": 500,
    "model_used": "gpt-4o",
    "tokens_input": 500,
    "tokens_output": 200,
    "input_preview": "alert test input",
    "output_preview": "alert test output",
    "started_at": started,
    "ended_at": ended,
    "tags": ["alert-test"],
    "metadata": {"test": True},
}

print(f"\n[AlertTest] Sending trace with cost_inr=1.00 (threshold=0.01) ...")
print(f"[AlertTest] Endpoint: {ENDPOINT}")
print(f"[AlertTest] API Key : {API_KEY[:12]}...")

try:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{ENDPOINT}/v1/traces",
        data=data,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    )
    # Bypass local SSL validation issues
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
        status_code = response.getcode()
        resp_body = response.read().decode("utf-8")
        resp_json = json.loads(resp_body) if resp_body else {}

    print(f"\n[AlertTest] HTTP {status_code}")
    print(f"[AlertTest] Response: {resp_json}")
except urllib.error.HTTPError as e:
    status_code = e.code
    print(f"\n[AlertTest] HTTP {status_code}")
    print(f"[AlertTest] Error Response: {e.read().decode('utf-8')}")
except Exception as e:
    status_code = 0
    print(f"\n[AlertTest] Exception: {e}")

if status_code == 201:
    print("\n[SUCCESS] Trace accepted. Now check Render logs for:")
    print("   [ALERT] Scheduling alert evaluation for project=...")
    print("   [ALERT] evaluate_alerts_for_project: project=... found 1 enabled rule(s)")
    print("   [ALERT] cost_spike check: total_cost_inr=1.000000 threshold=0.010000 exceeded=True")
    print("   [ALERT] THRESHOLD EXCEEDED - firing alert for rule id=...")
    print("   [ALERT] Resend API SUCCESS - email_id=...")
    print("\n   Then check your inbox for the alert email!")
else:
    print(f"\n[FAILED] Trace rejected! Fix this first before checking alerts.")
