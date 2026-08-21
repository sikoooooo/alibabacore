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
        """معالجة النص مع دعم الذاكرة القصيرة للتاجر"""
        if chat_history is None: chat_history = []
        
        try:
            rules_res = supabase.table("business_rules").select("*").eq("branch", branch).execute()
            known_rules = rules_res.data if rules_res.data else []
        except:
            known_rules = []
            
        # تجهيز سياق المحادثة السابقة (الذاكرة القصيرة)
        history_context = "\n".join([f"- {msg['role']}: {msg['content']}" for msg in chat_history[-3:]]) if chat_history else "لا يوجد سياق سابق."
        
        model = cls.get_model()
        prompt = f"""
        أنت محاسب ذكي لنظام ERP.
        سياق آخر رسائل بينك وبين التاجر (استخدمه لفهم المقصد إذا كان الكلام مختصراً مثل "حط 5 كمان"):
        {history_context}
        
        الجملة الجديدة للتاجر الآن: "{user_text}"
        قواعد التحويل المحفوظة للفرع: {json.dumps(known_rules, ensure_ascii=False)}
        
        بناءً على السياق والجملة الجديدة، استخرج العملية.
        يجب أن يكون ردك بصيغة JSON نقي فقط:
        {{"type": "SALE أو PURCHASE أو QUERY", "item_name": "اسم الصنف", "quantity": رقم, "unit": "وحدة القياس", "unit_price": رقم, "message_to_user": "رد تأكيدي"}}
        """
        response = model.generate_content(prompt)
        try:
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception:
            return {"type": "QUERY", "item_name": user_text, "quantity": 1, "unit": "قطعة", "unit_price": 0, "message_to_user": "تم الاستلام"}
