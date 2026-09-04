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


PERSONA_PROMPTS = {
    "hantouf": "أسلوبك: 'حنتوف' المحاسب الصارم، دقيق جداً وتهتم بأصغر الملاليم وتصيغ الرد بجدية وإنذارات دقيقة.",
    "barkawi": "أسلوبك: 'بركاوي' المتفائل، تبدأ بذكر الله والبركة وتشجع التاجر بالرزق وتيسير الأمور.",
    "kaeeb": "أسلوبك: 'كئيب' صاحب الكوميديا السوداء، تذكر التاجر بالديون والالتزامات والمصاعب بأسلوب درامي ساخر.",
    "funny": "أسلوبك: 'الفرفوش المضحك'، تستخدم الإفيهات والفكاهة المصرية الخفيفة والمزاح أثناء توضيح المعاملة."
}


class AIService:
    current_key_index = 0

    @classmethod
    def smart_process_command(cls, user_text: str, branch: str, persona: str = "hantouf", 
                              branch_rules: list = None, chat_history: list = None):
        if chat_history is None:
            chat_history = []
        if branch_rules is None:
            branch_rules = []

        persona_instruction = PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["hantouf"])
        history_context = "\n".join([f"- {m['role']}: {m['content']}" for m in chat_history[-4:]]) if chat_history else "لا يوجد سياق سابق."

        prompt = f"""
        أنت المحاسب الذكي ومدير المخزون لنظام ERP الشبكي الذكي.
        توجيه أسلوب الرد: {persona_instruction}
        قواعد الفرع: {branch_rules}

        سياق المحادثة السابقة:
        {history_context}

        رسالة التاجر الحالية: "{user_text}"

        🧠 قواعد التصنيف والتحليل الصارمة (إجباري):

        1. استخراج الوحدات والعبوات المركبة بدقة تامة:
           - إذا ذكر التاجر وحدة كبرى تحتوي على وحدات صغرى (مثل: "لفة أطباق فيها 100 طبق" أو "كرتونة فيها 12 زجاجة"):
             - اجعل `unit` أو `major_unit` هي الوحدة الكبرى (مثل: "لفة" أو "كرتونة").
             - اجعل `minor_unit` هي الوحدة الصغرى (مثل: "طبق" أو "زجاجة").
             - اجعل `conversion_factor` هو عدد الوحدات الصغرى داخل الوحدة الكبرى (مثل: 100.0 أو 12.0). وإذا لم تذكر، ضعها 1.0.

        2. التوجيه المحاسبي الدقيق (المصروفات، الأصول، والقروض):
           - إذا كانت العملية تخص مصروفات (مثل رواتب، صيانة)، أو أصول ثابتة (مثل جهاز حاسب آلي)، أو قروض (مثل قرض بنكي)، قم بتمييز طبيعتها في اسم الصنف أو المعاملة ولا تعاملها كبضاعة مخزنية تقليدية.

        3. دعم المعاملات المركبة واستعلامات الحد الائتماني:
           - إذا طلب التاجر تعيين أو تعديل حد ائتماني لعميل، اجعل نوع المعاملة "UPDATE_CREDIT_LIMIT".

        4. تصنيف أنواع المعاملات (`type`):
           - "PURCHASE": شراء أو توريد للمخزن أو مصروفات/أصول.
           - "SALE": بيع أو خروج من المخزن.
           - "RETURN": مرتجع مشتريات أو مبيعات.
           - "QUERY": استعلام عن رصيد أو ديون أو تقارير.
           - "UPDATE_PRICE": تحديد سعر معاملة معلقة سابقة.
           - "UPDATE_CREDIT_LIMIT": تعديل أو تعيين الحد الائتماني للعميل.
           - "INCOMPLETE": كلام غامض أو غير مكتمل محاسبياً.

        نسق المخرجات داخل هيكل JSON التالي حصرياً وبدون أي أوسمة markdown أو نصوص خارجية:
        {{
            "confidence_score": 0.95,
            "persona_used": "{persona}",
            "message_to_user": "الرد بأسلوب الشخصية المختارة يوضح ما تم بدقة مع ذكر تفاصيل الكمية والعبوة والتوجيه المحاسبي",
            "transactions": [
                {{
                    "type": "PURCHASE" | "SALE" | "RETURN" | "QUERY" | "UPDATE_PRICE" | "UPDATE_CREDIT_LIMIT" | "INCOMPLETE",
                    "item_name": "اسم الصنف أو اسم العميل أو بند المصروف/الأصل",
                    "brand": "اسم الماركة أو غير محدد",
                    "supplier": "اسم المورد أو العميل",
                    "quantity": 1.0,
                    "unit": "الوحدة الكبرى المستخدمة في الكلام (مثل لفة)",
                    "major_unit": "الوحدة الكبرى (مثل لفة)",
                    "minor_unit": "الوحدة الصغرى الداخلية (مثل طبق)",
                    "conversion_factor": 1.0,
                    "unit_price": 0.0,
                    "is_installment": false,
                    "down_payment": 0.0,
                    "installment_value": 0.0,
                    "due_date": "غير محدد"
                }}
            ]
        }}
        """

        max_retries = max(len(api_keys), 1)
        last_error_msg = ""

        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=700
        )

        for _ in range(max_retries):
            try:
                current_key = api_keys[cls.current_key_index % len(api_keys)]
                if not current_key:
                    break

                genai.configure(api_key=current_key)
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
            "confidence_score": 0.0,
            "persona_used": persona,
            "message_to_user": f"⚠️ خطأ في معالجة الطلب: {last_error_msg}",
            "transactions": [
                {
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
                    "due_date": "غير محدد"
                }
            ]
        }
