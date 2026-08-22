import json
import os
try:
    import streamlit as st
except ImportError:
    st = None

import google.generativeai as genai
from core.database import supabase

# 🔑 قائمة مفاتيح الـ API
api_keys = [
    "AQ.Ab8RN6I6hnoEy5aNRBFLo00dNpr_tE6tkZLRpkWb0nfgpVzr2w",
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
        
        # تجربة المفاتيح بشكل مباشر ومنظم
        for _ in range(len(api_keys)):
            try:
                current_key = api_keys[cls.current_key_index % len(api_keys)]
                genai.configure(api_key=current_key)
                
                model = genai.GenerativeModel('gemini-1.5-flash')
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
                print(f"⚠️ خطأ مع المفتاح الحالي (Index {cls.current_key_index}): {err_str}")
                
                # الانتقال للمفتاح التالي في حال حدوث خطأ حقيقي في الـ Quota أو الصلاحية
                if any(err in err_str.lower() for err in ["429", "quota", "limit", "resourceexhausted", "unauthorized"]):
                    cls.current_key_index = (cls.current_key_index + 1) % len(api_keys)
                    continue
                else:
                    # لو الخطأ بسبب صياغة الرد أو شيء آخر، نرجع تفاصيل الخطأ بدلاً من رسالة الاستنفاد الوهمية
                    return {
                        "type": "INCOMPLETE",
                        "item_name": "غير محدد",
                        "quantity": 1.0,
                        "unit": "وحدة",
                        "unit_price": 0.0,
                        "message_to_user": f"حدث خطأ تقني في المعالجة: {err_str}"
                    }

        return {
            "type": "INCOMPLETE",
            "item_name": "غير محدد",
            "quantity": 1.0,
            "unit": "وحدة",
            "unit_price": 0.0,
            "message_to_user": "⚠️ عذراً، تعذر تنفيذ الطلب باستخدام المفاتيح الحالية."
        }
