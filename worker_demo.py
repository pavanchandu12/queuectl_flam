#!/usr/bin/env python3
"""Run worker and show results"""
import subprocess
import sys
import time
import json

print("\n" + "="*70)
print("STARTING WORKER - Will process all pending jobs")
print("="*70 + "\n")

# Start the worker in a subprocess
cmd = [sys.executable, "main.py", "worker", "start", "--count", "1"]
process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Let it run for 10 seconds
time.sleep(10)

# Kill the worker
process.terminate()
try:
    stdout, stderr = process.communicate(timeout=2)
    print(stdout)
    if stderr:
        print("[STDERR]", stderr)
except:
    process.kill()

print("\n" + "="*70)
print("WORKER STOPPED - Checking final status")
print("="*70 + "\n")

# Show final status
cmd = [sys.executable, "main.py", "status"]
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)

# Show final jobs
print("\n" + "="*70)
print("FINAL JOBS")
print("="*70 + "\n")
cmd = [sys.executable, "main.py", "list"]
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)

# Show DLQ
print("\n" + "="*70)
print("DEAD LETTER QUEUE")
print("="*70 + "\n")
cmd = [sys.executable, "main.py", "dlq", "list"]
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
