import streamlit as st
from core.ai_service import AIService
from services.inventory_service import InventoryService
from services.installment_service import InstallmentService
from services.notification_service import NotificationService
from services.query_service import QueryService

st.set_page_config(page_title="التنين - المساعد المحاسبي", page_icon="🐉", layout="centered")

st.title("🐉 نظام التنين المحاسبي الذكي")
st.write("مرحباً بك يا باشا، المساعد الذكي لإدارة المخزن، الفروع، النواقص، والأقساط تحت أمرك.")

# اختيار الشخصية المحاسبية من الشريط الجانبي
with st.sidebar:
    st.header("⚙️ إعدادات التنين")
    selected_persona = st.selectbox(
        "اختر شخصية المحاسب:",
        options=["hantouf", "barkawi", "kaeeb", "funny"],
        format_func=lambda x: {
            "hantouf": "💼 حنتوف (الصارم الدقيق)",
            "barkawi": "🤲 بركاوي (المتفائل بالرزق)",
            "kaeeb": "📉 كئيب (الكوميديا السوداء والديون)",
            "funny": "😄 الفرفوش المضحك"
        }[x]
    )
    branch_name = st.text_input("اسم الفرع:", value="الفرع الرئيسي")

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

    # 2. تحليل الطلب عبر الذكاء الاصطناعي (AIService) والشخصية المختارة
    user_input_clean = user_input.lower()
    
    with st.spinner("جاري تحليل المعاملة بواسطة التنين الذكي..."):
        ai_response = AIService.smart_process_command(
            user_text=user_input,
            branch=branch_name,
            persona=selected_persona,
            chat_history=st.session_state.messages
        )
        
        response_message = ai_response.get("message_to_user", "🤖 لم أفهم طلبك بدقة، هل يمكنك التوضيح؟")
        transactions = ai_response.get("transactions", [])

        # 3. دمج الذكاء الاصطناعي مع دوال الخدمات القوية لديك عند وجود استعلامات خاصة
        for tx in transactions:
            tx_type = tx.get("type")
            
            if tx_type == "QUERY":
                if any(word in user_input_clean for word in ["مخزن", "بضاعة", "جرد", "رصيد", "الرصيد"]):
                    res = QueryService.get_comprehensive_report(branch_name, "inventory")
                    response_message += f"\n\n{res.get('message', '')}"
                    
                elif any(word in user_input_clean for word in ["أقساط", "قسط", "فلوس بره", "ديون", "متاخرات", "أجل"]):
                    res = QueryService.get_comprehensive_report(branch_name, "installments")
                    response_message += f"\n\n{res.get('message', '')}"
                    
                elif any(word in user_input_clean for word in ["موردين", "شركات", "عايزين فلوس", "مورد"]):
                    res = QueryService.get_comprehensive_report(branch_name, "suppliers")
                    response_message += f"\n\n{res.get('message', '')}"
                    
                elif any(word in user_input_clean for word in ["نواقص", "ناقص", "خلص", "بيخلص", "تنبيه", "إشعارات"]):
                    res = NotificationService.get_smart_alerts(branch_name)
                    response_message += f"\n\n{res.get('message', '')}"

            elif tx_type == "UPDATE_CREDIT_LIMIT":
                item_name = tx.get("item_name", "غير محدد")
                response_message += f"\n\n✅ تم رصد طلب تحديث الحد الائتماني للعميل/المورد: **{item_name}**."

    # 4. طباعة الرد للمستخدم بالشخصية المحاسبية
    with st.chat_message("assistant"):
        st.markdown(response_message)
    
    # 5. حفظ الرد في سجل الجلسة
    st.session_state.messages.append({"role": "assistant", "content": response_message})
