from typing import Dict, Any
from services.supabase_client import get_supabase_client

class CollectivePurchasingService:

    @classmethod
    def analyze_market_prices(cls, branch: str, item_name: str, current_offered_price: float) -> Dict[str, Any]:
        """
        تحليل أسعار السوق ومؤشر الشراء الجماعي لاكتشاف زيادات الأسعار أو عروض جملة الجملة
        التي تقل بنسبة 10% أو أكثر عن المتوسط السائد.
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
            
        try:
            # جلب السجل التاريخي لأسعار تكلفة الصنف من جدول الحركات أو المشتريات السابقة
            res = supabase.table("transactions").select("total_price, quantity").eq("branch", branch).ilike("item_name", f"%{item_name}%").eq("type", "purchase").execute()
            
            if not res.data:
                return {
                    "status": "SUCCESS",
                    "is_good_deal": False,
                    "message": f"ℹ️ لا توجد بيانات تاريخية كافية للصنف '{item_name}' لمقارنة الأسعار، السعر الحالي معتمد."
                }
                
            # حساب متوسط تكلفة الشراء السابقة
            total_cost = sum(float(i.get("total_price", 0)) for i in res.data)
            total_qty = sum(float(i.get("quantity", 1)) for i in res.data)
            
            if total_qty == 0:
                return {"status": "SUCCESS", "is_good_deal": False, "message": "⚠️ الكميات المسجلة صفرية."}
                
            avg_historical_cost = total_cost / total_qty
            
            # حساب نسبة الانخفاض أو الزيادة مقارنة بالسعر المعروض حالياً
            price_diff_ratio = (current_offered_price - avg_historical_cost) / avg_historical_cost
            
            if current_offered_price < avg_historical_cost and abs(price_diff_ratio) >= 0.10:
                saving_percentage = round(abs(price_diff_ratio) * 100, 1)
                return {
                    "status": "SUCCESS",
                    "is_good_deal": True,
                    "saving_percentage": saving_percentage,
                    "message": f"🔥 **عرض جملة مميز!** السعر المعروض للصنف '{item_name}' يقل بنسبة ({saving_percentage}%) عن المتوسط التاريخي. فرصة ذهبية للشراء الجماعي وتوفير التكلفة."
                }
            elif price_diff_ratio > 0.10:
                increase_percentage = round(price_diff_ratio * 100, 1)
                return {
                    "status": "SUCCESS",
                    "is_good_deal": False,
                    "price_increased": True,
                    "message": f"⚠️ **تنبيه زيادة أسعار:** سعر الصنف '{item_name}' زاد بنسبة ({increase_percentage}%) مقارنة بمتوسط الشراء السابق."
                }
            else:
                return {
                    "status": "SUCCESS",
                    "is_good_deal": False,
                    "message": f"✅ السعر المعروض للصنف '{item_name}' مستقر وضمن المعدل الطبيعي مقارنة بالسابق."
                }
                
        except Exception as e:
            print(f"Collective purchasing service error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء تحليل الأسعار: {str(e)}"}
