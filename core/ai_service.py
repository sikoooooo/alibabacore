import json
import os
try:
    import streamlit as st
except ImportError:
    st = None

import google.generativeai as genai
from core.database import supabase

# سحب المفاتيح بمرونة شديدة من الـ Secrets
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
    def smart_process_command(cls, user_text: str, branch: str, chat_history: list = None):
        if chat_history is None: 
            chat_history = []
        
        try:
            rules_res = supabase.table("business_rules").select("*").eq("branch", branch).execute()
            known_rules = rules_res.data if rules_res.data else []
        except Exception:
            known_rules = []
            
        history_context = "\n".join([f"- {msg['role']}: {msg['content']}" for msg in chat_history[-3:]]) if chat_history else "لا يوجد سياق سابق."
        
        prompt = f"""
        أنت محاسب ذكي لنظام ERP متطور. مهمتك تحليل كلام التاجر واستخراج بيانات المعاملة أو الاستعلام بدقة.
        قواعد ومعلومات الفرع المعروفة: {known_rules}
        سياق آخر رسائل بينك وبين التاجر:
        {history_context}

        الرسالة الحالية من المستخدم: "{user_text}"

        صنف الرسالة بدقة إلى أحد الأنواع التالية:
        - "PURCHASE" (شراء بضاعة أو إدخال وارد للمخزن)
        - "SALE" (بيع بضاعة أو إخراج من المخزن)
        - "QUERY" (استعلام عن رصيد صنف، بضاعة، حالة المخزن، أو تقارير)
        - "INCOMPLETE" (بيانات ناقصة تماماً)

        ⚠️ **قواعد حاسمة وحازمة لمعالجة الكراتين والوحدات والأسعار (نظام الوحدة الصغرى):**
        1. **حساب الكمية (`quantity`):** يجب أن تكون قيمة `quantity` دائماً محسوبة بالوحدة الصغرى الأساسية (كيس، زجاجة، علبة، قطعة، باكو).
           - إذا ذكر المستخدم الشراء أو البيع بالكرتونة (مثلاً: 10 كراتين، الكرتونة 12 كيس)، اضرب عدد الكراتين في سعة الكرتونة إجبارياً وأخرج الناتج النهائي: `quantity: 120`.
           - إذا لم يحدد سعة الكرتونة، افترض افتراضياً أن الكرتونة = 12 وحدة صغرى.
        2. **اسم الصنف (`item_name`):** استخرج اسم الصنف مجرداً تماماً بدون ذكر أعداد الكراتين (مثلاً: "مكرونة قلم" وليس "10 كراتين مكرونة").
        3. **سعر الوحدة (`unit_price`):** يجب أن يكون سعر الوحدة الصغرى الواحدة فقط!
           - إذا ذكر إجمالي المبلغ (مثلاً: 10000 جنيه لـ 10 كراتين كل كرتونة 12 كيس -> الإجمالي 120 كيس)، اقسم الإجمالي على إجمالي الأكياس (`10000 / 120 = 83.33`).
           - إذا ذكر سعر الكرتونة (مثلاً: الكرتونة بـ 1200 جنيه وسعتها 12 كيس)، اقسم سعر الكرتونة على أكياسها (`1200 / 12 = 100`).
        4. **إياك أن ترسل عدد الكراتين كـ quantity أو سعر الكرتونة كـ unit_price.**

        أخرج النتيجة ككود JSON حصرياً بدون أي نصوص أو شروحات خارجه:
        {{
            "type": "PURCHASE" أو "SALE" أو "QUERY" أو "INCOMPLETE",
            "item_name": "اسم الصنف مجرداً",
            "quantity": 1.0 (رقم فقط يمثل إجمالي الأكياس/القطع الصغرى),
            "unit": "الوحدة الصغرى (كيس / زجاجة / علبة / قطعة)",
            "unit_price": 0.0 (تكلفة الوحدة الصغرى الواحدة بالجنيه),
            "message_to_user": "رد احترافي يوضح التفكيك والعملية الحسابية التي تمت بالكامل"
        }}
        """
        
        max_retries = max(len(api_keys), 1)
        last_error_msg = ""
        
        for _ in range(max_retries):
            try:
                current_key = api_keys[cls.current_key_index % len(api_keys)]
                if not current_key:
                    return {
                        "type": "INCOMPLETE",
                        "item_name": "غير محدد",
                        "quantity": 1.0,
                        "unit": "وحدة",
                        "unit_price": 0.0,
                        "message_to_user": "⚠️ تنبيه: لم يتم العثور على أي مفاتيح API في إعدادات الأسرار (Secrets) على Streamlit."
                    }
                    
                genai.configure(api_key=current_key)
                
                model = genai.GenerativeModel('gemini-3.6-flash')
                response = model.generate_content(prompt)
                
                clean_text = response.text.replace("```json", "").replace("```", "").strip()
                
                start_idx = clean_text.find('{')
                end_idx = clean_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = clean_text[start_idx:end_idx+1]
                    return json.loads(json_str)
                else:
                    return {
                        "type": "INCOMPLETE",
                        "item_name": "غير محدد",
                        "quantity": 1.0,
                        "unit": "وحدة",
                        "unit_price": 0.0,
                        "message_to_user": "عذراً، لم أفهم تفاصيل طلبك بدقة."
                    }
            except Exception as e:
                err_str = str(e)
                last_error_msg = err_str
                cls.current_key_index = (cls.current_key_index + 1) % len(api_keys)
                continue

        return {
            "type": "INCOMPLETE",
            "item_name": "غير محدد",
            "quantity": 1.0,
            "unit": "وحدة",
            "unit_price": 0.0,
            "message_to_user": f"⚠️ خطأ في المصادقة أو التنفيذ: {last_error_msg}"
        }
