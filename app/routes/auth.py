from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import UserMixin, login_user, login_required, logout_user, current_user
from app import login_manager
import pymysql
from app.config import DB_CONFIG
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)  # 用字典游标方便取字段名访问
    return conn, cursor

# User 类必须继承 UserMixin
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role


@login_manager.user_loader
def load_user(user_id):
    conn, cursor = get_db()
    cursor.execute('SELECT id, username, role FROM user WHERE id=%s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['role'])
    return None

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = 'customer'  # 强制只能注册顾客
        conn, cursor = get_db()
        cursor.execute('SELECT id FROM user WHERE username=%s', (username,))
        if cursor.fetchone():
            flash('用户名已存在')
            cursor.close()
            conn.close()
            return render_template('auth/register.html', now=datetime.now())
        hashed_pw = generate_password_hash(password)
        cursor.execute('INSERT INTO user (username, password, role) VALUES (%s, %s, %s)', (username, hashed_pw, role))
        conn.commit()
        cursor.close()
        conn.close()
        flash('注册成功，请登录')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', now=datetime.now())

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn, cursor = get_db()
        cursor.execute('SELECT id, username, password, role FROM user WHERE username=%s', (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and check_password_hash(user['password'], password):
            user_obj = User(user['id'], user['username'], user['role'])
            login_user(user_obj)
            flash('登录成功')
            return redirect(url_for('main.index'))
        flash('用户名或密码错误')
    return render_template('auth/login.html', now=datetime.now())

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已登出')
    return redirect(url_for('auth.login'))

# 权限控制装饰器示例
from functools import wraps

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(**kwargs):
        if current_user.role != 'admin':
            flash('无权限访问')
            return redirect(url_for('main.index'))
        return view(**kwargs)
    return wrapped_view

def analyst_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(**kwargs):
        if current_user.role not in ['admin', 'analyst']:
            flash('无权限访问')
            return redirect(url_for('main.index'))
        return view(**kwargs)
    return wrapped_view
