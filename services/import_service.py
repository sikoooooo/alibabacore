import pandas as pd
from typing import Dict, Any
from services.supabase_client import get_supabase_client

class ImportService:

    @classmethod
    def import_legacy_data_from_excel(cls, branch: str, file_path_or_buffer) -> Dict[str, Any]:
        """
        استيراد وتفريغ البيانات القديمة من شيتات إكسيل (أصناف، كميات، أسعار، تكلفة، وموردين) دفعة واحدة.
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
            
        try:
            # قراءة ملف الإكسيل عبر pandas
            df = pd.read_excel(file_path_or_buffer)
            
            # التأكد من وجود الأعمدة الأساسية المطلوبة
            required_columns = ["item_name", "quantity", "price"]
            for col in required_columns:
                if col not in df.columns:
                    return {"status": "ERROR", "message": f"⚠️ الملف المرفق يفتقر إلى العمود الأساسي المطلوب: '{col}'."}
                    
            imported_count = 0
            failed_rows = []
            
            for index, row in df.iterrows():
                try:
                    item_qty = float(row.get("quantity", 0))
                    item_cost = float(row.get("cost", row.get("price", 0))) if ("cost" in df.columns or "price" in df.columns) and pd.notna(row.get("cost", row.get("price"))) else 0.0
                    
                    item_data = {
                        "branch": branch,
                        "item_name": str(row.get("item_name", "")).strip(),
                        "total_base_quantity": item_qty,
                        "avg_cost_per_base": item_cost,
                        "major_unit": str(row.get("unit", "وحدة")).strip(),
                        "supplier": str(row.get("supplier", "")).strip() if "supplier" in df.columns and pd.notna(row.get("supplier")) else "غير محدد",
                        "brand": str(row.get("brand", "")).strip() if "brand" in df.columns and pd.notna(row.get("brand")) else "غير محدد"
                    }
                    
                    if not item_data["item_name"]:
                        continue
                        
                    # إدخال الصنف إلى جدول المخزن بالأسماء الصح للأعمدة
                    supabase.table("inventory").insert(item_data).execute()
                    imported_count += 1
                    
                except Exception as row_err:
                    failed_rows.append(f"الصف {index + 1}: {str(row_err)}")
                    
            return {
                "status": "SUCCESS",
                "imported_count": imported_count,
                "failed_rows": failed_rows,
                "message": f"✅ تم بنجاح استيراد وتفريغ ({imported_count}) صنفاً من البيانات القديمة إلى مخزن الفرع ({branch})."
            }
            
        except Exception as e:
            print(f"Import legacy data error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء قراءة واستيراد الملف: {str(e)}"}
