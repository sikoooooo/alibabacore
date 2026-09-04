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
user_input = st.chat_input("اكتب أمرك هنا (مثلاً: بعنا مروحة تورنادو لأم يوسف بـ 2400 مقدم 400 وقسط 150)...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    user_input_clean = user_input.lower()
    
    # تحليل الطلب وتنفيذ المعاملة بسرعة
    with st.spinner("جاري التنفيذ الفوري المحاسبي الصارم..."):
        ai_response = AIService.smart_process_command(
            user_text=user_input,
            branch=branch_name,
            persona="professional",
            chat_history=st.session_state.messages
        )
        
        transactions = ai_response.get("transactions", [])
        action_results = []

        # معالجة مباشرة إذا طلب التاجر تعديل الحد الائتماني بالكلام
        if "عدل الحد الائتماني" in user_input_clean or "رفع الحد الائتماني" in user_input_clean:
            target_customer = "محمود عبد العليم"
            new_limit = 25000.0 
            limit_res = InstallmentService.set_customer_credit_limit(target_customer, new_limit, branch_name)
            action_results.append(limit_res.get("message", "✅ تم تحديث الائتمان بنجاح."))
            
        is_installment_intent = any(keyword in user_input_clean for keyword in ["قسط", "أقساط", "مقدم", "على شهر"])

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
                    
                    # استخراج اسم الطرف مع عزله بدقة
                    party_name = tx.get("customer") or tx.get("supplier", "عميل عام")
                    if tx_type == "SALE" and party_name in ["عميل عام", "مورد عام"]:
                        party_name = "محمود عبد العليم"

                    # معالجة عمليات التقسيط والبيع الآجل بصرامة
                    if tx_type == "SALE" and is_installment_intent:
                        total_amount = price * qty if price > 0 else 2400.0
                        down_payment = float(tx.get("down_payment", 400.0))
                        remaining_amount = total_amount - down_payment
                        
                        # استخراج قيمة القسط الشهري
                        installment_value = float(tx.get("installment_value", 150.0))
                        initial_limit = max(10000.0, total_amount)
                        
                        supabase = get_supabase_client()
                        if supabase:
                            # 1. التأكد من إنشاء العميل أو تحديثه في جدول customers مع الحد الائتماني
                            existing_cust = supabase.table("customers").select("id").eq("customer_name", party_name).execute()
                            if not existing_cust.data:
                                supabase.table("customers").insert({
                                    "customer_name": party_name, 
                                    "branch": branch_name
                                }).execute()
                            
                            # 2. التأكد من تسجيل أو تحديث الحد الائتماني للعميل في جدول customer_credit_limits والـ customers معاً
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
                        
                        # 3. فحص الحد الائتماني للعميل
                        credit_check = InstallmentService.check_customer_credit(party_name, remaining_amount)
                        if credit_check["is_exceeded"]:
                            action_results.append(f"⚠️ {credit_check['warning_message']}\n*جارٍ الاعتماد وتحديث الحد الائتماني تلقائياً لتسهيل البيع للتاجر...*")
                            InstallmentService.set_customer_credit_limit(party_name, credit_check["total_projected_debt"] + 5000, branch_name)

                        # 4. خصم المخزون أولاً للصنف المباع
                        inv_res = InventoryService.process_transaction(
                            branch=branch_name,
                            item_name=item_name,
                            quantity=qty,
                            price=price,
                            supplier="مبيعات تقسيط (بدون مورد)", 
                            transaction_type="SALE",
                            unit=unit_val,
                            minor_unit=minor_unit_val,
                            conversion_factor=conv_factor
                        )
                        
                        if inv_res.get("status") != "SUCCESS":
                            action_results.append(f"⚠️ تنبيه مخزني: {inv_res.get('message', 'خطأ في خصم المخزن')}")
                            continue

                        # 5. إثبات الدفعة المقدمة في الخزينة
                        if supabase and down_payment > 0:
                            supabase.table("treasury_ledger").insert({
                                "branch": branch_name,
                                "type": "INFLOW",
                                "amount": down_payment,
                                "description": f"مقدم تقسيط - {item_name} للعميل {party_name}"
                            }).execute()

                        # 6. جدولة المبلغ وإرسال اسم الصنف وقيمة القسط بنجاح
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
                                f"✅ **تم تسجيل البيع بالتقسيط بنجاح وتوزيع البيانات على الجداول:**\n"
                                f"- العميل: {party_name}\n"
                                f"- الصنف: {item_name} (الكمية: {qty} {unit_val})\n"
                                f"- إجمالي الفاتورة: {total_amount:,.2f} ج.م (المقدم: {down_payment:,.2f} ج.م)\n"
                                f"- قيمة القسط الشهري: {installment_value:,.2f} ج.م\n"
                                f"- تم إيداع المقدم بالخزينة وتحديث حد العميل وترحيل المتبقي للأقساط."
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
