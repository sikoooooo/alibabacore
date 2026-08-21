import json
import google.generativeai as genai
from core.database import supabase

try:
    import streamlit as st
    # جمع كل مفاتيح الـ API المتاحة في الإعدادات السرية تلقائياً
    api_keys = []
    for key_name in ["GOOGLE_API_KEY", "GOOGLE_API_KEY_1", "GOOGLE_API_KEY_2", "GOOGLE_API_KEY_3", "GEMINI_API_KEY"]:
        val = st.secrets.get(key_name, "")
        if val and val not in api_keys:
            api_keys.append(val)
            
    # دعم صيغة السسلسلة المفصولة بفاصلة إن وجدت
    if "GOOGLE_API_KEYS" in st.secrets:
        extra_keys = st.secrets["GOOGLE_API_KEYS"].split(",")
        for k in extra_keys:
            k_clean = k.strip()
            if k_clean and k_clean not in api_keys:
                api_keys.append(k_clean)
except Exception:
    api_keys = []

if not api_keys:
    api_keys = [""] # مفتاح فارغ افتراضي

class AIService:
    current_key_index = 0

    @classmethod
    def get_model(cls):
        if api_keys:
            key = api_keys[cls.current_key_index % len(api_keys)]
            genai.configure(api_key=key)
        return genai.GenerativeModel('gemini-3.6-flash')

    @classmethod
    def smart_process_command(cls, user_text: str, branch: str, chat_history: list = None):
        """معالجة النص مع نظام التبديل التلقائي لمفاتيح API عند نفاد الكوته"""
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

        أخرج النتيجة ككود JSON حصرياً بدون أي نصوص أو شروحات خارجه:
        {{
            "type": "PURCHASE" أو "SALE" أو "QUERY" أو "INCOMPLETE",
            "item_name": "اسم الصنف إن وجد أو عام",
            "quantity": 1.0 (رقم فقط),
            "unit": "وحدة القياس أو غير محدد",
            "unit_price": 0.0 (رقم السعر إن وجد وإلا 0),
            "message_to_user": "رد احترافي باللغة العربية يوضح ما تم أو يجيب على الاستعلام مبدئياً"
        }}
        """
        
        max_retries = max(len(api_keys), 1)
        for attempt in range(max_retries):
            try:
                model = cls.get_model()
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
                        "message_to_user": "عذراً، لم أفهم تفاصيل طلبك بدقة. هل يمكنك التوضيح؟"
                    }
            except Exception as e:
                err_str = str(e)
                # إذا حدث خطأ حصة (429 أو quota أو limit)، انتقل للمفتاح التالي فوراً وجرب
                if "429" in err_str or "quota" in err_str.lower() or "limit" in err_str.lower():
                    cls.current_key_index = (cls.current_key_index + 1) % len(api_keys)
                    continue
                else:
                    return {
                        "type": "INCOMPLETE",
                        "item_name": "غير محدد",
                        "quantity": 1.0,
                        "unit": "وحدة",
                        "unit_price": 0.0,
                        "message_to_user": f"حدث خطأ أثناء معالجة الذكاء الاصطناعي: {err_str}"
                    }

        return {
            "type": "INCOMPLETE",
            "item_name": "غير محدد",
            "quantity": 1.0,
            "unit": "وحدة",
            "unit_price": 0.0,
            "message_to_user": "⚠️ تم استنفاد حصة جميع مفاتيح API المتاحة مؤقتاً. يرجى المحاولة بعد قليل."
        }
