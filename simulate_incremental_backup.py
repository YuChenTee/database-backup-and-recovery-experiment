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

# --- Log Files ---
BACKUP_LOG_CSV = 'incremental_backup_log.csv'      # Logs full + incremental
RESTORE_LOG_CSV = 'incremental_restore_log.csv'    # Logs restore performance

# --- CSV Headers ---
backup_headers = ['batch', 'type', 'records_inserted', 'backup_time_s', 'backup_size_MB']
restore_headers = ['phase', 'batch', 'restore_time_s', 'cpu_before', 'cpu_after']

fake = Faker()

# --- Utility: Log to CSV ---
def log_to_csv(file_path, data, headers):
    write_header = not os.path.exists(file_path)
    with open(file_path, mode='a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if write_header:
            writer.writeheader()
        writer.writerow(data)

# --- DB Connection ---
def get_conn(use_db=True):
    return mysql.connector.connect(
        host='localhost',
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME if use_db else None
    )

# --- DB Size ---
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
print("[*] Performing full backup...")
start_time = time.time()
subprocess.run([
    "mysqldump", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME
], stdout=open(FULL_BACKUP_FILE, "w"))
backup_duration = round(time.time() - start_time, 2)
backup_size = round(os.path.getsize(FULL_BACKUP_FILE) / 1024 / 1024, 2)
print(f"[✔] Full backup completed in {backup_duration}s, size: {backup_size} MB")

log_to_csv(BACKUP_LOG_CSV, {
    'batch': 0,
    'type': 'full',
    'records_inserted': NUM_INITIAL_RECORDS,
    'backup_time_s': backup_duration,
    'backup_size_MB': backup_size
}, backup_headers)

# --- Step 3: Insert Incremental Data + Binlog Backup ---
binlogs = []
total_inserted = NUM_INITIAL_RECORDS
for batch in range(1, NUM_INCREMENTAL_BATCHES + 1):
    print(f"[*] Flushing logs before batch {batch}...")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("FLUSH LOGS")
    cursor.execute("SHOW MASTER STATUS")
    log_file_before, log_pos = cursor.fetchone()[0:2]

    print(f"[*] Inserting batch {batch} of {NUM_INCREMENTAL_BATCHES}...")
    for _ in range(RECORDS_PER_BATCH):
        name = fake.name()
        email = fake.email()
        address = fake.address().replace("\n", " ")
        cursor.execute("INSERT INTO customers (name, email, address) VALUES (%s, %s, %s)", (name, email, address))
    conn.commit()

    binlog_path = os.path.join(BINLOG_DIR, log_file_before)
    binlog_output = f"binlog_batch{batch}.sql"
    binlogs.append(binlog_output)

    print(f"[*] Creating incremental backup from {log_file_before}...")
    start_inc_time = time.time()
    subprocess.run([
        "mysqlbinlog", binlog_path
    ], stdout=open(binlog_output, "w"))
    inc_duration = round(time.time() - start_inc_time, 2)
    inc_size = round(os.path.getsize(binlog_output) / 1024 / 1024, 2)
    print(f"[✔] Incremental backup {batch} saved: {binlog_output} (Time: {inc_duration}s, Size: {inc_size} MB)")

    total_inserted += RECORDS_PER_BATCH
    log_to_csv(BACKUP_LOG_CSV, {
        'batch': batch,
        'type': 'incremental',
        'records_inserted': total_inserted,
        'backup_time_s': inc_duration,
        'backup_size_MB': inc_size
    }, backup_headers)

    conn.close()

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

log_to_csv(RESTORE_LOG_CSV, {
    'phase': 'full',
    'batch': 0,
    'restore_time_s': restore_duration,
    'cpu_before': cpu_before,
    'cpu_after': cpu_after
}, restore_headers)

# --- Step 6: Apply Incremental Backups ---
for i, binlog_file in enumerate(binlogs, 1):
    print(f"[*] Applying incremental backup {i}...")
    cpu_before = psutil.cpu_percent(interval=1)
    start_time = time.time()
    subprocess.run([
        "mysql", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME
    ], stdin=open(binlog_file, "r"))
    duration = round(time.time() - start_time, 2)
    cpu_after = psutil.cpu_percent(interval=1)
    print(f"[✔] Applied {binlog_file} in {duration}s")
    print(f"[i] CPU load during restore (approx): from {cpu_before}% to {cpu_after}%")

    log_to_csv(RESTORE_LOG_CSV, {
        'phase': 'incremental',
        'batch': i,
        'restore_time_s': duration,
        'cpu_before': cpu_before,
        'cpu_after': cpu_after
    }, restore_headers)

# --- Step 7: Verify Data ---
print("[*] Verifying final row count...")
conn = get_conn()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM customers")
row_count = cursor.fetchone()[0]
conn.close()
print(f"[✔] Final row count after full + incremental restore: {row_count}")

