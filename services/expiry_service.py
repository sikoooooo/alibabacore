from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from core.database import get_supabase_client

class ExpiryAndStagnationService:

    @classmethod
    def check_expiry_and_stagnation(cls, branch: str) -> Dict[str, Any]:
        """
        فحص تواريخ الإنتاج والانتهاء وإخراج تقارير الصلاحية والرواكد لبرنامج نافع:
        - كشف المنتجات المنتهية الصلاحية أو التي قل العمر المتبقي لها عن 20%.
        - كشف الأصناف الراكدة التي لم تتحرك منذ أكثر من 30 يوماً وتوفر بها رصيد.
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
            
        try:
            res = supabase.table("inventory").select(
                "item_name, total_base_quantity, production_date, expiry_date, updated_at"
            ).eq("branch", branch).execute()
            
            if not res.data:
                return {"status": "SUCCESS", "message": "المخزن خالٍ من البيانات لفحص الصلاحية والرواكد."}
                
            now = datetime.now(timezone.utc)
            thirty_days_ago = now - timedelta(days=30)
            
            expired_items: List[str] = []
            near_expiry_items: List[str] = []
            stagnant_items: List[str] = []
            
            for item in res.data:
                item_name = item.get("item_name", "صنف غير معروف")
                qty = float(item.get("total_base_quantity", 0) or 0)
                prod_str = item.get("production_date")
                expiry_str = item.get("expiry_date")
                updated_at_str = item.get("updated_at")
                
                # 1. فحص الصلاحية والانتهاء
                if expiry_str:
                    try:
                        expiry_clean = expiry_str.replace("Z", "+00:00")
                        expiry_date = datetime.fromisoformat(expiry_clean)
                        if expiry_date.tzinfo is None:
                            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                            
                        remaining_days = (expiry_date - now).days
                        
                        if remaining_days < 0:
                            expired_items.append(f"- ❌ {item_name} (منتهي منذ {abs(remaining_days)} يوم - الرصيد: {qty})")
                        elif prod_str:
                            prod_clean = prod_str.replace("Z", "+00:00")
                            prod_date = datetime.fromisoformat(prod_clean)
                            if prod_date.tzinfo is None:
                                prod_date = prod_date.replace(tzinfo=timezone.utc)
                                
                            total_shelf_life = (expiry_date - prod_date).days
                            if total_shelf_life > 0:
                                remaining_percentage = (remaining_days / total_shelf_life) * 100
                                if remaining_percentage <= 20:
                                    near_expiry_items.append(
                                        f"- ⚠️ {item_name} (متبقي {remaining_days} يوم - {remaining_percentage:.1f}% من الصلاحية)"
                                    )
                        else:
                            if remaining_days <= 30:
                                near_expiry_items.append(f"- ⚠️ {item_name} (ينتهي خلال {remaining_days} يوم)")
                    except Exception as date_err:
                        print(f"Expiry date parse error for {item_name}: {date_err}")
                        
                # 2. فحص الرواكد (أكثر من 30 يوماً بدون حركة مع وجود رصيد بالمخزن)
                if updated_at_str and qty > 0:
                    try:
                        updated_clean = updated_at_str.replace("Z", "+00:00")
                        updated_date = datetime.fromisoformat(updated_clean)
                        if updated_date.tzinfo is None:
                            updated_date = updated_date.replace(tzinfo=timezone.utc)
                            
                        if updated_date <= thirty_days_ago:
                            days_inactive = (now - updated_date).days
                            stagnant_items.append(f"- 📦 {item_name} (الرصيد: {qty} | بدون حركة منذ {days_inactive} يوماً)")
                    except Exception as update_err:
                        print(f"Stagnation date parse error for {item_name}: {update_err}")
                        
            report_msg = f"⏳ **تقرير الصلاحيات والرواكد - فرع ({branch}):**\n\n"
            
            if expired_items:
                report_msg += "🛑 **أصناف منتهية الصلاحية (يلزم سحبها فوراً):**\n" + "\n".join(expired_items) + "\n\n"
                
            if near_expiry_items:
                report_msg += "🚨 **أصناف قربت تنتهي (أقل من 20% متبقي):**\n" + "\n".join(near_expiry_items) + "\n\n"
            elif not expired_items:
                report_msg += "✅ جميع الأصناف في حالة صلاحية آمنة.\n\n"
                
            if stagnant_items:
                report_msg += "📦 **الأصناف الراكدة (أكثر من 30 يوماً بدون حركة):**\n" + "\n".join(stagnant_items)
            else:
                report_msg += "✅ لا توجد أصناف راكدة حالياً."
                
            return {
                "status": "SUCCESS",
                "expired": expired_items,
                "near_expiry": near_expiry_items,
                "stagnant": stagnant_items,
                "message": report_msg
            }
            
        except Exception as e:
            print(f"Expiry and stagnation service error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء فحص الصلاحيات: {str(e)}"}
