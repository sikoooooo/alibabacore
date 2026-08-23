import os
from supabase import create_client, Client

# وضع الرابط والمفتاح بشكل مباشر وثابت لضمان عدم حدوث خطأ Invalid URL
SUPABASE_URL = "https://nqindgywshroejrcxtky.supabase.co".strip()
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xaW5kZ3l3c2hyb2VqcmN4dGt5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjgxNTExMCwiZXhwIjoyMTAyMzkxMTEwfQ.g-jpUzajE_OxGNNjF2QCFZINWjRfGSPCSHR2rtOtUTE".strip()

class DatabaseManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            
            # التحقق السريع من صحة الرابط لمنع الانهيار
            if not SUPABASE_URL or not SUPABASE_URL.startswith("http"):
                raise ValueError(f"رابط Supabase غير صالح: '{SUPABASE_URL}'")
                
            cls._instance.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return cls._instance

    def get_client(self) -> Client:
        return self.client

# تهيئة الاتصال بقاعدة البيانات
db_manager = DatabaseManager()
supabase = db_manager.get_client()
