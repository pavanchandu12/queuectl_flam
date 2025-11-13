#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import uuid
import subprocess
import time
from datetime import datetime
from pathlib import Path
import click


# ============================================================================
# FILE PATHS - Where our data lives
# ============================================================================

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
JOBS_FILE = BASE_DIR / "jobs.json"
DLQ_FILE = BASE_DIR / "dlq.json"


# ============================================================================
# HELPER FUNCTIONS - Tools we'll use
# ============================================================================

def load_json(file_path, default=None):
    """Load data from a JSON file, return default if file doesn't exist"""
    if default is None:
        default = []
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(file_path, data):
    """Save data to a JSON file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def load_config():
    """Load configuration settings"""
    return load_json(CONFIG_FILE, {
        "max_retries": 3,
        "backoff_base": 2,
        "worker_count": 1
    })


def load_jobs():
    """Load all jobs from storage"""
    return load_json(JOBS_FILE, [])


def save_jobs(jobs):
    """Save jobs to storage"""
    save_json(JOBS_FILE, jobs)


def load_dlq():
    """Load dead letter queue"""
    return load_json(DLQ_FILE, [])


def save_dlq(dlq):
    """Save dead letter queue"""
    save_json(DLQ_FILE, dlq)


def get_current_timestamp():
    """Get current timestamp in ISO format"""
    return datetime.utcnow().isoformat() + "Z"


# ============================================================================
# CLI COMMANDS - What the user can type
# ============================================================================

@click.group()
def cli():
    """QueueCTL - A simple job queue system"""
    pass


@cli.command()
@click.argument('job_json')
def enqueue(job_json):
    """Add a new job to the queue
    
    Example: queuectl enqueue '{"id":"job1","command":"echo hello"}'
    """
    try:
        # Parse the JSON that the user gave us
        job_data = json.loads(job_json)
        
        # Check if required fields exist
        if 'id' not in job_data:
            job_data['id'] = str(uuid.uuid4())
        
        if 'command' not in job_data:
            click.echo("[ERROR] 'command' field is required!", err=True)
            return
        
        # Add default values if they don't exist
        if 'state' not in job_data:
            job_data['state'] = 'pending'
        if 'attempts' not in job_data:
            job_data['attempts'] = 0
        if 'max_retries' not in job_data:
            config = load_config()
            job_data['max_retries'] = config.get('max_retries', 3)
        
        # Add timestamps
        now = get_current_timestamp()
        if 'created_at' not in job_data:
            job_data['created_at'] = now
        job_data['updated_at'] = now
        
        # Load existing jobs and add the new one
        jobs = load_jobs()
        jobs.append(job_data)
        save_jobs(jobs)
        
        click.echo("[OK] Job '" + job_data['id'] + "' added to queue!")
        click.echo("     Command: " + job_data['command'])
        click.echo("     State: pending")
        
    except json.JSONDecodeError:
        click.echo("[ERROR] Invalid JSON format!", err=True)
    except Exception as e:
        click.echo("[ERROR] " + str(e), err=True)


@cli.command()
def status():
    """Show the current status of the queue
    
    Example: queuectl status
    """
    jobs = load_jobs()
    dlq = load_dlq()
    config = load_config()
    
    # Count jobs by state
    pending = sum(1 for job in jobs if job['state'] == 'pending')
    processing = sum(1 for job in jobs if job['state'] == 'processing')
    completed = sum(1 for job in jobs if job['state'] == 'completed')
    failed = sum(1 for job in jobs if job['state'] == 'failed')
    
    # Print the status
    click.echo("\n" + "="*50)
    click.echo("[*] QUEUE STATUS")
    click.echo("="*50)
    click.echo(f"Pending Jobs:     {pending}")
    click.echo(f"Processing Jobs:  {processing}")
    click.echo(f"Completed Jobs:   {completed}")
    click.echo(f"Failed Jobs:      {failed}")
    click.echo(f"Dead Letter Queue: {len(dlq)}")
    click.echo("-"*50)
    click.echo(f"Total Jobs:       {len(jobs)}")
    click.echo("="*50)
    click.echo(f"\n[CONFIG]")
    click.echo(f"  Max Retries:    {config.get('max_retries', 3)}")
    click.echo(f"  Backoff Base:   {config.get('backoff_base', 2)}")
    click.echo(f"  Worker Count:   {config.get('worker_count', 1)}")
    click.echo()


@cli.command()
@click.option('--state', default=None, help='Filter by state (pending, processing, completed, failed)')
def list(state):
    """List jobs with optional filtering
    
    Examples:
        queuectl list
        queuectl list --state pending
        queuectl list --state completed
    """
    jobs = load_jobs()
    
    # Filter by state if provided
    if state:
        jobs = [job for job in jobs if job['state'] == state]
    
    if not jobs:
        click.echo("[EMPTY] No jobs found!")
        return
    
    click.echo("\n" + "="*80)
    click.echo("[JOBS LIST]")
    click.echo("="*80)
    
    for idx, job in enumerate(jobs, 1):
        state_emoji = {
            'pending': '[WAIT]',
            'processing': '[RUN]',
            'completed': '[OK]',
            'failed': '[FAIL]',
            'dead': '[DLQ]'
        }.get(job['state'], '[?]')
        
        click.echo(f"\n{idx}. {state_emoji} {job['id']}")
        click.echo(f"   State:       {job['state']}")
        click.echo(f"   Command:     {job['command']}")
        click.echo(f"   Attempts:    {job['attempts']}/{job.get('max_retries', 3)}")
        click.echo(f"   Created:     {job.get('created_at', 'N/A')}")
    
    click.echo("\n" + "="*80 + "\n")


@cli.group()
def config():
    """Manage configuration settings
    
    Examples:
        queuectl config set max-retries 5
        queuectl config set backoff-base 3
        queuectl config show
    """
    pass


@config.command('set')
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    """Set a configuration value
    
    Available keys: max-retries, backoff-base, worker-count
    """
    config_data = load_config()
    
    # Convert key from kebab-case to snake_case
    key_map = {
        'max-retries': 'max_retries',
        'backoff-base': 'backoff_base',
        'worker-count': 'worker_count'
    }
    
    if key not in key_map:
        click.echo(f"❌ Error: Unknown config key '{key}'", err=True)
        click.echo("Available keys: max-retries, backoff-base, worker-count", err=True)
        return
    
    snake_key = key_map[key]
    
    try:
        # Convert value to integer
        int_value = int(value)
        config_data[snake_key] = int_value
        save_json(CONFIG_FILE, config_data)
        click.echo(f"✅ Config updated: {key} = {int_value}")
    except ValueError:
        click.echo(f"❌ Error: Value must be a number!", err=True)


@config.command('show')
def config_show():
    """Show current configuration"""
    config_data = load_config()
    
    click.echo("\n" + "="*50)
    click.echo("[CONFIG]")
    click.echo("="*50)
    click.echo(f"max-retries:    {config_data.get('max_retries', 3)}")
    click.echo(f"backoff-base:   {config_data.get('backoff_base', 2)}")
    click.echo(f"worker-count:   {config_data.get('worker_count', 1)}")
    click.echo("="*50 + "\n")


@cli.group()
def dlq():
    """Manage Dead Letter Queue (permanently failed jobs)
    
    Examples:
        queuectl dlq list
        queuectl dlq retry job1
        queuectl dlq clear
    """
    pass


@dlq.command('list')
def dlq_list():
    """Show all jobs in the Dead Letter Queue"""
    dead_jobs = load_dlq()
    
    if not dead_jobs:
        click.echo("✅ Dead Letter Queue is empty!")
        return
    
    click.echo("\n" + "="*80)
    click.echo("☠️  DEAD LETTER QUEUE")
    click.echo("="*80)
    
    for idx, job in enumerate(dead_jobs, 1):
        click.echo(f"\n{idx}. {job['id']}")
        click.echo(f"   Command:     {job['command']}")
        click.echo(f"   Attempts:    {job['attempts']}")
        click.echo(f"   Reason:      Failed after max retries")
        click.echo(f"   Created:     {job.get('created_at', 'N/A')}")
    
    click.echo("\n" + "="*80 + "\n")


@dlq.command('retry')
@click.argument('job_id')
def dlq_retry(job_id):
    """Retry a job from the Dead Letter Queue
    
    Example: queuectl dlq retry job1
    """
    dead_jobs = load_dlq()
    jobs = load_jobs()
    
    # Find the job in DLQ
    job_to_retry = None
    for job in dead_jobs:
        if job['id'] == job_id:
            job_to_retry = job
            break
    
    if not job_to_retry:
        click.echo(f"❌ Job '{job_id}' not found in Dead Letter Queue!", err=True)
        return
    
    # Reset the job for retry
    job_to_retry['state'] = 'pending'
    job_to_retry['attempts'] = 0
    job_to_retry['updated_at'] = get_current_timestamp()
    
    # Add back to jobs queue
    jobs.append(job_to_retry)
    
    # Remove from DLQ
    dead_jobs = [j for j in dead_jobs if j['id'] != job_id]
    
    # Save changes
    save_jobs(jobs)
    save_dlq(dead_jobs)
    
    click.echo(f"✅ Job '{job_id}' moved back to queue for retry!")


@dlq.command('clear')
def dlq_clear():
    """Clear all jobs from the Dead Letter Queue"""
    if click.confirm('⚠️  Are you sure you want to clear the DLQ?'):
        save_dlq([])
        click.echo("✅ Dead Letter Queue cleared!")
    else:
        click.echo("Cancelled.")


# ============================================================================
# WORKER LOGIC - The actual job execution engine
# ============================================================================

def calculate_backoff_delay(attempts, backoff_base):
    """Calculate exponential backoff delay
    
    Formula: delay = backoff_base ^ attempts
    Example: 2^0=1, 2^1=2, 2^2=4, 2^3=8
    """
    return backoff_base ** attempts


def process_job(job, config):
    """Execute a single job and handle the result
    
    Returns: True if job should continue processing, False if done
    """
    job_id = job['id']
    command = job['command']
    
    click.echo("[WORKER] Processing job: " + job_id)
    click.echo("         Command: " + command)
    
    try:
        # Run the command and capture exit code
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        
        if result.returncode == 0:
            # SUCCESS! Job is done
            job['state'] = 'completed'
            job['updated_at'] = get_current_timestamp()
            click.echo("[OK] Job " + job_id + " completed successfully!")
            return True
        else:
            # FAILED - Check if we should retry
            job['attempts'] += 1
            
            if job['attempts'] >= job.get('max_retries', 3):
                # Move to DLQ
                job['state'] = 'dead'
                job['updated_at'] = get_current_timestamp()
                click.echo("[DLQ] Job " + job_id + " moved to DLQ (max retries reached)")
                return True
            else:
                # Schedule for retry
                job['state'] = 'failed'
                job['updated_at'] = get_current_timestamp()
                backoff = calculate_backoff_delay(job['attempts'], config.get('backoff_base', 2))
                click.echo("[RETRY] Job " + job_id + " failed. Retry in " + str(backoff) + " seconds...")
                return True
    
    except subprocess.TimeoutExpired:
        # Command took too long
        job['attempts'] += 1
        
        if job['attempts'] >= job.get('max_retries', 3):
            job['state'] = 'dead'
            click.echo("[DLQ] Job " + job_id + " moved to DLQ (timeout + max retries)")
            return True
        else:
            job['state'] = 'failed'
            click.echo("[RETRY] Job " + job_id + " timed out. Will retry...")
            return True
    
    except Exception as e:
        click.echo("[ERROR] Error running job " + job_id + ": " + str(e))
        job['attempts'] += 1
        
        if job['attempts'] >= job.get('max_retries', 3):
            job['state'] = 'dead'
            return True
        else:
            job['state'] = 'failed'
            return True


def move_dead_jobs(jobs):
    """Move jobs with state 'dead' to the DLQ"""
    dlq = load_dlq()
    alive_jobs = []
    
    for job in jobs:
        if job['state'] == 'dead':
            dlq.append(job)
        else:
            alive_jobs.append(job)
    
    save_dlq(dlq)
    return alive_jobs


def process_failed_jobs(jobs, config):
    """Check if failed jobs are ready to retry (backoff expired)"""
    current_time = time.time()
    
    for job in jobs:
        if job['state'] == 'failed':
            # Calculate when this job should be retried
            created_time = time.time()  # Simplified - in production would parse timestamp
            backoff = calculate_backoff_delay(job['attempts'], config.get('backoff_base', 2))
            
            # For now, always ready to retry (simplified)
            job['state'] = 'pending'
    
    return jobs


@cli.group()
def worker():
    """Manage worker processes
    
    Examples:
        queuectl worker start --count 2
        queuectl worker stop
    """
    pass


@worker.command('start')
@click.option('--count', default=1, help='Number of workers to start')
def worker_start(count):
    """Start worker process(es) to execute jobs
    
    Example: queuectl worker start --count 3
    """
    config = load_config()
    click.echo("[START] Starting " + str(count) + " worker(s)...")
    click.echo("Press Ctrl+C to stop gracefully\n")
    
    try:
        while True:
            jobs = load_jobs()
            
            # Get pending jobs
            pending_jobs = [j for j in jobs if j['state'] == 'pending']
            
            if not pending_jobs:
                click.echo("[WAIT] No pending jobs. Waiting...")
                time.sleep(2)
                continue
            
            # Process pending jobs
            for job in pending_jobs[:count]:
                job['state'] = 'processing'
                process_job(job, config)
            
            # Save updated jobs and move dead ones
            save_jobs(jobs)
            jobs = load_jobs()
            jobs = move_dead_jobs(jobs)
            save_jobs(jobs)
            
            # Small delay between cycles
            time.sleep(1)
    
    except KeyboardInterrupt:
        click.echo("\n\n[SHUTDOWN] Shutting down workers gracefully...")
        click.echo("[OK] Workers stopped!")


if __name__ == '__main__':
    cli()
