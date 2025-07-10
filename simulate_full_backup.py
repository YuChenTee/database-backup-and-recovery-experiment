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
BACKUP_FILE = 'backup.sql'
NUM_RECORDS = 500000

# --- Setup Faker and DB ---
fake = Faker()

# --- Step 1: Connect and prepare database ---
conn = mysql.connector.connect(
    host='localhost',
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME
)
cursor = conn.cursor()

print("[*] Dropping table if exists...")
cursor.execute("DROP TABLE IF EXISTS customers")

print(f"[*] Creating table and inserting {NUM_RECORDS} records...")
cursor.execute("""
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    address TEXT
)
""")

for _ in range(NUM_RECORDS):
    name = fake.name()
    email = fake.email()
    address = fake.address().replace("\n", " ")
    cursor.execute("INSERT INTO customers (name, email, address) VALUES (%s, %s, %s)", (name, email, address))

conn.commit()
conn.close()
print("[✔] Data inserted.")

# --- Step 2: Measure database size ---
def get_db_size():
    conn = mysql.connector.connect(
        host='localhost', user=DB_USER, password=DB_PASS, database=DB_NAME
    )
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2)
        FROM information_schema.tables
        WHERE table_schema = %s
    """, (DB_NAME,))
    size_mb = cursor.fetchone()[0]
    conn.close()
    return size_mb

db_size = get_db_size()
print(f"[i] Database size: {db_size} MB")

# --- Step 3: Full backup using mysqldump ---
print("[*] Starting full backup...")
start_time = time.time()
subprocess.run([
    "mysqldump", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME
], stdout=open(BACKUP_FILE, "w"))
backup_duration = round(time.time() - start_time, 2)
backup_size = round(os.path.getsize(BACKUP_FILE) / 1024 / 1024, 2)
print(f"[✔] Backup complete in {backup_duration} seconds, size: {backup_size} MB")

# --- Step 4: Drop database ---
print("[!] Dropping database...")
conn = mysql.connector.connect(
    host='localhost', user=DB_USER, password=DB_PASS
)
cursor = conn.cursor()
cursor.execute(f"DROP DATABASE {DB_NAME}")
cursor.execute(f"CREATE DATABASE {DB_NAME}")
conn.commit()
conn.close()
print("[✔] Database dropped and recreated.")

# --- Step 5: Restore from backup ---
print("[*] Restoring from full backup...")
start_time = time.time()
# Get CPU usage before restore
cpu_before = psutil.cpu_percent(interval=1)
restore_proc = subprocess.run([
    "mysql", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME
], stdin=open(BACKUP_FILE, "r"))
restore_duration = round(time.time() - start_time, 2)
cpu_after = psutil.cpu_percent(interval=1)

print(f"[✔] Restore completed in {restore_duration} seconds.")
print(f"[i] CPU load during restore (approx): from {cpu_before}% to {cpu_after}%")

# --- Step 6: Verify recovered data ---
print("[*] Verifying recovered data...")
conn = mysql.connector.connect(
    host='localhost', user=DB_USER, password=DB_PASS, database=DB_NAME
)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM customers")
row_count = cursor.fetchone()[0]
conn.close()
print(f"[✔] Recovered {row_count} rows in 'customers' table.")

