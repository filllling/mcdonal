from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import pymysql
from app.config import DB_CONFIG
from app.routes.auth import admin_required
from datetime import datetime

def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    return conn, cursor

menu_bp = Blueprint('menu', __name__, url_prefix='/menu')

# 分类管理
@menu_bp.route('/category/')
@admin_required
def category_list():
    conn, cursor = get_db()
    cursor.execute('SELECT * FROM menu_category')
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('menu/category_list.html', categories=categories, now=datetime.now())

@menu_bp.route('/category/add', methods=['GET', 'POST'])
@admin_required
def category_add():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        conn, cursor = get_db()
        cursor.execute('INSERT INTO menu_category (name, description) VALUES (%s, %s)', (name, description))
        conn.commit()
        cursor.close()
        conn.close()
        flash('分类添加成功')
        return redirect(url_for('menu.category_list'))
    return render_template('menu/category_add_edit.html', action='add', now=datetime.now())

@menu_bp.route('/category/edit/<int:cat_id>', methods=['GET', 'POST'])
@admin_required
def category_edit(cat_id):
    conn, cursor = get_db()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        cursor.execute('UPDATE menu_category SET name=%s, description=%s WHERE id=%s', (name, description, cat_id))
        conn.commit()
        flash('分类更新成功')
        cursor.close()
        conn.close()
        return redirect(url_for('menu.category_list'))
    cursor.execute('SELECT * FROM menu_category WHERE id=%s', (cat_id,))
    category = cursor.fetchone()
    cursor.close()
    conn.close()
    if not category:
        flash('分类不存在')
        return redirect(url_for('menu.category_list'))
    return render_template('menu/category_add_edit.html', action='edit', category=category, now=datetime.now())

@menu_bp.route('/category/delete/<int:cat_id>', methods=['POST'])
@admin_required
def category_delete(cat_id):
    conn, cursor = get_db()
    # 检查该分类下是否有菜单项
    cursor.execute('SELECT COUNT(*) as cnt FROM menu_item WHERE category_id=%s', (cat_id,))
    if cursor.fetchone()['cnt'] > 0:
        flash('该分类下有菜单项，无法删除')
        cursor.close()
        conn.close()
        return redirect(url_for('menu.category_list'))
    cursor.execute('DELETE FROM menu_category WHERE id=%s', (cat_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('分类已删除')
    return redirect(url_for('menu.category_list'))

# 菜单项管理
@menu_bp.route('/')
@login_required
def list_menu():
    category_id = request.args.get('category_id', type=int)
    conn, cursor = get_db()
    if category_id:
        cursor.execute('''SELECT mi.*, mc.name as category_name FROM menu_item mi JOIN menu_category mc ON mi.category_id=mc.id WHERE mc.id=%s''', (category_id,))
    else:
        cursor.execute('''SELECT mi.*, mc.name as category_name FROM menu_item mi JOIN menu_category mc ON mi.category_id=mc.id''')
    menu_items = cursor.fetchall()
    cursor.execute('SELECT * FROM menu_category')
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('menu/list.html', menu_items=menu_items, categories=categories, selected_category=category_id, now=datetime.now())

@menu_bp.route('/add', methods=['GET', 'POST'])
@admin_required
def add_menu():
    conn, cursor = get_db()
    cursor.execute('SELECT * FROM menu_category')
    categories = cursor.fetchall()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        category_id = request.form['category_id']
        cursor.execute('INSERT INTO menu_item (name, description, price, category_id) VALUES (%s, %s, %s, %s)', (name, description, price, category_id))
        conn.commit()
        flash('菜单项添加成功')
        cursor.close()
        conn.close()
        return redirect(url_for('menu.list_menu'))
    cursor.close()
    conn.close()
    return render_template('menu/add_edit.html', action='add', categories=categories, now=datetime.now())

@menu_bp.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@admin_required
def edit_menu(item_id):
    conn, cursor = get_db()
    cursor.execute('SELECT * FROM menu_category')
    categories = cursor.fetchall()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        category_id = request.form['category_id']
        cursor.execute('UPDATE menu_item SET name=%s, description=%s, price=%s, category_id=%s WHERE id=%s', (name, description, price, category_id, item_id))
        conn.commit()
        flash('菜单项更新成功')
        cursor.close()
        conn.close()
        return redirect(url_for('menu.list_menu'))
    cursor.execute('SELECT * FROM menu_item WHERE id=%s', (item_id,))
    item = cursor.fetchone()
    cursor.close()
    conn.close()
    if not item:
        flash('菜单项不存在')
        return redirect(url_for('menu.list_menu'))
    return render_template('menu/add_edit.html', action='edit', item=item, categories=categories, now=datetime.now())

@menu_bp.route('/delete/<int:item_id>', methods=['POST'])
@admin_required
def delete_menu(item_id):
    conn, cursor = get_db()
    cursor.execute('DELETE FROM menu_item WHERE id=%s', (item_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('菜单项已删除')
    return redirect(url_for('menu.list_menu')) 