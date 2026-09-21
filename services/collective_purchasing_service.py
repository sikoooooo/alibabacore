from typing import Dict, Any
from core.database import get_supabase_client

class CollectivePurchasingService:

    @classmethod
    def analyze_market_prices(cls, branch: str, item_name: str, current_offered_price: float) -> Dict[str, Any]:
        """
        تحليل أسعار السوق ومؤشر الشراء الجماعي لبرنامج نافع:
        لاكتشاف زيادات الأسعار أو عروض جملة الجملة التي تقل بنسبة 10% أو أكثر عن المتوسط التاريخي.
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
            
        try:
            # 1. جلب السجل التاريخي لحركات الشراء من جدول transactions
            res = supabase.table("transactions")\
                .select("unit_price, total_price, quantity")\
                .eq("branch", branch)\
                .ilike("item_name", f"%{item_name}%")\
                .ilike("type", "%purchase%")\
                .execute()
            
            avg_historical_cost = 0.0

            if res.data:
                total_cost = 0.0
                total_qty = 0.0
                for item in res.data:
                    qty = float(item.get("quantity", 0) or 0)
                    unit_p = float(item.get("unit_price", 0) or 0)
                    tot_p = float(item.get("total_price", 0) or 0)
                    
                    if tot_p > 0:
                        total_cost += tot_p
                    elif unit_p > 0 and qty > 0:
                        total_cost += (unit_p * qty)
                        
                    total_qty += qty

                if total_qty > 0 and total_cost > 0:
                    avg_historical_cost = total_cost / total_qty

            # 2. الاحتياط: في حال عدم وجود حركات مشتريات مدونة، يتم جلب التكلفة المسجلة في جدول inventory
            if avg_historical_cost == 0.0:
                inv_res = supabase.table("inventory")\
                    .select("avg_cost_per_base")\
                    .eq("branch", branch)\
                    .ilike("item_name", f"%{item_name}%")\
                    .execute()
                
                if inv_res.data and inv_res.data[0].get("avg_cost_per_base"):
                    avg_historical_cost = float(inv_res.data[0]["avg_cost_per_base"] or 0)

            # إذا لم تتوفر بيانات تاريخية أو كانت التكلفة صفرية
            if avg_historical_cost <= 0:
                return {
                    "status": "SUCCESS",
                    "is_good_deal": False,
                    "historical_avg": 0.0,
                    "message": f"ℹ️ لا توجد بيانات تاريخية كافية للصنف '{item_name}' لمقارنة الأسعار، السعر الحالي ({current_offered_price:,.2f} ج.م) اعتُمِد كسعر أساسي."
                }
                
            # 3. حساب نسبة الانخفاض أو الزيادة مقارنة بالسعر المعروض حالياً
            price_diff_ratio = (current_offered_price - avg_historical_cost) / avg_historical_cost
            
            # عرض جملة مميز (تخفيض >= 10%)
            if current_offered_price < avg_historical_cost and abs(price_diff_ratio) >= 0.10:
                saving_percentage = round(abs(price_diff_ratio) * 100, 1)
                return {
                    "status": "SUCCESS",
                    "is_good_deal": True,
                    "price_increased": False,
                    "saving_percentage": saving_percentage,
                    "historical_avg": round(avg_historical_cost, 2),
                    "message": (
                        f"🔥 **عرض جملة مميز لبرنامج نافع!**\n"
                        f"السعر المعروض للصنف '{item_name}' هو ({current_offered_price:,.2f} ج.م) ويقل بنسبة (**{saving_percentage}%**) "
                        f"عن المتوسط التاريخي ({avg_historical_cost:,.2f} ج.م).\n"
                        f"💡 **توصية:** فرصة ذهبية للشراء الجماعي وتوفير التكلفة."
                    )
                }
            # تنبيه زيادة أسعار (زيادة >= 10%)
            elif price_diff_ratio >= 0.10:
                increase_percentage = round(price_diff_ratio * 100, 1)
                return {
                    "status": "SUCCESS",
                    "is_good_deal": False,
                    "price_increased": True,
                    "increase_percentage": increase_percentage,
                    "historical_avg": round(avg_historical_cost, 2),
                    "message": (
                        f"⚠️ **تنبيه ارتفاع أسعار:**\n"
                        f"سعر الصنف '{item_name}' المعروض ({current_offered_price:,.2f} ج.م) ارتفع بنسبة (**{increase_percentage}%**) "
                        f"مقارنة بمتوسط الشراء السابق ({avg_historical_cost:,.2f} ج.م)."
                    )
                }
            # استقرار الأسعار
            else:
                return {
                    "status": "SUCCESS",
                    "is_good_deal": False,
                    "price_increased": False,
                    "historical_avg": round(avg_historical_cost, 2),
                    "message": f"✅ السعر المعروض للصنف '{item_name}' ({current_offered_price:,.2f} ج.م) مستقر وضمن المعدل الطبيعي مقارنة بالمتوسط السابق ({avg_historical_cost:,.2f} ج.م)."
                }
                
        except Exception as e:
            print(f"Collective purchasing service error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء تحليل الأسعار: {str(e)}"}
