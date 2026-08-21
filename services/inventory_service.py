import streamlit as st
from core.ai_service import AIService
from services.inventory_service import InventoryService

st.set_page_config(page_title="المحاسب الذكي - نواة علي بابا", page_icon="💼", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
html, body, [class*="css"] { font-family: 'Cairo', sans-serif; direction: rtl; text-align: right; }
.stApp { background: linear-gradient(135deg, #090d16 0%, #111827 100%); color: #f3f4f6; }
.hero-header { background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 20px; border-radius: 16px; color: white; text-align: center; margin-bottom: 20px; border: 1px solid #3b82f6; }
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown('<div class="hero-header"><h2>🤖 المحاسب الذكي - نواة علي بابا (v2.0)</h2></div>', unsafe_allow_html=True)

target_branch = st.selectbox("📍 اختر الفرع:", ["الفرع الرئيسي (القاهرة)", "فرع الإسكندرية"], key="branch_selector")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("اكتب معاملتك هنا (مثال: اشترينا 5 طن زيت)..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    with st.chat_message("assistant"):
        with st.spinner("🤖 جاري معالجة المعاملة بالنواة الذكية..."):
            parsed_data = AIService.smart_process_command(
                user_text=prompt, 
                branch=target_branch, 
                chat_history=st.session_state.messages
            )
            
            if parsed_data.get("type") == "QUERY":
                response_text = f"🔍 {parsed_data.get('message_to_user', 'تم الاستعلام بنجاح.')}"
            else:
                success, error_msg = InventoryService.execute_transaction(
                    branch=target_branch, 
                    parsed_data=parsed_data, 
                    raw_text=prompt
                )
                if success:
                    response_text = f"✅ {parsed_data.get('message_to_user', 'تم التسجيل بنجاح في السجلات والمخزن.')}\n\n- الصنف: {parsed_data.get('item_name')}\n- الكمية: {parsed_data.get('quantity')} {parsed_data.get('unit')}"
                else:
                    # 🚨 عرض تفاصيل الخطأ بدقة ليزر
                    response_text = f"❌ **النواة ترفض التسجيل، التفاصيل الدقيقة للخطأ:**\n\n`{error_msg}`"
            
            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})
