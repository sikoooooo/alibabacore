import streamlit as st
from datetime import datetime
from core.ai_service import AIService
from services.inventory_service import InventoryService
from core.database import supabase
import os

st.set_page_config(page_title="المحاسب الذكي - نواة علي بابا", page_icon="🤖", layout="centered")

st.title("🤖 المحاسب الذكي - نواة علي بابا (v2.3)")

# 🔑 قائمة مفاتيح الـ API (المفاتيح الخاصة بك)
API_KEYS_POOL = [
    "AQ.Ab8RN6KsmZlOVBitqBHl9MTKvhDTCrOkLckSZOLq5opLxEM97g",
    "AQ.Ab8RN6IOOQs421k9-f9CtpYl-b7mKWe1ID2e-VODE8WbGDLy0g",
    "AQ.Ab8RN6LDnxPObId4PxP_7RWvXtPSekj6ftHZ6AIwiVKyVQso5Q",
    "AQ.Ab8RN6IXSRGUETheaRkxa2JuolYCfGIL-888kwz8J9-OfWZ4Gw",
    "AQ.Ab8RN6K7vSSUfuhGYpcuwDBFOwwFa_F5lj-nsNeWulqimXRBFA",
    "AQ.Ab8RN6LTwEmXPjHD7K7HX_U8leyMSkkLOIwo7VNff3FLn3PKQA"
]

# تهيئة مؤشر التبديل التلقائي في الـ session_state
if "api_key_index" not in st.session_state:
    st.session_state.api_key_index = 0

def get_next_api_key():
    """الحصول على المفتاح الحالي والتقدم للمفتاح التالي بالترتيب (Round-Robin)"""
    if not API_KEYS_POOL:
        return None
    current_key = API_KEYS_POOL[st.session_state.api_key_index]
    st.session_state.api_key_index = (st.session_state.api_key_index + 1) % len(API_KEYS_POOL)
    return current_key

def execute_with_key_rotation(user_input, branch, messages):
    """محاولة تنفيذ الطلب مع تجربة المفاتيح تباعاً في حال حدوث خطأ استنفاد الحصة"""
    attempts = len(API_KEYS_POOL)
    last_error = None
    
    for _ in range(attempts):
        active_key = get_next_api_key()
        if active_key:
            os.environ["GOOGLE_API_KEY"] = active_key
            os.environ["GEMINI_API_KEY"] = active_key
            
        try:
            return AIService.smart_process_command(user_input, branch, messages), None
        except Exception as e:
            last_error = str(e)
            if any(err_word in last_error.lower() for err_word in ["resourceexhausted", "quota", "429", "exhausted"]):
                continue
            else:
                break
                
    return None, last_error

# اختيار الفرع النشط
branch = st.selectbox("📍 اختر الفرع:", ["الفرع الرئيسي (القاهرة)", "فرع الإسكندرية"])

# فصل الواجهات: المحادثة الذكية مقابل التقارير المحاسبية
main_tab, reports_tab = st.tabs(["💬 الدردشة والمساعد الذكي", "📊 تقارير المحاسب القانوني وميزان المراجعة"])

with main_tab:
    # تهيئة الذاكرة القصيرة في الجلسة
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # عرض المحادثة السابقة
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # إدخال رسالة التاجر
    if user_input := st.chat_input("اكتب معاملتك أو استعلامك هنا (مثلاً: بيعنا بكام النهارده؟ / عندنا قد ايه مكرونة؟ / متوسط سعر البلح كام؟)..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("جاري تحليل الطلب (التبديل الذكي للمفاتيح)..."):
                parsed, error = execute_with_key_rotation(user_input, branch, st.session_state.messages)
                
                if error or not parsed:
                    response_text = f"⚠️ عذراً، حدث خطأ أو نفدت حصة جميع مفاتيح API المتاحة: {error}"
                else:
                    trans_type = parsed.get("type")
                    item_name = parsed.get("item_name", "غير محدد")
                    ai_message = parsed.get("message_to_user", "تم الاستلام.")

                    if trans_type in ["PURCHASE", "SALE"]:
                        success, msg = InventoryService.execute_transaction(branch, parsed, user_input)
                        response_text = f"{ai_message}\n\n*{msg}*"
                    
                    elif trans_type == "QUERY":
                        # 🔍 محرك الاستعلامات الذكي الشامل بلغة السوق
                        try:
                            text_lower = user_input.lower()
                            
                            if "بيع" in text_lower or "مبيعات" in text_lower:
                                trans_res = supabase.table("transactions").select("total_amount").eq("branch", branch).eq("type", "SALE").execute()
                                if trans_res.data:
                                    total_sales = sum(float(t.get("total_amount", 0)) for t in trans_res.data)
                                    response_text = f"💰 إجمالي المبيعات المسجلة في {branch} هو: **{total_sales:,.2f} ج.م**"
                                else:
                                    response_text = f"📂 لا توجد مبيعات مسجلة في {branch} حتى الآن."
                                    
                            elif "شراء" in text_lower or "مشتريات" in text_lower:
                                trans_res = supabase.table("transactions").select("total_amount").eq("branch", branch).eq("type", "PURCHASE").execute()
                                if trans_res.data:
                                    total_purchases = sum(float(t.get("total_amount", 0)) for t in trans_res.data)
                                    response_text = f"🛒 إجمالي المشتريات المسجلة في {branch} هو: **{total_purchases:,.2f} ج.م**"
                                else:
                                    response_text = f"📂 لا توجد مشتريات مسجلة في {branch} حتى الآن."
                                    
                            elif "متوسط" in text_lower or "سعر" in text_lower:
                                inv_query = supabase.table("inventory").select("*").eq("branch", branch)
                                if item_name and item_name != "غير محدد" and item_name != "عام":
                                    inv_query = inv_query.ilike("item_name", f"%{item_name}%")
                                inv_res = inv_query.execute()
                                
                                if inv_res.data:
                                    if item_name and item_name != "غير محدد" and item_name != "عام":
                                        item = inv_res.data[0]
                                        avg_price = float(item.get("avg_cost_per_base", 0))
                                        response_text = f"🏷️ متوسط سعر صنف **{item['item_name']}** في {branch} هو: **{avg_price:,.2f} ج.م**"
                                    else:
                                        prices_summary = "\n".join([f"- **{i['item_name']}**: متوسط التكلفة {i.get('avg_cost_per_base', 0):,.2f} ج.م" for i in inv_res.data])
                                        response_text = f"🏷️ **متوسط أسعار الأصناف في {branch}:**\n\n{prices_summary}"
                                else:
                                    response_text = f"📂 لا توجد بيانات أسعار مسجلة للصنف '{item_name}'."
                            else:
                                inv_query = supabase.table("inventory").select("*").eq("branch", branch)
                                if item_name and item_name != "غير محدد" and item_name != "عام":
                                    inv_query = inv_query.ilike("item_name", f"%{item_name}%")
                                
                                inv_res = inv_query.execute()
                                if inv_res.data:
                                    if item_name and item_name != "غير محدد" and item_name != "عام":
                                        matched_item = inv_res.data[0]
                                        qty_raw = matched_item['total_base_quantity']
                                        
                                        # استدعاء دالة التنسيق الذكية مع اسم الصنف لاستنباط الوحدة الصغرى (زجاجة، كيس، علبة...)
                                        formatted_stock = InventoryService.format_stock_display(matched_item['item_name'], qty_raw, units_per_carton=12)
                                        
                                        response_text = f"📦 رصيد **{matched_item['item_name']}** في {branch} هو: **{formatted_stock}** (متوسط التكلفة: {matched_item.get('avg_cost_per_base', 0):,.2f} ج.م)"
                                    else:
                                        items_summary = "\n".join([f"- **{i['item_name']}**: {InventoryService.format_stock_display(i['item_name'], i['total_base_quantity'], 12)}" for i in inv_res.data])
                                        response_text = f"📊 **ملخص مخزن {branch}:**\n\n{items_summary}"
                                else:
                                    response_text = f"📂 عذراً، لا توجد بيانات مسجلة للصنف '{item_name}' في {branch}."
                        except Exception as e:
                            response_text = f"عذراً، حدث خطأ أثناء الاستعلام: {e}"
                    
                    else:
                        response_text = ai_message

                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})

with reports_tab:
    st.subheader("📊 لوحة التقارير وميزان المراجعة (للمحاسب القانوني)")
    
    r_tab1, r_tab2, r_tab3 = st.tabs(["دفتر اليومية العام", "ميزان المراجعة", "رصيد المخازن الحالي"])
    
    with r_tab1:
        st.markdown(f"### دفتر اليومية - {branch}")
        try:
            res = supabase.table("journal_entries").select("*").eq("branch_name", branch).execute()
            if res.data:
                st.dataframe(res.data, use_container_width=True)
            else:
                st.info("لا توجد قيود مسجلة حتى الآن لهذا الفرع.")
        except Exception as e:
            st.error(f"خطأ في جلب دفتر اليومية: {e}")

    with r_tab2:
        st.markdown(f"### ميزان المراجعة المبدئي - {branch}")
        try:
            trans_res = supabase.table("transactions").select("total_amount, type").eq("branch", branch).execute()
            if trans_res.data:
                total_in = sum(float(t["total_amount"]) for t in trans_res.data if t["type"] == "PURCHASE")
                total_out = sum(float(t["total_amount"]) for t in trans_res.data if t["type"] == "SALE")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("إجمالي المشتريات (مدين)", f"{total_in:,.2f} ج.م")
                col2.metric("إجمالي المبيعات (دائن)", f"{total_out:,.2f} ج.م")
                col3.metric("صافي الحركة", f"{(total_out - total_in):,.2f} ج.م")
            else:
                st.info("لا توجد بيانات كافية لعرض ميزان المراجعة.")
        except Exception as e:
            st.error(f"خطأ في حساب ميزان المراجعة: {e}")

    with r_tab3:
        st.markdown(f"### أرصدة المخزن الفعلية - {branch}")
        try:
            inv_res = supabase.table("inventory").select("*").eq("branch", branch).execute()
            if inv_res.data:
                st.dataframe(inv_res.data, use_container_width=True)
            else:
                st.info("المخزن فارغ حالياً.")
        except Exception as e:
            st.error(f"خطأ في جلب المخزون: {e}")
