#!/usr/bin/env python3
"""Test script for QueueCTL"""
import subprocess
import sys
import json
import time

def run_cmd(args):
    """Run a queuectl command"""
    cmd = [sys.executable, "main.py"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0

print("="*60)
print("🧪 TEST 1: Add a job to the queue")
print("="*60)
run_cmd(["enqueue", '{"id":"job1","command":"echo Test Job 1"}'])

print("\n" + "="*60)
print("🧪 TEST 2: Show status")
print("="*60)
run_cmd(["status"])

print("\n" + "="*60)
print("🧪 TEST 3: List all jobs")
print("="*60)
run_cmd(["list"])

print("\n" + "="*60)
print("🧪 TEST 4: Show configuration")
print("="*60)
run_cmd(["config", "show"])

print("\n✅ All tests completed!")
