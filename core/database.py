import os
from supabase import create_client, Client

SUPABASE_URL = "https://nqindgywshroejrcxtky.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xaW5kZ3l3c2hyb2VqcmN4dGt5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjgxNTExMCwiZXhwIjoyMTAyMzkxMTEwfQ.g-jpUzajE_OxGNNjF2QCFZINWjRfGSPCSHR2rtOtUTE"

class DatabaseManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return cls._instance

    def get_client(self) -> Client:
        return self.client

    def ensure_default_enterprise_setup(self, branch_name: str):
        try:
            client = self.get_client()
            comp_res = client.table("companies").select("id").limit(1).execute()
            if comp_res.data: company_id = comp_res.data[0]["id"]
            else: company_id = client.table("companies").insert({"name": "الشركة الافتراضية"}).execute().data[0]["id"]
                
            branch_res = client.table("branches").select("id").eq("branch_name", branch_name).execute()
            if branch_res.data: branch_id = branch_res.data[0]["id"]
            else: branch_id = client.table("branches").insert({"company_id": company_id, "branch_name": branch_name, "is_main_branch": True if "الرئيسي" in branch_name else False}).execute().data[0]["id"]
            return company_id, branch_id
        except Exception as e:
            print(f"DB Setup error: {e}")
            return None, None

db_manager = DatabaseManager()
supabase = db_manager.get_client()
