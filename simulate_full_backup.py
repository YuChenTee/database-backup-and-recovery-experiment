from faker import Faker
import mysql.connector
import subprocess
import os
import time
import psutil

# --- Config ---
DB_NAME = 'testdb'
DB_USER = 'testuser'
DB_PASS = 'testpass'
INITIAL_RECORDS = 400000
INCREMENTAL_BATCHES = 10
RECORDS_PER_BATCH = 10000
BACKUP_FILE = 'full_backup.sql'

fake = Faker()

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
    size = cursor.fetchone()[0]
    conn.close()
    return size

# --- Full Backup (Overwrite) ---
def do_full_backup():
    print(f"[*] Creating full backup: {BACKUP_FILE}")
    start = time.time()
    subprocess.run([
        "mysqldump", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME
    ], stdout=open(BACKUP_FILE, "w"))
    duration = round(time.time() - start, 2)
    size = round(os.path.getsize(BACKUP_FILE) / 1024 / 1024, 2)
    print(f"[✔] Backup completed in {duration}s, size: {size} MB")
    return BACKUP_FILE

# --- Insert Dummy Records ---
def insert_fake_data(count):
    conn = get_conn()
    cursor = conn.cursor()
    for _ in range(count):
        name = fake.name()
        email = fake.email()
        address = fake.address().replace("\n", " ")
        cursor.execute("INSERT INTO customers (name, email, address) VALUES (%s, %s, %s)", (name, email, address))
    conn.commit()
    conn.close()

# --- Step 1: Create DB and Insert Initial Data ---
print("[*] Setting up initial database...")
conn = get_conn()
cursor = conn.cursor()
cursor.execute("DROP TABLE IF EXISTS customers")
cursor.execute("""
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    address TEXT
)
""")
conn.commit()
conn.close()

print(f"[*] Inserting {INITIAL_RECORDS} initial records...")
insert_fake_data(INITIAL_RECORDS)
print("[✔] Initial data inserted.")

# --- Step 2: Initial Full Backup ---
db_size = get_db_size()
print(f"[i] DB size before full backup: {db_size} MB")
latest_backup = do_full_backup()

# --- Step 3: Incremental Batches with Full Backup Overwrite ---
for batch in range(1, INCREMENTAL_BATCHES + 1):
    print(f"[*] Inserting batch {batch} ({RECORDS_PER_BATCH} records)...")
    insert_fake_data(RECORDS_PER_BATCH)
    latest_backup = do_full_backup()  # Overwrites previous backup

# --- Step 4: Simulate DB Drop ---
print("[!] Dropping and recreating database...")
conn = get_conn(use_db=False)
cursor = conn.cursor()
cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
cursor.execute(f"CREATE DATABASE {DB_NAME}")
conn.commit()
conn.close()
print("[✔] Database reset.")

# --- Step 5: Restore from Full Backup ---
print("[*] Restoring from backup...")
cpu_before = psutil.cpu_percent(interval=1)
start_time = time.time()
subprocess.run([
    "mysql", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME
], stdin=open(latest_backup, "r"))
restore_time = round(time.time() - start_time, 2)
cpu_after = psutil.cpu_percent(interval=1)

print(f"[✔] Restore completed in {restore_time}s")
print(f"[i] CPU load during restore (approx): from {cpu_before}% to {cpu_after}%")

# --- Step 6: Verify Final Row Count ---
print("[*] Verifying recovered data...")
conn = get_conn()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM customers")
row_count = cursor.fetchone()[0]
conn.close()
print(f"[✔] Final row count after restore: {row_count}")

