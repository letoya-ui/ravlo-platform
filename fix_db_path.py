import os
import sqlite3

# Detect current working directory (where script is run)
project_root = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(project_root, "instance")
db_path = os.path.join(instance_dir, "loanmvp.db")

print("🔍 Checking database setup...")
print(f"📁 Project root: {project_root}")
print(f"📂 Instance folder: {instance_dir}")
print(f"🗄️ Database file: {db_path}")

# Step 1: Ensure instance folder exists
if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)
    print("✅ Created 'instance' folder.")

# Step 2: Ensure database file exists (create if missing)
if not os.path.exists(db_path):
    print("⚙️ Creating new SQLite database...")
    conn = sqlite3.connect(db_path)
    conn.close()
    print("✅ Database created successfully.")
else:
    print("✅ Database file already exists.")

# Step 3: Verify permissions
try:
    with open(db_path, "a"):
        pass
    print("✅ File permissions are OK.")
except PermissionError:
    print("❌ Permission denied: Please run as Administrator or move folder outside OneDrive (e.g., C:\\LoanMVP_Bundle).")

print("\nAll checks complete! You can now run:")
print("venv\\Scripts\\activate")
print("flask --app LoanMVP.app run")
