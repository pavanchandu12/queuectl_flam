# QueueCTL Architecture & Design

## System Design

QueueCTL is a **single-machine background job queue** designed for simplicity and reliability.

```
┌─────────────────────────────────────────────────────────────┐
│                    User (CLI)                               │
│            (enqueue, status, list, worker)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────▼─────────────────┐
        │    Click CLI Framework           │
        │  (command parsing & validation)  │
        └────────────────┬─────────────────┘
                         │
        ┌────────────────▼──────────────────────┐
        │    Main Application Logic             │
        │  - load/save jobs                     │
        │  - manage states                      │
        │  - handle retries                     │
        └────────────────┬──────────────────────┘
                         │
        ┌────────────────▼──────────────────────┐
        │    Worker Engine                      │
        │  - execute commands                   │
        │  - calculate backoff                  │
        │  - manage job states                  │
        └────────────────┬──────────────────────┘
                         │
        ┌────────────────▼──────────────────────┐
        │    File Storage                       │
        │  - jobs.json                          │
        │  - dlq.json                           │
        │  - config.json                        │
        └───────────────────────────────────────┘
```

---

## Data Model

### Job Schema

```json
{
  "id": "unique-job-id",
  "command": "bash command to execute",
  "state": "pending|processing|completed|failed|dead",
  "attempts": 0,
  "max_retries": 3,
  "created_at": "2025-11-13T10:30:00Z",
  "updated_at": "2025-11-13T10:30:00Z"
}
```

### State Transitions

```
PENDING ────────────→ PROCESSING ────────→ COMPLETED ✅
  ▲                      │
  │                      │ (exit code ≠ 0)
  │                      ▼
  │                   FAILED
  │                      │
  │         (wait + retry if attempts < max_retries)
  │                      │
  └──────────────────────┘

After max_retries exhausted:
  FAILED → DEAD ☠️ (moved to DLQ)
```

---

## Key Algorithms

### 1. Exponential Backoff

**Purpose**: Gradually increase retry delays to avoid hammering failing services

**Formula**: 
```
delay_seconds = backoff_base ^ attempt_number
```

**Example** (backoff_base=2):
- Attempt 1: 2¹ = 2 seconds
- Attempt 2: 2² = 4 seconds
- Attempt 3: 2³ = 8 seconds
- Total wait: 14 seconds before DLQ

**Benefits**:
- Gives failing services time to recover
- Reduces load on system
- Prevents retry storms

### 2. Worker Processing Loop

```python
while True:
    jobs = load_jobs()
    pending = [j for j in jobs if j['state'] == 'pending']
    
    if not pending:
        wait(2 seconds)
        continue
    
    for job in pending[:worker_count]:
        job['state'] = 'processing'
        result = execute_command(job['command'])
        
        if result.success:
            job['state'] = 'completed'
        else:
            if job['attempts'] < job['max_retries']:
                job['state'] = 'failed'
                job['attempts'] += 1
            else:
                job['state'] = 'dead'
    
    save_jobs(jobs)
    move_dead_jobs_to_dlq()
```

### 3. DLQ Migration

Jobs are moved from jobs.json to dlq.json when:
- `job['attempts'] >= job['max_retries']` AND
- `job['state'] == 'dead'`

This prevents corruption of the main queue with permanently failed jobs.

---

## Persistence Strategy

### File Format: JSON

**Why JSON?**
- Human readable (easy debugging)
- Built-in Python support
- Simple to parse and modify
- Sufficient for single-machine use case

### Files

1. **jobs.json** - Main queue
   - Contains all jobs in all states (except dead)
   - Updated after each job processes
   - ~50 lines per job average

2. **dlq.json** - Dead Letter Queue
   - Contains only permanently failed jobs
   - Separated for clean queue management
   - Can be archived or analyzed

3. **config.json** - Configuration
   - System settings (retries, backoff, workers)
   - Modified by `config set` command
   - Loaded at worker startup

### Atomic Operations

All saves use:
```python
def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
```

**Note**: In high-concurrency scenarios, implement file locking to prevent race conditions.

---

## Concurrency Model

### Current Implementation: Single Process

Workers run in **one Python process** with a **processing loop**:
- One worker processes one job at a time
- Multiple workers process multiple jobs in parallel (using `--count`)
- Each iteration sleeps 1 second between job batches

### Example with 3 Workers

```
Iteration 1:
  Worker 1: Process job-1
  Worker 2: Process job-2
  Worker 3: Process job-3
  
Iteration 2:
  (Check for new pending jobs)
  Worker 1: Process job-4
  ...
```

### Thread Safety

Currently **not thread-safe** because:
- No file locking
- No process synchronization
- Multiple processes could corrupt files

**For production**, consider:
- File locks (fcntl on Unix, msvcrt on Windows)
- Database instead of JSON
- Process-level synchronization

---

## Error Handling

### Job Execution Errors

```python
try:
    result = subprocess.run(command, timeout=30)
except subprocess.TimeoutExpired:
    # Treat as failure, retry
except Exception as e:
    # Catch all other errors, retry
```

### User Input Errors

```python
# Invalid JSON
if not json.loads(input):
    raise JSONDecodeError

# Missing required fields
if 'command' not in job_data:
    raise ValueError("'command' required")

# Invalid state filter
if state not in ['pending', 'completed', ...]:
    raise ValueError(f"Unknown state: {state}")
```

---

## Performance Considerations

### Scalability Limits

| Parameter | Current | Bottleneck |
|-----------|---------|-----------|
| Jobs per queue | 10K | JSON file I/O |
| Job size | Any | Disk I/O |
| Workers | 10+ | CPU/memory |
| Retry delay | 2³ = 8s max | Exponential growth |

### Optimization Ideas

1. **Lazy Loading**: Load only recent jobs
2. **Indexing**: Pre-sort jobs by state
3. **Batch Processing**: Process multiple jobs per cycle
4. **Database**: Replace JSON with SQLite for speed
5. **Async Workers**: Use threading/asyncio instead of blocking

---

## Security Considerations

### Current Vulnerabilities

⚠️ **Command Injection Risk**
```python
# VULNERABLE: User can pass arbitrary commands
subprocess.run(job['command'], shell=True)
```

**Mitigation**:
- Validate/whitelist allowed commands
- Use `subprocess.run(args, shell=False)` when possible
- Run workers in sandboxed environment

⚠️ **No Authentication**
- Anyone with file access can modify jobs
- Add user permissions/ACLs for production

⚠️ **No Input Validation**
- Large command strings could cause issues
- Add max length limits

### Recommendations for Production

1. Use `shell=False` with command array
2. Implement command validation/whitelist
3. Add file permissions (chmod 600)
4. Use environment variables for secrets
5. Add audit logging

---

## Testing Strategy

### Unit Tests (To Add)

```python
def test_calculate_backoff():
    assert calculate_backoff_delay(0, 2) == 1
    assert calculate_backoff_delay(1, 2) == 2
    assert calculate_backoff_delay(3, 2) == 8

def test_job_state_transitions():
    job = create_test_job()
    assert job['state'] == 'pending'
    process_job(job)
    assert job['state'] in ['completed', 'failed']
```

### Integration Tests (Current)

- `full_test.py` - End-to-end workflow
- `worker_demo.py` - Worker processing demo

### Manual Tests

1. Add job → Check status → Verify in JSON
2. Run worker → Check job completed
3. Add invalid command → Check retry → Check DLQ
4. Config change → Verify applied
5. Restart → Verify data persisted

---

## Future Enhancements

### Phase 1: Reliability
- [ ] File locking for concurrency
- [ ] Transaction-like job updates
- [ ] Error recovery mechanism
- [ ] Job output logging

### Phase 2: Features
- [ ] Job priorities
- [ ] Scheduled jobs (run_at)
- [ ] Job dependencies
- [ ] Webhooks on completion

### Phase 3: Operations
- [ ] Web dashboard
- [ ] Metrics & monitoring
- [ ] Job analytics
- [ ] Alerting system

### Phase 4: Scalability
- [ ] Multi-machine support
- [ ] Message queue (RabbitMQ/Redis)
- [ ] Distributed workers
- [ ] Database backend

---

## Deployment

### Single Machine

```bash
# Install
pip install -r requirements.txt

# Run worker
python main.py worker start --count 4

# Monitor
watch -n 1 'python main.py status'
```

### Docker Container (Future)

```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py", "worker", "start", "--count", "1"]
```

### Systemd Service (Future)

```ini
[Unit]
Description=QueueCTL Worker
After=network.target

[Service]
Type=simple
User=queuectl
ExecStart=/usr/bin/python3 /opt/queuectl/main.py worker start --count 4
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Debugging Tips

### View jobs.json directly
```bash
cat jobs.json | python -m json.tool
```

### Check job status
```bash
python main.py list --state failed
```

### Monitor in real-time
```bash
while true; do python main.py status; sleep 1; done
```

### Trace execution
```bash
python -u main.py worker start --count 1 2>&1 | tee worker.log
```

---

## Questions?

Refer to README.md for usage or reach out!
