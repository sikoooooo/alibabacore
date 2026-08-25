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

env_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if env_key and env_key not in api_keys:
    api_keys.append(env_key)

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
        
        # تجهيز الذاكرة القصيرة (آخر 4 رسائل)
        history_context = "\n".join([f"- {m['role']}: {m['content']}" for m in chat_history[-4:]]) if chat_history else "لا يوجد سياق سابق."
        
        prompt = f"""
        أنت المحاسب الذكي ومدير المخزون لنظام ERP. مهمتك تحليل كلام التاجر واستخراج بيانات المعاملة أو الاستعلام بدقة محاسبية صارمة.
        قواعد الفرع: {branch_rules}
        
        سياق المحادثة السابقة (الذاكرة القصيرة):
        {history_context}

        رسالة التاجر الحالية: "{user_text}"

        🧠 قواعد التصنيف والفهم الصارمة (إجباري):

        1. تصنيف نوع المعاملة (`type`):
           - "QUERY": عند السؤال عن المخزون أو الرصيد المتبقي (أمثلة: "عندنا كام...", "كم متبقي من...", "رصيد ال...", "فيه كام طقم/قطعة...").
           - "PURCHASE": عند عمليات الشراء أو التوريد للمخزن (أمثلة: "اشترينا", "وصلنا", "دخل المخزن").
           - "SALE": عند عمليات البيع أو الخروج من المخزن (أمثلة: "بعنا", "طلعنا", "خرج").
           - "UPDATE_PRICE": فقط إذا كانت الرسالة رداً مباشراً لتحديد سعر معاملة معلقة سابقة (مثال: "سعر الكيس 9 جنيه").
           - "INCOMPLETE": إذا كانت الرسالة غامضة أو غير مفهومة محاسبياً.

        2. فصل الفئات والأحجام المميزة (SKU Differentiation):
       - يمنع تماماً دمج فئات مختلفة تحت اسم عام واحد لحماية متوسط التكلفة.
       - إذا ذكر التاجر فئة سعرية أو حجماً/مقاساً (مثال: شيبسي أبو 5، شيبسي أبو 10، كاوتش مقاس 16)، اجعل الفئة/المقاس جزءاً أساسياً من `item_name`.
       - أمثلة:
         * "اشتريت كرتونة شيبسي أبو 5" -> item_name: "شيبسي (فئة 5 ج)"
         * "بعنا 2 كرتونة شيبسي أبو 10" -> item_name: "شيبسي (فئة 10 ج)"
         * "اشترينا طقم كاوتش بريلي 16" -> item_name: "كاوتش بريلي مقاس 16"

        3. استخراج الوحدات والتحويلات الافتراضية (Conversion Factors):
           - إذا ذكر العبوة والتعبئة صراحة (مثل: "10 كرتونة والكرتونة 20 كيس"):
             * `quantity`: 10.0 | `unit`: "كرتونة" | `major_unit`: "كرتونة" | `minor_unit`: "كيس" | `conversion_factor`: 20.0
           - إذا ذكر وحدة كبرى (كرتونة، طقم، دستة) ولم يذكر التعبئة بداخلها:
             * طقم (كاوتش/أدوات) -> conversion_factor: 4.0 | minor_unit: "فردة" (أو قطعة)
             * دستة -> conversion_factor: 12.0 | minor_unit: "قطعة"
             * كرتونة (سناكس/شيبسي) -> conversion_factor: 12.0 | minor_unit: "كيس"
             * كرتونة (معلبات/مشروبات) -> conversion_factor: 24.0 | minor_unit: "علبة"
             * افتراضي عام للكرتونة -> conversion_factor: 12.0

        4. حظر هلوسة الأسعار والتعامل مع السعر المفقود:
           - لا تسحب أي سعر من المحادثات السابقة لمعاملة جديدة إطلاقاً. إذا لم يذكر السعر صراحة الآن، اجعل `unit_price` = 0.0.
           - إذا كان السعر 0.0 في عملية شراء/بيع، اكتب في `message_to_user` أنه تم تسجيل الكمية وفي انتظار السعر لتسوية الفاتورة.

        5. التقسيط والآجل:
           - إذا كانت المعاملة آجل أو تقسيط، اجعل `is_installment` = true واستخرج المقدم (`down_payment`) وقيمة القسط (`installment_value`) وتاريخ الاستحقاق (`due_date`).

        6. تنسيق النصوص:
           - تجنب استخدام علامات التنصيص المزدوجة داخل قيم النصوص المرجعة لتفادي تلف هيكل JSON.

        نسق المخرجات داخل هيكل JSON التالي حصرياً وبدون أي أوسمة markdown أو نصوص خارجية:
        {{
            "type": "PURCHASE" | "SALE" | "QUERY" | "INCOMPLETE" | "UPDATE_PRICE",
            "item_name": "اسم الصنف مميزاً بالفئة السعرية أو المقاس",
            "brand": "اسم الماركة أو غير محدد",
            "supplier": "اسم المورد/العميل أو غير محدد",
            "quantity": 1.0,
            "unit": "وحدة",
            "major_unit": "الوحدة الكبرى أو غير محدد",
            "minor_unit": "الوحدة الصغرى أو غير محدد",
            "conversion_factor": 1.0,
            "unit_price": 0.0,
            "is_installment": false,
            "down_payment": 0.0,
            "installment_value": 0.0,
            "due_date": "غير محدد",
            "message_to_user": "رد احترافي للتاجر يوضح ما تم بدقة"
        }}
        """
        
        max_retries = max(len(api_keys), 1)
        last_error_msg = ""
        
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,
            max_output_tokens=500
        )

        for _ in range(max_retries):
            try:
                current_key = api_keys[cls.current_key_index % len(api_keys)]
                if not current_key:
                    break
                    
                genai.configure(api_key=current_key)
                
                # استخدام اسم الموديل المستقر والأسرع في معالجة البيانات النصية
                model = genai.GenerativeModel('gemini-3.5-flash-lite', generation_config=generation_config)
                response = model.generate_content(prompt)
                
                raw_text = response.text.strip()
                
                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
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
            "major_unit": "غير محدد",
            "minor_unit": "غير محدد",
            "conversion_factor": 1.0,
            "unit_price": 0.0,
            "is_installment": False,
            "down_payment": 0.0,
            "installment_value": 0.0,
            "due_date": "غير محدد",
            "message_to_user": f"⚠️ خطأ في المعالجة: {last_error_msg}"
        }
