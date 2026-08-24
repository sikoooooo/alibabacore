import json
import os
try:
    import streamlit as st
except ImportError:
    st = None

import google.generativeai as genai

api_keys = []
if st and hasattr(st, "secrets") and st.secrets:
    for secret_key, val in st.secrets.items():
        if val and isinstance(val, str) and (val.startswith("AIza") or val.startswith("AQ.") or len(val) > 20):
            if val not in api_keys:
                api_keys.append(val)

env_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if env_key and env_key not in api_keys:
    api_keys.append(env_key)

if not api_keys:
    api_keys = [""]

class AIService:
    current_key_index = 0

    # 🟢 بداية الدالة: smart_process_command (معالجة النص، الذاكرة، وحقول تحويل الوحدات)
    @classmethod
    def smart_process_command(cls, user_text: str, branch: str, branch_rules: list = None, chat_history: list = None):
        if chat_history is None: 
            chat_history = []
        if branch_rules is None:
            branch_rules = []
        
        # تجهيز الذاكرة القصيرة (آخر 4 رسائل)
        history_context = "\n".join([f"- {m['role']}: {m['content']}" for m in chat_history[-4:]]) if chat_history else "لا يوجد سياق سابق."
        
        prompt = f"""
        أنت المحاسب الذكي لنظام ERP. حلل كلام التاجر واستخرج بيانات المعاملة بالاعتماد على سياق المحادثة السابقة إذا كانت الرسالة استكمالاً لطلب سابق.
        قواعد الفرع: {branch_rules}
        
        سياق المحادثة السابقة (الذاكرة القصيرة):
        {history_context}

        رسالة التاجر الحالية: "{user_text}"

        🧠 قواعد الفهم (إجباري):
        1. الذاكرة والسياق: إذا كان الكلام استكمالاً لمعاملة سابقة (مثل تحديد سعر)، اربطه بالصنف والكمية في السياق السابق.
        2. الكمية والوحدة: استخرج الكمية والوحدة التي أذكرها التاجر بدقة (مثلاً: 10 كرتونة).
        3. تحويل الوحدات: إذا ذكر التاجر تعبئة الكرتونة أو العلبة (مثال: "الكرتونة 20 كيس")، استخرج:
           - `major_unit`: الوحدة الكبرى ("كرتونة").
           - `minor_unit`: الوحدة الصغرى ("كيس" أو "قطعة").
           - `conversion_factor`: معامل التحويل المذكور (مثلاً 20.0). إذا لم يذكر اجعله 1.0.
        4. التقسيط: إذا كانت العملية تقسيط أو آجل، اجعل `is_installment` تساوي true واستخرج المقدم (`down_payment`) وقيمة القسط (`installment_value`) وتاريخ الاستحقاق (`due_date`).
        5. لا تستخدم أي علامات تنصيص مزدوجة داخل قيم النصوص المرجعة لتجنب تلف الـ JSON.

        نسق المخرجات داخل هيكل JSON التالي حصرياً وبدون أي أوسمة إضافية:
        {{
            "type": "PURCHASE" | "SALE" | "QUERY" | "INCOMPLETE",
            "item_name": "اسم الصنف",
            "brand": "اسم الماركة أو غير محدد",
            "supplier": "اسم المورد/العميل أو غير محدد",
            "quantity": 1.0,
            "unit": "وحدة",
            "major_unit": "الوحدة الكبرى أو غير محدد",
            "minor_unit": "الوحدة الصغرى أو غير محدد",
            "conversion_factor": 1.0,
            "unit_price": 0.0,
            "is_installment": false,
            "down_payment": 0.0,
            "installment_value": 0.0,
            "due_date": "غير محدد",
            "message_to_user": "رد احترافي للتاجر يشرح تفاصيل المعاملة"
        }}
        """
        
        max_retries = max(len(api_keys), 1)
        last_error_msg = ""
        
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=500
        )

        for _ in range(max_retries):
            try:
                current_key = api_keys[cls.current_key_index % len(api_keys)]
                if not current_key:
                    break
                    
                genai.configure(api_key=current_key)
                
                # 🎯 نموذج gemini-3.5-flash-lite المعتمد
                model = genai.GenerativeModel('gemini-3.5-flash-lite', generation_config=generation_config)
                response = model.generate_content(prompt)
                
                raw_text = response.text.strip()
                
                # فلترة وتنظيف نصوص الماركداون المتبقية لضمان سلامة الـ JSON
                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_text = "\n".join(lines).strip()

                return json.loads(raw_text)
            except Exception as e:
                last_error_msg = str(e)
                cls.current_key_index = (cls.current_key_index + 1) % len(api_keys)
                continue

        return {
            "type": "INCOMPLETE",
            "item_name": "غير محدد",
            "brand": "غير محدد",
            "supplier": "غير محدد",
            "quantity": 1.0,
            "unit": "وحدة",
            "major_unit": "غير محدد",
            "minor_unit": "غير محدد",
            "conversion_factor": 1.0,
            "unit_price": 0.0,
            "is_installment": False,
            "down_payment": 0.0,
            "installment_value": 0.0,
            "due_date": "غير محدد",
            "message_to_user": f"⚠️ خطأ في المعالجة: {last_error_msg}"
        }
    # 🔴 نهاية الدالة: smart_process_command
