def handle_user_input(user_input: str):
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    parsed, error = execute_with_key_rotation(
        user_input, 
        branch, 
        st.session_state.get("branch_rules", []), 
        st.session_state.messages,
        persona=st.session_state.persona
    )
    
    if error or not parsed:
        response_text = f"⚠️ عذراً، حدث خطأ: {error}"
    else:
        ai_message = parsed.get("message_to_user", "تم الاستلام.")
        execution_notes = []
        
        # استخراج قائمة المعاملات سواء كانت مفردة أو داخل قائمة transactions
        transactions_list = parsed.get("transactions", [])
        if not transactions_list and "type" in parsed:
            transactions_list = [parsed]

        for tx in transactions_list:
            trans_type = tx.get("type")
            if trans_type and trans_type != "QUERY" and InventoryService:
                try:
                    if tx.get("is_installment") and InstallmentService:
                        cust_name = tx.get("supplier") or tx.get("supplier_customer") or "عميل غير محدد"
                        total_amt = float(tx.get("quantity", 1)) * float(tx.get("unit_price", 0))
                        down_pay = float(tx.get("down_payment", 0))
                        rem_amt = total_amt - down_pay

                        success, msg = InventoryService.execute_transaction(branch, tx, user_input)
                        InstallmentService.record_installment(
                            transaction_id="TX_INST",
                            branch=branch,
                            customer_name=cust_name,
                            total_amount=total_amt,
                            down_payment=down_pay,
                            remaining_amount=rem_amt,
                            due_date=tx.get("due_date", "غير محدد")
                        )
                        execution_notes.append(f"✅ {msg}\n💳 قسط مسجل: {rem_amt:,.2f} ج ({cust_name})")
                    else:
                        success, msg = InventoryService.execute_transaction(branch, tx, user_input)
                        if success:
                            execution_notes.append(f"✅ {msg}")
                        else:
                            execution_notes.append(f"❌ خطأ الحفظ: {msg}")
                except Exception as e:
                    execution_notes.append(f"🚨 خطأ برمجى: {str(e)}")

        if st.session_state.persona == "mongez":
            response_text = "\n".join(execution_notes) if execution_notes else ai_message
        else:
            response_text = f"{ai_message}\n\n" + "\n\n".join(execution_notes) if execution_notes else ai_message

    st.session_state.messages.append({"role": "assistant", "content": response_text})
