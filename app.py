import streamlit as st
from core.ai_service import AIService
from services.inventory_service import InventoryService
from services.installment_service import InstallmentService
from services.notification_service import NotificationService
from services.query_service import QueryService

st.set_page_config(page_title="التنين - المساعد المحاسبي", page_icon="🐉", layout="centered")

st.title("🐉 نظام التنين المحاسبي الصارم")
st.write("النظام المحاسبي المباشر لإدارة المعاملات، المخزن، والموردين بسرعة فائقة.")

# إعدادات النظام بالجانب
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
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    user_input_clean = user_input.lower()
    
    # 2. تحليل الطلب وتنفيذ المعاملة بسرعة
    with st.spinner("جاري التنفيذ الفوري..."):
        ai_response = AIService.smart_process_command(
            user_text=user_input,
            branch=branch_name,
            persona="professional",
            chat_history=st.session_state.messages
        )
        
        transactions = ai_response.get("transactions", [])
        action_results = []

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
                        action_results.append(f"⚠️ تنبيه: {res.get('message', 'خطأ بالحفظ')}")
                except Exception as e:
                    action_results.append(f"❌ خطأ: {str(e)}")

            elif tx_type == "EXPENSE":
                action_results.append(f"✅ تم الحفظ - مصروفات: {item_name}")

            elif tx_type == "QUERY":
                if "مخزن" in user_input_clean or "رصيد" in user_input_clean:
                    res = QueryService.get_comprehensive_report(branch_name, "inventory")
                    action_results.append(res.get('message', ''))
                elif "أقساط" in user_input_clean or "ديون" in user_input_clean:
                    res = QueryService.get_comprehensive_report(branch_name, "installments")
                    action_results.append(res.get('message', ''))
                elif "مورد" in user_input_clean:
                    res = QueryService.get_comprehensive_report(branch_name, "suppliers")
                    action_results.append(res.get('message', ''))
                elif "نواقص" in user_input_clean:
                    res = NotificationService.get_smart_alerts(branch_name)
                    action_results.append(res.get('message', ''))

        if action_results:
            response_message = "\n\n".join(action_results)
        else:
            response_message = ai_response.get("message_to_user", "✅ تم التنفيذ بنجاح.")

    with st.chat_message("assistant"):
        st.markdown(response_message)
    
    st.session_state.messages.append({"role": "assistant", "content": response_message})
