import json
# التحديث الجديد: استخدام المكتبة الحديثة فقط لدعم المفاتيح الجديدة
from google import genai
from core.database import supabase

api_keys = [
    "AQ.Ab8RN6KsmZlOVBitqBHl9MTKvhDTCrOkLckSZOLq5opLxEM97g",
    "AQ.Ab8RN6IOOQs421k9-f9CtpYl-b7mKWe1ID2e-VODE8WbGDLy0g",
    "AQ.Ab8RN6LDnxPObId4PxP_7RWvXtPSekj6ftHZ6AIwiVKyVQso5Q",
    "AQ.Ab8RN6IXSRGUETheaRkxa2JuolYCfGIL-888kwz8J9-OfWZ4Gw",
    "AQ.Ab8RN6K7vSSUfuhGYpcuwDBFOwwFa_F5lj-nsNeWulqimXRBFA",
    "AQ.Ab8RN6KBRA7A1-2FeQ5dffRxP6OCTiAqzC5PPfJ59NAT7zNvIA",
    "AQ.Ab8RN6JVygUc808mR9xfWPrWau0zgvPT-Ak-1CCAARyDdMQRMA"
]

class AIService:
    current_key_index = 0

    @classmethod
    def get_client(cls):
        if api_keys:
            key = api_keys[cls.current_key_index % len(api_keys)]
            return genai.Client(api_key=key)
        return genai.Client()

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
        
        max_retries = max(len(api_keys), 1)
        for attempt in range(max_retries):
            try:
                client = cls.get_client()
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
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
                        "message_to_user": "عذراً، لم أفهم تفاصيل طلبك بدقة. هل يمكنك التوضيح؟"
                    }
            except Exception as e:
                err_str = str(e)
                if any(err in err_str.lower() for err in ["429", "quota", "limit", "401", "unauthorized", "token"]):
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
