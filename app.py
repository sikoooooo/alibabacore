import streamlit as st
from datetime import datetime
from core.ai_service import AIService
from services.inventory_service import InventoryService
from core.database import supabase

st.set_page_config(page_title="المحاسب الذكي - نواة علي بابا", page_icon="🤖", layout="centered")

st.title("🤖 المحاسب الذكي - نواة علي بابا (v2.3)")

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
            with st.spinner("جاري تحليل الطلب..."):
                parsed = AIService.smart_process_command(user_input, branch, st.session_state.messages)
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
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        
                        if "بيع" in text_lower or "مبيعات" in text_lower:
                            # استعلام إجمالي المبيعات
                            trans_res = supabase.table("transactions").select("total_amount").eq("branch", branch).eq("type", "SALE").execute()
                            if trans_res.data:
                                total_sales = sum(float(t.get("total_amount", 0)) for t in trans_res.data)
                                response_text = f"💰 إجمالي المبيعات المسجلة في {branch} هو: **{total_sales:,.2f} ج.م**"
                            else:
                                response_text = f"📂 لا توجد مبيعات مسجلة في {branch} حتى الآن."
                                
                        elif "شراء" in text_lower or "مشتريات" in text_lower:
                            # استعلام إجمالي المشتريات
                            trans_res = supabase.table("transactions").select("total_amount").eq("branch", branch).eq("type", "PURCHASE").execute()
                            if trans_res.data:
                                total_purchases = sum(float(t.get("total_amount", 0)) for t in trans_res.data)
                                response_text = f"🛒 إجمالي المشتريات المسجلة في {branch} هو: **{total_purchases:,.2f} ج.م**"
                            else:
                                response_text = f"📂 لا توجد مشتريات مسجلة في {branch} حتى الآن."
                                
                        elif "متوسط" in text_lower or "سعر" in text_lower:
                            # استعلام متوسط سعر صنف معين
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
                            # استعلام أرصدة المخزن للأصناف بالوحدة الفعلية
                            inv_query = supabase.table("inventory").select("*").eq("branch", branch)
                            if item_name and item_name != "غير محدد" and item_name != "عام":
                                inv_query = inv_query.ilike("item_name", f"%{item_name}%")
                            
                            inv_res = inv_query.execute()
                            if inv_res.data:
                                if item_name and item_name != "غير محدد" and item_name != "عام":
                                    matched_item = inv_res.data[0]
                                    qty = matched_item['total_base_quantity']
                                    # عرض الوحدة بذكاء بناءً على الكمية أو الصنف (بدون كلمة وحدة جامدة)
                                    unit_label = "طن" if "طن" in user_input or qty >= 10 else "وحدة"
                                    response_text = f"📦 رصيد **{matched_item['item_name']}** في {branch} هو: **{qty} {unit_label}** (متوسط التكلفة: {matched_item.get('avg_cost_per_base', 0):,.2f} ج.م)"
                                else:
                                    items_summary = "\n".join([f"- **{i['item_name']}**: {i['total_base_quantity']} وحدة" for i in inv_res.data])
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
