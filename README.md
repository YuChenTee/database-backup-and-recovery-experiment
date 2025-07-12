# 📦 MySQL Backup and Recovery Experiments

This project demonstrates three types of MySQL backup and recovery methods, using Python scripts to simulate database activity and measure backup/restore performance. It is intended for testing in a Linux VM (e.g., Ubuntu/Debian).

---

## 🔧 Prerequisites

Ensure the following are installed in your VM:

- Python 3.8+
- MySQL Server (with binlog enabled)
- `mysqldump` and `mysqlbinlog` tools
- pip packages (see `requirements.txt`):
  - `mysql-connector-python`
  - `faker`
  - `psutil`
  - `pandas`
  - `matplotlib`

---

## ✅ Install Dependencies

```bash
sudo apt update
sudo apt install mysql-server python3-pip
pip install -r requirements.txt
````

---

## ✅ Configure MySQL

Edit `/etc/mysql/mysql.conf.d/mysqld.cnf`:

```ini
[mysqld]
server-id         = 1
log_bin           = /var/log/mysql/mysql-bin.log
binlog_expire_logs_seconds = 2592000
max_binlog_size   = 100M
```

Restart MySQL:

```bash
sudo systemctl restart mysql
```

---

## ✅ Create MySQL User and Database

```sql
CREATE USER 'testuser'@'localhost' IDENTIFIED BY 'testpass';
CREATE DATABASE testdb;
GRANT ALL PRIVILEGES ON testdb.* TO 'testuser'@'localhost';
FLUSH PRIVILEGES;
```

---

## 📁 Script Overview

| Script                           | Backup Type                 | Description                                                                     |
| -------------------------------- | --------------------------- | ------------------------------------------------------------------------------- |
| `simulate_full_backup.py`        | Full backup                 | Creates and restores full backups after each batch. Only latest backup is kept. |
| `simulate_incremental_backup.py` | Incremental via binlog      | Uses `mysqlbinlog` to extract changes after each batch insert.                  |
| `simulate_log_based_backup.py`   | Log-based backup simulation | Captures and replays binlogs batch-by-batch to simulate point-in-time recovery. |
| `performance_comparison.py`      | Performance charting        | Plots bar charts comparing time and size across all three backup methods.       |

---

## 🚀 How to Run

### 1. Full Backup Only

```bash
python3 simulate_full_backup.py
```

* Inserts 400,000 records
* Performs full backup
* Adds 10 batches of 10,000 records
* Overwrites the full backup after each batch
* Drops and restores DB from the last full backup
* Logs data to `full_backup_log.csv`, `full_restore_log.csv`

### 2. Incremental Backup Using Binlog

```bash
python3 simulate_incremental_backup.py
```

* Inserts 400,000 records, performs full backup
* Adds 10 incremental batches
* Extracts binlog changes using `mysqlbinlog`
* Drops and restores DB from full + incremental backups
* Logs data to `incremental_backup_log.csv`, `incremental_restore_log.csv`

### 3. Log-Based Backup Simulation

```bash
python3 simulate_log_based_backup.py
```

* Inserts 400,000 initial records, performs full backup
* Adds 10 batches, extracts binlogs per batch
* Replays logs sequentially to simulate restore
* Logs data to `log_based_backup_log.csv`, `log_based_restore_log.csv`

---

## 📊 Plot Performance Charts

```bash
python3 performance_comparison.py
```

Generates and saves **bar charts** comparing:

* Backup time per batch
* Restore time per batch
* Backup file size per batch
* CPU usage after each restore step

Each chart is saved as a `.png` file (e.g., `backup_time_comparison.png`).

---

## 📂 Output Files

* `full_backup.sql` – Full backup dump
* `binlog_batchX.sql` – Incremental backup binlogs
* `logbackup_batchX.sql` – Log-based backups
* `*_backup_log.csv` – Backup time and size logs
* `*_restore_log.csv` – Restore time and CPU logs
* `*.png` – Performance comparison bar charts

---

## 🧪 Tips for Testing in a VM

* Allocate at least **2 GB RAM** and **2 CPUs**
* Use `time` to benchmark execution time
* Monitor MySQL logs:

```bash
sudo tail -f /var/log/mysql/error.log
```

* Clear MySQL binlogs if needed:

```sql
RESET MASTER;
```

---

## 📜 License

This project is intended for educational and experimental use. Feel free to adapt it for your own testing and analysis.

