import streamlit as st
from services.inventory_service import InventoryService
from services.installment_service import InstallmentService
from services.notification_service import NotificationService
from services.query_service import QueryService

st.set_page_config(page_title="التنين - المساعد المحاسبي", page_icon="🐉", layout="centered")

st.title("🐉 نظام التنين المحاسبي الذكي")
st.write("مرحباً بك، المساعد الذكي لإدارة المخزن والفروع والأقساط.")

# إعداد الجلسة للمحادثة
if "messages" not in st.session_state:
    st.session_state.messages = []

# عرض رسائل المححادثة السابقة
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# استقبال مدخلات التاجر
user_input = st.chat_input("اكتب أمرك هنا (مثلاً: تقرير المخزن، الأقساط، إلخ)...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # معالجة الأوامر أو توجيهها للخدمات
    response_message = "🤖 تم استلام أمرك وجاري تنفيذه عبر الخدمات المربطة."
    
    # مثال توجيه سريع لاستعلامات المخزن
    if "مخزن" in user_input or "المخزن" in user_input:
        res = QueryService.get_comprehensive_report("الفرع الرئيسي", "inventory")
        response_message = res.get("message", "حدث خطأ في جلب تقرير المخزن.")
    elif "أقساط" in user_input or "الأقساط" in user_input:
        res = QueryService.get_comprehensive_report("الفرع الرئيسي", "installments")
        response_message = res.get("message", "حدث خطأ في جلب تقرير الأقساط.")
    elif "موردين" in user_input:
        res = QueryService.get_comprehensive_report("الفرع الرئيسي", "suppliers")
        response_message = res.get("message", "حدث خطأ في جلب مستحقات الموردين.")

    with st.chat_message("assistant"):
        st.markdown(response_message)
    
    st.session_state.messages.append({"role": "assistant", "content": response_message})
