from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
import pymysql
from app.config import DB_CONFIG
from app.routes.auth import admin_required
from datetime import datetime

def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    return conn, cursor

order_bp = Blueprint('order', __name__, url_prefix='/order')

# 购物车功能
@order_bp.route('/cart')
@login_required
def cart():
    cart_items = session.get('cart', {})
    
    # 如果购物车是旧格式（列表），转换为新格式（字典）
    if isinstance(cart_items, list):
        old_cart = cart_items
        cart_items = {}
        for item_id_old in old_cart:
            item_id_str = str(item_id_old)
            if item_id_str in cart_items:
                cart_items[item_id_str] += 1
            else:
                cart_items[item_id_str] = 1
        # 更新session中的购物车
        session['cart'] = cart_items
        session.modified = True
    
    conn, cursor = get_db()
    # 获取购物车中菜单项的详细信息
    if cart_items:
        item_ids = list(cart_items.keys())
        placeholders = ','.join(['%s'] * len(item_ids))
        cursor.execute(f'''SELECT mi.*, mc.name as category_name FROM menu_item mi 
                          JOIN menu_category mc ON mi.category_id=mc.id 
                          WHERE mi.id IN ({placeholders})''', item_ids)
        items = cursor.fetchall()
        # 为每个商品添加数量信息
        for item in items:
            item['quantity'] = cart_items[str(item['id'])]
    else:
        items = []
    cursor.close()
    conn.close()
    return render_template('order/cart.html', items=items, now=datetime.now())

@order_bp.route('/add_to_cart/<int:item_id>', methods=['POST'])
@login_required
def add_to_cart(item_id):
    quantity = int(request.form.get('quantity', 1))
    if quantity < 1:
        quantity = 1
    elif quantity > 99:
        quantity = 99
    
    if 'cart' not in session:
        session['cart'] = {}
    
    # 如果购物车是旧格式（列表），转换为新格式（字典）
    if isinstance(session['cart'], list):
        # 将列表转换为字典
        old_cart = session['cart']
        session['cart'] = {}
        for item_id_old in old_cart:
            item_id_str = str(item_id_old)
            if item_id_str in session['cart']:
                session['cart'][item_id_str] += 1
            else:
                session['cart'][item_id_str] = 1
    
    # 使用字典存储购物车，key为item_id，value为数量
    if str(item_id) in session['cart']:
        session['cart'][str(item_id)] += quantity
    else:
        session['cart'][str(item_id)] = quantity
    
    session.modified = True
    flash(f'已添加 {quantity} 个商品到购物车')
    return redirect(url_for('menu.list_menu'))

@order_bp.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    cart_items = session.get('cart', {})
    
    # 如果购物车是旧格式（列表），转换为新格式（字典）
    if isinstance(cart_items, list):
        old_cart = cart_items
        cart_items = {}
        for item_id_old in old_cart:
            item_id_str = str(item_id_old)
            if item_id_str in cart_items:
                cart_items[item_id_str] += 1
            else:
                cart_items[item_id_str] = 1
        # 更新session中的购物车
        session['cart'] = cart_items
        session.modified = True
    
    if str(item_id) in session['cart']:
        del session['cart'][str(item_id)]
        session.modified = True
        flash('已从购物车移除')
    return redirect(url_for('order.cart'))

@order_bp.route('/clear_cart', methods=['POST'])
@login_required
def clear_cart():
    session.pop('cart', None)
    flash('购物车已清空')
    return redirect(url_for('order.cart'))

# 下单功能
@order_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = session.get('cart', {})
    
    # 如果购物车是旧格式（列表），转换为新格式（字典）
    if isinstance(cart_items, list):
        old_cart = cart_items
        cart_items = {}
        for item_id_old in old_cart:
            item_id_str = str(item_id_old)
            if item_id_str in cart_items:
                cart_items[item_id_str] += 1
            else:
                cart_items[item_id_str] = 1
        # 更新session中的购物车
        session['cart'] = cart_items
        session.modified = True
    
    if not cart_items:
        flash('购物车为空')
        return redirect(url_for('order.cart'))
    
    conn, cursor = get_db()
    # 获取购物车商品详情
    item_ids = list(cart_items.keys())
    placeholders = ','.join(['%s'] * len(item_ids))
    cursor.execute(f'''SELECT mi.*, mc.name as category_name FROM menu_item mi 
                      JOIN menu_category mc ON mi.category_id=mc.id 
                      WHERE mi.id IN ({placeholders})''', item_ids)
    items = cursor.fetchall()
    
    # 计算数量和总价
    total_price = 0
    for item in items:
        item['quantity'] = cart_items[str(item['id'])]
        total_price += item['price'] * item['quantity']
    
    if request.method == 'POST':
        # 检查用户是否存在
        cursor.execute("SELECT id FROM user WHERE id = %s", (current_user.id,))
        result = cursor.fetchone()
        if result is None:
            # 用户不存在，不能插入订单
            flash('用户不存在，无法下单')
            cursor.close()
            conn.close()
            return redirect(url_for('order.cart'))
        
        # 用户存在，执行插入订单操作
        cursor.execute('''INSERT INTO `order` (user_id, order_time, total_price, status, payment_status) 
                          VALUES (%s, %s, %s, %s, %s)''', 
                      (current_user.id, datetime.now(), total_price, '待制作', '未支付'))
        order_id = cursor.lastrowid
        
        # 创建订单详情
        for item in items:
            cursor.execute('''INSERT INTO order_item (order_id, menu_item_id, quantity, unit_price, subtotal) 
                              VALUES (%s, %s, %s, %s, %s)''',
                          (order_id, item['id'], item['quantity'], item['price'], item['price'] * item['quantity']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # 清空购物车
        session.pop('cart', None)
        flash(f'订单提交成功！订单号：{order_id}')
        return redirect(url_for('order.my_orders'))
    
    cursor.close()
    conn.close()
    return render_template('order/checkout.html', items=items, total_price=total_price, now=datetime.now())

# 订单查看
@order_bp.route('/my_orders')
@login_required
def my_orders():
    conn, cursor = get_db()
    cursor.execute('''SELECT * FROM `order` WHERE user_id=%s ORDER BY order_time DESC''', (current_user.id,))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('order/my_orders.html', orders=orders, now=datetime.now())

@order_bp.route('/order_detail/<int:order_id>')
@login_required
def order_detail(order_id):
    conn, cursor = get_db()
    # 获取订单信息
    cursor.execute('''SELECT * FROM `order` WHERE id=%s AND user_id=%s''', (order_id, current_user.id))
    order = cursor.fetchone()
    if not order:
        flash('订单不存在')
        cursor.close()
        conn.close()
        return redirect(url_for('order.my_orders'))
    
    # 获取订单详情
    cursor.execute('''SELECT oi.*, mi.name, mi.description FROM order_item oi 
                      JOIN menu_item mi ON oi.menu_item_id=mi.id 
                      WHERE oi.order_id=%s''', (order_id,))
    order_items = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('order/order_detail.html', order=order, order_items=order_items, now=datetime.now())

# 管理员订单管理
@order_bp.route('/admin/orders')
@admin_required
def admin_orders():
    conn, cursor = get_db()
    cursor.execute('''SELECT o.*, u.username FROM `order` o 
                      JOIN user u ON o.user_id=u.id 
                      ORDER BY o.order_time DESC''')
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('order/admin_orders.html', orders=orders, now=datetime.now())

@order_bp.route('/admin/order_detail/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    conn, cursor = get_db()
    # 获取订单信息
    cursor.execute('''SELECT o.*, u.username FROM `order` o 
                      JOIN user u ON o.user_id=u.id 
                      WHERE o.id=%s''', (order_id,))
    order = cursor.fetchone()
    if not order:
        flash('订单不存在')
        cursor.close()
        conn.close()
        return redirect(url_for('order.admin_orders'))
    
    # 获取订单详情
    cursor.execute('''SELECT oi.*, mi.name, mi.description FROM order_item oi 
                      JOIN menu_item mi ON oi.menu_item_id=mi.id 
                      WHERE oi.order_id=%s''', (order_id,))
    order_items = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('order/admin_order_detail.html', order=order, order_items=order_items, now=datetime.now())

@order_bp.route('/admin/update_status/<int:order_id>', methods=['POST'])
@admin_required
def update_order_status(order_id):
    status = request.form['status']
    payment_status = request.form.get('payment_status')
    conn, cursor = get_db()
    if payment_status:
        cursor.execute('UPDATE `order` SET status=%s, payment_status=%s WHERE id=%s', (status, payment_status, order_id))
    else:
        cursor.execute('UPDATE `order` SET status=%s WHERE id=%s', (status, order_id))
    conn.commit()
    cursor.close()
    conn.close()
    flash('订单状态已更新')
    return redirect(url_for('order.admin_order_detail', order_id=order_id)) 