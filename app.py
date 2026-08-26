import os
import streamlit as st
from datetime import datetime

try:
    from core.ai_service import AIService
except ImportError:
    AIService = None

try:
    from services.inventory_service import InventoryService
except ImportError:
    InventoryService = None

try:
    from services.installment_service import InstallmentService
except ImportError:
    InstallmentService = None

try:
    from services.notification_service import NotificationService
except ImportError:
    NotificationService = None

try:
    from core.database import supabase
except ImportError:
    supabase = None

st.set_page_config(
    page_title="المحاسب الذكي - نواة علي بابا",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

def execute_with_key_rotation(user_input, branch, branch_rules, messages, persona="mongez"):
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
            import inspect
            sig = inspect.signature(AIService.smart_process_command)
            kwargs = {}
            if "user_text" in sig.parameters: kwargs["user_text"] = user_input
            elif "user_input" in sig.parameters: kwargs["user_input"] = user_input
            else: kwargs["user_input"] = user_input

            if "branch" in sig.parameters: kwargs["branch"] = branch
            if "branch_rules" in sig.parameters: kwargs["branch_rules"] = branch_rules
            if "messages" in sig.parameters: kwargs["messages"] = messages
            elif "chat_history" in sig.parameters: kwargs["chat_history"] = messages
            if "persona" in sig.parameters: kwargs["persona"] = persona

            try:
                return AIService.smart_process_command(**kwargs), None
            except TypeError:
                return AIService.smart_process_command(user_input, branch, branch_rules, messages), None
        except Exception as e:
            last_error = str(e)
            if any(err_word in last_error.lower() for err_word in ["resourceexhausted", "quota", "429"]): 
                continue
            else: 
                break
    return None, last_error

PERSONA_DETAILS = {
    "mongez": {"name": "منجز (العملي السريع)", "avatar": "⚡", "desc": "إنجاز فوري بدون مقدمات أو رغي"},
    "hantouf": {"name": "حنتوف (المحاسب الصارم)", "avatar": "⚖️", "desc": "دقيق بالمليم وإنذارات مباشرة"},
    "barkawi": {"name": "بركاوي (المتفائل)", "avatar": "🤲", "desc": "يبدأ بالبركة ويركز على الرزق"},
    "kaeeb": {"name": "كئيب (الكوميديا السوداء)", "avatar": "🎭", "desc": "يُذكرك بالديون والالتزامات بأسلوب درامي"},
    "funny": {"name": "الفرفوش (المسلّي)", "avatar": "🥳", "desc": "نكات وإفيهات خفيفة أثناء إدارة الحسابات"}
}

if "messages" not in st.session_state:
    st.session_state.messages = []
if "ui_mode" not in st.session_state:
    st.session_state.ui_mode = "MINIMAL_VOICE"
if "persona" not in st.session_state:
    st.session_state.persona = "mongez"

with st.sidebar:
    st.title("⚙️ الإعدادات والشخصيات")
    branch = st.selectbox("📍 اختر الفرع:", ["الفرع الرئيسي (القاهرة)", "فرع الإسكندرية"])

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

    st.divider()
    selected_p = st.selectbox(
        "اختر نمط التفاعل:",
        options=list(PERSONA_DETAILS.keys()),
        format_func=lambda x: f"{PERSONA_DETAILS[x]['avatar']} {PERSONA_DETAILS[x]['name']}"
    )
    st.session_state.persona = selected_p

    st.divider()
    st.session_state.ui_mode = st.radio(
        "اختر طريقة العرض:",
        options=["MINIMAL_VOICE", "FULL_DASHBOARD"],
        format_func=lambda x: "🎙️ الوضع البسيط (Voice-First)" if x == "MINIMAL_VOICE" else "📊 اللوحة الكاملة (Full BI)"
    )

current_avatar = PERSONA_DETAILS[st.session_state.persona]["avatar"]

def process_and_display_chat(user_input):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar=current_avatar):
        with st.spinner("جاري التنفيذ..."):
            parsed, error = execute_with_key_rotation(
                user_input, 
                branch, 
                st.session_state.get("branch_rules", []), 
                st.session_state.messages,
                persona=st.session_state.persona
            )
            
            if error or not parsed:
                response_text = f"⚠️ خطأ: {error}"
            else:
                ai_message = parsed.get("message_to_user", "تم.")
                execution_notes = []
                
                transactions_list = parsed.get("transactions", [])
                if not transactions_list and "type" in parsed:
                    transactions_list = [parsed]

                for tx in transactions_list:
                    trans_type = tx.get("type")
                    if trans_type and trans_type != "QUERY" and InventoryService:
                        try:
                            success, msg = InventoryService.execute_transaction(branch, tx, user_input)
                            if success:
                                execution_notes.append(f"✅ {msg}")
                            else:
                                execution_notes.append(f"❌ {msg}")
                        except Exception as e:
                            execution_notes.append(f"🚨 خطأ: {str(e)}")

                # تقصير تام وصارم للردود بدون أي مقدمات
                if execution_notes:
                    response_text = "\n".join(execution_notes)
                else:
                    response_text = ai_message

            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})

# ** عرض الواجهة حسب الاختيار (وضع صوتي أو لوحة كاملة بالتابات) **
if st.session_state.ui_mode == "MINIMAL_VOICE":
    st.title(f"{current_avatar} المحاسب الذكي - نواة علي بابا")
    st.caption(f"📍 الفرع: **{branch}**")
    
    for message in st.session_state.messages:
        avatar_icon = current_avatar if message["role"] == "assistant" else "🧑‍💼"
        with st.chat_message(message["role"], avatar=avatar_icon):
            st.markdown(message["content"])

    if user_input := st.chat_input("سجل معاملتك أو اسأل..."):
        process_and_display_chat(user_input)
else:
    st.title(f"📊 المحاسب الذكي - لوحة تحليلات الأعمال ({branch})")
    
    main_tab, inv_tab, reports_tab, notif_tab = st.tabs([
        "💬 الدردشة", "📦 المخزون", "📊 التقارير", "🔔 التنبيهات"
    ])
    
    with main_tab:
        for message in st.session_state.messages:
            avatar_icon = current_avatar if message["role"] == "assistant" else "🧑‍💼"
            with st.chat_message(message["role"], avatar=avatar_icon):
                st.markdown(message["content"])

        if user_input := st.chat_input("سجل معاملتك أو اسأل..."):
            process_and_display_chat(user_input)

    with inv_tab:
        st.subheader("📦 رصيد المخزون الحالي")
        if InventoryService:
            success, inv_data = InventoryService.query_inventory(branch)
            st.markdown(inv_data)

    with reports_tab:
        st.subheader("📊 لوحة التقارير")
        if InstallmentService:
            debts = InstallmentService.get_branch_debts_summary(branch)
            if debts: st.dataframe(debts)
            else: st.info("لا توجد ديون معلقة.")

    with notif_tab:
        st.subheader("🔔 التنبيهات")
        if NotificationService:
            all_notifs = NotificationService.get_unread_notifications(branch)
            for n in all_notifs:
                st.write(f"- {n['title']}: {n['message']}")
