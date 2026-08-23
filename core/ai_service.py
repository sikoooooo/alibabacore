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
        
        history_context = "\n".join([f"- {m['role']}: {m['content']}" for m in chat_history[-2:]]) if chat_history else "لا يوجد سياق."
        
        prompt = f"""
        أنت المحاسب الذكي لنظام ERP. حلل كلام التاجر واستخرج بيانات المعاملة.
        قواعد الفرع: {branch_rules}
        رسالة التاجر: "{user_text}"

        🧠 قواعد الفهم (إجباري):
        1. الكمية (`quantity`): احسب الإجمالي بالوحدة الصغرى دائماً. لو ذكر كراتين اضرب الرقمين.
        2. السعر (`unit_price`): سعر الوحدة الصغرى الواحدة فقط!
        3. المورد/العميل (`supplier`): استخرج اسم الشركة أو الشخص.
        4. الماركة (`brand`): استخرج اسم الماركة المصنعة.
        5. التقسيط (`is_installment`): إذا كانت العملية بيع بالتقسيط أو شراء آجل، اجعلها true واستخرج المقدم (`down_payment`) وقيمة القسط (`installment_value`).

        نسق المخرجات داخل هيكل JSON التالي حصرياً:
        {{
            "type": "PURCHASE" | "SALE" | "QUERY" | "INCOMPLETE",
            "item_name": "اسم الصنف",
            "brand": "اسم الماركة أو غير محدد",
            "supplier": "اسم المورد/العميل أو غير محدد",
            "quantity": 1.0,
            "unit": "الوحدة الصغرى",
            "unit_price": 0.0,
            "is_installment": false,
            "down_payment": 0.0,
            "installment_value": 0.0,
            "message_to_user": "رد احترافي يشرح الحسبة، الماركة، المورد، وتفاصيل التقسيط إن وجد"
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
                model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)
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
            "message_to_user": f"⚠️ خطأ في المعالجة: {last_error_msg}"
        }
