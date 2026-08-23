import os
from supabase import create_client, Client

try:
    import streamlit as st
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "[https://nqindgywshroejrcxtky.supabase.co](https://nqindgywshroejrcxtky.supabase.co)")
    SUPABASE_SERVICE_KEY = st.secrets.get("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xaW5kZ3l3c2hyb2VqcmN4dGt5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjgxNTExMCwiZXhwIjoyMTAyMzkxMTEwfQ.g-jpUzajE_OxGNNjF2QCFZINWjRfGSPCSHR2rtOtUTE")
except Exception:
    SUPABASE_URL = os.getenv("SUPABASE_URL", "[https://nqindgywshroejrcxtky.supabase.co](https://nqindgywshroejrcxtky.supabase.co)")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xaW5kZ3l3c2hyb2VqcmN4dGt5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjgxNTExMCwiZXhwIjoyMTAyMzkxMTEwfQ.g-jpUzajE_OxGNNjF2QCFZINWjRfGSPCSHR2rtOtUTE")

class DatabaseManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return cls._instance

    def get_client(self) -> Client:
        return self.client

db_manager = DatabaseManager()
supabase = db_manager.get_client()
