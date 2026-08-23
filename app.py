import streamlit as st
from datetime import datetime
from core.ai_service import AIService
from services.inventory_service import InventoryService
from core.database import supabase
import os

st.set_page_config(page_title="المحاسب الذكي - نواة علي بابا", page_icon="🤖", layout="centered")

st.title("🤖 المحاسب الذكي - نواة علي بابا (v3.0 - التقسيط الذكي)")

API_KEYS_POOL = [
    "AQ.Ab8RN6KsmZlOVBitqBHl9MTKvhDTCrOkLckSZOLq5opLxEM97g",
    "AQ.Ab8RN6IOOQs421k9-f9CtpYl-b7mKWe1ID2e-VODE8WbGDLy0g",
    "AQ.Ab8RN6LDnxPObId4PxP_7RWvXtPSekj6ftHZ6AIwiVKyVQso5Q",
    "AQ.Ab8RN6IXSRGUETheaRkxa2JuolYCfGIL-888kwz8J9-OfWZ4Gw",
    "AQ.Ab8RN6K7vSSUfuhGYpcuwDBFOwwFa_F5lj-nsNeWulqimXRBFA",
    "AQ.Ab8RN6LTwEmXPjHD7K7HX_U8leyMSkkLOIwo7VNff3FLn3PKQA"
]

if "api_key_index" not in st.session_state: st.session_state.api_key_index = 0

def get_next_api_key():
    if not API_KEYS_POOL: return None
    current_key = API_KEYS_POOL[st.session_state.api_key_index]
    st.session_state.api_key_index = (st.session_state.api_key_index + 1) % len(API_KEYS_POOL)
    return current_key

def execute_with_key_rotation(user_input, branch, branch_rules, messages):
    attempts = len(API_KEYS_POOL)
    last_error = None
    for _ in range(attempts):
        active_key = get_next_api_key()
        if active_key:
            os.environ["GOOGLE_API_KEY"] = active_key
            os.environ["GEMINI_API_KEY"] = active_key
        try:
            return AIService.smart_process_command(user_input, branch, branch_rules, messages), None
        except Exception as e:
            last_error = str(e)
            if any(err_word in last_error.lower() for err_word in ["resourceexhausted", "quota", "429"]): continue
            else: break
    return None, last_error

branch = st.selectbox("📍 اختر الفرع:", ["الفرع الرئيسي (القاهرة)", "فرع الإسكندرية"])

if "current_branch" not in st.session_state or st.session_state.current_branch != branch:
    st.session_state.current_branch = branch
    try:
        rules_res = supabase.table("business_rules").select("*").eq("branch", branch).execute()
        st.session_state.branch_rules = rules_res.data if rules_res.data else []
    except Exception:
        st.session_state.branch_rules = []

main_tab, reports_tab = st.tabs(["💬 الدردشة والمساعد الذكي", "📊 التقارير والأقساط"])

with main_tab:
    if "messages" not in st.session_state: st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("سجل معاملتك (مثال: بعنا طقم كاوتش ميشلان لأحمد بـ 6000 دفع 2000 مقدم والباقي قسط 1000 شهرياً)"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("جاري التحليل السريع..."):
                parsed, error = execute_with_key_rotation(user_input, branch, st.session_state.branch_rules, st.session_state.messages)
                
                if error or not parsed:
                    response_text = f"⚠️ عذراً، حدث خطأ: {error}"
                else:
                    trans_type = parsed.get("type")
                    ai_message = parsed.get("message_to_user", "تم الاستلام.")

                    if trans_type in ["PURCHASE", "SALE"]:
                        success, msg = InventoryService.execute_transaction(branch, parsed, user_input)
                        response_text = f"{ai_message}\n\n*{msg}*"
                    else:
                        response_text = ai_message

                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})

with reports_tab:
    st.subheader("📊 لوحة التقارير والمتابعة")
    r_tab1, r_tab2, r_tab3, r_tab4 = st.tabs(["دفتر اليومية", "ميزان المراجعة", "رصيد المخازن", "💳 سجل الأقساط النشطة"])
    
    with r_tab1:
        st.markdown(f"### دفتر اليومية - {branch}")
        res = supabase.table("journal_entries").select("*").eq("branch_name", branch).execute()
        if res.data: st.dataframe(res.data, use_container_width=True)
        else: st.info("لا توجد قيود.")
        
    with r_tab2:
        st.info("نظام ميزان المراجعة قيد العمل.")

    with r_tab3:
        st.markdown(f"### المخازن - {branch}")
        inv_res = supabase.table("inventory").select("*").eq("branch", branch).execute()
        if inv_res.data: st.dataframe(inv_res.data, use_container_width=True)
        else: st.info("المخزن فارغ.")

    with r_tab4:
        st.markdown(f"### متابعة الأقساط - {branch}")
        inst_res = supabase.table("installments").select("*").eq("branch", branch).eq("status", "نشط").execute()
        if inst_res.data: 
            st.dataframe(inst_res.data, use_container_width=True)
        else: 
            st.success("لا توجد أقساط نشطة أو ديون معلقة في هذا الفرع.")
