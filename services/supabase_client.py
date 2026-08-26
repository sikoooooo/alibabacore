import os
import streamlit as st
from supabase import create_client, Client
from typing import Optional

# استخدام الكاش لمنع فتح اتصال جديد مع كل تفاعل
@st.cache_resource
def get_supabase_client() -> Optional[Client]:
    """إرجاع كائن الاتصال بقاعدة البيانات بشكل آمن ومخزن مؤقتاً."""
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ بيانات الاتصال بقاعدة البيانات (URL/KEY) مفقودة.")
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        return None
