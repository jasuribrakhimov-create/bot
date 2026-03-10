import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('DB_PATH', 'openbudget.db')


class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_db()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_conn()
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            full_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            full_name TEXT,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            full_name TEXT,
            username TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        defaults = [
            ('welcome_text',
             '🏛 <b>OpenBudget Ovoz Berish Botiga Xush Kelibsiz!</b>\n\n'
             'Ushbu bot orqali siz ochiq byudjet loyihalariga ovoz berishingiz mumkin.\n\n'
             'Quyidagi tugmalardan birini tanlang:'),
            ('vote_text',
             "🗳 <b>Ovoz Berish</b>\n\n"
             "Quyidagi tugma orqali ovoz berish sahifasiga o'ting.\n"
             "Ovoz berganingizdan so'ng <b>screenshot</b> olib, shu yerga yuboring.\n\n"
             "📸 Screenshot yuborilgandan so'ng adminlar tekshirib siz bilan bog'lanishadi."),
            ('info_text',
             "📋 <b>Ma'lumotlar</b>\n\n"
             "Bu yerda OpenBudget loyihasi haqida ma'lumotlar joylashadi.\n\n"
             "Admin tomonidan ma'lumotlar kiritilmagan."),
            ('video_text',
             "🎓 <b>Video Qo'llanma</b>\n\n"
             "Ovoz berish jarayonini o'rganish uchun quyidagi videoni tomosha qiling."),
            ('vote_link', ''),
            ('guide_video_id', ''),
        ]
        for key, value in defaults:
            c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))

        first_admin = os.getenv('ADMIN_ID')
        if first_admin:
            c.execute('INSERT OR IGNORE INTO admins (user_id, full_name) VALUES (?, ?)',
                      (int(first_admin), 'Super Admin'))

        conn.commit()
        conn.close()

    def add_user(self, user_id, username, full_name):
        conn = self.get_conn()
        conn.execute(
            'INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)',
            (user_id, username, full_name)
        )
        conn.execute(
            'UPDATE users SET username=?, full_name=? WHERE user_id=?',
            (username, full_name, user_id)
        )
        conn.commit()
        conn.close()

    def is_admin(self, user_id):
        conn = self.get_conn()
        result = conn.execute('SELECT 1 FROM admins WHERE user_id=?', (user_id,)).fetchone()
        conn.close()
        return result is not None

    def get_admins(self):
        conn = self.get_conn()
        rows = conn.execute('SELECT user_id FROM admins').fetchall()
        conn.close()
        return [row['user_id'] for row in rows]

    def get_admins_info(self):
        conn = self.get_conn()
        rows = conn.execute('SELECT * FROM admins').fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_admin(self, user_id, full_name='Admin'):
        conn = self.get_conn()
        conn.execute(
            'INSERT OR IGNORE INTO admins (user_id, full_name) VALUES (?, ?)',
            (user_id, full_name)
        )
        conn.commit()
        conn.close()

    def remove_admin(self, user_id):
        conn = self.get_conn()
        conn.execute('DELETE FROM admins WHERE user_id=?', (user_id,))
        conn.commit()
        conn.close()

    def get_settings(self):
        conn = self.get_conn()
        rows = conn.execute('SELECT key, value FROM settings').fetchall()
        conn.close()
        return {row['key']: row['value'] for row in rows}

    def update_setting(self, key, value):
        conn = self.get_conn()
        conn.execute(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
        conn.commit()
        conn.close()

    def save_screenshot(self, user_id, file_id, full_name, username):
        conn = self.get_conn()
        conn.execute(
            'INSERT INTO screenshots (user_id, file_id, full_name, username) VALUES (?, ?, ?, ?)',
            (user_id, file_id, full_name, username)
        )
        conn.commit()
        conn.close()

    def get_screenshots_paged(self, page, per_page):
        offset = (page - 1) * per_page
        conn = self.get_conn()
        rows = conn.execute(
            'SELECT * FROM screenshots ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (per_page, offset)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_voters_list(self, page, per_page):
        offset = (page - 1) * per_page
        conn = self.get_conn()
        rows = conn.execute('''
            SELECT 
                s.user_id,
                s.full_name,
                s.username,
                COUNT(s.id) as vote_count,
                MAX(s.created_at) as last_vote
            FROM screenshots s
            GROUP BY s.user_id
            ORDER BY vote_count DESC, last_vote DESC
            LIMIT ? OFFSET ?
        ''', (per_page, offset)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_top_voters(self, limit=5):
        conn = self.get_conn()
        rows = conn.execute('''
            SELECT user_id, full_name, username, COUNT(id) as vote_count
            FROM screenshots
            GROUP BY user_id
            ORDER BY vote_count DESC
            LIMIT ?
        ''', (limit,)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_stats(self):
        conn = self.get_conn()
        users = conn.execute('SELECT COUNT(*) as cnt FROM users').fetchone()['cnt']
        screenshots = conn.execute('SELECT COUNT(*) as cnt FROM screenshots').fetchone()['cnt']
        voters = conn.execute(
            'SELECT COUNT(DISTINCT user_id) as cnt FROM screenshots'
        ).fetchone()['cnt']
        conn.close()
        return {'users': users, 'screenshots': screenshots, 'voters': voters}

    def get_all_users(self):
        """Barcha foydalanuvchilar ro'yxati broadcast uchun"""
        conn = self.get_conn()
        rows = conn.execute('SELECT user_id FROM users').fetchall()
        conn.close()
        return [dict(row) for row in rows]
