import json
import google.generativeai as genai
from core.database import supabase

try:
    import streamlit as st
    gemini_api_key = st.secrets.get("GOOGLE_API_KEY", "")
except Exception:
    gemini_api_key = ""

genai.configure(api_key=gemini_api_key)

class AIService:
    @staticmethod
    def get_model():
        return genai.GenerativeModel('gemini-3.6-flash')

    @classmethod
    def smart_process_command(cls, user_text: str, branch: str, chat_history: list = None):
        """معالجة النص مع دعم الذاكرة القصيرة للتاجر واستعلامات المخزون الذكية"""
        if chat_history is None: 
            chat_history = []
        
        try:
            rules_res = supabase.table("business_rules").select("*").eq("branch", branch).execute()
            known_rules = rules_res.data if rules_res.data else []
        except Exception:
            known_rules = []
            
        # تجهيز سياق المحادثة السابقة (الذاكرة القصيرة)
        history_context = "\n".join([f"- {msg['role']}: {msg['content']}" for msg in chat_history[-3:]]) if chat_history else "لا يوجد سياق سابق."
        
        model = cls.get_model()
        prompt = f"""
        أنت مساعد محاسبي ذكي لنظام ERP. مهمتك تحليل كلام التاجر واستخراج بيانات المعاملة أو الاستعلام بدقة.
        قواعد ومعلومات الفرع المعروفة: {known_rules}
        سياق آخر رسائل بينك وبين التاجر (استخدمه لفهم المقصد إذا كان الكلام مختصراً مثل "حط 5 كمان"):
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
        
        try:
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
            return {
                "type": "INCOMPLETE",
                "item_name": "غير محدد",
                "quantity": 1.0,
                "unit": "وحدة",
                "unit_price": 0.0,
                "message_to_user": f"حدث خطأ أثناء معالجة الذكاء الاصطناعي: {str(e)}"
            }
