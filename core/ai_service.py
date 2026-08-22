import json
import os
try:
    import streamlit as st
except ImportError:
    st = None

from google import genai
from core.database import supabase

# 🔑 قائمة مفاتيح الـ API مباشرة داخل الكود (بدون سيكريت)
api_keys = [
    "AQ.Ab8RN6KsmZlOVBitqBHl9MTKvhDTCrOkLckSZOLq5opLxEM97g",
    "AQ.Ab8RN6IOOQs421k9-f9CtpYl-b7mKWe1ID2e-VODE8WbGDLy0g",
    "AQ.Ab8RN6LDnxPObId4PxP_7RWvXtPSekj6ftHZ6AIwiVKyVQso5Q",
    "AQ.Ab8RN6IXSRGUETheaRkxa2JuolYCfGIL-888kwz8J9-OfWZ4Gw",
    "AQ.Ab8RN6K7vSSUfuhGYpcuwDBFOwwFa_F5lj-nsNeWulqimXRBFA",
    "AQ.Ab8RN6LTwEmXPjHD7K7HX_U8leyMSkkLOIwo7VNff3FLn3PKQA"
]

class AIService:
    current_key_index = 0

    @classmethod
    def get_client(cls):
        # اختيار المفتاح الحالي بناءً على المؤشر بالدور (Round-Robin)
        key = api_keys[cls.current_key_index % len(api_keys)] if api_keys else ""
        
        # تمرير المفتاح بوضوح لعميل جيميني
        if key:
            return genai.Client(api_key=key)
        raise ValueError("No API keys found in the pool.")

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
        
        max_retries = len(api_keys)
        for attempt in range(max_retries):
            try:
                client = cls.get_client()
                
                # استخدام الموديل المطلوب بدقة
                response = client.models.generate_content(
                    model='gemini-3.6-flash',  # أو gemini-3.6-flash حسب المتاح في SDK لديك
                    contents=prompt
                )
                
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
                # إذا حدث خطأ استنفاد حصة أو خطأ في المفتاح، ننتقل للمفتاح التالي تلقائياً
                if any(err in err_str.lower() for err in ["429", "quota", "limit", "401", "unauthorized", "token", "not found", "400", "no api key"]):
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
            "message_to_user": "⚠️ تم استنفاد حصة جميع مفاتيح API المتاحة مؤقتاً، برجاء المحاولة بعد قليل."
        }
