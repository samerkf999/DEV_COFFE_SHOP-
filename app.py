# ============================================================
# app.py — الخادم الرئيسي لنظام نشمي كافيه
# Flask Backend + REST API
# ============================================================

import os, json, base64
from datetime import datetime, date
from flask import Flask, request, jsonify, render_template, send_from_directory
from database import get_db, init_db
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'items')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB حد رفع الصور

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def row_to_dict(row):
    """تحويل صف قاعدة البيانات إلى قاموس"""
    return dict(row) if row else None


def rows_to_list(rows):
    """تحويل قائمة صفوف إلى قائمة قواميس"""
    return [dict(r) for r in rows]


# ════════════════════════════════════════════════════════════
# صفحات HTML
# ════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('admin.html')


@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/menu')
def customer_menu():
    """شاشة المنيو للزبائن (QR Code)"""
    return render_template('menu.html')


@app.route('/static/uploads/items/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ════════════════════════════════════════════════════════════
# API — الإعدادات
# ════════════════════════════════════════════════════════════

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """جلب جميع الإعدادات"""
    conn = get_db()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    conn.close()
    return jsonify({r['key']: r['value'] for r in rows})


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """تحديث الإعدادات"""
    data = request.get_json()
    conn = get_db()
    now = datetime.now().isoformat()
    for key, value in data.items():
        conn.execute(
            'INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
            (key, str(value), now)
        )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم حفظ الإعدادات'})


# ════════════════════════════════════════════════════════════
# API — التصنيفات والأصناف
# ════════════════════════════════════════════════════════════

@app.route('/api/categories', methods=['GET'])
def get_categories():
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order'
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.get_json()
    conn = get_db()
    conn.execute(
        'INSERT INTO categories (name, name_ar, icon, sort_order) VALUES (?, ?, ?, ?)',
        (data['name'], data['name_ar'], data.get('icon', '☕'), data.get('sort_order', 99))
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم إضافة التصنيف'})


@app.route('/api/items', methods=['GET'])
def get_items():
    """جلب الأصناف مع فلترة اختيارية"""
    cat_id = request.args.get('category_id')
    conn = get_db()
    if cat_id:
        rows = conn.execute(
            '''SELECT i.*, c.name_ar AS category_name FROM items i
               JOIN categories c ON i.category_id=c.id
               WHERE i.category_id=? ORDER BY i.id''', (cat_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            '''SELECT i.*, c.name_ar AS category_name FROM items i
               JOIN categories c ON i.category_id=c.id
               ORDER BY c.sort_order, i.id'''
        ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route('/api/items', methods=['POST'])
def add_item():
    data = request.get_json()
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO items (category_id, name, name_ar, price, description, is_available) VALUES (?,?,?,?,?,?)',
        (data['category_id'], data['name'], data['name_ar'],
         float(data['price']), data.get('description', ''), data.get('is_available', 1))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({'success': True, 'id': new_id, 'message': 'تم إضافة الصنف'})


@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    data = request.get_json()
    conn = get_db()
    conn.execute(
        '''UPDATE items SET category_id=?, name=?, name_ar=?, price=?,
           description=?, is_available=? WHERE id=?''',
        (data['category_id'], data['name'], data['name_ar'],
         float(data['price']), data.get('description', ''),
         data.get('is_available', 1), item_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم تحديث الصنف'})


@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    conn = get_db()
    conn.execute('DELETE FROM items WHERE id=?', (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم حذف الصنف'})


@app.route('/api/items/<int:item_id>/image', methods=['POST'])
def upload_item_image(item_id):
    """رفع صورة الصنف"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'لا توجد صورة'}), 400
    f = request.files['image']
    if f.filename == '':
        return jsonify({'success': False, 'message': 'اسم الملف فارغ'}), 400
    if f and allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        filename = f'item_{item_id}.{ext}'
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(path)
        img_url = f'/static/uploads/items/{filename}'
        conn = get_db()
        conn.execute('UPDATE items SET image_path=? WHERE id=?', (img_url, item_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'image_path': img_url})
    return jsonify({'success': False, 'message': 'نوع الملف غير مدعوم'}), 400


@app.route('/api/logo/upload', methods=['POST'])
def upload_logo():
    """رفع لوقو الكافيه"""
    if 'logo' not in request.files:
        return jsonify({'success': False, 'message': 'لا توجد صورة'}), 400
    f = request.files['logo']
    if f and allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        filename = f'logo.{ext}'
        path = os.path.join('static', filename)
        f.save(path)
        return jsonify({'success': True, 'message': 'تم تحديث اللوقو', 'logo_path': f'/static/{filename}'})
    return jsonify({'success': False, 'message': 'نوع الملف غير مدعوم'}), 400


# ════════════════════════════════════════════════════════════
# API — إدارة اليوم (فتح / إغلاق)
# ════════════════════════════════════════════════════════════

@app.route('/api/daily/today', methods=['GET'])
def get_today():
    """جلب سجل اليوم الحالي"""
    today = date.today().isoformat()
    conn = get_db()
    row = conn.execute('SELECT * FROM daily_records WHERE date=?', (today,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row))


@app.route('/api/daily/open', methods=['POST'])
def open_day():
    """فتح اليوم"""
    data = request.get_json() or {}
    today = date.today().isoformat()
    now = datetime.now().strftime('%H:%M')
    conn = get_db()
    existing = conn.execute('SELECT * FROM daily_records WHERE date=?', (today,)).fetchone()
    if existing:
        conn.close()
        return jsonify({'success': False, 'message': 'اليوم مفتوح بالفعل'})
    conn.execute(
        'INSERT INTO daily_records (date, opening_time, opening_cash, status) VALUES (?,?,?,?)',
        (today, now, float(data.get('opening_cash', 0)), 'open')
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f'تم فتح يوم {today}'})


@app.route('/api/daily/close', methods=['POST'])
def close_day():
    """إغلاق اليوم وحساب الإجماليات"""
    data = request.get_json() or {}
    today = date.today().isoformat()
    now = datetime.now().strftime('%H:%M')
    conn = get_db()

    rec = conn.execute('SELECT * FROM daily_records WHERE date=? AND status="open"', (today,)).fetchone()
    if not rec:
        conn.close()
        return jsonify({'success': False, 'message': 'لا يوجد يوم مفتوح'})

    # حساب مجموع المبيعات
    totals = conn.execute(
        '''SELECT
            COALESCE(SUM(CASE WHEN payment_method="cash"  THEN total_amount ELSE 0 END),0) AS cash,
            COALESCE(SUM(CASE WHEN payment_method="cliq"  THEN total_amount ELSE 0 END),0) AS cliq,
            COALESCE(SUM(total_amount),0) AS total
           FROM orders WHERE daily_record_id=? AND status="completed"''',
        (rec['id'],)
    ).fetchone()

    conn.execute(
        '''UPDATE daily_records SET
            closing_time=?, closing_cash=?,
            total_sales_cash=?, total_sales_cliq=?, total_sales=?,
            notes=?, status="closed"
           WHERE id=?''',
        (now, float(data.get('closing_cash', 0)),
         totals['cash'], totals['cliq'], totals['total'],
         data.get('notes', ''), rec['id'])
    )
    conn.commit()
    conn.close()
    return jsonify({
        'success': True,
        'message': 'تم إغلاق اليوم',
        'summary': {'cash': totals['cash'], 'cliq': totals['cliq'], 'total': totals['total']}
    })


@app.route('/api/daily/records', methods=['GET'])
def get_daily_records():
    """جلب سجلات الأيام"""
    limit = request.args.get('limit', 30)
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM daily_records ORDER BY date DESC LIMIT ?', (limit,)
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route('/api/daily/<int:record_id>', methods=['DELETE'])
def delete_daily_record(record_id):
    """حذف سجل يوم بالكامل"""
    conn = get_db()
    # حذف الطلبات المرتبطة أولاً
    orders = conn.execute('SELECT id FROM orders WHERE daily_record_id=?', (record_id,)).fetchall()
    for o in orders:
        conn.execute('DELETE FROM order_items WHERE order_id=?', (o['id'],))
    conn.execute('DELETE FROM orders WHERE daily_record_id=?', (record_id,))
    conn.execute('DELETE FROM daily_records WHERE id=?', (record_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم حذف السجل'})


# ════════════════════════════════════════════════════════════
# API — الطلبات والمبيعات
# ════════════════════════════════════════════════════════════

@app.route('/api/orders', methods=['POST'])
def create_order():
    """إنشاء طلب جديد"""
    data = request.get_json()
    today = date.today().isoformat()
    now = datetime.now().isoformat()
    conn = get_db()

    # جلب أو إنشاء سجل اليوم
    rec = conn.execute('SELECT id FROM daily_records WHERE date=?', (today,)).fetchone()
    if not rec:
        conn.execute('INSERT INTO daily_records (date, opening_time, status) VALUES (?,?,?)',
                     (today, datetime.now().strftime('%H:%M'), 'open'))
        conn.commit()
        rec = conn.execute('SELECT id FROM daily_records WHERE date=?', (today,)).fetchone()

    daily_id = rec['id']
    items_data = data.get('items', [])
    total = sum(i['quantity'] * i['unit_price'] for i in items_data)

    # تحديد طريقة الدفع — ذمة إذا كان account_id موجوداً
    payment = data.get('payment_method', 'cash')
    account_id = data.get('account_id')
    if account_id:
        payment = 'account'

    cur = conn.execute(
        '''INSERT INTO orders
           (daily_record_id, table_number, customer_name, account_id,
            payment_method, total_amount, notes, created_at)
           VALUES (?,?,?,?,?,?,?,?)''',
        (daily_id, data.get('table_number'), data.get('customer_name', ''),
         account_id, payment, total, data.get('notes', ''), now)
    )
    order_id = cur.lastrowid

    for it in items_data:
        conn.execute(
            '''INSERT INTO order_items
               (order_id, item_id, item_name, quantity, unit_price, total_price)
               VALUES (?,?,?,?,?,?)''',
            (order_id, it['item_id'], it['item_name'],
             it['quantity'], it['unit_price'],
             it['quantity'] * it['unit_price'])
        )

    # تحديث رصيد الذمة إذا كان الدفع بالآجل
    if account_id:
        conn.execute('UPDATE accounts SET total_debt=total_debt+? WHERE id=?', (total, account_id))
        conn.execute(
            '''INSERT INTO account_transactions (account_id, order_id, type, amount, description)
               VALUES (?,?,"debit",?,?)''',
            (account_id, order_id, total, f'فاتورة طاولة {data.get("table_number","—")}')
        )

    # تحديث إجماليات اليوم
    if payment == 'cash':
        conn.execute('UPDATE daily_records SET total_sales_cash=total_sales_cash+?, total_sales=total_sales+? WHERE id=?',
                     (total, total, daily_id))
    elif payment == 'cliq':
        conn.execute('UPDATE daily_records SET total_sales_cliq=total_sales_cliq+?, total_sales=total_sales+? WHERE id=?',
                     (total, total, daily_id))
    else:
        conn.execute('UPDATE daily_records SET total_sales=total_sales+? WHERE id=?', (total, daily_id))

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'order_id': order_id, 'total': total})


@app.route('/api/orders', methods=['GET'])
def get_orders():
    """جلب الطلبات مع فلترة تاريخية"""
    date_filter = request.args.get('date', date.today().isoformat())
    conn = get_db()
    rows = conn.execute(
        '''SELECT o.*, d.date AS order_date FROM orders o
           LEFT JOIN daily_records d ON o.daily_record_id=d.id
           WHERE d.date=? ORDER BY o.created_at DESC''',
        (date_filter,)
    ).fetchall()
    result = []
    for r in rows:
        order = dict(r)
        items = conn.execute(
            'SELECT * FROM order_items WHERE order_id=?', (r['id'],)
        ).fetchall()
        order['items'] = rows_to_list(items)
        result.append(order)
    conn.close()
    return jsonify(result)


@app.route('/api/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    conn = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
    if not order:
        conn.close()
        return jsonify({'success': False, 'message': 'الطلب غير موجود'})

    # عكس إجماليات اليوم
    total = order['total_amount']
    pm = order['payment_method']
    if pm == 'cash':
        conn.execute('UPDATE daily_records SET total_sales_cash=total_sales_cash-?, total_sales=total_sales-? WHERE id=?',
                     (total, total, order['daily_record_id']))
    elif pm == 'cliq':
        conn.execute('UPDATE daily_records SET total_sales_cliq=total_sales_cliq-?, total_sales=total_sales-? WHERE id=?',
                     (total, total, order['daily_record_id']))
    else:
        conn.execute('UPDATE daily_records SET total_sales=total_sales-? WHERE id=?',
                     (total, order['daily_record_id']))

    # عكس رصيد الذمة
    if order['account_id']:
        conn.execute('UPDATE accounts SET total_debt=total_debt-? WHERE id=?',
                     (total, order['account_id']))

    conn.execute('DELETE FROM order_items WHERE order_id=?', (order_id,))
    conn.execute('DELETE FROM orders WHERE id=?', (order_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم حذف الطلب'})


# ════════════════════════════════════════════════════════════
# API — الذمم (حسابات الزبائن الآجلة)
# ════════════════════════════════════════════════════════════

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM accounts WHERE is_active=1 ORDER BY total_debt DESC'
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route('/api/accounts', methods=['POST'])
def add_account():
    data = request.get_json()
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO accounts (customer_name, phone, notes) VALUES (?,?,?)',
        (data['customer_name'], data.get('phone', ''), data.get('notes', ''))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({'success': True, 'id': new_id, 'message': 'تم إضافة الحساب'})


@app.route('/api/accounts/<int:acc_id>', methods=['GET'])
def get_account_detail(acc_id):
    conn = get_db()
    acc = conn.execute('SELECT * FROM accounts WHERE id=?', (acc_id,)).fetchone()
    txns = conn.execute(
        'SELECT * FROM account_transactions WHERE account_id=? ORDER BY created_at DESC',
        (acc_id,)
    ).fetchall()
    conn.close()
    if not acc:
        return jsonify({'success': False, 'message': 'الحساب غير موجود'}), 404
    return jsonify({'account': row_to_dict(acc), 'transactions': rows_to_list(txns)})


@app.route('/api/accounts/<int:acc_id>/pay', methods=['POST'])
def account_payment(acc_id):
    """تسجيل دفعة على حساب ذمة"""
    data = request.get_json()
    amount = float(data['amount'])
    conn = get_db()
    acc = conn.execute('SELECT * FROM accounts WHERE id=?', (acc_id,)).fetchone()
    if not acc:
        conn.close()
        return jsonify({'success': False, 'message': 'الحساب غير موجود'}), 404

    conn.execute('UPDATE accounts SET total_debt=total_debt-? WHERE id=?', (amount, acc_id))
    conn.execute(
        '''INSERT INTO account_transactions (account_id, type, amount, description)
           VALUES (?,"credit",?,?)''',
        (acc_id, amount, data.get('description', 'دفعة نقدية'))
    )
    conn.commit()
    new_debt = conn.execute('SELECT total_debt FROM accounts WHERE id=?', (acc_id,)).fetchone()['total_debt']
    conn.close()
    return jsonify({'success': True, 'new_debt': new_debt, 'message': 'تم تسجيل الدفعة'})


@app.route('/api/accounts/<int:acc_id>', methods=['DELETE'])
def delete_account(acc_id):
    conn = get_db()
    conn.execute('UPDATE accounts SET is_active=0 WHERE id=?', (acc_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم أرشفة الحساب'})


# ════════════════════════════════════════════════════════════
# API — المخزون
# ════════════════════════════════════════════════════════════

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    conn = get_db()
    rows = conn.execute('SELECT * FROM inventory_items ORDER BY name').fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route('/api/inventory', methods=['POST'])
def add_inventory_item():
    data = request.get_json()
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO inventory_items (name, unit, current_stock, min_stock) VALUES (?,?,?,?)',
        (data['name'], data['unit'],
         float(data.get('current_stock', 0)),
         float(data.get('min_stock', 0)))
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': cur.lastrowid})


@app.route('/api/inventory/<int:item_id>/restock', methods=['POST'])
def restock_inventory(item_id):
    """إضافة كمية للمخزون (وارد جديد)"""
    data = request.get_json()
    qty = float(data['quantity'])
    conn = get_db()
    conn.execute('UPDATE inventory_items SET current_stock=current_stock+? WHERE id=?', (qty, item_id))
    conn.execute(
        'INSERT INTO inventory_transactions (item_id, type, quantity, notes) VALUES (?,"in",?,?)',
        (item_id, qty, data.get('notes', 'وارد جديد'))
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم تحديث المخزون'})


@app.route('/api/inventory/<int:item_id>/adjust', methods=['POST'])
def adjust_inventory(item_id):
    """تعديل المخزون (جرد فعلي)"""
    data = request.get_json()
    new_qty = float(data['quantity'])
    conn = get_db()
    old = conn.execute('SELECT current_stock FROM inventory_items WHERE id=?', (item_id,)).fetchone()
    diff = new_qty - old['current_stock']
    conn.execute('UPDATE inventory_items SET current_stock=? WHERE id=?', (new_qty, item_id))
    conn.execute(
        'INSERT INTO inventory_transactions (item_id, type, quantity, notes) VALUES (?,"adjust",?,?)',
        (item_id, diff, f'جرد فعلي — تعديل {diff:+.2f}')
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم تحديث الجرد'})


@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def delete_inventory_item(item_id):
    conn = get_db()
    conn.execute('DELETE FROM inventory_items WHERE id=?', (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ════════════════════════════════════════════════════════════
# API — التقارير والإحصاءات
# ════════════════════════════════════════════════════════════

@app.route('/api/reports/dashboard', methods=['GET'])
def dashboard_stats():
    """إحصاءات لوحة التحكم"""
    today = date.today().isoformat()
    conn = get_db()

    # مبيعات اليوم
    today_rec = conn.execute('SELECT * FROM daily_records WHERE date=?', (today,)).fetchone()
    today_sales = today_rec['total_sales'] if today_rec else 0
    today_cash = today_rec['total_sales_cash'] if today_rec else 0
    today_cliq = today_rec['total_sales_cliq'] if today_rec else 0

    # عدد طلبات اليوم
    today_orders = 0
    if today_rec:
        r = conn.execute('SELECT COUNT(*) AS cnt FROM orders WHERE daily_record_id=?',
                         (today_rec['id'],)).fetchone()
        today_orders = r['cnt']

    # إجمالي الذمم
    total_debt = conn.execute(
        'SELECT COALESCE(SUM(total_debt),0) AS s FROM accounts WHERE is_active=1'
    ).fetchone()['s']

    # عدد الأصناف
    items_count = conn.execute('SELECT COUNT(*) AS cnt FROM items WHERE is_available=1').fetchone()['cnt']

    # مواد المخزون المنخفضة
    low_stock = conn.execute(
        'SELECT COUNT(*) AS cnt FROM inventory_items WHERE current_stock <= min_stock'
    ).fetchone()['cnt']

    # آخر 7 أيام مبيعات
    weekly = conn.execute(
        '''SELECT date, total_sales, total_sales_cash, total_sales_cliq
           FROM daily_records ORDER BY date DESC LIMIT 7'''
    ).fetchall()

    conn.close()
    return jsonify({
        'today_sales': round(today_sales, 3),
        'today_cash': round(today_cash, 3),
        'today_cliq': round(today_cliq, 3),
        'today_orders': today_orders,
        'total_debt': round(total_debt, 3),
        'items_count': items_count,
        'low_stock_count': low_stock,
        'day_status': today_rec['status'] if today_rec else 'closed',
        'weekly_sales': rows_to_list(weekly)
    })


@app.route('/api/reports/top-items', methods=['GET'])
def top_items():
    """الأصناف الأكثر والأقل مبيعاً"""
    limit = int(request.args.get('limit', 10))
    date_from = request.args.get('from', '')
    date_to = request.args.get('to', date.today().isoformat())

    conn = get_db()
    date_clause = ''
    params_top = []
    params_bot = []

    if date_from:
        date_clause = '''AND d.date BETWEEN ? AND ?'''
        params_top = [date_from, date_to, limit]
        params_bot = [date_from, date_to, limit]
    else:
        params_top = [limit]
        params_bot = [limit]

    query = f'''
        SELECT oi.item_name, oi.item_id,
               SUM(oi.quantity) AS total_qty,
               SUM(oi.total_price) AS total_revenue
        FROM order_items oi
        JOIN orders o ON oi.order_id=o.id
        JOIN daily_records d ON o.daily_record_id=d.id
        WHERE o.status="completed" {date_clause}
        GROUP BY oi.item_id, oi.item_name
        ORDER BY total_qty DESC LIMIT ?'''

    top = conn.execute(query, params_top).fetchall()

    query_bot = query.replace('DESC LIMIT', 'ASC LIMIT')
    bot = conn.execute(query_bot, params_bot).fetchall()

    conn.close()
    return jsonify({'top': rows_to_list(top), 'bottom': rows_to_list(bot)})


@app.route('/api/reports/monthly', methods=['GET'])
def monthly_report():
    """تقرير شهري"""
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    conn = get_db()
    rows = conn.execute(
        '''SELECT date, total_sales, total_sales_cash, total_sales_cliq, status
           FROM daily_records WHERE date LIKE ? ORDER BY date''',
        (f'{month}%',)
    ).fetchall()
    totals = conn.execute(
        '''SELECT
            COALESCE(SUM(total_sales),0) AS total,
            COALESCE(SUM(total_sales_cash),0) AS cash,
            COALESCE(SUM(total_sales_cliq),0) AS cliq,
            COUNT(*) AS days
           FROM daily_records WHERE date LIKE ?''',
        (f'{month}%',)
    ).fetchone()
    conn.close()
    return jsonify({'records': rows_to_list(rows), 'totals': row_to_dict(totals)})


# ════════════════════════════════════════════════════════════
# نقطة الدخول
# ════════════════════════════════════════════════════════════

if __name__ == '__main__':
    os.makedirs(os.path.join('static', 'uploads', 'items'), exist_ok=True)
    init_db()
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'dev':
        print("🚀 نشمي كافيه — النظام يعمل على http://localhost:5000")
        print("📋 لوحة الإدارة: http://localhost:5000/admin")
        print("📱 منيو الزبائن: http://localhost:5000/menu")
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        # Production mode (Render, Heroku, etc.)
        port = int(os.environ.get('PORT', 5000))
        app.run(debug=False, host='0.0.0.0', port=port)
