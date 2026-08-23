elif trans_type == "QUERY" and supabase:
                        customer_query = parsed.get("supplier", "").strip()
                        try:
                            q_builder = supabase.table("installments").select("*").eq("branch", branch)
                            if customer_query and customer_query != "غير محدد":
                                q_builder = q_builder.ilike("customer_name", f"%{customer_query}%")
                            
                            inst_results = q_builder.execute()
                            if inst_results.data:
                                response_text = f"📋 **نتائج البحث في الأقساط للفرع ({branch}):**\n\n"
                                for row in inst_results.data:
                                    due_date_val = row.get('due_date') or row.get('installment_date') or "غير محدد"
                                    response_text += f"- **العميل:** {row.get('customer_name')} | **الصنف:** {row.get('item_name')} | **المتبقي:** {row.get('remaining_amount')} ج.م | **قيمة القسط:** {row.get('installment_value')} ج.م | 📅 **موعد القسط:** {due_date_val} | **الحالة:** {row.get('status')}\n"
                            else:
                                response_text = f"🔍 لم يتم العثور على أقساط مطابقة في قاعدة البيانات بهذا الاسم ({customer_query})."
                        except Exception as ex:
                            response_text = f"⚠️ حدث خطأ أثناء الاستعلام من قاعدة البيانات: {str(ex)}"
