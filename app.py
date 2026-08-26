import os
import streamlit as st
from datetime import datetime

# 1. الاستيراد الآمن للخدمات والنواة
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

# 2. إعدادات الصفحة الأولية
st.set_page_config(
    page_title="المحاسب الذكي - نواة علي بابا",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 3. إدارة مفاتيح الـ API وتدويرها تلقائياً
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

# 4. تفاصيل الشخصيات (تم إضافة شخصية منجز للعمل السريع المختصر)
PERSONA_DETAILS = {
    "mongez": {"name": "منجز (العملي السريع)", "avatar": "⚡", "desc": "إنجاز فوري بدون مقدمات أو رغي"},
    "hantouf": {"name": "حنتوف (المحاسب الصارم)", "avatar": "⚖️", "desc": "دقيق بالمليم وإنذارات مباشرة"},
    "barkawi": {"name": "بركاوي (المتفائل)", "avatar": "🤲", "desc": "يبدأ بالبركة ويركز على الرزق"},
    "kaeeb": {"name": "كئيب (الكوميديا السوداء)", "avatar": "🎭", "desc": "يُذكرك بالديون والالتزامات بأسلوب درامي"},
    "funny": {"name": "الفرفوش (المسلّي)", "avatar": "🥳", "desc": "نكات وإفيهات خفيفة أثناء إدارة الحسابات"}
}

# 5. تهيئة حالات الجلسة (Session State)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "ui_mode" not in st.session_state:
    st.session_state.ui_mode = "MINIMAL_VOICE"
if "persona" not in st.session_state:
    st.session_state.persona = "mongez"

# 6. الشريط الجانبي (Sidebar) والإعدادات
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
    st.subheader("🎭 شخصية المساعد الذكي")
    selected_p = st.selectbox(
        "اختر نمط التفاعل:",
        options=list(PERSONA_DETAILS.keys()),
        format_func=lambda x: f"{PERSONA_DETAILS[x]['avatar']} {PERSONA_DETAILS[x]['name']}"
    )
    st.session_state.persona = selected_p
    st.caption(PERSONA_DETAILS[selected_p]["desc"])

    st.divider()
    st.subheader("🖥️ نمط عرض الواجهة")
    st.session_state.ui_mode = st.radio(
        "اختر طريقة العرض:",
        options=["MINIMAL_VOICE", "FULL_DASHBOARD"],
        format_func=lambda x: "🎙️ الوضع البسيط (Voice-First)" if x == "MINIMAL_VOICE" else "📊 اللوحة الكاملة (Full BI)"
    )

    st.divider()
    if NotificationService:
        unread_notifs = NotificationService.get_unread_notifications(branch)
        st.subheader(f"🔔 التنبيهات ({len(unread_notifs)})")
        if unread_notifs:
            for n in unread_notifs[:3]:
                st.warning(f"**{n['title']}**\n\n{n['message']}")
        else:
            st.success("لا توجد تنبيهات معلقة.")

current_avatar = PERSONA_DETAILS[st.session_state.persona]["avatar"]

# 7. دالة معالجة التفاعل وتنسيق الردود المحاسبية
def handle_user_input(user_input: str):
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    parsed, error = execute_with_key_rotation(
        user_input, 
        branch, 
        st.session_state.get("branch_rules", []), 
        st.session_state.messages,
        persona=st.session_state.persona
    )
    
    if error or not parsed:
        response_text = f"⚠️ عذراً، حدث خطأ: {error}"
    else:
        trans_type = parsed.get("type")
        ai_message = parsed.get("message_to_user", "تم الاستلام.")
        execution_notes = []

        # [تعديل جذري هنا]: ضمان تنفيذ الحفظ لأي عملية ما عدا الاستعلام الصريح لتفادي مشكلة مسميات أنواع المعاملات
        if trans_type and trans_type != "QUERY" and InventoryService:
            try:
                if parsed.get("is_installment") and InstallmentService:
                    cust_name = parsed.get("supplier") or parsed.get("supplier_customer") or "عميل غير محدد"
                    total_amt = float(parsed.get("quantity", 1)) * float(parsed.get("unit_price", 0))
                    down_pay = float(parsed.get("down_payment", 0))
                    rem_amt = total_amt - down_pay

                    credit_check = InstallmentService.check_customer_credit(cust_name, rem_amt)
                    if credit_check.get("is_exceeded"):
                        execution_notes.append(credit_check.get("warning_message"))

                    success, msg = InventoryService.execute_transaction(branch, parsed, user_input)
                    InstallmentService.record_installment(
                        transaction_id="TX_INST",
                        branch=branch,
                        customer_name=cust_name,
                        total_amount=total_amt,
                        down_payment=down_pay,
                        remaining_amount=rem_amt,
                        due_date=parsed.get("due_date", "غير محدد")
                    )
                    execution_notes.append(f"✅ {msg}\n💳 قسط: {rem_amt:,.2f} ج ({cust_name})")
                else:
                    success, msg = InventoryService.execute_transaction(branch, parsed, user_input)
                    execution_notes.append(f"✅ {msg}" if success else f"❌ خطأ الحفظ: {msg}")
            except Exception as e:
                execution_notes.append(f"⚠️ خطأ تنفيذ: {str(e)}")

        elif trans_type == "QUERY":
            if InventoryService:
                try:
                    item_q = parsed.get("item_name")
                    inv_success, inv_msg = InventoryService.query_inventory(branch, item_q)
                    if inv_success and "لم يتم العثور" not in inv_msg:
                        execution_notes.append(inv_msg)
                except Exception:
                    pass

            if supabase:
                customer_query = (parsed.get("supplier") or parsed.get("supplier_customer") or "").strip()
                try:
                    q_builder = supabase.table("installments").select("*").eq("branch", branch)
                    if customer_query and customer_query != "غير محدد":
                        q_builder = q_builder.ilike("customer_name", f"%{customer_query}%")
                    
                    inst_results = q_builder.execute()
                    if inst_results.data:
                        inst_text = "📋 الأقساط:\n"
                        for row in inst_results.data:
                            due = row.get('due_date') or row.get('installment_date') or "غير محدد"
                            inst_text += f"- {row.get('customer_name')}: {row.get('remaining_amount')}ج (موعد: {due})\n"
                        execution_notes.append(inst_text)
                except Exception as ex:
                    execution_notes.append(f"⚠️ خطأ الأقساط: {str(ex)}")

        # إذا كانت الشخصية "منجز"، يتم عرض المضمون باختصار شديد
        if st.session_state.persona == "mongez":
            response_text = "\n".join(execution_notes) if execution_notes else ai_message
        else:
            response_text = f"{ai_message}\n\n" + "\n\n".join(execution_notes) if execution_notes else ai_message

    st.session_state.messages.append({"role": "assistant", "content": response_text})

# 8. عرض الواجهة
if st.session_state.ui_mode == "MINIMAL_VOICE":
    st.title(f"{current_avatar} المحاسب الذكي - نواة علي بابا")
    st.caption(f"📍 الفرع: **{branch}** | 🎭 الشخصية: **{PERSONA_DETAILS[st.session_state.persona]['name']}**")
    
    for message in st.session_state.messages:
        avatar_icon = current_avatar if message["role"] == "assistant" else "🧑‍💼"
        with st.chat_message(message["role"], avatar=avatar_icon):
            st.markdown(message["content"])

    if user_input := st.chat_input("سجل معاملتك أو اسأل عن المخزون..."):
        handle_user_input(user_input)
        st.rerun()
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

        if user_input := st.chat_input("سجل معاملتك أو اسأل عن المخزون..."):
            handle_user_input(user_input)
            st.rerun()

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
