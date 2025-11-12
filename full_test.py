#!/usr/bin/env python3
"""Complete test of QueueCTL functionality"""
import subprocess
import sys
import time
import json

def run_cmd(args, show_output=True):
    """Run a queuectl command"""
    cmd = [sys.executable, "main.py"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if show_output:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("[STDERR]", result.stderr)
    return result.returncode == 0

print("\n" + "="*70)
print("TEST 1: Clear everything and add test jobs")
print("="*70 + "\n")

# Clear existing data
with open("jobs.json", "w") as f:
    json.dump([], f)
with open("dlq.json", "w") as f:
    json.dump([], f)

# Add test jobs
run_cmd(["enqueue", '{"id":"test-job-1","command":"echo SUCCESS"}'])
run_cmd(["enqueue", '{"id":"test-job-2","command":"echo Another job"}'])
run_cmd(["enqueue", '{"id":"test-job-3","command":"invalid-command"}'])

print("\n" + "="*70)
print("TEST 2: Show status BEFORE running workers")
print("="*70 + "\n")
run_cmd(["status"])

print("\n" + "="*70)
print("TEST 3: List all jobs")
print("="*70 + "\n")
run_cmd(["list"])

print("\n" + "="*70)
print("TEST 4: Start 1 worker for 5 seconds (simulating worker processing)")
print("="*70 + "\n")

# Start worker in subprocess and let it run for a bit
import threading
worker_process = None

def run_worker():
    global worker_process
    cmd = [sys.executable, "main.py", "worker", "start", "--count", "1"]
    worker_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
# Start worker thread
worker_thread = threading.Thread(target=run_worker, daemon=True)
worker_thread.start()
time.sleep(3)  # Let worker run for 3 seconds

# Kill the worker
if worker_process:
    worker_process.terminate()
    try:
        worker_process.wait(timeout=2)
    except:
        worker_process.kill()
    
    # Read output
    try:
        stdout, stderr = worker_process.communicate(timeout=1)
        if stdout:
            print(stdout)
        if stderr:
            print("[STDERR]", stderr)
    except:
        pass

print("\n" + "="*70)
print("TEST 5: Show status AFTER running workers")
print("="*70 + "\n")
run_cmd(["status"])

print("\n" + "="*70)
print("TEST 6: List pending jobs")
print("="*70 + "\n")
run_cmd(["list", "--state", "pending"])

print("\n" + "="*70)
print("TEST 7: List completed jobs")
print("="*70 + "\n")
run_cmd(["list", "--state", "completed"])

print("\n" + "="*70)
print("TEST 8: Check DLQ (Dead Letter Queue)")
print("="*70 + "\n")
run_cmd(["dlq", "list"])

print("\n[SUCCESS] All tests completed!\n")
