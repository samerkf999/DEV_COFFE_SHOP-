# ============================================================
# database.py — إدارة قاعدة البيانات لنظام نشمي كافيه
# ============================================================

import sqlite3
from datetime import datetime

DATABASE_PATH = 'nashmi_cafe.db'


def get_db():
    """الحصول على اتصال مع قاعدة البيانات"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """تهيئة قاعدة البيانات وإنشاء جميع الجداول"""
    conn = get_db()
    c = conn.cursor()

    # جدول التصنيفات
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, name_ar TEXT NOT NULL,
        icon TEXT DEFAULT "☕", sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')

    # جدول الأصناف
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL, name_ar TEXT NOT NULL,
        price REAL NOT NULL, description TEXT,
        image_path TEXT, is_available INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE)''')

    # جدول سجلات اليوم
    c.execute('''CREATE TABLE IF NOT EXISTS daily_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        opening_time TEXT, closing_time TEXT,
        opening_cash REAL DEFAULT 0, closing_cash REAL DEFAULT 0,
        total_sales_cash REAL DEFAULT 0, total_sales_cliq REAL DEFAULT 0,
        total_sales REAL DEFAULT 0, notes TEXT,
        status TEXT DEFAULT "open",
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')

    # جدول الطلبات
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        daily_record_id INTEGER, table_number INTEGER,
        customer_name TEXT, account_id INTEGER,
        payment_method TEXT DEFAULT "cash",
        total_amount REAL NOT NULL,
        status TEXT DEFAULT "completed", notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (daily_record_id) REFERENCES daily_records(id),
        FOREIGN KEY (account_id) REFERENCES accounts(id))''')

    # جدول تفاصيل الطلبات
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
        item_name TEXT NOT NULL, quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL, total_price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES items(id))''')

    # جدول الذمم
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL, phone TEXT,
        total_debt REAL DEFAULT 0, notes TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')

    # جدول معاملات الذمم
    c.execute('''CREATE TABLE IF NOT EXISTS account_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL, order_id INTEGER,
        type TEXT NOT NULL, amount REAL NOT NULL,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
        FOREIGN KEY (order_id) REFERENCES orders(id))''')

    # جدول عناصر المخزون
    c.execute('''CREATE TABLE IF NOT EXISTS inventory_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, unit TEXT NOT NULL,
        current_stock REAL DEFAULT 0, min_stock REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')

    # جدول حركات المخزون
    c.execute('''CREATE TABLE IF NOT EXISTS inventory_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        type TEXT NOT NULL, quantity REAL NOT NULL,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES inventory_items(id) ON DELETE CASCADE)''')

    # جدول الإعدادات
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')

    conn.commit()
    _seed_defaults(c, conn)
    conn.close()
    print("✅ قاعدة البيانات جاهزة")


def _seed_defaults(c, conn):
    """إدراج بيانات البداية الافتراضية"""
    for key, value in [
        ('cafe_name','نشمي كافيه'),('phone','0791234567'),
        ('tables_count','15'),('currency','د.أ'),
        ('wifi_name','Nashmi_Cafe'),('wifi_password',''),
        ('footer_text','شكراً لزيارتكم — نشمي كافيه'),
        ('admin_password','admin123'),
    ]:
        c.execute('INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)',(key,value))

    for name,name_ar,icon,order in [
        ('hot_coffee','قهوة ساخنة','☕',1),('cold_coffee','قهوة باردة','🧊',2),
        ('drinks','مشروبات','🥤',3),('hookah','أراجيل','💨',4),
        ('car_wash','غسيل سيارات','🚗',5),
    ]:
        c.execute('INSERT OR IGNORE INTO categories (name,name_ar,icon,sort_order) VALUES (?,?,?,?)',
                  (name,name_ar,icon,order))
    conn.commit()

    c.execute('SELECT COUNT(*) AS cnt FROM items')
    if c.fetchone()['cnt'] == 0:
        for cat,name,name_ar,price,desc in [
            (1,'Espresso','إسبريسو',1.5,'قهوة إسبريسو أصيلة'),
            (1,'Cappuccino','كابتشينو',2.5,'كابتشينو كريمي'),
            (1,'Latte','لاتيه',2.5,'لاتيه ناعم'),
            (1,'Turkish Coffee','قهوة تركية',1.5,'قهوة تركية أصيلة'),
            (1,'Nescafe','نسكافيه',2.0,'نسكافيه ساخن'),
            (1,'White Coffee','وايت كوفي',2.5,'قهوة بيضاء'),
            (2,'Iced Latte','آيس لاتيه',3.0,'لاتيه مثلج'),
            (2,'Frappuccino','فرابتشينو',3.5,'فرابتشينو كريمي'),
            (2,'Cold Brew','كولد برو',3.0,'قهوة باردة'),
            (2,'Iced Caramel','آيس كراميل',3.5,'كراميل مثلج'),
            (3,'Fresh Juice','عصير طازج',2.0,'عصير فواكه طازج'),
            (3,'Smoothie','سموذي',3.0,'سموذي فواكه'),
            (3,'Soft Drink','مشروب غازي',1.0,'مشروب غازي'),
            (3,'Water','ماء',0.5,'ماء معدني'),
            (3,'Lemonade','ليمون نعناع',2.0,'عصير ليمون نعناع'),
            (4,'Hookah Standard','أرجيلة عادية',5.0,'أرجيلة بنكهات متعددة'),
            (4,'Hookah Premium','أرجيلة بريميوم',7.0,'أرجيلة بريميوم'),
            (4,'Hookah Double','أرجيلة دبل',8.0,'أرجيلة دبل فحم'),
            (5,'Basic Wash','غسيل عادي',5.0,'غسيل خارجي'),
            (5,'Premium Wash','غسيل بريميوم',10.0,'غسيل شامل'),
            (5,'Full Detail','تلميع كامل',20.0,'تلميع وتنظيف كامل'),
        ]:
            c.execute('INSERT INTO items (category_id,name,name_ar,price,description) VALUES (?,?,?,?,?)',
                      (cat,name,name_ar,price,desc))
        for name,unit,stock,min_s in [
            ('حبوب قهوة','كيلو',5.0,1.0),('حليب','لتر',10.0,2.0),
            ('سكر','كيلو',3.0,0.5),('معسل أرجيلة','علبة',20.0,5.0),
            ('فحم أرجيلة','كيلو',15.0,3.0),('مياه معدنية','كرتون',10.0,2.0),
        ]:
            c.execute('INSERT INTO inventory_items (name,unit,current_stock,min_stock) VALUES (?,?,?,?)',
                      (name,unit,stock,min_s))
        conn.commit()
