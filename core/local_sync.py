import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

class LocalSyncManager:
    def __init__(self, db_path: str = "offline_queue.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """إنشاء كائن الاتصال بقاعدة البيانات المحلية وتفعيل نمط الصفوف."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """إنشاء قاعدة البيانات المحلية لتخزين الحركات عند انقطاع الإنترنت"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pending_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        branch TEXT,
                        raw_text TEXT,
                        parsed_data TEXT,
                        created_at TIMESTAMP,
                        status TEXT DEFAULT 'pending',
                        retry_count INTEGER DEFAULT 0,
                        last_error TEXT
                    )
                ''')
                conn.commit()
        except Exception as e:
            print(f"Error initializing local DB: {e}")

    def save_offline(self, branch: str, raw_text: str, parsed_data: dict) -> bool:
        """حفظ الحركة أو التعديل (مثل الحد الائتماني) محلياً عند فشل الاتصال بالسحابة"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO pending_transactions (branch, raw_text, parsed_data, created_at) VALUES (?, ?, ?, ?)",
                    (branch, raw_text, json.dumps(parsed_data, ensure_ascii=False), datetime.now().isoformat())
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"Error saving offline transaction: {e}")
            return False

    def get_pending_transactions(self, branch: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """جلب قائمة الحركات المعلقة المجهزة لإعادة المزامنة مع السحابة فور عودة الاتصال."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if branch:
                    cursor.execute(
                        "SELECT * FROM pending_transactions WHERE status = 'pending' AND branch = ? ORDER BY id ASC LIMIT ?",
                        (branch, limit)
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM pending_transactions WHERE status = 'pending' ORDER BY id ASC LIMIT ?",
                        (limit,)
                    )
                
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    row_dict = dict(row)
                    if row_dict.get("parsed_data"):
                        try:
                            row_dict["parsed_data"] = json.loads(row_dict["parsed_data"])
                        except Exception:
                            pass
                    results.append(row_dict)
                return results
        except Exception as e:
            print(f"Error fetching pending transactions: {e}")
            return []

    def get_pending_count(self, branch: Optional[str] = None) -> int:
        """معرفة عدد الحركات المعلقة في طابور الانتظار (مع تصفية اختيارية للفرع)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if branch:
                    cursor.execute("SELECT COUNT(*) FROM pending_transactions WHERE status = 'pending' AND branch = ?", (branch,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM pending_transactions WHERE status = 'pending'")
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            print(f"Error getting pending count: {e}")
            return 0

    def mark_as_synced(self, tx_id: int) -> bool:
        """تحديث حالة الحركة إلى تم المزامنة بنجاح وإغلاقها في السجل المحلي."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE pending_transactions SET status = 'synced' WHERE id = ?",
                    (tx_id,)
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"Error marking transaction as synced: {e}")
            return False

    def mark_as_failed(self, tx_id: int, error_msg: str) -> bool:
        """تسجيل فشل محاولة المزامنة مع زيادة عداد المحاولات وتوثيق الخطأ."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE pending_transactions SET retry_count = retry_count + 1, last_error = ? WHERE id = ?",
                    (error_msg, tx_id)
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"Error marking transaction as failed: {e}")
            return False

    def clear_synced_transactions(self, days_old: int = 7) -> int:
        """تنظيف وأرشفة السجلات المزامنة القديمة لتخفيف حجم قاعدة البيانات المحلية."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM pending_transactions WHERE status = 'synced' AND created_at <= ?",
                    (cutoff_date,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
        except Exception as e:
            print(f"Error clearing synced transactions: {e}")
            return 0
