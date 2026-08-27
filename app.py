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
user_input = st.chat_input("اكتب أمرك هنا (مثلاً: اشترينا 20 طن حديد، بعنا 5 كرتونة زيت)...")

if user_input:
    # 1. عرض أمر المستخدم
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    user_input_clean = user_input.lower()
    
    # 2. تحليل الطلب عبر الذكاء الاصطناعي
    with st.spinner("جاري تحليل المعاملة بواسطة التنين الذكي..."):
        ai_response = AIService.smart_process_command(
            user_text=user_input,
            branch=branch_name,
            persona=selected_persona,
            chat_history=st.session_state.messages
        )
        
        response_message = ai_response.get("message_to_user", "🤖 تم استلام طلبك.")
        transactions = ai_response.get("transactions", [])

        # 3. تفعيل الحفظ الشامل لكل أنواع المعاملات مع تمرير الوحدة ومعامل التحويل بدقة
        for tx in transactions:
            tx_type = tx.get("type")
            item_name = tx.get("item_name")
            
            # معالجة الشراء (PURCHASE) أو البيع (SALE)
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
                        response_message += f"\n\n✨ **[تم تسجيل المعاملة وحفظ الوحدة ({minor_unit_val or unit_val}) ومعامل التحويل في الداتابيز بنجاح]**"
                    else:
                        response_message += f"\n\n⚠️ **[تنبيه الحفظ]**: {res.get('message', 'خطأ غير معروف')}"
                except Exception as e:
                    response_message += f"\n\n❌ خطأ أثناء تنفيذ الحفظ: {str(e)}"

            # معالجة الاستعلامات والتقارير الشاملة
            elif tx_type == "QUERY":
                if any(word in user_input_clean for word in ["مخزن", "بضاعة", "جرد", "رصيد", "الرصيد"]):
                    res = QueryService.get_comprehensive_report(branch_name, "inventory")
                    response_message += f"\n\n{res.get('message', '')}"
                elif any(word in user_input_clean for word in ["أقساط", "قسط", "فلوس بره", "ديون", "متاخرات", "أجل"]):
                    res = QueryService.get_comprehensive_report(branch_name, "installments")
                    response_message += f"\n\n{res.get('message', '')}"
                elif any(word in user_input_clean for word in ["موردين", "شركات", "مورد"]):
                    res = QueryService.get_comprehensive_report(branch_name, "suppliers")
                    response_message += f"\n\n{res.get('message', '')}"
                elif any(word in user_input_clean for word in ["نواقص", "ناقص", "خلص", "بيخلص", "تنبيه"]):
                    res = NotificationService.get_smart_alerts(branch_name)
                    response_message += f"\n\n{res.get('message', '')}"

    # 4. طباعة رد المساعد بالشخصية
    with st.chat_message("assistant"):
        st.markdown(response_message)
    
    # 5. حفظ الرد في سجل الجلسة
    st.session_state.messages.append({"role": "assistant", "content": response_message})
