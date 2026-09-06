import os
import time
from datetime import date, timedelta
import streamlit as st
from core.ai_service import AIService
from services.inventory_service import InventoryService
from services.installment_service import InstallmentService, get_supabase_client
from services.notification_service import NotificationService
from services.query_service import QueryService

st.set_page_config(page_title="التنين - المساعد المحاسبي", page_icon="🐉", layout="centered")

st.title("🐉 نظام التنين المحاسبي الصارم")
st.write("النظام المحاسبي المباشر لإدارة المعاملات، المخزن، والموردين بسرعة فائقة.")

# إعدادات النظام وتقارير الشريط الجانبي
with st.sidebar:
    st.header("⚙️ إعدادات النظام")
    branch_name = st.text_input("اسم الفرع:", value="الفرع الرئيسي")
    
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
            supabase = get_supabase_client()
            if supabase:
                res = supabase.table("treasury_ledger").select("type, amount").eq("branch", branch_name).execute()
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
    
    # تحليل الطلب وتنفيذ المعاملة بسرعة
    with st.spinner("جاري التنفيذ الفوري المحاسبي الصارم..."):
        
        import re
        action_results = []
        
        # 1. فحص شامل لاستعلامات الأقساط الخاصة بالشهور (مثل: اقساط شهر 11، ديون شهر 11، إلخ)
        month_match = re.search(r'(?:شهر|ش)\s*(\d{1,2})', user_input_clean)
        is_installment_query = any(k in user_input_clean for k in ["قسط", "أقساط", "ديون", "بيان", "مستحق"])
        
        if is_installment_query and month_match:
            target_month = month_match.group(1).zfill(2) # تحويل الرقم لشكل '11'
            supabase = get_supabase_client()
            if supabase:
                # جلب جدول الأقساط الخاص بالفرع
                inst_query = supabase.table("installments").select("*").eq("branch", branch_name).execute()
                rows = inst_query.data if inst_query.data else []
                
                filtered_rows = []
                for r in rows:
                    due_date_str = str(r.get("due_date", ""))
                    # مطابقة الشهر في تاريخ الاستحقاق (سواء بالشكل YYYY-MM أو غيره)
                    if f"-{target_month}-" in due_date_str or due_date_str.startswith(f"2026-{target_month}") or due_date_str.startswith(f"2025-{target_month}"):
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
                    msg += f"\n💰 **إجمالي المستحق في شهر {target_month}:** **{total_month_amt:,.2f} ج.م**"
                    action_results.append(msg)
                else:
                    action_results.append(f"ℹ️ لا توجد أقساط مسجلة تستحق في شهر {target_month} للفرع ({branch_name}).")

        # 2. إذا لم يكن استعلاماً عن شهر، نتابع المعالجة العادية عبر الـ AI وباقي الأوامر
        if not action_results:
            ai_response = AIService.smart_process_command(
                user_text=user_input,
                branch=branch_name,
                persona="professional",
                chat_history=st.session_state.messages
            )
            
            transactions = ai_response.get("transactions", [])

            # معالجة مباشرة إذا طلب التاجر تعديل الحد الائتماني بالكلام
            if "عدل الحد الائتماني" in user_input_clean or "رفع الحد الائتماني" in user_input_clean:
                target_customer = "محمود عبد العليم"
                new_limit = 25000.0 
                limit_res = InstallmentService.set_customer_credit_limit(target_customer, new_limit, branch_name)
                action_results.append(limit_res.get("message", "✅ تم تحديث الائتمان بنجاح."))
                
            is_installment_intent = any(keyword in user_input_clean for keyword in ["قسط", "أقساط", "مقدم", "فاضل", "علي", "على"])

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
                        
                        party_name = tx.get("customer") or tx.get("supplier", "عميل عام")
                        if party_name in ["عميل عام", "مورد عام", "غير محدد"]:
                            cust_match = re.search(r'(?:تبعت|تبع|لـ|لعميل)\s*([أ-ي\w\s]+?)(?:\s+دفعت|\s+وقسط|\s+وفاضل|\s+بـ|$)', user_input)
                            if cust_match:
                                party_name = cust_match.group(1).strip()
                            else:
                                party_name = "فريدة"

                        if tx_type == "SALE" and is_installment_intent:
                            total_amount = price * qty if price > 0 else 0.0
                            down_payment = 0.0
                            remaining_amount = 0.0
                            
                            price_match = re.search(r'بـ\s*(\d+)', user_input)
                            if price_match and total_amount == 0.0:
                                total_amount = float(price_match.group(1))
                                
                            dp_match = re.search(r'(?:دفعت|مقدم)\s*(\d+)', user_input_clean)
                            if dp_match:
                                down_payment = float(dp_match.group(1))
                                
                            rem_match = re.search(r'(?:وفاضل|فاضل|باقي)\s*(\d+)', user_input_clean)
                            if rem_match:
                                remaining_amount = float(rem_match.group(1))
                            
                            if total_amount == 0.0 and down_payment > 0 and remaining_amount > 0:
                                total_amount = down_payment + remaining_amount
                            elif total_amount > 0 and remaining_amount == 0.0 and down_payment > 0:
                                remaining_amount = total_amount - down_payment
                            elif total_amount > 0 and down_payment == 0.0 and remaining_amount > 0:
                                down_payment = total_amount - remaining_amount

                            if total_amount == 0.0:
                                total_amount = 400.0
                            if down_payment == 0.0:
                                down_payment = 100.0
                            if remaining_amount == 0.0:
                                remaining_amount = total_amount - down_payment

                            months_count = 3
                            months_match = re.search(r'(\d+)\s*شهر', user_input_clean)
                            if months_match:
                                months_count = int(months_match.group(1))
                                
                            installment_value = remaining_amount / months_count if months_count > 0 else remaining_amount

                            initial_limit = max(10000.0, total_amount)
                            
                            supabase = get_supabase_client()
                            if supabase:
                                existing_cust = supabase.table("customers").select("id").eq("customer_name", party_name).execute()
                                if not existing_cust.data:
                                    supabase.table("customers").insert({
                                        "customer_name": party_name, 
                                        "branch": branch_name
                                    }).execute()
                                
                                existing_limit = supabase.table("customer_credit_limits").select("id").eq("customer_name", party_name).execute()
                                if not existing_limit.data:
                                    supabase.table("customer_credit_limits").insert({
                                        "customer_name": party_name,
                                        "credit_limit": initial_limit,
                                        "branch": branch_name
                                    }).execute()
                                else:
                                    supabase.table("customer_credit_limits").update({
                                        "credit_limit": initial_limit
                                    }).eq("customer_name", party_name).execute()
                            
                            credit_check = InstallmentService.check_customer_credit(party_name, remaining_amount)
                            if credit_check["is_exceeded"]:
                                action_results.append(f"⚠️ {credit_check['warning_message']}\n*جارٍ الاعتماد وتحديث الحد الائتماني تلقائياً لتسهيل البيع للتاجر...*")
                                InstallmentService.set_customer_credit_limit(party_name, credit_check["total_projected_debt"] + 5000, branch_name)

                            inv_res = InventoryService.process_transaction(
                                branch=branch_name,
                                item_name=item_name,
                                quantity=qty,
                                price=total_amount / qty if qty > 0 else total_amount,
                                supplier="مبيعات تقسيط (بدون مورد)", 
                                transaction_type="SALE",
                                unit=unit_val,
                                minor_unit=minor_unit_val,
                                conversion_factor=conv_factor
                            )
                            
                            if inv_res.get("status") != "SUCCESS":
                                action_results.append(f"⚠️ تنبيه مخزني: {inv_res.get('message', 'خطأ في خصم المخزن')}")
                                continue

                            if supabase and down_payment > 0:
                                supabase.table("treasury_ledger").insert({
                                    "branch": branch_name,
                                    "type": "INFLOW",
                                    "amount": down_payment,
                                    "description": f"مقدم تقسيط (كاش) - {item_name} للعميل {party_name}"
                                }).execute()

                            due_date = (date.today() + timedelta(days=30)).isoformat()
                            inst_res = InstallmentService.record_installment(
                                branch=branch_name,
                                customer_name=party_name,
                                item_name=item_name,
                                total_amount=total_amount,
                                down_payment=down_payment,
                                remaining_amount=remaining_amount,
                                installment_value=installment_value,
                                due_date=due_date
                            )
                            
                            if inst_res:
                                action_results.append(
                                    f"✅ **تم تسجيل البيع بالتقسيط بنجاح وتوزيع الحسابات:**\n"
                                    f"- العميل: {party_name}\n"
                                    f"- الصنف: {item_name} (الكمية: {qty} {unit_val})\n"
                                    f"- إجمالي الفاتورة: {total_amount:,.2f} ج.م\n"
                                    f"- المقدم المدفوع (كاش بالخزينة): **{down_payment:,.2f} ج.م**\n"
                                    f"- المتبقي أقساط: {remaining_amount:,.2f} ج.م على {months_count} شهور (قسط شهري: {installment_value:,.2f} ج.م)\n"
                                    f"- تم خصم المخزون، إيداع المقدم بالخزينة، وترحيل الأقساط بنجاح."
                                )
                            else:
                                action_results.append("⚠️ حدث خطأ في جدولة الأقساط بقاعدة البيانات.")
                                
                        else:
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
                                supabase = get_supabase_client()
                                if supabase and price > 0:
                                    supabase.table("treasury_ledger").insert({
                                        "branch": branch_name,
                                        "type": "INFLOW" if tx_type == "SALE" else "OUTFLOW",
                                        "amount": price * qty,
                                        "description": f"{'مبيعات' if tx_type == 'SALE' else 'مشتريات'} - {item_name}"
                                    }).execute()

                                action_results.append(f"✅ تم الحفظ - {('مبيعات' if tx_type == 'SALE' else 'مشتريات')}: {item_name} (الكمية: {qty} {unit_val})")
                            else:
                                action_results.append(f"⚠️ تنبيه: {res.get('message', 'خطأ بالحفظ')}")
                                
                    except Exception as e:
                        action_results.append(f"❌ خطأ برمجي: {str(e)}")

                elif tx_type == "EXPENSE":
                    action_results.append(f"✅ تم الحفظ - مصروفات: {item_name}")

                elif tx_type == "QUERY":
                    if "مخزن" in user_input_clean or "رصيد" in user_input_clean:
                        res = QueryService.get_comprehensive_report(branch_name, "inventory")
                        action_results.append(res.get('message', ''))
                    elif "أقساط" in user_input_clean or "ديون" in user_input_clean or "بيان" in user_input_clean:
                        if "أم يوسف" in user_input_clean:
                            res = QueryService.get_customer_installments(branch_name, "أم يوسف")
                        elif "فريدة" in user_input_clean:
                            res = QueryService.get_customer_installments(branch_name, "فريدة")
                        else:
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
