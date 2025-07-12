import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# --- Config: CSV paths ---
csv_files = {
    'Full': {
        'backup': 'full_backup_log.csv',
        'restore': 'full_restore_log.csv'
    },
    'Incremental': {
        'backup': 'incremental_backup_log.csv',
        'restore': 'incremental_restore_log.csv'
    },
    'Log-Based': {
        'backup': 'log_based_backup_log.csv',
        'restore': 'log_based_restore_log.csv'
    }
}

# --- Load and print CSVs ---
def load_csvs():
    data = {}
    for method, paths in csv_files.items():
        backup_df = pd.read_csv(paths['backup'])
        restore_df = pd.read_csv(paths['restore'])
        data[method] = {'backup': backup_df, 'restore': restore_df}
        
        print(f"\n=== {method} Backup Data ===")
        print(backup_df)
        print(f"\n=== {method} Restore Data ===")
        print(restore_df)
    return data

# --- Utility: Save plot ---
def save_plot(title):
    filename = f"{title.lower().replace(' ', '_')}.png"
    plt.tight_layout()
    plt.savefig(filename)
    print(f"[✔] Plot saved: {filename}")
    plt.close()

# --- Bar Chart: Backup Time ---
def plot_backup_time_bar(data):
    plt.figure(figsize=(12, 6))
    bar_width = 0.25
    batches = range(11)  # assuming 0 to 10
    offsets = {'Full': -bar_width, 'Incremental': 0, 'Log-Based': bar_width}
    colors = {'Full': '#1f77b4', 'Incremental': '#ff7f0e', 'Log-Based': '#2ca02c'}

    for method in data:
        df = data[method]['backup']
        if 'backup_time_s' in df.columns:
            x = df['batch']
            plt.bar(
                [b + offsets[method] for b in x],
                df['backup_time_s'],
                width=bar_width,
                label=f"{method} Backup",
                color=colors[method]
            )

    plt.title("Backup Time Comparison (Bar Chart)")
    plt.xlabel("Batch")
    plt.ylabel("Backup Time (s)")
    plt.xticks(batches)
    plt.legend()
    plt.grid(True, axis='y')
    save_plot("backup_time_comparison_bar")

# --- Bar Chart: Backup Size ---
def plot_backup_size_bar(data):
    plt.figure(figsize=(12, 6))
    bar_width = 0.25
    batches = range(11)
    offsets = {'Full': -bar_width, 'Incremental': 0, 'Log-Based': bar_width}
    colors = {'Full': '#1f77b4', 'Incremental': '#ff7f0e', 'Log-Based': '#2ca02c'}

    for method in data:
        df = data[method]['backup']
        if 'backup_size_MB' in df.columns:
            x = df['batch']
            plt.bar(
                [b + offsets[method] for b in x],
                df['backup_size_MB'],
                width=bar_width,
                label=f"{method} Backup Size",
                color=colors[method]
            )

    plt.title("Backup Size Comparison (Bar Chart)")
    plt.xlabel("Batch")
    plt.ylabel("Backup Size (MB)")
    plt.xticks(batches)
    plt.legend()
    plt.grid(True, axis='y')
    save_plot("backup_size_comparison_bar")

# --- Bar Chart: Restore Time ---
def plot_restore_time_bar(data):
    plt.figure(figsize=(10, 6))
    methods = []
    restore_times = []

    for method in data:
        df = data[method]['restore']
        if method == 'Incremental':
            time = df['restore_time_s'].sum()
        else:
            time = df['restore_time_s'].sum()
        methods.append(method)
        restore_times.append(time)

    plt.bar(methods, restore_times, color=['#1f77b4', '#ff7f0e', '#2ca02c'])
    plt.title("Total Restore Time by Method")
    plt.ylabel("Restore Time (s)")
    save_plot("restore_time_total_bar")

# --- Bar Chart: CPU After Restore ---
def plot_cpu_after_bar(data):
    plt.figure(figsize=(10, 6))
    methods = []
    cpu_usages = []

    for method in data:
        df = data[method]['restore']
        if 'cpu_after' in df.columns:
            avg_cpu = df['cpu_after'].mean()
            methods.append(method)
            cpu_usages.append(avg_cpu)

    plt.bar(methods, cpu_usages, color=['#1f77b4', '#ff7f0e', '#2ca02c'])
    plt.title("Average CPU Usage After Restore")
    plt.ylabel("CPU (%)")
    save_plot("cpu_after_restore_bar")

# --- Run ---
if __name__ == '__main__':
    all_data = load_csvs()
    plot_backup_time_bar(all_data)
    plot_backup_size_bar(all_data)
    plot_restore_time_bar(all_data)
    plot_cpu_after_bar(all_data)

