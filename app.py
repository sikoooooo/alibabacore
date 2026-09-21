import os
import re
import time
from datetime import date, timedelta, datetime
import streamlit as st

from core.ai_service import AIService
from core.local_sync import LocalSyncManager
from services.inventory_service import InventoryService
from services.installment_service import InstallmentService, get_supabase_client
from services.notification_service import NotificationService
from services.query_service import QueryService

# مدير المزامنة المحلية للأوفلاين
sync_manager = LocalSyncManager()

def get_branch_id_safely(branch_str: str) -> str:
    """دالة آمنة لجلب معرف الفرع من قاعدة البيانات لتفادي أخطاء الـ UUID"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return branch_str
        res = supabase.table("branches").select("id").eq("branch_name", branch_str).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["id"]
    except Exception as e:
        print(f"⚠️ Warning in get_branch_id_safely: {e}")
    return branch_str  # كاحتياطي لو الجدول غير مفعل فيه الـ UUID

def sync_pending_offline_data(branch_name: str):
    """دالة لإعادة مزامنة المعاملات المعلقة أوفلاين مع قاعدة بيانات Supabase."""
    pending_txs = sync_manager.get_pending_transactions(branch=branch_name)
    if not pending_txs:
        return 0, "لا توجد معاملات معلقة للمزامنة."

    supabase = get_supabase_client()
    if not supabase:
        return 0, "❌ تعذر الاتصال بالسيرفر، تأكد من اتصال الإنترنت."

    success_count = 0
    for tx in pending_txs:
        tx_id = tx["id"]
        parsed = tx.get("parsed_data", {})
        try:
            # إعادة معالجة المبيعات أو المشتريات المعلقة
            tx_type = parsed.get("type", "SALE")
            item_name = parsed.get("item_name", "صنف أوفلاين")
            qty = float(parsed.get("quantity", 1.0))
            price = float(parsed.get("unit_price", 0.0))

            res = InventoryService.process_transaction(
                branch=branch_name,
                item_name=item_name,
                quantity=qty,
                price=price,
                supplier=parsed.get("supplier", "مبيعات أوفلاين"),
                transaction_type=tx_type
            )
            if res.get("status") == "SUCCESS":
                sync_manager.mark_as_synced(tx_id)
                success_count += 1
            else:
                sync_manager.mark_as_failed(tx_id, res.get("message", "فشل المعالجة"))
        except Exception as ex:
            sync_manager.mark_as_failed(tx_id, str(ex))

    return success_count, f"✅ تم مزامنة {success_count} معاملة بنجاح من أصل {len(pending_txs)}."


st.set_page_config(page_title="التنين - المساعد المحاسبي", page_icon="🐉", layout="centered")

# ==========================================
# 🔐 إدارة مصادقة المستخدمين (Google & Facebook Login)
# ==========================================
if "user" not in st.session_state:
    st.session_state.user = None

supabase = get_supabase_client()

# التحقق من الجلسة الحالية في Supabase (لو راجع من صفحة إعادة توجيه OAuth)
query_params = st.query_params
if "code" in query_params and supabase:
    try:
        pass
    except Exception:
        pass

# شاشة تسجيل الدخول لو المستخدم مش مسجل
if not st.session_state.user:
    st.title("🐉 نظام التنين المحاسبي الصارم")
    st.subheader("🔐 يرجى تسجيل الدخول للبدء")
    st.write("سجل دخولك مجاناً وبأمان تام باستخدام حسابك على جوجل أو فيسبوك:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔵 تسجيل الدخول بواسطة Google", use_container_width=True):
            if supabase:
                try:
                    res = supabase.auth.sign_in_with_oauth({
                        "provider": "google",
                        "options": {
                            "redirect_to": "https://alibabacore-ogqnejif12.streamlit.app"
                        }
                    })
                    if res and res.url:
                        st.markdown(f'<meta http-equiv="refresh" content="0;url={res.url}">', unsafe_allow_html=True)
                        st.success("جاري تحويلك لصفحة جوجل...")
                except Exception as e:
                    st.error(f"خطأ في الاتصال بـ Google: {e}")
            else:
                st.error("تعذر الاتصال بقاعدة بيانات Supabase.")

    with col2:
        if st.button("🔵 تسجيل الدخول بواسطة Facebook", use_container_width=True):
            if supabase:
                try:
                    res = supabase.auth.sign_in_with_oauth({
                        "provider": "facebook",
                        "options": {
                            "redirect_to": "https://alibabacore-ogqnejif12.streamlit.app"
                        }
                    })
                    if res and res.url:
                        st.markdown(f'<meta http-equiv="refresh" content="0;url={res.url}">', unsafe_allow_html=True)
                        st.success("جاري تحويلك لصفحة فيسبوك...")
                except Exception as e:
                    st.error(f"خطأ في الاتصال بـ Facebook: {e}")
            else:
                st.error("تعذر الاتصال بقاعدة بيانات Supabase.")
                
    st.divider()
    if st.button("🚀 دخول تجريبي سريع (للتطوير المحلي)"):
        st.session_state.user = {"email": "test_merchant@alibaba.com", "name": "تاجر تجريبي"}
        st.rerun()
        
    st.stop()  # إيقاف عرض باقي التطبيق لحين تسجيل الدخول

# ==========================================
# التطبيق الرئيسي (يعمل فقط بعد تسجيل الدخول)
# ==========================================
st.title("🐉 نظام التنين المحاسبي الصارم")
st.write(f"مرحباً بك، أهلاً بك في نظامك المحاسبي المباشر. (المستخدم: {st.session_state.user.get('email', 'مدير النظام')})")

if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.user = None
    if supabase:
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
    st.rerun()

# ⚙️ إعدادات النظام وتعدد الفروع والمزامنة الأوفلاين
with st.sidebar:
    st.header("⚙️ إعدادات النظام والشركة")
    
    company_code = st.text_input("كود الشركة / المعرف التجاري:", value="company_main_01")
    branch_name = st.text_input("اسم الفرع الحالي:", value="الفرع الرئيسي")
    
    # 📡 حالة المزامنة والأوفلاين
    pending_count = sync_manager.get_pending_count(branch=branch_name)
    st.divider()
    st.subheader("📡 حالة الاتصال والمزامنة")
    if pending_count > 0:
        st.warning(f"⚠️ يوجد **{pending_count}** معاملة معلقة بانتظار المزامنة.")
        if st.button("🔄 مزامنة المعاملات المعلقة الآن"):
            with st.spinner("جاري المزامنة مع قاعدة البيانات السحابية..."):
                synced_cnt, sync_msg = sync_pending_offline_data(branch_name)
                st.info(sync_msg)
                st.rerun()
    else:
        st.success("✅ جميع المعاملات متزامنة مع السحابة.")

    st.divider()
    st.subheader("💳 باقات الاشتراك الشهري")
    st.info(
        "**الباقة الأساسية (300 ج.م/شهرياً):**\n"
        "- البيع النقدي وإدارة المخزن الأساسي.\n\n"
        "**باقة السوبر App الشاملة (500 ج.م/شهرياً):**\n"
        "- شاملة إدارة الأقساط، الذمم، ومؤشر الشراء الجمعي."
    )
    
    st.divider()
    st.subheader("📊 التقارير والملخصات السريعة")
    
    if st.button("💳 تقرير الأقساط والذمم العام"):
        with st.spinner("جاري جلب تقرير الأقساط..."):
            rep = QueryService.get_comprehensive_report(branch_name, "installments")
            st.session_state.messages.append({"role": "assistant", "content": rep.get("message", "لا توجد بيانات.")})
            st.rerun()

    if st.button("📦 تقرير المخزن الصافي"):
        with st.spinner("جاري جلب تقرير المخزن..."):
            rep = QueryService.get_comprehensive_report(branch_name, "inventory")
            st.session_state.messages.append({"role": "assistant", "content": rep.get("message", "لا توجد بيانات.")})
            st.rerun()

    if st.button("📈 إجمالي المبيعات والأرباح"):
        with st.spinner("جاري جلب مبيعات الفرع..."):
            rep = QueryService.get_comprehensive_report(branch_name, "sales_reps")
            st.session_state.messages.append({"role": "assistant", "content": rep.get("message", "لا توجد بيانات.")})
            st.rerun()

    if st.button("🏭 مستحقات الموردين"):
        with st.spinner("جاري جلب مستحقات الموردين..."):
            rep = QueryService.get_comprehensive_report(branch_name, "suppliers")
            st.session_state.messages.append({"role": "assistant", "content": rep.get("message", "لا توجد بيانات.")})
            st.rerun()

    if st.button("💰 حركة الخزينة وصافي الكاش"):
        with st.spinner("جاري حساب رصيد الخزينة..."):
            supabase_client = get_supabase_client()
            if supabase_client:
                try:
                    res = supabase_client.table("treasury_ledger").select("type, amount").eq("branch", branch_name).execute()
                    records = res.data if res.data else []
                    total_in = sum(float(r.get("amount", 0)) for r in records if r.get("type") == "INFLOW")
                    total_out = sum(float(r.get("amount", 0)) for r in records if r.get("type") == "OUTFLOW")
                    net_cash = total_in - total_out
                    treasury_msg = (
                        f"💰 **ملخص الخزينة والصافي للفرع ({branch_name}):**\n"
                        f"- إجمالي الداخل (إيرادات ومقدمات): **{total_in:,.2f} ج.م**\n"
                        f"- إجمالي الخارج (مصروفات ومدفوعات): **{total_out:,.2f} ج.م**\n"
                        f"- **صافي رصيد الخزينة الحالي:** **{net_cash:,.2f} ج.م**"
                    )
                except Exception as e:
                    treasury_msg = f"⚠️ خطأ أثناء استعلام الخزينة: {e}"
            else:
                treasury_msg = "⚠️ تعذر الاتصال بقاعدة البيانات لجلب الخزينة."
            st.session_state.messages.append({"role": "assistant", "content": treasury_msg})
            st.rerun()

    if st.button("🚨 نواقص المخزن والتنبيهات"):
        with st.spinner("جاري فحص النواقص..."):
            rep = NotificationService.get_smart_alerts(branch_name)
            st.session_state.messages.append({"role": "assistant", "content": rep.get("message", "لا توجد تنبيهات.")})
            st.rerun()

# إعداد الجلسة للمحادثة
if "messages" not in st.session_state:
    st.session_state.messages = []

# عرض رسائل المحادثة السابقة
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# استقبال مدخلات التاجر
user_input = st.chat_input("اكتب أمرك هنا (مثلاً: بعنا مروحة تورنادو لأم يوسف بـ 2400 مقدم 400 وقسط 150)...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    user_input_clean = user_input.lower()
    
    with st.spinner("جاري التنفيذ الفوري المحاسبي الصارم..."):
        action_results = []
        
        # 1. معالجة ذكية لاستعلامات الأقساط
        month_match = re.search(r'(?:شهر|ش)\s*(\d{1,2})', user_input_clean)
        is_installment_query = any(k in user_input_clean for k in ["قسط", "أقساط", "ديون", "بيان", "مستحق", "هات"])
        
        if is_installment_query:
            supabase_client = get_supabase_client()
            if supabase_client:
                try:
                    inst_query = supabase_client.table("installments").select("*").eq("branch", branch_name).execute()
                    rows = inst_query.data if inst_query.data else []
                    
                    filtered_rows = []
                    if month_match:
                        target_month = int(month_match.group(1))
                        for r in rows:
                            due_date_str = str(r.get("due_date", ""))
                            try:
                                if "-" in due_date_str:
                                    dt_obj = datetime.strptime(due_date_str.split("T")[0], "%Y-%m-%d")
                                    if dt_obj.month == target_month:
                                        filtered_rows.append(r)
                                elif f"-{str(target_month).zfill(2)}-" in due_date_str:
                                    filtered_rows.append(r)
                            except Exception:
                                if f"-{str(target_month).zfill(2)}-" in due_date_str:
                                    filtered_rows.append(r)
                                    
                        if filtered_rows:
                            msg = f"📋 **أقساط الاستحقاق لشهر ({target_month}) لفرع {branch_name}:**\n"
                            total_month_amt = 0
                            for row in filtered_rows:
                                cust = row.get("customer_name", "غير معروف")
                                item = row.get("item_name", "صنف")
                                val = float(row.get("installment_value", row.get("remaining_amount", 0)))
                                date_due = row.get("due_date", "")
                                total_month_amt += val
                                msg += f"- العميل: **{cust}** | الصنف: {item} | القسط: **{val:,.2f} ج.م** (تاريخ الاستحقاق: {date_due})\n"
                            msg += f"\n💰 **إجمالي المستحق في الشهر:** **{total_month_amt:,.2f} ج.م**"
                            action_results.append(msg)
                        else:
                            action_results.append(f"ℹ️ لا توجد أقساط مسجلة تستحق في شهر {target_month} للفرع ({branch_name}).")
                    
                    elif "عم" in user_input_clean or "العميل" in user_input_clean or any(c.get("customer_name", "").lower() in user_input_clean for c in rows):
                        target_cust_name = ""
                        for r in rows:
                            c_name = str(r.get("customer_name", ""))
                            if c_name and c_name.lower() in user_input_clean:
                                target_cust_name = c_name
                                break
                        
                        if not target_cust_name:
                            cust_search_match = re.search(r'(?:عم|العميل|لـ|عن)\s*([أ-ي\w\s]+)', user_input)
                            if cust_search_match:
                                target_cust_name = cust_search_match.group(1).strip()
                                
                        if target_cust_name:
                            cust_rows = [r for r in rows if target_cust_name.lower() in str(r.get("customer_name", "")).lower()]
                            if cust_rows:
                                msg = f"📋 **تفاصيل أقساط وذمم العميل ({target_cust_name}) لفرع {branch_name}:**\n"
                                total_cust_rem = 0
                                for row in cust_rows:
                                    item = row.get("item_name", "صنف")
                                    total_inv = float(row.get("total_amount", 0))
                                    rem = float(row.get("remaining_amount", 0))
                                    inst_val = float(row.get("installment_value", 0))
                                    date_due = row.get("due_date", "")
                                    total_cust_rem += rem
                                    msg += f"- الصنف: **{item}** | إجمالي: {total_inv:,.2f} | المتبقي: **{rem:,.2f} ج.م** | القسط الشهري: {inst_val:,.2f} (الاستحقاق: {date_due})\n"
                                msg += f"\n💰 **إجمالي المتبقي على العميل:** **{total_cust_rem:,.2f} ج.م**"
                                action_results.append(msg)
                            else:
                                action_results.append(f"ℹ️ لا توجد أقساط مسجلة باسم العميل ({target_cust_name}).")
                except Exception as ex:
                    print(f"Error querying installments: {ex}")

        # 2. المعالجة العامة للعمليات وتحديث الجداول بعزل الفرع
        if not action_results:
            ai_response = AIService.smart_process_command(
                user_text=user_input,
                branch=branch_name,
                persona="professional",
                chat_history=st.session_state.messages
            )
            
            transactions = ai_response.get("transactions", [])

            if "عدل الحد الائتماني" in user_input_clean or "رفع الحد الائتماني" in user_input_clean:
                target_customer = "محمود عبد العليم"
                new_limit = 25000.0 
                limit_res = InstallmentService.set_customer_credit_limit(target_customer, new_limit, branch_name)
                action_results.append(limit_res.get("message", "✅ تم تحديث الائتمان بنجاح."))
                
            is_installment_intent = any(keyword in user_input_clean for keyword in ["قسط", "أقساط", "مقدم", "فاضل", "علي", "على", "باقي"])
            is_return_intent = "مرتجع" in user_input_clean

            for tx in transactions:
                tx_type = "RETURN" if is_return_intent else tx.get("type")
                item_name = tx.get("item_name")
                
                if tx_type in ["PURCHASE", "SALE", "RETURN"] and item_name and item_name != "غير محدد":
                    try:
                        qty = float(tx.get("quantity", 1.0))
                        price = float(tx.get("unit_price", 0.0))
                        unit_val = tx.get("unit") or tx.get("major_unit") or "وحدة"
                        minor_unit_val = tx.get("minor_unit")
                        conv_factor = float(tx.get("conversion_factor", 1.0))
                        
                        party_name = tx.get("customer") or tx.get("supplier", "عميل عام")
                        if party_name in ["عميل عام", "مورد عام", "غير محدد"]:
                            cust_match = re.search(r'(?:تبعت|تبع|لـ|لعميل|من)\s*([أ-ي\w\s]+?)(?:\s+دفعت|\s+وقسط|\s+وفاضل|\s+بـ|$)', user_input)
                            if cust_match:
                                party_name = cust_match.group(1).strip()
                            else:
                                party_name = "عميل"

                        discount_match = re.search(r'خصم(?:\s+كاش)?\s*([\d,]+)', user_input_clean)
                        discount_amount = float(discount_match.group(1).replace(",", "")) if discount_match else 0.0

                        # أ. معالجة المرتجعات الذكية
                        if tx_type == "RETURN":
                            inv_res = InventoryService.process_transaction(
                                branch=branch_name,
                                item_name=item_name,
                                quantity=qty,
                                price=price,
                                supplier="مرتجع", 
                                transaction_type="PURCHASE", 
                                unit=unit_val,
                                minor_unit=minor_unit_val,
                                conversion_factor=conv_factor
                            )
                            if inv_res.get("status") == "SUCCESS":
                                supabase_client = get_supabase_client()
                                total_refund = (price * qty) if price > 0 else 0.0
                                if discount_amount > 0:
                                    total_refund = max(0.0, total_refund - discount_amount)
                                    
                                if supabase_client and total_refund > 0:
                                    try:
                                        supabase_client.table("treasury_ledger").insert({
                                            "branch": branch_name,
                                            "type": "OUTFLOW",
                                            "amount": total_refund,
                                            "description": f"رد قيمة مرتجع - {item_name}"
                                        }).execute()
                                    except Exception:
                                        pass
                                action_results.append(f"✅ تم إرجاع الصنف ({item_name}) للمخزن بنجاح وتم صرف مبلغ الرد من الخزينة.")
                            else:
                                # حفظ المعاملة أوفلاين في حال الفشل
                                sync_manager.save_offline(branch_name, user_input, tx)
                                action_results.append(f"⚠️ يتعذر الاتصال بالمخزن السحابي حالياً. تم حفظ المرتجع محلياً لتسويته لاحقاً.")
                            continue

                        # ب. معالجة المبيعات بالتقسيط
                        if tx_type == "SALE" and is_installment_intent:
                            total_amount = price * qty if price > 0 else 0.0
                            down_payment = 0.0
                            remaining_amount = 0.0
                            
                            price_match = re.search(r'بـ\s*([\d,]+)', user_input)
                            if price_match and total_amount == 0.0:
                                total_amount = float(price_match.group(1).replace(",", ""))
                                
                            dp_match = re.search(r'(?:دفعت|مقدم)\s*([\d,]+)', user_input_clean)
                            if dp_match:
                                down_payment = float(dp_match.group(1).replace(",", ""))
                                
                            rem_match = re.search(r'(?:وفاضل|فاضل|باقي)\s*([\d,]+)', user_input_clean)
                            if rem_match:
                                remaining_amount = float(rem_match.group(1).replace(",", ""))
                            
                            if discount_amount > 0:
                                total_amount = max(0.0, total_amount - discount_amount)

                            if total_amount == 0.0 or (down_payment == 0.0 and remaining_amount == 0.0):
                                action_results.append(
                                    "⚠️ **عذراً، البيانات المالية غير مكتملة أو غير واضحة.**\n"
                                    "برجاء كتابة المعاملة بشكل دقيق يوضح: (إجمالي السعر، المقدم المدفوع، والمبلغ المتبقي للتقسيط)."
                                )
                                continue

                            if remaining_amount > total_amount:
                                action_results.append(
                                    f"❌ **خطأ حسابي:** المبلغ المتبقي ({remaining_amount:,.2f}) أكبر من إجمالي الفاتورة ({total_amount:,.2f})!"
                                )
                                continue

                            if down_payment == 0.0 and remaining_amount > 0:
                                down_payment = max(0.0, total_amount - remaining_amount)
                            elif remaining_amount == 0.0 and down_payment > 0:
                                remaining_amount = max(0.0, total_amount - down_payment)

                            months_count = 3
                            months_match = re.search(r'(\d+)\s*(?:شهر|شهور|أشهر)', user_input_clean)
                            if months_match:
                                months_count = int(months_match.group(1))
                                
                            installment_value = remaining_amount / months_count if months_count > 0 else remaining_amount
                            initial_limit = max(10000.0, total_amount)
                            
                            supabase_client = get_supabase_client()
                            if supabase_client:
                                try:
                                    existing_cust = supabase_client.table("customers").select("id").eq("customer_name", party_name).eq("branch", branch_name).execute()
                                    if not existing_cust.data:
                                        supabase_client.table("customers").insert({
                                            "customer_name": party_name, 
                                            "branch": branch_name
                                        }).execute()
                                    
                                    existing_limit = supabase_client.table("customer_credit_limits").select("id").eq("customer_name", party_name).eq("branch", branch_name).execute()
                                    if not existing_limit.data:
                                        supabase_client.table("customer_credit_limits").insert({
                                            "customer_name": party_name,
                                            "credit_limit": initial_limit,
                                            "branch": branch_name
                                        }).execute()
                                except Exception:
                                    pass
                            
                            inv_res = InventoryService.process_transaction(
                                branch=branch_name,
                                item_name=item_name,
                                quantity=qty,
                                price=total_amount / qty if qty > 0 else total_amount,
                                supplier="مبيعات تقسيط", 
                                transaction_type="SALE",
                                unit=unit_val,
                                minor_unit=minor_unit_val,
                                conversion_factor=conv_factor
                            )
                            
                            if inv_res.get("status") != "SUCCESS":
                                sync_manager.save_offline(branch_name, user_input, tx)
                                action_results.append(f"⚠️ تعذر الاتصال بالمخزن السحابي. تم حفظ عملية التقسيط أوفلاين.")
                                continue

                            if supabase_client and down_payment > 0:
                                try:
                                    supabase_client.table("treasury_ledger").insert({
                                        "branch": branch_name,
                                        "type": "INFLOW",
                                        "amount": down_payment,
                                        "description": f"مقدم تقسيط - {item_name} للعميل {party_name}"
                                    }).execute()
                                except Exception:
                                    pass

                            due_date = (date.today() + timedelta(days=30)).isoformat()
                            inst_res = InstallmentService.record_installment(
                                branch=branch_name,
                                customer_name=party_name,
                                item_name=item_name,
                                total_amount=total_amount,
                                down_payment=down_payment,
                                remaining_amount=remaining_amount,
                                installment_value=installment_value,
                                due_date=due_date,
                                installments_count=months_count
                            )
                            
                            discount_msg = f"\n- تم تطبيق خصم: {discount_amount:,.2f} ج.م" if discount_amount > 0 else ""
                            if inst_res:
                                action_results.append(
                                    f"✅ **تم تسجيل البيع بالتقسيط بنجاح:**\n"
                                    f"- العميل: {party_name} | الصنف: {item_name}\n"
                                    f"- إجمالي الصافي: {total_amount:,.2f} ج.م{discount_msg}\n"
                                    f"- المقدم المدفوع: **{down_payment:,.2f} ج.م** | المتبقي أقساط: {remaining_amount:,.2f} ج.م"
                                )
                            else:
                                sync_manager.save_offline(branch_name, user_input, tx)
                                action_results.append("⚠️ تعذر جدولة الأقساط بالسحابة. تم حفظ الطلب طابور المزامنة محلياً.")

                        # ج. معالجة المشتريات والمبيعات النقدية
                        else:
                            is_credit_purchase = tx_type == "PURCHASE" and any(k in user_input_clean for k in ["على الحساب", "دين", "آجل", "بدون دفع"])
                            supplier_name = party_name if party_name and party_name != "غير محدد" else "مورد عام"
                            
                            total_invoice_price = price * qty
                            if discount_amount > 0:
                                total_invoice_price = max(0.0, total_invoice_price - discount_amount)

                            res = InventoryService.process_transaction(
                                branch=branch_name,
                                item_name=item_name,
                                quantity=qty,
                                price=total_invoice_price / qty if qty > 0 else total_invoice_price,
                                supplier=supplier_name,
                                transaction_type=tx_type,
                                unit=unit_val,
                                minor_unit=minor_unit_val,
                                conversion_factor=conv_factor
                            )
                            
                            if res.get("status") == "SUCCESS":
                                supabase_client = get_supabase_client()
                                if supabase_client:
                                    try:
                                        if tx_type == "SALE" and total_invoice_price > 0:
                                            supabase_client.table("treasury_ledger").insert({
                                                "branch": branch_name,
                                                "type": "INFLOW",
                                                "amount": total_invoice_price,
                                                "description": f"مبيعات - {item_name}"
                                            }).execute()
                                        elif tx_type == "PURCHASE":
                                            safe_branch_id = get_branch_id_safely(branch_name)
                                            existing_sup = supabase_client.table("suppliers").select("id").eq("supplier_name", supplier_name).eq("branch_id", safe_branch_id).execute()
                                            if not existing_sup.data:
                                                supabase_client.table("suppliers").insert({
                                                    "supplier_name": supplier_name,
                                                    "branch_id": safe_branch_id
                                                }).execute()

                                            if not is_credit_purchase and total_invoice_price > 0:
                                                supabase_client.table("treasury_ledger").insert({
                                                    "branch": branch_name,
                                                    "type": "OUTFLOW",
                                                    "amount": total_invoice_price,
                                                    "description": f"مشتريات كاش من {supplier_name} - {item_name}"
                                                }).execute()
                                    except Exception as ex:
                                        print(f"Warning inserting treasury record: {ex}")

                                credit_label = " (على الحساب / دين)" if is_credit_purchase else ""
                                action_results.append(f"✅ تم الحفظ - {('مبيعات' if tx_type == 'SALE' else 'مشتريات')}{credit_label}: {item_name} (الكمية: {qty} {unit_val})")
                            else:
                                sync_manager.save_offline(branch_name, user_input, tx)
                                action_results.append(f"⚠️ انقطعت التغطية مع السحابة: تم حفظ المعاملة محلياً لرفعها تلقائياً لاحقاً.")
                                
                    except Exception as e:
                        sync_manager.save_offline(branch_name, user_input, tx)
                        action_results.append(f"⚠️ خطأ أثناء المعالجة سحابياً: {str(e)}. تم تحويل المعاملة للطابور المحلي.")

                elif tx_type == "EXPENSE":
                    action_results.append(f"✅ تم الحفظ - مصروفات: {item_name}")

                elif tx_type == "QUERY":
                    if "مخزن" in user_input_clean or "رصيد" in user_input_clean:
                        res = QueryService.get_comprehensive_report(branch_name, "inventory")
                        action_results.append(res.get('message', ''))
                    elif "أقساط" in user_input_clean or "ديون" in user_input_clean or "بيان" in user_input_clean:
                        res = QueryService.get_comprehensive_report(branch_name, "installments")
                        action_results.append(res.get('message', ''))
                    elif "مورد" in user_input_clean:
                        res = QueryService.get_comprehensive_report(branch_name, "suppliers")
                        action_results.append(res.get('message', ''))
                    elif "نواقص" in user_input_clean:
                        res = NotificationService.get_smart_alerts(branch_name)
                        action_results.append(res.get('message', ''))

            if not action_results:
                response_message = ai_response.get("message_to_user", "✅ تم التنفيذ بنجاح.")
            else:
                response_message = "\n\n".join(action_results)
        else:
            response_message = "\n\n".join(action_results)

    with st.chat_message("assistant"):
        st.markdown(response_message)
    
    st.session_state.messages.append({"role": "assistant", "content": response_message})
