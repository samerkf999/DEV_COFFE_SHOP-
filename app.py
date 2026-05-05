# ============================================================
# app.py — نظام نشمي كافيه (نسخة محسّنة مع RBAC)
# ============================================================
import os, json, logging
from datetime import datetime, date
from functools import wraps
from flask import Flask, request, jsonify, render_template, \
    send_from_directory, session, redirect, url_for
from database import get_db, init_db
from werkzeug.utils import secure_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'))
app.secret_key = os.environ.get('SECRET_KEY', 'nashmi-super-secret-2024!')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'items')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ════════════════════════════════════════════════════════════
# RBAC — المستخدمون والصلاحيات
# ════════════════════════════════════════════════════════════
USERS = {
    '1234': {'name': 'أبو نشمي',  'role': 'owner',    'nameEn': 'Owner'},
    '5555': {'name': 'نشمي',       'role': 'manager',  'nameEn': 'Manager'},
    '9999': {'name': 'عمر',        'role': 'employee', 'nameEn': 'Omar'},
    '0000': {'name': 'ناصر',       'role': 'employee', 'nameEn': 'Nasser'},
}
ROLE_PAGES = {
    'owner':    'admin',
    'manager':  'manager',
    'employee': 'pos',
}

def login_required(roles=None):
    """Decorator للتحقق من الجلسة والدور"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user' not in session:
                if request.is_json:
                    return jsonify({'success': False, 'message': 'غير مصرح', 'redirect': '/login'}), 401
                return redirect(url_for('login_page'))
            if roles and session['user']['role'] not in roles:
                if request.is_json:
                    return jsonify({'success': False, 'message': 'ليس لديك صلاحية'}), 403
                return redirect(url_for('login_page'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ════════════════════════════════════════════════════════════
# مساعدات
# ════════════════════════════════════════════════════════════
def allowed_file(fn): return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def row_to_dict(r): return dict(r) if r else None
def rows_to_list(r): return [dict(x) for x in r]

@app.before_request
def init_database():
    try: init_db()
    except Exception as e: logger.error(f"DB Init Error: {e}")

@app.errorhandler(500)
def err500(e):
    logger.error(f"500: {e}")
    return jsonify({'success': False, 'message': 'خطأ في الخادم'}), 500

# ════════════════════════════════════════════════════════════
# صفحات HTML
# ════════════════════════════════════════════════════════════
@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    role = session['user']['role']
    return redirect(url_for(ROLE_PAGES[role]))

@app.route('/login')
def login_page():
    if 'user' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/admin')
@login_required(roles=['owner'])
def admin():
    return render_template('admin.html')

@app.route('/manager')
@login_required(roles=['owner', 'manager'])
def manager():
    return render_template('manager.html')

@app.route('/pos')
@login_required(roles=['owner', 'manager', 'employee'])
def pos():
    return render_template('pos.html')

@app.route('/menu')
def customer_menu():
    return render_template('menu.html')

@app.route('/customer-order')
def customer_order():
    return render_template('customer_order.html')

@app.route('/static/uploads/items/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ════════════════════════════════════════════════════════════
# API — Auth
# ════════════════════════════════════════════════════════════
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json()
    pw = str(data.get('password', '')).strip()
    user = USERS.get(pw)
    if not user:
        return jsonify({'success': False, 'message': 'كلمة المرور غير صحيحة'}), 401
    session.permanent = True
    session['user'] = {'name': user['name'], 'role': user['role'], 'nameEn': user['nameEn']}
    return jsonify({'success': True, 'user': session['user'], 'redirect': '/' + ROLE_PAGES[user['role']]})

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True, 'redirect': '/login'})

@app.route('/api/auth/me', methods=['GET'])
def api_me():
    if 'user' not in session:
        return jsonify({'loggedIn': False}), 401
    return jsonify({'loggedIn': True, 'user': session['user']})

# ════════════════════════════════════════════════════════════
# API — الإعدادات
# ════════════════════════════════════════════════════════════
@app.route('/api/settings', methods=['GET'])
def get_settings():
    conn = get_db()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    conn.close()
    return jsonify({r['key']: r['value'] for r in rows})

@app.route('/api/settings', methods=['POST'])
@login_required(roles=['owner'])
def update_settings():
    data = request.get_json()
    conn = get_db()
    now = datetime.now().isoformat()
    for key, value in data.items():
        conn.execute('INSERT OR REPLACE INTO settings (key,value,updated_at) VALUES (?,?,?)', (key, str(value), now))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم حفظ الإعدادات'})

# ════════════════════════════════════════════════════════════
# API — التصنيفات
# ════════════════════════════════════════════════════════════
@app.route('/api/categories', methods=['GET'])
def get_categories():
    conn = get_db()
    rows = conn.execute('SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order').fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@app.route('/api/categories', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def add_category():
    data = request.get_json()
    conn = get_db()
    conn.execute('INSERT INTO categories (name,name_ar,icon,sort_order) VALUES (?,?,?,?)',
        (data['name'], data['name_ar'], data.get('icon', '☕'), data.get('sort_order', 99)))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تمت الإضافة'})

# ════════════════════════════════════════════════════════════
# API — الأصناف
# ════════════════════════════════════════════════════════════
@app.route('/api/items', methods=['GET'])
def get_items():
    cat = request.args.get('category_id')
    conn = get_db()
    if cat:
        rows = conn.execute(
            'SELECT i.*,c.name_ar AS category_name FROM items i JOIN categories c ON i.category_id=c.id WHERE i.category_id=? ORDER BY i.id', (cat,)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT i.*,c.name_ar AS category_name FROM items i JOIN categories c ON i.category_id=c.id ORDER BY c.sort_order,i.id'
        ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@app.route('/api/items', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def add_item():
    data = request.get_json()
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO items (category_id,name,name_ar,price,description,is_available) VALUES (?,?,?,?,?,?)',
        (data['category_id'], data['name'], data['name_ar'], float(data['price']), data.get('description',''), data.get('is_available',1))
    )
    conn.commit(); nid = cur.lastrowid; conn.close()
    return jsonify({'success': True, 'id': nid, 'message': 'تمت الإضافة'})

@app.route('/api/items/<int:iid>', methods=['PUT'])
@login_required(roles=['owner', 'manager'])
def update_item(iid):
    data = request.get_json()
    conn = get_db()
    conn.execute(
        'UPDATE items SET category_id=?,name=?,name_ar=?,price=?,description=?,is_available=? WHERE id=?',
        (data['category_id'], data['name'], data['name_ar'], float(data['price']), data.get('description',''), data.get('is_available',1), iid)
    )
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم التحديث'})

@app.route('/api/items/<int:iid>', methods=['DELETE'])
@login_required(roles=['owner'])
def delete_item(iid):
    conn = get_db()
    conn.execute('DELETE FROM items WHERE id=?', (iid,))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم الحذف'})

@app.route('/api/items/<int:iid>/image', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def upload_item_image(iid):
    if 'image' not in request.files: return jsonify({'success': False, 'message': 'لا توجد صورة'}), 400
    f = request.files['image']
    if f and allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        fn = f'item_{iid}.{ext}'
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
        url = f'/static/uploads/items/{fn}'
        conn = get_db()
        conn.execute('UPDATE items SET image_path=? WHERE id=?', (url, iid))
        conn.commit(); conn.close()
        return jsonify({'success': True, 'image_path': url})
    return jsonify({'success': False, 'message': 'نوع غير مدعوم'}), 400

@app.route('/api/logo/upload', methods=['POST'])
@login_required(roles=['owner'])
def upload_logo():
    if 'logo' not in request.files: return jsonify({'success': False}), 400
    f = request.files['logo']
    if f and allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        f.save(os.path.join(BASE_DIR, 'static', f'logo.{ext}'))
        return jsonify({'success': True, 'message': 'تم تحديث اللوقو'})
    return jsonify({'success': False}), 400

# ════════════════════════════════════════════════════════════
# API — إدارة اليوم
# ════════════════════════════════════════════════════════════
@app.route('/api/daily/today', methods=['GET'])
def daily_today():
    conn = get_db()
    rec = conn.execute('SELECT * FROM daily_records WHERE date=?', (date.today().isoformat(),)).fetchone()
    conn.close()
    return jsonify(row_to_dict(rec) or {})

@app.route('/api/daily/open', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def daily_open():
    data = request.get_json() or {}
    today = date.today().isoformat()
    conn = get_db()
    ex = conn.execute('SELECT id FROM daily_records WHERE date=?', (today,)).fetchone()
    if ex:
        conn.close()
        return jsonify({'success': False, 'message': 'اليوم مفتوح بالفعل'})
    conn.execute('INSERT INTO daily_records (date,opening_time,opening_cash,status) VALUES (?,?,?,?)',
        (today, datetime.now().strftime('%H:%M'), float(data.get('opening_cash', 0)), 'open'))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم فتح اليوم'})

@app.route('/api/daily/close', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def daily_close():
    data = request.get_json() or {}
    today = date.today().isoformat()
    conn = get_db()
    rec = conn.execute('SELECT * FROM daily_records WHERE date=? AND status=?', (today, 'open')).fetchone()
    if not rec:
        conn.close()
        return jsonify({'success': False, 'message': 'لا يوجد يوم مفتوح'})
    now = datetime.now().strftime('%H:%M')
    conn.execute('''UPDATE daily_records SET status=?,closing_time=?,closing_cash=?,notes=? WHERE id=?''',
        ('closed', now, float(data.get('closing_cash', 0)), data.get('notes', ''), rec['id']))
    conn.commit()
    summary = conn.execute('SELECT * FROM daily_records WHERE id=?', (rec['id'],)).fetchone()
    conn.close()
    return jsonify({'success': True, 'message': 'تم إغلاق اليوم', 'summary': row_to_dict(summary)})

@app.route('/api/daily/records', methods=['GET'])
@login_required(roles=['owner', 'manager'])
def daily_records():
    limit = request.args.get('limit', 30)
    conn = get_db()
    rows = conn.execute('SELECT * FROM daily_records ORDER BY date DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@app.route('/api/daily/<int:rid>', methods=['DELETE'])
@login_required(roles=['owner'])
def delete_daily(rid):
    conn = get_db()
    conn.execute('DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE daily_record_id=?)', (rid,))
    conn.execute('DELETE FROM orders WHERE daily_record_id=?', (rid,))
    conn.execute('DELETE FROM daily_records WHERE id=?', (rid,))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم الحذف'})

# ════════════════════════════════════════════════════════════
# API — الطلبات
# ════════════════════════════════════════════════════════════
@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    items = data.get('items', [])
    if not items:
        return jsonify({'success': False, 'message': 'السلة فارغة'}), 400
    total = sum(float(i['unit_price']) * int(i['quantity']) for i in items)
    today = date.today().isoformat()
    conn = get_db()
    rec = conn.execute('SELECT id FROM daily_records WHERE date=? AND status=?', (today, 'open')).fetchone()
    if not rec:
        conn.close()
        return jsonify({'success': False, 'message': 'اليوم غير مفتوح — يرجى فتح اليوم أولاً'}), 400
    pm = data.get('payment_method', 'cash')
    acc_id = data.get('account_id')
    source = data.get('source', 'pos')  # pos | customer
    cur = conn.execute(
        'INSERT INTO orders (daily_record_id,table_number,customer_name,account_id,payment_method,total_amount,source,created_at) VALUES (?,?,?,?,?,?,?,?)',
        (rec['id'], data.get('table_number'), data.get('customer_name'), acc_id, pm, total, source, datetime.now().isoformat())
    )
    oid = cur.lastrowid
    for it in items:
        conn.execute(
            'INSERT INTO order_items (order_id,item_id,item_name,quantity,unit_price,total_price) VALUES (?,?,?,?,?,?)',
            (oid, it['item_id'], it['item_name'], it['quantity'], float(it['unit_price']), float(it['unit_price']) * int(it['quantity']))
        )
    # تحديث الإجماليات
    if pm == 'cash':
        conn.execute('UPDATE daily_records SET total_sales_cash=total_sales_cash+?,total_sales=total_sales+? WHERE id=?', (total, total, rec['id']))
    elif pm == 'cliq':
        conn.execute('UPDATE daily_records SET total_sales_cliq=total_sales_cliq+?,total_sales=total_sales+? WHERE id=?', (total, total, rec['id']))
    elif pm == 'account' and acc_id:
        conn.execute('UPDATE accounts SET total_debt=total_debt+? WHERE id=?', (total, acc_id))
        conn.execute('INSERT INTO account_transactions (account_id,type,amount,description,created_at) VALUES (?,?,?,?,?)',
            (acc_id, 'debit', total, f'طلب #{oid}', datetime.now().isoformat()))
        conn.execute('UPDATE daily_records SET total_sales=total_sales+? WHERE id=?', (total, rec['id']))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'order_id': oid, 'total': total})

@app.route('/api/orders', methods=['GET'])
@login_required(roles=['owner', 'manager', 'employee'])
def get_orders():
    d = request.args.get('date', date.today().isoformat())
    conn = get_db()
    orders = conn.execute(
        'SELECT o.* FROM orders o JOIN daily_records dr ON o.daily_record_id=dr.id WHERE dr.date=? ORDER BY o.id DESC', (d,)
    ).fetchall()
    result = []
    for o in orders:
        od = dict(o)
        od['items'] = rows_to_list(conn.execute('SELECT * FROM order_items WHERE order_id=?', (o['id'],)).fetchall())
        result.append(od)
    conn.close()
    return jsonify(result)

@app.route('/api/orders/<int:oid>', methods=['DELETE'])
@login_required(roles=['owner', 'manager'])
def delete_order(oid):
    conn = get_db()
    o = conn.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    if not o:
        conn.close()
        return jsonify({'success': False, 'message': 'الطلب غير موجود'}), 404
    t = o['total_amount']
    pm = o['payment_method']
    rid = o['daily_record_id']
    if pm == 'cash':
        conn.execute('UPDATE daily_records SET total_sales_cash=total_sales_cash-?,total_sales=total_sales-? WHERE id=?', (t, t, rid))
    elif pm == 'cliq':
        conn.execute('UPDATE daily_records SET total_sales_cliq=total_sales_cliq-?,total_sales=total_sales-? WHERE id=?', (t, t, rid))
    elif pm == 'account' and o['account_id']:
        conn.execute('UPDATE accounts SET total_debt=total_debt-? WHERE id=?', (t, o['account_id']))
        conn.execute('UPDATE daily_records SET total_sales=total_sales-? WHERE id=?', (t, rid))
    conn.execute('DELETE FROM order_items WHERE order_id=?', (oid,))
    conn.execute('DELETE FROM orders WHERE id=?', (oid,))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم حذف الطلب'})

# ════════════════════════════════════════════════════════════
# API — الذمم
# ════════════════════════════════════════════════════════════
@app.route('/api/accounts', methods=['GET'])
@login_required(roles=['owner', 'manager'])
def get_accounts():
    conn = get_db()
    rows = conn.execute('SELECT * FROM accounts WHERE is_active=1 ORDER BY customer_name').fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@app.route('/api/accounts', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def add_account():
    data = request.get_json()
    if not data.get('customer_name'):
        return jsonify({'success': False, 'message': 'الاسم مطلوب'}), 400
    conn = get_db()
    conn.execute('INSERT INTO accounts (customer_name,phone) VALUES (?,?)', (data['customer_name'], data.get('phone', '')))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تمت الإضافة'})

@app.route('/api/accounts/<int:aid>', methods=['GET'])
@login_required(roles=['owner', 'manager'])
def get_account(aid):
    conn = get_db()
    a = conn.execute('SELECT * FROM accounts WHERE id=?', (aid,)).fetchone()
    txns = conn.execute('SELECT * FROM account_transactions WHERE account_id=? ORDER BY id DESC', (aid,)).fetchall()
    conn.close()
    return jsonify({'account': row_to_dict(a), 'transactions': rows_to_list(txns)})

@app.route('/api/accounts/<int:aid>/pay', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def pay_account(aid):
    data = request.get_json()
    amt = float(data.get('amount', 0))
    if amt <= 0:
        return jsonify({'success': False, 'message': 'مبلغ غير صحيح'}), 400
    conn = get_db()
    conn.execute('UPDATE accounts SET total_debt=total_debt-? WHERE id=?', (amt, aid))
    conn.execute('INSERT INTO account_transactions (account_id,type,amount,description,created_at) VALUES (?,?,?,?,?)',
        (aid, 'credit', amt, data.get('description', 'دفعة'), datetime.now().isoformat()))
    conn.commit()
    new_debt = conn.execute('SELECT total_debt FROM accounts WHERE id=?', (aid,)).fetchone()['total_debt']
    conn.close()
    return jsonify({'success': True, 'message': 'تم تسجيل الدفعة', 'new_debt': new_debt})

@app.route('/api/accounts/<int:aid>', methods=['DELETE'])
@login_required(roles=['owner'])
def delete_account(aid):
    conn = get_db()
    conn.execute('UPDATE accounts SET is_active=0 WHERE id=?', (aid,))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم الأرشفة'})

# ════════════════════════════════════════════════════════════
# API — المخزون
# ════════════════════════════════════════════════════════════
@app.route('/api/inventory', methods=['GET'])
@login_required(roles=['owner', 'manager'])
def get_inventory():
    conn = get_db()
    rows = conn.execute('SELECT * FROM inventory_items ORDER BY name').fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@app.route('/api/inventory', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def add_inventory():
    data = request.get_json()
    conn = get_db()
    conn.execute('INSERT INTO inventory_items (name,unit,current_stock,min_stock) VALUES (?,?,?,?)',
        (data['name'], data['unit'], float(data.get('current_stock', 0)), float(data.get('min_stock', 0))))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تمت الإضافة'})

@app.route('/api/inventory/<int:iid>/restock', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def restock(iid):
    data = request.get_json()
    qty = float(data.get('quantity', 0))
    conn = get_db()
    conn.execute('UPDATE inventory_items SET current_stock=current_stock+? WHERE id=?', (qty, iid))
    conn.execute('INSERT INTO inventory_transactions (inventory_item_id,type,quantity,notes,created_at) VALUES (?,?,?,?,?)',
        (iid, 'in', qty, data.get('notes', ''), datetime.now().isoformat()))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم تسجيل الوارد'})

@app.route('/api/inventory/<int:iid>/adjust', methods=['POST'])
@login_required(roles=['owner', 'manager'])
def adjust(iid):
    data = request.get_json()
    qty = float(data.get('quantity', 0))
    conn = get_db()
    old = conn.execute('SELECT current_stock FROM inventory_items WHERE id=?', (iid,)).fetchone()['current_stock']
    diff = qty - old
    conn.execute('UPDATE inventory_items SET current_stock=? WHERE id=?', (qty, iid))
    conn.execute('INSERT INTO inventory_transactions (inventory_item_id,type,quantity,notes,created_at) VALUES (?,?,?,?,?)',
        (iid, 'adjust', diff, data.get('notes', 'جرد'), datetime.now().isoformat()))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم تحديث المخزون'})

@app.route('/api/inventory/<int:iid>', methods=['DELETE'])
@login_required(roles=['owner'])
def del_inventory(iid):
    conn = get_db()
    conn.execute('DELETE FROM inventory_items WHERE id=?', (iid,))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': 'تم الحذف'})

# ════════════════════════════════════════════════════════════
# API — التقارير
# ════════════════════════════════════════════════════════════
@app.route('/api/reports/dashboard', methods=['GET'])
@login_required(roles=['owner', 'manager'])
def dashboard():
    today = date.today().isoformat()
    conn = get_db()
    rec = conn.execute('SELECT * FROM daily_records WHERE date=?', (today,)).fetchone()
    items_count = conn.execute('SELECT COUNT(*) AS c FROM items WHERE is_available=1').fetchone()['c']
    debt = conn.execute('SELECT COALESCE(SUM(total_debt),0) AS d FROM accounts WHERE is_active=1').fetchone()['d']
    low = conn.execute('SELECT COUNT(*) AS c FROM inventory_items WHERE current_stock<=min_stock').fetchone()['c']
    week = rows_to_list(conn.execute(
        'SELECT date,total_sales,total_sales_cash,total_sales_cliq FROM daily_records ORDER BY date DESC LIMIT 7'
    ).fetchall())
    orders_today = 0
    if rec:
        orders_today = conn.execute('SELECT COUNT(*) AS c FROM orders WHERE daily_record_id=?', (rec['id'],)).fetchone()['c']
    conn.close()
    return jsonify({
        'today_sales': rec['total_sales'] if rec else 0,
        'today_cash': rec['total_sales_cash'] if rec else 0,
        'today_cliq': rec['total_sales_cliq'] if rec else 0,
        'today_orders': orders_today,
        'today_status': rec['status'] if rec else 'closed',
        'items_count': items_count,
        'total_debt': debt,
        'low_stock': low,
        'week': week
    })

@app.route('/api/reports/top-items', methods=['GET'])
@login_required(roles=['owner', 'manager'])
def top_items():
    limit = int(request.args.get('limit', 8))
    conn = get_db()
    top = rows_to_list(conn.execute(
        'SELECT item_name,SUM(quantity) AS total_qty,SUM(total_price) AS total_revenue FROM order_items GROUP BY item_id ORDER BY total_qty DESC LIMIT ?', (limit,)
    ).fetchall())
    bottom = rows_to_list(conn.execute(
        'SELECT item_name,SUM(quantity) AS total_qty,SUM(total_price) AS total_revenue FROM order_items GROUP BY item_id ORDER BY total_qty ASC LIMIT ?', (limit,)
    ).fetchall())
    conn.close()
    return jsonify({'top': top, 'bottom': bottom})

@app.route('/api/reports/monthly', methods=['GET'])
@login_required(roles=['owner', 'manager'])
def monthly():
    month = request.args.get('month', date.today().isoformat()[:7])
    conn = get_db()
    rows = rows_to_list(conn.execute('SELECT * FROM daily_records WHERE date LIKE ? ORDER BY date DESC', (f'{month}%',)).fetchall())
    totals = row_to_dict(conn.execute(
        'SELECT COALESCE(SUM(total_sales),0) AS total,COALESCE(SUM(total_sales_cash),0) AS cash,COALESCE(SUM(total_sales_cliq),0) AS cliq,COUNT(*) AS days FROM daily_records WHERE date LIKE ?', (f'{month}%',)
    ).fetchone())
    conn.close()
    return jsonify({'records': rows, 'totals': totals})

# ════════════════════════════════════════════════════════════
# نقطة الدخول
# ════════════════════════════════════════════════════════════
if __name__ == '__main__':
    os.makedirs(os.path.join(BASE_DIR, 'static', 'uploads', 'items'), exist_ok=True)
    init_db()
    import sys
    port = int(os.environ.get('PORT', 5000))
    debug = '--dev' in sys.argv
    if debug:
        print("🚀 Dev mode: http://localhost:5000")
    app.run(debug=debug, host='0.0.0.0', port=port)
