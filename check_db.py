import sqlite3

def display_all_table_data():
    # Connect to your SQLite database
    conn = sqlite3.connect('instance/carbonhero.db')
    cur = conn.cursor()

    # 1. Find all user-created tables in the database
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]

    print(f"--- 📊 FULL DATABASE DUMP: {len(tables)} TABLES FOUND ---\n")

    for table in tables:
        print(f"=== TABLE: {table.upper()} ===")
        
        # 2. Get the column names to use as headers
        cur.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cur.fetchall()]
        print(" | ".join(columns))
        print("-" * (len(" | ".join(columns))))

        # 3. Fetch all rows from the current table
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        
        if not rows:
            print("[Empty Table]")
        else:
            for row in rows:
                # Convert all values to string for easy joining
                print(" | ".join(map(str, row)))
        
        print("\n" + "="*40 + "\n")

    conn.close()

if __name__ == "__main__":
    display_all_table_data()
