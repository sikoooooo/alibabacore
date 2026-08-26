
from datetime import datetime, timedelta
from typing import Dict, Any
from services.supabase_client import get_supabase_client

class ExpiryAndStagnationService:

    @classmethod
    def check_expiry_and_stagnation(cls, branch: str) -> Dict[str, Any]:
        """
        التحقق من تواريخ الإنتاج والانتهاء والتنبيه التلقائي قبلها بشهرين،
        واكتشاف الأصناف الراكدة التي لم يتم بيعها منذ أكثر من 60 يوماً.
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
            
        try:
            # جلب أصناف المخزن التي تحتوي على تاريخ انتهاء
            res = supabase.table("inventory").select("item_name, quantity, expiry_date, updated_at").eq("branch", branch).execute()
            
            if not res.data:
                return {"status": "SUCCESS", "message": "المخزن خالٍ من البيانات لفحص الصلاحية."}
                
            today = datetime.now()
            two_months_later = today + timedelta(days=60)
            sixty_days_ago = today - timedelta(days=60)
            
            near_expiry_items = []
            stagnant_items = []
            
            for item in res.data:
                item_name = item.get("item_name")
                expiry_str = item.get("expiry_date")
                updated_at_str = item.get("updated_at")
                
                # فحص تواريخ الانتهاء (أقل من شهرين)
                if expiry_str:
                    try:
                        expiry_date = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                        if expiry_date <= two_months_later:
                            near_expiry_items.append(f"- {item_name} (ينتهي في: {expiry_str[:10]})")
                    except Exception:
                        pass
                        
                # فحص الرواكد (لم يتم تحديثها أو بيعها منذ أكثر من 60 يوماً)
                if updated_at_str:
                    try:
                        updated_date = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                        if updated_date <= sixty_days_ago:
                            stagnant_items.append(f"- {item_name} (بدون حركات منذ 60 يوماً)")
                    except Exception:
                        pass
                        
            report_msg = f"⏳ **تقرير الصلاحيات والرواكد للفرع ({branch}):**\n\n"
            
            if near_expiry_items:
                report_msg += "🚨 **أصناف تقترب من انتهاء الصلاحية (أقل من شهرين):**\n" + "\n".join(near_expiry_items) + "\n\n"
            else:
                report_msg += "✅ لا توجد أصناف تقترب من انتهاء الصلاحية.\n\n"
                
            if stagnant_items:
                report_msg += "📦 **الأصناف الراكدة:**\n" + "\n".join(stagnant_items)
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
