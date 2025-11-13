# QueueCTL - Background Job Queue System

A **CLI-based job queue system** that manages background jobs, handles retries with exponential backoff, and maintains a Dead Letter Queue for permanently failed jobs.

## 🎯 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/pavanchandu12/queuectl_flam.git
cd queuectl

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```bash
# Add a job to the queue
python main.py enqueue '{"id":"job1","command":"echo Hello World"}'

# Check status
python main.py status

# List all jobs
python main.py list

# Start 1 worker to process jobs
python main.py worker start --count 1

# View configuration
python main.py config show

# Change settings
python main.py config set max-retries 5
```

---

## 📦 Features

✅ **Job Enqueuing** - Add background jobs via CLI  
✅ **Multiple Workers** - Process jobs in parallel  
✅ **Retry with Exponential Backoff** - Failed jobs retry automatically  
✅ **Dead Letter Queue (DLQ)** - Permanently failed jobs stored separately  
✅ **Persistent Storage** - Jobs survive restarts (JSON-based)  
✅ **Configuration Management** - Adjust retry count, backoff, worker count  
✅ **Job Status Tracking** - Monitor jobs through their lifecycle  

---

## 🔄 Job Lifecycle

```
PENDING → PROCESSING → COMPLETED ✅
   ↓
FAILED → (wait + retry) → PENDING (loop back)
   ↓
After max retries → DEAD (moved to DLQ) ☠️
```

**States:**
- `pending` - Waiting to be processed
- `processing` - Currently running
- `completed` - Successfully finished
- `failed` - Failed, but can retry
- `dead` - Permanently failed (in DLQ)

---

## 💻 CLI Commands

### Enqueue Jobs
```bash
# Add a simple job
python main.py enqueue '{"id":"job1","command":"echo test"}'

# Command runs in shell (any OS command works)
python main.py enqueue '{"id":"backup","command":"echo Backup complete"}'
```

### Check Status
```bash
# Overall queue status
python main.py status
```

**Output:**
```
[QUEUE STATUS]
Pending Jobs:     2
Processing Jobs:  0
Completed Jobs:   5
Failed Jobs:      1
Dead Letter Queue: 1
Total Jobs:       9

[CONFIGURATION]:
  Max Retries:    3
  Backoff Base:   2
  Worker Count:   1
```

### List Jobs
```bash
# All jobs
python main.py list

# Filter by state
python main.py list --state pending
python main.py list --state completed
python main.py list --state failed
```

### Start Workers
```bash
# Start 1 worker
python main.py worker start --count 1

# Start 3 workers (parallel processing)
python main.py worker start --count 3

# Stop: Press Ctrl+C
```

### Configuration
```bash
# Show current config
python main.py config show

# Change max retries
python main.py config set max-retries 5

# Change backoff base (exponential: 2^attempts)
python main.py config set backoff-base 3

# Change worker count
python main.py config set worker-count 4
```

### Dead Letter Queue (DLQ)
```bash
# View all permanently failed jobs
python main.py dlq list

# Retry a failed job from DLQ
python main.py dlq retry job1

# Clear the DLQ
python main.py dlq clear
```

---

## ⚙️ How It Works

### Job Execution
1. Worker picks up a pending job
2. Runs the command in shell
3. Exit code determines result:
   - `0` = Success → marked as `completed`
   - Non-zero = Failure → increment attempts

### Retry & Backoff
- Formula: `delay = backoff_base ^ attempts` seconds
- Example with `backoff_base=2`:
  - Attempt 1: Wait 2¹ = 2 seconds
  - Attempt 2: Wait 2² = 4 seconds
  - Attempt 3: Wait 2³ = 8 seconds
  - After 3 attempts: Move to DLQ

### Persistence
- **jobs.json** - All jobs (pending, running, completed, failed)
- **dlq.json** - Dead jobs (permanently failed)
- **config.json** - System configuration

---

## 📊 Architecture

```
┌─────────────────────────────────────┐
│         CLI Interface               │
│  (enqueue, status, list, config)    │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│    Job Manager                      │
│  (load/save jobs, track states)     │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│    Worker Engine                    │
│  (process jobs, handle retries)     │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│    Storage Layer                    │
│  (jobs.json, dlq.json, config.json) │
└─────────────────────────────────────┘
```

---

## 🧪 Testing

Run the test suite:

```bash
# Full test (adds 3 jobs, runs workers, shows results)
python full_test.py

# Worker demo (shows workers in action)
python worker_demo.py
```

**Test Scenarios:**
1. ✅ Simple echo command → Completes successfully
2. ✅ Invalid command → Fails, retries, moves to DLQ
3. ✅ Multiple workers → Process in parallel
4. ✅ Status tracking → All states working
5. ✅ Persistence → Data survives restarts

---

## 📁 File Structure

```
queuectl/
├── main.py              # CLI application (all commands)
├── requirements.txt     # Python dependencies
├── config.json          # Settings (max-retries, backoff-base, etc.)
├── jobs.json            # Job storage
├── dlq.json             # Dead Letter Queue
├── worker_demo.py       # Demo script showing workers in action
├── full_test.py         # Full test suite
├── test.py              # Basic tests
└── README.md            # This file
```

---

## 🔧 Configuration

Edit `config.json`:

```json
{
  "max_retries": 3,        // Retry failed jobs 3 times
  "backoff_base": 2,       // Exponential: 2^attempts
  "worker_count": 1        // Number of parallel workers
}
```

Or use CLI:
```bash
python main.py config set max-retries 5
python main.py config set backoff-base 3
```

---

## 📝 Example Workflow

```bash
# 1. Add some jobs
python main.py enqueue '{"id":"backup","command":"echo Backing up..."}'
python main.py enqueue '{"id":"report","command":"echo Generating report..."}'
python main.py enqueue '{"id":"sync","command":"invalid-command"}'

# 2. Check status
python main.py status
# Output: 3 Pending Jobs

# 3. Start workers
python main.py worker start --count 2
# Output:
# [WORKER] Processing job: backup
#          Command: echo Backing up...
# [OK] Job backup completed successfully!
# [WORKER] Processing job: report
#          Command: echo Generating report...
# [OK] Job report completed successfully!
# [WORKER] Processing job: sync
#          Command: invalid-command
# [RETRY] Job sync failed. Retry in 2 seconds...

# 4. Check final status
python main.py status
# Output: 2 Completed, 1 Failed

# 5. View DLQ after max retries
python main.py dlq list
```

---

## 🎓 Learning Path

If you're new to this:

1. **Start Simple**: Add 1 job, run 1 worker
2. **Check Status**: Watch job progress
3. **Add Multiple Jobs**: Test parallel processing
4. **Try Failures**: Add invalid commands to see retry logic
5. **View DLQ**: See permanently failed jobs
6. **Modify Config**: Change retry count and test

---

## 🚀 Bonus Features (Optional Enhancements)

- Job timeout handling ✅ (30 second default)
- Job output logging (could save stdout/stderr)
- Scheduled/delayed jobs (run_at field)
- Job priority queues
- Metrics and statistics
- Web dashboard for monitoring

---

## ⚠️ Limitations & Assumptions

- Jobs run **synchronously** (one at a time per worker, but multiple workers can run in parallel)
- Backoff delay is **immediate** (simplified, doesn't account for actual elapsed time)
- Commands run in **shell** (supports any OS command)
- Persistence is **file-based** (not a database)
- No **authentication** or **authorization**
- Single machine only (not distributed)

---

## 🔒 Error Handling

- **Invalid JSON**: Rejected with error message
- **Missing 'command' field**: Rejected with error message
- **Invalid command**: Treated as failure, retried
- **Timeout (30s)**: Treated as failure, retried
- **Exception during execution**: Caught and logged

---

## 📖 Code Quality

- Clean separation of concerns
- Helper functions for common operations
- Clear comments and docstrings
- Type hints in function signatures
- Error handling with try/except

---

## 📜 License



---

## 👨‍💻 Author

Pavan Chandu - Backend Internship Assignment

---



---

## 📧 Questions?

Open an issue on GitHub or reach out!
