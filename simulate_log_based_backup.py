from faker import Faker
import mysql.connector
import subprocess
import os
import time
import psutil
import csv

# --- Config ---
DB_NAME = 'testdb'
DB_USER = 'testuser'
DB_PASS = 'testpass'
FULL_BACKUP_FILE = 'full_backup.sql'
BINLOG_DIR = '/var/log/mysql'
NUM_INITIAL_RECORDS = 400000
NUM_INCREMENTAL_BATCHES = 10
RECORDS_PER_BATCH = 10000
BACKUP_CSV = 'log_based_backup_log.csv'
RESTORE_CSV = 'log_based_restore_log.csv'

fake = Faker()

# --- CSV Setup ---
with open(BACKUP_CSV, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['batch', 'type', 'File Name', 'backup_size_MB', 'backup_time_s'])

with open(RESTORE_CSV, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Step', 'File Name', 'restore_time_s', 'cpu_before', 'cpu_after'])

# --- Function: Connect to DB ---
def get_conn(use_db=True):
    return mysql.connector.connect(
        host='localhost',
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME if use_db else None
    )

# --- Function: Get DB Size ---
def get_db_size():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2)
        FROM information_schema.tables
        WHERE table_schema = %s
    """, (DB_NAME,))
    size_mb = cursor.fetchone()[0]
    conn.close()
    return size_mb

# --- Step 1: Setup DB ---
conn = get_conn()
cursor = conn.cursor()
print("[*] Dropping table if exists...")
cursor.execute("DROP TABLE IF EXISTS customers")
print(f"[*] Creating table and inserting {NUM_INITIAL_RECORDS} records...")
cursor.execute("""
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    address TEXT
)
""")

for _ in range(NUM_INITIAL_RECORDS):
    name = fake.name()
    email = fake.email()
    address = fake.address().replace("\n", " ")
    cursor.execute("INSERT INTO customers (name, email, address) VALUES (%s, %s, %s)", (name, email, address))

conn.commit()
conn.close()
print("[✔] Initial data inserted.")

# --- Step 2: Full Backup ---
db_size = get_db_size()
print(f"[i] Database size before full backup: {db_size} MB")
print("[*] Performing full backup...")
start_time = time.time()
subprocess.run([
    "mysqldump", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME
], stdout=open(FULL_BACKUP_FILE, "w"))
backup_duration = round(time.time() - start_time, 2)
backup_size = round(os.path.getsize(FULL_BACKUP_FILE) / 1024 / 1024, 2)
print(f"[✔] Full backup completed in {backup_duration}s, size: {backup_size} MB")

# Log full backup
with open(BACKUP_CSV, 'a', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([0, 'Full', FULL_BACKUP_FILE, backup_size, backup_duration])

# --- Step 3: Insert Incremental Data + Log-Based Backup ---
binlogs = []
conn = get_conn()
cursor = conn.cursor()
cursor.execute("SHOW MASTER STATUS")
current_binlog_file, current_position = cursor.fetchone()[0:2]
conn.close()

for batch in range(1, NUM_INCREMENTAL_BATCHES + 1):
    print(f"[*] Inserting batch {batch} of {NUM_INCREMENTAL_BATCHES}...")

    conn = get_conn()
    cursor = conn.cursor()
    for _ in range(RECORDS_PER_BATCH):
        name = fake.name()
        email = fake.email()
        address = fake.address().replace("\n", " ")
        cursor.execute("INSERT INTO customers (name, email, address) VALUES (%s, %s, %s)", (name, email, address))
    conn.commit()

    # Get current binlog info AFTER batch insert
    cursor.execute("SHOW MASTER STATUS")
    binlog_file_after, end_position = cursor.fetchone()[0:2]
    conn.close()

    if binlog_file_after != current_binlog_file:
        print(f"[!] Binlog file rotated from {current_binlog_file} to {binlog_file_after}. This script assumes no rotation.")
        break

    binlog_output = f"logbackup_batch{batch}.sql"
    binlogs.append(binlog_output)

    binlog_path = os.path.join(BINLOG_DIR, current_binlog_file)

    print(f"[*] Extracting log-based incremental backup from position {current_position} to {end_position}...")
    start_inc_time = time.time()
    subprocess.run([
        "mysqlbinlog",
        f"--start-position={current_position}",
        f"--stop-position={end_position}",
        binlog_path
    ], stdout=open(binlog_output, "w"))
    inc_duration = round(time.time() - start_inc_time, 2)
    inc_size = round(os.path.getsize(binlog_output) / 1024 / 1024, 2)
    print(f"[✔] Log-based backup {batch} saved: {binlog_output} (Time: {inc_duration}s, Size: {inc_size} MB)")

    # Log incremental backup
    with open(BACKUP_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([batch, 'Log-Based', binlog_output, inc_size, inc_duration])

    current_position = end_position

# --- Step 4: Drop and Recreate DB ---
print("[!] Dropping and recreating database...")
conn = get_conn(use_db=False)
cursor = conn.cursor()
cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
cursor.execute(f"CREATE DATABASE {DB_NAME}")
conn.commit()
conn.close()
print("[✔] Database reset complete.")

# --- Step 5: Restore Full Backup ---
print("[*] Restoring full backup...")
cpu_before = psutil.cpu_percent(interval=1)
start_time = time.time()
subprocess.run([
    "mysql", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME
], stdin=open(FULL_BACKUP_FILE, "r"))
restore_duration = round(time.time() - start_time, 2)
cpu_after = psutil.cpu_percent(interval=1)
print(f"[✔] Full restore completed in {restore_duration}s")
print(f"[i] CPU load during restore (approx): from {cpu_before}% to {cpu_after}%")

# Log restore
with open(RESTORE_CSV, 'a', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Full Restore', FULL_BACKUP_FILE, restore_duration, cpu_before, cpu_after])

# --- Step 6: Apply Log-Based Incremental Backups ---
for i, binlog_file in enumerate(binlogs, 1):
    print(f"[*] Applying log-based incremental backup {i} ({binlog_file})...")
    cpu_before = psutil.cpu_percent(interval=1)
    start_time = time.time()
    subprocess.run([
        "mysql", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME
    ], stdin=open(binlog_file, "r"))
    duration = round(time.time() - start_time, 2)
    cpu_after = psutil.cpu_percent(interval=1)
    print(f"[✔] Applied {binlog_file} in {duration}s")
    print(f"[i] CPU load during restore (approx): from {cpu_before}% to {cpu_after}%")

    with open(RESTORE_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([f"Log-Based Restore {i}", binlog_file, duration, cpu_before, cpu_after])

# --- Step 7: Verify Data ---
print("[*] Verifying final row count...")
conn = get_conn()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM customers")
row_count = cursor.fetchone()[0]
conn.close()
print(f"[✔] Final row count after full + incremental restore: {row_count}")

