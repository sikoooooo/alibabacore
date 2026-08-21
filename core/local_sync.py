import sqlite3
import os
from datetime import datetime

class LocalSyncManager:
    def __init__(self, db_path="offline_queue.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """إنشاء قاعدة البيانات المحلية لتخزين الحركات عند انقطاع الإنترنت"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch TEXT,
                raw_text TEXT,
                parsed_data TEXT,
                created_at TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        conn.commit()
        conn.close()

    def save_offline(self, branch: str, raw_text: str, parsed_data: dict):
        """حفظ الحركة محلياً عند فشل الاتصال بالسحابة"""
        import json
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pending_transactions (branch, raw_text, parsed_data, created_at) VALUES (?, ?, ?, ?)",
            (branch, raw_text, json.dumps(parsed_data), datetime.now())
        )
        conn.commit()
        conn.close()
        return True

    def get_pending_count(self):
        """معرفة عدد الحركات المعلقة في طابور الانتظار"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pending_transactions WHERE status = 'pending'")
        count = cursor.fetchone()[0]
        conn.close()
        return count
