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

if not api_keys:
    api_keys = [""]

class AIService:
    current_key_index = 0

    @classmethod
    def smart_process_command(cls, user_text: str, branch: str, branch_rules: list = None, chat_history: list = None):
        if chat_history is None: 
            chat_history = []
        if branch_rules is None:
            branch_rules = []
        
        # 1. تجهيز الذاكرة القصيرة لدمجها داخل الـ Prompt
        history_context = "\n".join([f"- {m['role']}: {m['content']}" for m in chat_history[-4:]]) if chat_history else "لا يوجد سياق سابق."
        
        prompt = f"""
        أنت المحاسب الذكي لنظام ERP. حلل كلام التاجر واستخرج بيانات المعاملة بالاعتماد على سياق المحادثة السابقة إذا كانت الرسالة استكمالاً لطلب سابق.
        قواعد الفرع: {branch_rules}
        
        سياق المحادثة السابقة (الذاكرة القصيرة):
        {history_context}

        رسالة التاجر الحالية: "{user_text}"

        🧠 قواعد الفهم (إجباري):
        1. الذاكرة والسياق: إذا كان الكلام استكمالاً لمعاملة سابقة (مثل تحديد سعر)، اربطه بالصنف والكمية في السياق السابق.
        2. الكمية والوحدة: استخرج الكمية والوحدة كما ذكرها التاجر بدقة.
        3. التقسيط: إذا كانت العملية تقسيط أو آجل، اجعل `is_installment` تساوي true واستخرج المقدم (`down_payment`) وقيمة القسط (`installment_value`) وتاريخ الاستحقاق (`due_date`).

        نسق المخرجات داخل هيكل JSON التالي حصرياً:
        {{
            "type": "PURCHASE" | "SALE" | "QUERY" | "INCOMPLETE",
            "item_name": "اسم الصنف",
            "brand": "اسم الماركة أو غير محدد",
            "supplier": "اسم المورد/العميل أو غير محدد",
            "quantity": 1.0,
            "unit": "وحدة",
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
                model = genai.GenerativeModel('gemini-3.6-flash', generation_config=generation_config)
                response = model.generate_content(prompt)
                
                return json.loads(response.text.strip())
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
            "unit_price": 0.0,
            "is_installment": False,
            "down_payment": 0.0,
            "installment_value": 0.0,
            "due_date": "غير محدد",
            "message_to_user": f"⚠️ خطأ في المعالجة: {last_error_msg}"
        }
