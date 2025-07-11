# 📦 MySQL Backup and Recovery Experiments

This project demonstrates three types of MySQL backup and recovery methods, using Python scripts to simulate database activity and measure backup/restore performance. It is intended for testing in a Linux VM (e.g., Ubuntu/Debian).

## 🔧 Prerequisites

Ensure the following are installed in your VM:

* Python 3.8+
* MySQL Server (with binlog enabled)
* `mysqldump` and `mysqlbinlog` tools
* `pip` packages: `mysql-connector-python`, `faker`, `psutil`

### ✅ Install dependencies

```bash
sudo apt update
sudo apt install mysql-server python3-pip
pip install faker mysql-connector-python psutil
```

### ✅ Configure MySQL

Edit `/etc/mysql/mysql.conf.d/mysqld.cnf`:

```ini
[mysqld]
server-id         = 1
log_bin           = /var/log/mysql/mysql-bin.log
binlog_expire_logs_seconds      = 2592000
max_binlog_size   = 100M
```

Then restart MySQL:

```bash
sudo systemctl restart mysql
```

### ✅ Create MySQL User and Database

```sql
CREATE USER 'testuser'@'localhost' IDENTIFIED BY 'testpass';
CREATE DATABASE testdb;
GRANT ALL PRIVILEGES ON testdb.* TO 'testuser'@'localhost';
FLUSH PRIVILEGES;
```

---

## 📁 Script Overview

| Script Name                    | Backup Type                 | Description                                                                     |
| ------------------------------ | --------------------------- | ------------------------------------------------------------------------------- |
| `simulate_full_backup.py`               | Full backup only            | Creates and restores full backups after each batch. Only latest backup is kept. |
| `simulate_incremental_backup.py` | Incremental via binlog      | Uses `mysqlbinlog` to back up data in chunks after each insertion batch.        |
| `simulate_log_based_backup.py`          | Log-based backup simulation | Demonstrates continuous binlog capture and replay simulation.                   |

---

## 🚀 How to Run

### 1. Full Backup Only

```bash
python3 simulate_full_backup.py
```

* Inserts **400,000 records**
* Performs a full backup
* Inserts **10 batches of 10,000 records**, creating a **new full backup each time (overwrite)**
* Drops and restores the DB from the **last backup**
* Prints final row count (should be 500,000)

---

### 2. Incremental Backup Using Binlog

```bash
python3 simulate_incremental_backup.py
```

* Inserts **400,000 initial records**, performs full backup
* Inserts **10 incremental batches of 10,000**
* Extracts binlog after each batch using `mysqlbinlog`
* Drops and restores the DB from full + incremental backups
* Final row count: **500,000**

---

### 3. Log-Based Backup Simulation

```bash
python3 simulate_log_based_backup.py
```

* Enables binlog capture at startup
* Inserts **400,000 initial records**, performs full backup
* Inserts **10 incremental batches of 10,000**
* Replays logs during recovery to simulate point-in-time restore
* Final row count: **500,000**

> ⚠️ Ensure binlog path and permissions are correct (default: `/var/log/mysql/mysql-bin.*`).

---

## 📂 Output Files

* `full_backup.sql` – latest full dump
* `binlog_batchX.sql` – individual binlog chunks per batch (for incremental backup)
* `logbackup_batchX.sql` – log-based backup per batch (for log-based backup)
* Timing, CPU, and size metrics printed on console

---

## 🧪 Tips for Testing in a VM

* Allocate at least **2 GB RAM** and **2 CPUs** for faster testing.
* Run scripts using `time` to benchmark system-level performance.
* Monitor MySQL logs with: `sudo tail -f /var/log/mysql/error.log`
* Clear MySQL binlog files manually (if needed):

  ```sql
  RESET MASTER;
  ```

---

## 📜 License

This project is intended for educational and experimental use. Feel free to adapt it for your own testing.

---

Let me know if you'd like to split the README into per-script documentation or add performance plots/logging.
