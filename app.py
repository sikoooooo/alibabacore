import streamlit as st
from services.inventory_service import InventoryService
from services.installment_service import InstallmentService
from services.notification_service import NotificationService
from services.query_service import QueryService
# في حال أردت استدعاء خدمات إضافية مستقبلاً يمكنك إضافتها هنا

st.set_page_config(page_title="التنين - المساعد المحاسبي", page_icon="🐉", layout="centered")

st.title("🐉 نظام التنين المحاسبي الذكي")
st.write("مرحباً بك يا باشا، المساعد الذكي لإدارة المخزن، الفروع، النواقص، والأقساط تحت أمرك.")

# إعداد الجلسة للمحادثة
if "messages" not in st.session_state:
    st.session_state.messages = []

# عرض رسائل المحادثة السابقة
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# استقبال مدخلات التاجر
user_input = st.chat_input("اكتب أمرك هنا (مثلاً: تقرير المخزن، هات النواقص، مين عليه فلوس؟)...")

if user_input:
    # 1. عرض أمر المستخدم
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. تنظيف النص لفهمه بشكل أفضل
    user_input_clean = user_input.lower()
    response_message = "🤖 لم أفهم طلبك بدقة، هل يمكنك التوضيح؟ (أمثلة: تقرير المخزن، الأقساط، النواقص، الموردين)"
    
    # 3. توجيه ذكي باستخدام الكلمات المفتاحية المتعددة
    if any(word in user_input_clean for word in ["مخزن", "بضاعة", "جرد", "رصيد", "الرصيد"]):
        res = QueryService.get_comprehensive_report("الفرع الرئيسي", "inventory")
        response_message = res.get("message", "حدث خطأ في جلب تقرير المخزن.")
        
    elif any(word in user_input_clean for word in ["أقساط", "قسط", "فلوس بره", "ديون", "متاخرات", "أجل"]):
        res = QueryService.get_comprehensive_report("الفرع الرئيسي", "installments")
        response_message = res.get("message", "حدث خطأ في جلب تقرير الأقساط.")
        
    elif any(word in user_input_clean for word in ["موردين", "شركات", "عايزين فلوس", "مورد"]):
        res = QueryService.get_comprehensive_report("الفرع الرئيسي", "suppliers")
        response_message = res.get("message", "حدث خطأ في جلب مستحقات الموردين.")
        
    elif any(word in user_input_clean for word in ["نواقص", "ناقص", "خلص", "بيخلص", "تنبيه", "إشعارات"]):
        res = NotificationService.get_smart_alerts("الفرع الرئيسي")
        response_message = res.get("message", "حدث خطأ في جلب الإشعارات.")

    # 4. طباعة الرد للمستخدم
    with st.chat_message("assistant"):
        st.markdown(response_message)
    
    # 5. حفظ الرد في سجل الجلسة
    st.session_state.messages.append({"role": "assistant", "content": response_message})
