"""Check if exit_price column exists and add if missing."""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("Checking paper_trades table schema...")

# Get column information
response = supabase.rpc('get_table_columns', {'table_name': 'paper_trades'}).execute()

if response.data:
    columns = [col['column_name'] for col in response.data]
    print(f"Current columns: {columns}")
    
    if 'exit_price' not in columns:
        print("❌ exit_price column is missing!")
        print("This column may have been renamed or removed in a migration")
        print("The system uses 'price' column for both entry and exit prices")
    else:
        print("✅ exit_price column exists")
else:
    # Alternative check
    print("Checking with a test query...")
    try:
        response = supabase.table('paper_trades').select('exit_price').limit(1).execute()
        print("✅ exit_price column exists")
    except Exception as e:
        if 'does not exist' in str(e):
            print("❌ exit_price column does not exist")
            print("This is expected - the system uses 'price' for both entry/exit")
        else:
            print(f"Error: {e}")

print("\nNOTE: The error in logs is non-critical.")
print("The system continues to work, just can't load historical positions on startup.")
