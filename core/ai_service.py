import json
import os
try:
    import streamlit as st
except ImportError:
    st = None

import google.generativeai as genai

class AIService:
    current_key_index = 0

    @classmethod
    def smart_process_command(cls, user_text: str, branch: str, branch_rules: list = None, chat_history: list = None):
        if chat_history is None: 
            chat_history = []
        if branch_rules is None:
            branch_rules = []
        
        prompt = f"""
        أنت المحاسب الذكي لنظام ERP. حلل كلام التاجر وحدد نوع الطلب بدقة.
        قواعد الفرع: {branch_rules}
        رسالة التاجر: "{user_text}"

        🧠 قواعد الفهم والتصنيف:
        1. إذا كانت الرسالة تسجيل عملية شراء أو بيع بضاعة، اجعل `type` إما "PURCHASE" أو "SALE".
        2. إذا كانت الرسالة **سؤالاً أو استعلاماً** عن الأقساط، الديون، العملاء، أو المخزن (مثل: "موقف أقساط محمود الصاوي" أو "أقساط شهر 9")، اجعل `type` تساوي "QUERY".
        3. استخرج اسم العميل (`supplier` أو `customer_name`) إن وجد في نص الاستعلام.

        نسق المخرجات داخل هيكل JSON التالي حصرياً ودون أي نصوص إضافية:
        {{
            "type": "PURCHASE" | "SALE" | "QUERY" | "INCOMPLETE",
            "item_name": "اسم الصنف أو غير محدد",
            "brand": "غير محدد",
            "supplier": "اسم المورد أو العميل المستعلم عنه أو غير محدد",
            "quantity": 1.0,
            "unit": "وحدة",
            "unit_price": 0.0,
            "is_installment": false,
            "down_payment": 0.0,
            "installment_value": 0.0,
            "message_to_user": "رد احترافي أو توجيهي"
        }}
        """
        
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

        max_retries = max(len(api_keys), 1)
        last_error_msg = ""
        
        for _ in range(max_retries):
            try:
                current_key = api_keys[cls.current_key_index % len(api_keys)]
                if not current_key:
                    break
                    
                genai.configure(api_key=current_key)
                model = genai.GenerativeModel('gemini-3.5-flash-lite')
                response = model.generate_content(prompt)
                
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    if lines[0].startswith("```"): lines = lines[1:]
                    if lines and lines[-1].startswith("```"): lines = lines[:-1]
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
            "unit_price": 0.0,
            "is_installment": False,
            "down_payment": 0.0,
            "installment_value": 0.0,
            "message_to_user": f"⚠️ خطأ في المعالجة: {last_error_msg}"
        }
