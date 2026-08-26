import os
from supabase import create_client, Client

try:
    import streamlit as st
except ImportError:
    st = None

# جلب بيانات الاتصال من أسرار البيئة بأمان تام وعدم الكشف عنها كودياً
SUPABASE_URL = ""
SUPABASE_SERVICE_KEY = ""

if st and hasattr(st, "secrets") and "SUPABASE_URL" in st.secrets:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
if st and hasattr(st, "secrets") and "SUPABASE_SERVICE_KEY" in st.secrets:
    SUPABASE_SERVICE_KEY = st.secrets["SUPABASE_SERVICE_KEY"].strip()

if not SUPABASE_URL:
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
if not SUPABASE_SERVICE_KEY:
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()


# 1. دالة مساعدة لإنشاء الاتصال (سيتم تخزينها في الكاش)
def _init_supabase_connection() -> Client:
    if not SUPABASE_URL or not SUPABASE_URL.startswith("http"):
        raise ValueError(f"رابط Supabase غير صالح: '{SUPABASE_URL}'")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# 2. تطبيق كاش Streamlit بشكل آمن (يعمل حتى لو تم تشغيل الكود كسكربت بايثون عادي)
if st:
    get_cached_supabase = st.cache_resource(_init_supabase_connection)
else:
    get_cached_supabase = _init_supabase_connection


class DatabaseManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            # 3. استخدام الاتصال المكيش (Cached) بدلاً من فتح اتصال جديد مع كل ريفرش للصفحة
            cls._instance.client: Client = get_cached_supabase()
        return cls._instance

    def get_client(self) -> Client:
        return self.client

    def ensure_default_enterprise_setup(self, branch_name: str):
        try:
            client = self.get_client()
            comp_res = client.table("companies").select("id").limit(1).execute()
            if comp_res.data: 
                company_id = comp_res.data[0]["id"]
            else: 
                company_id = client.table("companies").insert({"name": "الشركة الافتراضية"}).execute().data[0]["id"]
                
            branch_res = client.table("branches").select("id").eq("branch_name", branch_name).execute()
            if branch_res.data: 
                branch_id = branch_res.data[0]["id"]
            else: 
                branch_data = {
                    "company_id": company_id, 
                    "branch_name": branch_name, 
                    "is_main_branch": True if "الرئيسي" in branch_name else False
                }
                branch_id = client.table("branches").insert(branch_data).execute().data[0]["id"]
            return company_id, branch_id
        except Exception as e:
            print(f"DB Setup error: {e}")
            return None, None

# إنشاء نسخة واحدة للمدير وتجهيز الاتصال
db_manager = DatabaseManager()
supabase = db_manager.get_client()

# 4. إضافة هذه الدالة لتتوافق مع استدعاءات ملفات الـ (Services)
def get_supabase_client() -> Client:
    """إرجاع كائن الاتصال بقاعدة البيانات ليكون متوافقاً مع الاستدعاءات الخارجية."""
    return db_manager.get_client()
