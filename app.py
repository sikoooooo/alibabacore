import streamlit as st
from datetime import datetime
import os

st.set_page_config(page_title="المحاسب الذكي - نواة علي بابا", page_icon="🤖", layout="centered")

st.title("🤖 المحاسب الذكي - نواة علي بابا (v3.0)")

# 1. الاستيراد الآمن للخدمات لمنع انهيار التطبيق إذا كان ملف مفقوداً
try:
    from core.ai_service import AIService
except ImportError:
    AIService = None

try:
    from services.inventory_service import InventoryService
except ImportError:
    InventoryService = None

try:
    from core.database import supabase
except ImportError:
    supabase = None

# سحب المفاتيح مباشرة من Streamlit Secrets بأمان تام
API_KEYS_POOL = []
if st and hasattr(st, "secrets") and st.secrets:
    for secret_key, val in st.secrets.items():
        if val and isinstance(val, str) and (val.startswith("AIza") or val.startswith("AQ.") or len(val) > 20):
            if val not in API_KEYS_POOL:
                API_KEYS_POOL.append(val)

if "api_key_index" not in st.session_state: 
    st.session_state.api_key_index = 0

def get_next_api_key():
    if not API_KEYS_POOL: return None
    current_key = API_KEYS_POOL[st.session_state.api_key_index % len(API_KEYS_POOL)]
    st.session_state.api_key_index = (st.session_state.api_key_index + 1) % len(API_KEYS_POOL)
    return current_key

def execute_with_key_rotation(user_input, branch, branch_rules, messages):
    if not AIService:
        return None, "خدمة الذكاء الاصطناعي غير متوفرة."
    
    attempts = max(len(API_KEYS_POOL), 1)
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
            if any(err_word in last_error.lower() for err_word in ["resourceexhausted", "quota", "429"]): 
                continue
            else: 
                break
    return None, last_error

# اختيار الفرع
branch = st.selectbox("📍 اختر الفرع:", ["الفرع الرئيسي (القاهرة)", "فرع الإسكندرية"])

# 2. تحميل قواعد الفرع بطريقة آمنة لا تسبب تعليق التطبيق
if "current_branch" not in st.session_state or st.session_state.current_branch != branch:
    st.session_state.current_branch = branch
    st.session_state.branch_rules = []
    if supabase:
        try:
            rules_res = supabase.table("business_rules").select("*").eq("branch", branch).execute()
            if rules_res and rules_res.data:
                st.session_state.branch_rules = rules_res.data
        except Exception:
            pass

main_tab, reports_tab = st.tabs(["💬 الدردشة والمساعد الذكي", "📊 التقارير والأقساط"])

with main_tab:
    if "messages" not in st.session_state: 
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("سجل معاملتك أو اسأل عن الأقساط (مثال: قسط محمود الصاوي)"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"): 
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("جاري التحليل السريع..."):
                parsed, error = execute_with_key_rotation(user_input, branch, st.session_state.branch_rules, st.session_state.messages)
                
                if error or not parsed:
                    response_text = f"⚠️ عذراً، حدث خطأ: {error}"
                else:
                    trans_type = parsed.get("type")
                    ai_message = parsed.get("message_to_user", "تم الاستلام.")

                    # 1. إذا كانت عملية بيع أو شراء
                    if trans_type in ["PURCHASE", "SALE"] and InventoryService:
                        try:
                            success, msg = InventoryService.execute_transaction(branch, parsed, user_input)
                            if success:
                                response_text = f"{ai_message}\n\n✅ *{msg}*"
                            else:
                                response_text = f"{ai_message}\n\n❌ *فشل الحفظ: {msg}*"
                        except Exception as e:
                            response_text = f"{ai_message}\n\n⚠️ *خطأ في التنفيذ: {str(e)}*"
                    
                    # 2. إذا كان سؤالاً أو استعلاماً عن الأقساط (مع عرض موعد القسط)
                    elif trans_type == "QUERY" and supabase:
                        customer_query = parsed.get("supplier", "").strip()
                        try:
                            q_builder = supabase.table("installments").select("*").eq("branch", branch)
                            if customer_query and customer_query != "غير محدد":
                                q_builder = q_builder.ilike("customer_name", f"%{customer_query}%")
                            
                            inst_results = q_builder.execute()
                            if inst_results.data:
                                response_text = f"📋 **نتائج البحث في الأقساط للفرع ({branch}):**\n\n"
                                for row in inst_results.data:
                                    due_date_val = row.get('due_date') or row.get('installment_date') or "غير محدد"
                                    response_text += f"- **العميل:** {row.get('customer_name')} | **الصنف:** {row.get('item_name')} | **المتبقي:** {row.get('remaining_amount')} ج.م | **قيمة القسط:** {row.get('installment_value')} ج.م | 📅 **موعد القسط:** {due_date_val} | **الحالة:** {row.get('status')}\n"
                            else:
                                response_text = f"🔍 لم يتم العثور على أقساط مطابقة في قاعدة البيانات بهذا الاسم ({customer_query})."
                        except Exception as ex:
                            response_text = f"⚠️ حدث خطأ أثناء الاستعلام من قاعدة البيانات: {str(ex)}"
                    
                    # 3. لأي حالة أخرى
                    else:
                        response_text = ai_message

                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})

with reports_tab:
    st.subheader("📊 لوحة التقارير والمتابعة")
    r_tab1, r_tab2, r_tab3, r_tab4 = st.tabs(["دفتر اليومية", "ميزان المراجعة", "رصيد المخازن", "💳 سجل الأقساط النشطة"])
    
    with r_tab1:
        st.markdown(f"### دفتر اليومية - {branch}")
        if supabase:
            try:
                res = supabase.table("journal_entries").select("*").eq("branch_name", branch).execute()
                if res.data: 
                    st.dataframe(res.data, use_container_width=True)
                else: 
                    st.info("لا توجد قيود.")
            except Exception:
                st.error("تعذر جلب قيود اليومية.")
        else:
            st.warning("قاعدة البيانات غير متصلة.")
        
    with r_tab2:
        st.info("نظام ميزان المراجعة قيد العمل.")

    with r_tab3:
        st.markdown(f"### المخازن - {branch}")
        if supabase:
            try:
                inv_res = supabase.table("inventory").select("*").eq("branch", branch).execute()
                if inv_res.data: 
                    st.dataframe(inv_res.data, use_container_width=True)
                else: 
                    st.info("المخزن فارغ.")
            except Exception:
                st.error("تعذر جلب بيانات المخزن.")

    with r_tab4:
        st.markdown(f"### متابعة الأقساط - {branch}")
        if supabase:
            try:
                inst_res = supabase.table("installments").select("*").eq("branch", branch).eq("status", "نشط").execute()
                if inst_res.data: 
                    st.dataframe(inst_res.data, use_container_width=True)
                else: 
                    st.success("لا توجد أقساط نشطة أو ديون معلقة في هذا الفرع.")
            except Exception:
                st.error("تعذر جلب الأقساط.")
