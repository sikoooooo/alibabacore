from datetime import datetime, timedelta
from typing import Dict, Any
from services.supabase_client import get_supabase_client

class ExpiryAndStagnationService:

    @classmethod
    def check_expiry_and_stagnation(cls, branch: str) -> Dict[str, Any]:
        """
        التحقق من تواريخ الإنتاج والانتهاء (تنبيه إذا قل العمر المتبقي عن 20%)،
        واكتشاف الأصناف الراكدة التي لم يتم بيعها منذ أكثر من 30 يوماً.
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
            
        try:
            res = supabase.table("inventory").select("item_name, total_base_quantity, production_date, expiry_date, updated_at").eq("branch", branch).execute()
            
            if not res.data:
                return {"status": "SUCCESS", "message": "المخزن خالٍ من البيانات لفحص الصلاحية."}
                
            today = datetime.now()
            thirty_days_ago = today - timedelta(days=30)
            
            near_expiry_items = []
            stagnant_items = []
            
            for item in res.data:
                item_name = item.get("item_name")
                prod_str = item.get("production_date")
                expiry_str = item.get("expiry_date")
                updated_at_str = item.get("updated_at")
                
                # 1. فحص الصلاحية بالنسبة والتناسب (أقل من 20% متبقي)
                if prod_str and expiry_str:
                    try:
                        prod_date = datetime.fromisoformat(prod_str.replace("Z", "+00:00"))
                        expiry_date = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                        
                        total_shelf_life = (expiry_date - prod_date).days
                        remaining_life = (expiry_date - today).days
                        
                        if total_shelf_life > 0:
                            remaining_percentage = (remaining_life / total_shelf_life) * 100
                            if remaining_percentage <= 20:
                                near_expiry_items.append(f"- {item_name} (المتبقي {remaining_life} يوم - {remaining_percentage:.1f}% من الصلاحية)")
                    except Exception:
                        pass
                elif expiry_str:
                    try:
                        expiry_date = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                        if (expiry_date - today).days <= 30:
                            near_expiry_items.append(f"- {item_name} (ينتهي في: {expiry_str[:10]})")
                    except Exception:
                        pass
                        
                # 2. فحص الرواكد (أكثر من 30 يوماً بدون حركة)
                if updated_at_str:
                    try:
                        updated_date = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                        if updated_date <= thirty_days_ago:
                            stagnant_items.append(f"- {item_name} (بدون حركات منذ 30 يوماً)")
                    except Exception:
                        pass
                        
            report_msg = f"⏳ **تقرير الصلاحيات والرواكد للفرع ({branch}):**\n\n"
            
            if near_expiry_items:
                report_msg += "🚨 **أصناف قربت تنتهي (أقل من 20% من عمر الصلاحية):**\n" + "\n".join(near_expiry_items) + "\n\n"
            else:
                report_msg += "✅ لا توجد أصناف حرجة في الصلاحية.\n\n"
                
            if stagnant_items:
                report_msg += "📦 **الأصناف الراكدة (أكثر من 30 يوماً بدون حركة):**\n" + "\n".join(stagnant_items)
            else:
                report_msg += "✅ لا توجد أصناف راكدة حالياً."
                
            return {
                "status": "SUCCESS",
                "near_expiry": near_expiry_items,
                "stagnant": stagnant_items,
                "message": report_msg
            }
            
        except Exception as e:
            print(f"Expiry and stagnation service error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء فحص الصلاحيات: {str(e)}"}
