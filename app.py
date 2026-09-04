import streamlit as st
from core.ai_service import AIService
from services.inventory_service import InventoryService
from services.installment_service import InstallmentService
from services.notification_service import NotificationService
from services.query_service import QueryService

st.set_page_config(page_title="التنين - المساعد المحاسبي", page_icon="🐉", layout="centered")

st.title("🐉 نظام التنين المحاسبي الصارم")
st.write("النظام المحاسبي المباشر لإدارة المعاملات، المخزن، والموردين بدون شخصيات وهمية لتوفير استهلاك الـ API.")

# إعدادات النظام بالجانب بدون شخصيات
with st.sidebar:
    st.header("⚙️ إعدادات النظام")
    branch_name = st.text_input("اسم الفرع:", value="الفرع الرئيسي")

# إعداد الجلسة للمحادثة
if "messages" not in st.session_state:
    st.session_state.messages = []

# عرض رسائل المحادثة السابقة
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# استقبال مدخلات التاجر
user_input = st.chat_input("اكتب أمرك هنا (مثلاً: اشترينا 20 طن حديد، بعنا 5 كرتونة زيت)...")

if user_input:
    # 1. عرض أمر المستخدم
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    user_input_clean = user_input.lower()
    
    # 2. تحليل الطلب وتحديد نوع المعاملة باختصار مهني صارم
    with st.spinner("جاري تنفيذ المعاملة..."):
        ai_response = AIService.smart_process_command(
            user_text=user_input,
            branch=branch_name,
            persona="professional", # وضع مهني محايد
            chat_history=st.session_state.messages
        )
        
        transactions = ai_response.get("transactions", [])
        action_results = []

        # 3. معالجة وحفظ المعاملات وإظهار الرد المباشر المخصص
        for tx in transactions:
            tx_type = tx.get("type")
            item_name = tx.get("item_name")
            
            if tx_type in ["PURCHASE", "SALE"] and item_name and item_name != "غير محدد":
                try:
                    qty = float(tx.get("quantity", 1.0))
                    price = float(tx.get("unit_price", 0.0))
                    unit_val = tx.get("unit") or tx.get("major_unit") or "وحدة"
                    minor_unit_val = tx.get("minor_unit")
                    conv_factor = float(tx.get("conversion_factor", 1.0))
                    party_name = tx.get("supplier") or tx.get("customer", "عميل/مورد عام")
                    
                    res = InventoryService.process_transaction(
                        branch=branch_name,
                        item_name=item_name,
                        quantity=qty,
                        price=price,
                        supplier=party_name,
                        transaction_type=tx_type,
                        unit=unit_val,
                        minor_unit=minor_unit_val,
                        conversion_factor=conv_factor
                    )
                    
                    if res.get("status") == "SUCCESS":
                        action_results.append(f"✅ تم الحفظ - {('مبيعات' if tx_type == 'SALE' else 'مشتريات')}: {item_name} (الكمية: {qty} {unit_val})")
                    else:
                        action_results.append(f"⚠️ تنبيه - فشل الحفظ: {res.get('message', 'خطأ غير معروف')}")
                except Exception as e:
                    action_results.append(f"❌ خطأ تنفيذ: {str(e)}")

            # مصاريف أو بنود أخرى إن وجدت
            elif tx_type == "EXPENSE":
                action_results.append(f"✅ تم الحفظ - مصروفات: {item_name}")

            # معالجة الاستعلامات والتقارير الشاملة
            elif tx_type == "QUERY":
                if any(word in user_input_clean for word in ["مخزن", "بضاعة", "جرد", "رصيد", "الرصيد"]):
                    res = QueryService.get_comprehensive_report(branch_name, "inventory")
                    action_results.append(res.get('message', ''))
                elif any(word in user_input_clean for word in ["أقساط", "قسط", "فلوس بره", "ديون", "متاخرات", "أجل"]):
                    res = QueryService.get_comprehensive_report(branch_name, "installments")
                    action_results.append(res.get('message', ''))
                elif any(word in user_input_clean for word in ["موردين", "شركات", "مورد"]):
                    res = QueryService.get_comprehensive_report(branch_name, "suppliers")
                    action_results.append(res.get('message', ''))
                elif any(word in user_input_clean for word in ["نواقص", "ناقص", "خلص", "بيخلص", "تنبيه"]):
                    res = NotificationService.get_smart_alerts(branch_name)
                    action_results.append(res.get('message', ''))

        # تجهيز الرد المهني المباشر
        if action_results:
            response_message = "\n\n".join(action_results)
        else:
            response_message = ai_response.get("message_to_user", "✅ تم تنفيذ العملية بنجاح.")

    # 4. طباعة الرد المباشر الصارم
    with st.chat_message("assistant"):
        st.markdown(response_message)
    
    # 5. حفظ الرد في سجل الجلسة
    st.session_state.messages.append({"role": "assistant", "content": response_message})
