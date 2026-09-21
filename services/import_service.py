import pandas as pd
from typing import Dict, Any, List
from core.database import get_supabase_client

class ImportService:

    @classmethod
    def import_legacy_data_from_excel(cls, branch: str, file_path_or_buffer) -> Dict[str, Any]:
        """
        استيراد وتفريغ البيانات القديمة من شيتات إكسيل (أصناف، كميات، تكلفة، سعر بيع، وموردين)
        مع الدعم الآلي لأسماء الأعمدة بالعربية والإنجليزية والتحديث الذكي للمخزن الحالي.
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
            
        try:
            # 1. قراءة ملف الإكسيل عبر pandas
            df = pd.read_excel(file_path_or_buffer)
            
            if df.empty:
                return {"status": "ERROR", "message": "⚠️ ملف الإكسيل المرفق فارغ ولا يحتوي على بيانات."}

            # 2. توحيد وتطابق أسماء الأعمدة (دعم العربية والإنجليزية)
            column_mapping = {
                "اسم الصنف": "item_name", "اسم_الصنف": "item_name", "الصنف": "item_name", "المنتج": "item_name", "item": "item_name", "item_name": "item_name",
                "الكمية": "quantity", "الرصيد": "quantity", "العدد": "quantity", "qty": "quantity", "quantity": "quantity",
                "التكلفة": "cost", "سعر التكلفة": "cost", "سعر_التكلفة": "cost", "cost": "cost", "avg_cost": "cost",
                "سعر البيع": "selling_price", "سعر_البيع": "selling_price", "البيع": "selling_price", "selling_price": "selling_price",
                "السعر": "price", "سعر": "price", "price": "price",
                "الوحدة": "unit", "الوحدة الكبرى": "unit", "unit": "unit", "major_unit": "unit",
                "المورد": "supplier", "supplier": "supplier",
                "البراند": "brand", "الماركة": "brand", "brand": "brand"
            }

            # إعادة تسمية الأعمدة الموجودة بناءً على المبادلة
            df_renamed = df.rename(columns=lambda col: column_mapping.get(str(col).strip(), str(col).strip()))
            
            # التأكد من وجود الأعمدة الأساسية المطلوبة
            if "item_name" not in df_renamed.columns:
                return {"status": "ERROR", "message": "⚠️ لم يتم العثور على عمود اسم الصنف (مثل: item_name أو 'اسم الصنف')."}
                
            imported_count = 0
            updated_count = 0
            failed_rows: List[str] = []
            
            for index, row in df_renamed.iterrows():
                try:
                    raw_name = str(row.get("item_name", "")).strip()
                    if not raw_name or raw_name.lower() == "nan":
                        continue

                    item_qty = float(row.get("quantity", 0)) if pd.notna(row.get("quantity")) else 0.0
                    
                    # استخراج سعر التكلفة
                    item_cost = 0.0
                    if "cost" in df_renamed.columns and pd.notna(row.get("cost")):
                        item_cost = float(row.get("cost"))
                    elif "price" in df_renamed.columns and pd.notna(row.get("price")):
                        item_cost = float(row.get("price"))

                    # استخراج سعر البيع
                    item_selling_price = 0.0
                    if "selling_price" in df_renamed.columns and pd.notna(row.get("selling_price")):
                        item_selling_price = float(row.get("selling_price"))
                    elif "price" in df_renamed.columns and pd.notna(row.get("price")) and item_cost == 0:
                        item_selling_price = float(row.get("price"))

                    unit_val = str(row.get("unit", "وحدة")).strip() if pd.notna(row.get("unit")) else "وحدة"
                    supplier_val = str(row.get("supplier", "غير محدد")).strip() if pd.notna(row.get("supplier")) else "غير محدد"
                    brand_val = str(row.get("brand", "غير محدد")).strip() if pd.notna(row.get("brand")) else "غير محدد"

                    # 3. التحقق مما إذا كان الصنف موجوداً مسبقاً في المخزن لتحديثه أو إضافته
                    existing = supabase.table("inventory").select("*").eq("branch", branch).ilike("item_name", f"%{raw_name}%").execute()

                    if existing.data:
                        # تحديث الصنف الحالي (إضافة الكمية الجديدة وحساب التكلفة وسعر البيع)
                        row_data = existing.data[0]
                        current_qty = float(row_data.get("total_base_quantity", 0) or 0)
                        current_cost = float(row_data.get("avg_cost_per_base", 0) or 0)
                        
                        new_qty = current_qty + item_qty
                        new_cost = item_cost if item_cost > 0 else current_cost
                        if current_qty > 0 and item_qty > 0 and item_cost > 0:
                            new_cost = ((current_qty * current_cost) + (item_qty * item_cost)) / new_qty

                        update_payload = {
                            "total_base_quantity": new_qty,
                            "avg_cost_per_base": new_cost,
                            "major_unit": unit_val if unit_val != "وحدة" else row_data.get("major_unit", "وحدة")
                        }
                        if item_selling_price > 0:
                            update_payload["selling_price"] = item_selling_price

                        supabase.table("inventory").update(update_payload).eq("id", row_data["id"]).execute()
                        updated_count += 1

                    else:
                        # إدراج صنف جديد
                        insert_payload = {
                            "branch": branch,
                            "item_name": raw_name,
                            "total_base_quantity": item_qty,
                            "avg_cost_per_base": item_cost,
                            "selling_price": item_selling_price,
                            "major_unit": unit_val,
                            "supplier": supplier_val,
                            "brand": brand_val
                        }
                        supabase.table("inventory").insert(insert_payload).execute()
                        imported_count += 1

                    # 4. تسجيل حركة رصيد أول المشتريات/الافتتاحي في جدول المعاملات
                    try:
                        tx_payload = {
                            "branch": branch,
                            "item_name": raw_name,
                            "quantity": item_qty,
                            "unit_price": item_cost,
                            "supplier": supplier_val,
                            "type": "PURCHASE",
                            "unit": unit_val
                        }
                        supabase.table("transactions").insert(tx_payload).execute()
                    except Exception as tx_err:
                        print(f"Opening tx log error for {raw_name}: {tx_err}")

                except Exception as row_err:
                    failed_rows.append(f"الصف {index + 2}: {str(row_err)}")
                    
            summary_msg = f"✅ تم الاستيراد بنجاح لفرع ({branch}): إضافة ({imported_count}) صنف جديد، وتحديث ({updated_count}) صنف قائم."
            if failed_rows:
                summary_msg += f"\n⚠️ توجد {len(failed_rows)} صفوف تعذر استيرادها."

            return {
                "status": "SUCCESS",
                "imported_count": imported_count,
                "updated_count": updated_count,
                "failed_rows": failed_rows,
                "message": summary_msg
            }
            
        except Exception as e:
            print(f"Import legacy data error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء قراءة واستيراد الملف: {str(e)}"}
