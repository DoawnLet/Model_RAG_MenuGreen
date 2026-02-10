import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.core.supabase_client import get_supabase

def main():
    print("Verifying Supabase Connection...")
    try:
        client = get_supabase()
        print(f"Supabase URL: {client.supabase_url}")
        if not client.supabase_key or client.supabase_key == "your-anon-key":
             print("WARNING: Supabase Key is not set or is using the default placeholder.")
        else:
             print("Supabase Key is set.")
        
        # We can't easily ping without a table, but if we get here, imports and init are good.
        print("Supabase Client initialized successfully.")
        
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")

if __name__ == "__main__":
    main()
