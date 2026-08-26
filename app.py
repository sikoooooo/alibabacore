def process_and_display_chat(user_input):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar=current_avatar):
        with st.spinner("جاري التنفيذ..."):
            parsed, error = execute_with_key_rotation(
                user_input, 
                branch, 
                st.session_state.get("branch_rules", []), 
                st.session_state.messages,
                persona=st.session_state.persona
            )
            
            if error or not parsed:
                response_text = f"⚠️ خطأ: {error}"
            else:
                ai_message = parsed.get("message_to_user", "تم.")
                execution_notes = []
                
                transactions_list = parsed.get("transactions", [])
                if not transactions_list and "type" in parsed:
                    transactions_list = [parsed]

                for tx in transactions_list:
                    trans_type = tx.get("type")
                    if trans_type and trans_type != "QUERY" and InventoryService:
                        try:
                            success, msg = InventoryService.execute_transaction(branch, tx, user_input)
                            if success:
                                execution_notes.append(f"✅ {msg}")
                            else:
                                execution_notes.append(f"❌ {msg}")
                        except Exception as e:
                            execution_notes.append(f"🚨 خطأ: {str(e)}")

                # تقصير تام وصارم للردود بدون أي مقدمات
                if execution_notes:
                    response_text = "\n".join(execution_notes)
                else:
                    response_text = ai_message

            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})
