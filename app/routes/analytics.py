from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, Response
from flask_login import login_required, current_user
import pymysql
from app.config import DB_CONFIG
from app.routes.auth import analyst_required
from datetime import datetime, timedelta
import pandas as pd
import json
import re
import csv
from io import StringIO

def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    return conn, cursor

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

# 可查询的表和字段定义
AVAILABLE_TABLES = {
    'order': {
        'name': '订单表',
        'fields': {
            'id': {'name': '订单ID', 'type': 'int'},
            'user_id': {'name': '用户ID', 'type': 'int'},
            'order_time': {'name': '下单时间', 'type': 'datetime'},
            'total_price': {'name': '订单金额', 'type': 'decimal'},
            'status': {'name': '订单状态', 'type': 'varchar'},
            'payment_status': {'name': '支付状态', 'type': 'varchar'}
        }
    },
    'order_item': {
        'name': '订单详情表',
        'fields': {
            'id': {'name': '详情ID', 'type': 'int'},
            'order_id': {'name': '订单ID', 'type': 'int'},
            'menu_item_id': {'name': '商品ID', 'type': 'int'},
            'quantity': {'name': '数量', 'type': 'int'},
            'unit_price': {'name': '单价', 'type': 'decimal'},
            'subtotal': {'name': '小计', 'type': 'decimal'}
        }
    },
    'menu_item': {
        'name': '菜单项表',
        'fields': {
            'id': {'name': '商品ID', 'type': 'int'},
            'name': {'name': '商品名称', 'type': 'varchar'},
            'description': {'name': '商品描述', 'type': 'varchar'},
            'price': {'name': '价格', 'type': 'decimal'},
            'category_id': {'name': '分类ID', 'type': 'int'}
        }
    },
    'user': {
        'name': '用户表',
        'fields': {
            'id': {'name': '用户ID', 'type': 'int'},
            'username': {'name': '用户名', 'type': 'varchar'},
            'role': {'name': '用户角色', 'type': 'varchar'},
            'created_at': {'name': '注册时间', 'type': 'datetime'}
        }
    }
}

@analytics_bp.route('/')
@analyst_required
def index():
    return render_template('analytics/index.html', now=datetime.now())

@analytics_bp.route('/sales')
@analyst_required
def sales():
    # 获取时间范围参数
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # 如果没有提供时间范围，默认使用最近30天
    if not start_date or not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    conn, cursor = get_db()
    
    # 获取指定时间范围的每日订单数和销售额
    cursor.execute('''
        SELECT DATE(order_time) as date, 
               COUNT(*) as order_count, 
               SUM(total_price) as total_sales
        FROM `order` 
        WHERE DATE(order_time) BETWEEN %s AND %s
        GROUP BY DATE(order_time)
        ORDER BY date
    ''', (start_date, end_date))
    daily_sales = cursor.fetchall()
    
    # 获取商品销量排行榜（带分页）
    offset = (page - 1) * per_page
    
    # 先获取总数
    cursor.execute('''
        SELECT COUNT(DISTINCT mi.id) as total
        FROM order_item oi
        JOIN menu_item mi ON oi.menu_item_id = mi.id
        JOIN `order` o ON oi.order_id = o.id
        WHERE DATE(o.order_time) BETWEEN %s AND %s
    ''', (start_date, end_date))
    total_products = cursor.fetchone()['total']
    
    # 获取分页数据
    cursor.execute('''
        SELECT mi.name, mi.description, mc.name as category_name,
               SUM(oi.quantity) as total_quantity,
               SUM(oi.subtotal) as total_revenue
        FROM order_item oi
        JOIN menu_item mi ON oi.menu_item_id = mi.id
        JOIN menu_category mc ON mi.category_id = mc.id
        JOIN `order` o ON oi.order_id = o.id
        WHERE DATE(o.order_time) BETWEEN %s AND %s
        GROUP BY mi.id, mi.name, mi.description, mc.name
        ORDER BY total_quantity DESC
        LIMIT %s OFFSET %s
    ''', (start_date, end_date, per_page, offset))
    top_products = cursor.fetchall()
    
    # 获取分类销量统计
    cursor.execute('''
        SELECT mc.name as category_name,
               COUNT(DISTINCT o.id) as order_count,
               SUM(oi.quantity) as total_quantity,
               SUM(oi.subtotal) as total_revenue
        FROM order_item oi
        JOIN menu_item mi ON oi.menu_item_id = mi.id
        JOIN menu_category mc ON mi.category_id = mc.id
        JOIN `order` o ON oi.order_id = o.id
        WHERE DATE(o.order_time) BETWEEN %s AND %s
        GROUP BY mc.id, mc.name
        ORDER BY total_revenue DESC
    ''', (start_date, end_date))
    category_sales = cursor.fetchall()
    
    # 计算统计摘要
    cursor.execute('''
        SELECT 
            COUNT(*) as total_orders,
            SUM(total_price) as total_sales,
            AVG(total_price) as avg_order_value
        FROM `order`
        WHERE DATE(order_time) BETWEEN %s AND %s
    ''', (start_date, end_date))
    summary = cursor.fetchone()
    
    # 计算平均日订单数和销售额
    cursor.execute('''
        SELECT 
            COUNT(DISTINCT DATE(order_time)) as days_with_orders
        FROM `order`
        WHERE DATE(order_time) BETWEEN %s AND %s
    ''', (start_date, end_date))
    days_info = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    # 计算分页信息
    total_pages = (total_products + per_page - 1) // per_page
    
    # 计算平均日订单数和销售额
    days_with_orders = days_info['days_with_orders'] if days_info['days_with_orders'] > 0 else 1
    avg_daily_orders = summary['total_orders'] / days_with_orders if summary['total_orders'] else 0
    avg_daily_sales = summary['total_sales'] / days_with_orders if summary['total_sales'] else 0
    
    return render_template('analytics/sales.html', 
                         daily_sales=daily_sales,
                         top_products=top_products,
                         category_sales=category_sales,
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         total_products=total_products,
                         start_date=start_date,
                         end_date=end_date,
                         total_orders=summary['total_orders'] or 0,
                         total_sales=summary['total_sales'] or 0,
                         avg_daily_orders=avg_daily_orders,
                         avg_daily_sales=avg_daily_sales,
                         now=datetime.now(),
                         timedelta=timedelta)

@analytics_bp.route('/users')
@analyst_required
def users():
    # 获取时间范围参数
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # 如果没有提供时间范围，默认使用最近30天
    if not start_date or not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    conn, cursor = get_db()
    
    # 获取用户总数和角色分布
    cursor.execute('''
        SELECT role, COUNT(*) as count
        FROM user
        GROUP BY role
    ''')
    role_distribution = cursor.fetchall()
    
    # 获取用户总数
    cursor.execute('SELECT COUNT(*) as total FROM user')
    total_users = cursor.fetchone()['total']
    
    # 获取活跃用户排行（指定时间范围内下单次数最多）
    cursor.execute('''
        SELECT u.username, u.role, u.created_at,
               COUNT(o.id) as order_count,
               SUM(o.total_price) as total_spent,
               AVG(o.total_price) as avg_order_value,
               MAX(o.order_time) as last_order_date
        FROM user u
        LEFT JOIN `order` o ON u.id = o.user_id AND DATE(o.order_time) BETWEEN %s AND %s
        GROUP BY u.id, u.username, u.role, u.created_at
        HAVING order_count > 0
        ORDER BY order_count DESC, total_spent DESC
        LIMIT 10
    ''', (start_date, end_date))
    active_users = cursor.fetchall()
    
    # 获取新用户注册趋势（指定时间范围）
    cursor.execute('''
        SELECT DATE(created_at) as date, COUNT(*) as new_users
        FROM user
        WHERE DATE(created_at) BETWEEN %s AND %s
        GROUP BY DATE(created_at)
        ORDER BY date
    ''', (start_date, end_date))
    new_users_trend = cursor.fetchall()
    
    # 获取用户消费金额分布（指定时间范围）
    cursor.execute('''
        SELECT 
            CASE 
                WHEN total_spent >= 500 THEN '高消费用户(≥500)'
                WHEN total_spent >= 200 THEN '中消费用户(200-499)'
                WHEN total_spent >= 50 THEN '低消费用户(50-199)'
                ELSE '新用户(<50)'
            END as spending_level,
            COUNT(*) as user_count,
            AVG(total_spent) as avg_spending
        FROM (
            SELECT u.id, COALESCE(SUM(o.total_price), 0) as total_spent
            FROM user u
            LEFT JOIN `order` o ON u.id = o.user_id AND DATE(o.order_time) BETWEEN %s AND %s
            GROUP BY u.id
        ) user_spending
        GROUP BY spending_level
        ORDER BY 
            CASE spending_level
                WHEN '高消费用户(≥500)' THEN 1
                WHEN '中消费用户(200-499)' THEN 2
                WHEN '低消费用户(50-199)' THEN 3
                WHEN '新用户(<50)' THEN 4
            END
    ''', (start_date, end_date))
    spending_distribution = cursor.fetchall()
    
    # 获取用户活跃度分析（指定时间范围）
    cursor.execute('''
        SELECT 
            CASE 
                WHEN order_count >= 10 THEN '高度活跃(≥10单)'
                WHEN order_count >= 5 THEN '中度活跃(5-9单)'
                WHEN order_count >= 2 THEN '轻度活跃(2-4单)'
                WHEN order_count = 1 THEN '偶尔活跃(1单)'
                ELSE '不活跃(0单)'
            END as activity_level,
            COUNT(*) as user_count,
            AVG(order_count) as avg_orders,
            AVG(total_spent) as avg_spending
        FROM (
            SELECT u.id, 
                   COALESCE(COUNT(o.id), 0) as order_count,
                   COALESCE(SUM(o.total_price), 0) as total_spent
            FROM user u
            LEFT JOIN `order` o ON u.id = o.user_id AND DATE(o.order_time) BETWEEN %s AND %s
            GROUP BY u.id
        ) user_activity
        GROUP BY activity_level
        ORDER BY 
            CASE activity_level
                WHEN '高度活跃(≥10单)' THEN 1
                WHEN '中度活跃(5-9单)' THEN 2
                WHEN '轻度活跃(2-4单)' THEN 3
                WHEN '偶尔活跃(1单)' THEN 4
                WHEN '不活跃(0单)' THEN 5
            END
    ''', (start_date, end_date))
    user_activity = cursor.fetchall()
    
    # 计算平均订单金额
    cursor.execute('''
        SELECT AVG(total_price) as avg_order_value
        FROM `order`
        WHERE DATE(order_time) BETWEEN %s AND %s
    ''', (start_date, end_date))
    avg_order_result = cursor.fetchone()
    avg_order_value = avg_order_result['avg_order_value'] if avg_order_result['avg_order_value'] else 0
    
    cursor.close()
    conn.close()
    
    return render_template('analytics/users.html',
                         role_distribution=role_distribution,
                         total_users=total_users,
                         active_users=active_users,
                         new_users_trend=new_users_trend,
                         spending_distribution=spending_distribution,
                         user_activity=user_activity,
                         avg_order_value=avg_order_value,
                         start_date=start_date,
                         end_date=end_date,
                         now=datetime.now(),
                         timedelta=timedelta)

# 灵活数据分析功能
@analytics_bp.route('/flexible')
@analyst_required
def flexible():
    return render_template('analytics/flexible.html', tables=AVAILABLE_TABLES, now=datetime.now())

@analytics_bp.route('/query', methods=['POST'])
@analyst_required
def execute_query():
    try:
        data = request.get_json()
        table_name = data.get('table')
        selected_fields = data.get('fields', [])
        filters = data.get('filters', [])
        group_by = data.get('group_by', [])
        order_by = data.get('order_by', [])
        limit = data.get('limit', 100)
        offset = data.get('offset', 0)
        
        if not table_name or table_name not in AVAILABLE_TABLES:
            return jsonify({'error': '无效的表名'}), 400
        
        # 构建 SQL 查询
        sql_parts = []
        params = []
        
        # SELECT 子句 - 支持聚合函数
        if not selected_fields:
            selected_fields = ['*']
        
        # 处理字段，支持聚合函数
        processed_fields = []
        for field in selected_fields:
            if isinstance(field, dict):
                # 聚合字段格式: {"function": "SUM", "field": "total_price", "alias": "total_sales"}
                func = field.get('function', '')
                field_name = field.get('field', '')
                alias = field.get('alias', '')
                
                if func and field_name:
                    if func.upper() in ['SUM', 'AVG', 'MAX', 'MIN', 'COUNT']:
                        if alias:
                            processed_fields.append(f"{func.upper()}(`{field_name}`) AS `{alias}`")
                        else:
                            processed_fields.append(f"{func.upper()}(`{field_name}`)")
                    else:
                        return jsonify({'error': f'不支持的聚合函数: {func}'}), 400
                else:
                    processed_fields.append(f"`{field_name}`")
            else:
                # 普通字段
                if field == '*':
                    processed_fields.append('*')
                else:
                    processed_fields.append(f"`{field}`")
        
        sql_parts.append(f"SELECT {', '.join(processed_fields)}")
        
        # FROM 子句
        sql_parts.append(f"FROM `{table_name}`")
        
        # WHERE 子句
        where_conditions = []
        for filter_item in filters:
            field = filter_item.get('field')
            operator = filter_item.get('operator', '=')
            value = filter_item.get('value')
            
            if field and value is not None:
                if operator in ['LIKE', 'like']:
                    where_conditions.append(f"`{field}` LIKE %s")
                    params.append(f"%{value}%")
                elif operator in ['IN', 'in']:
                    placeholders = ','.join(['%s'] * len(value))
                    where_conditions.append(f"`{field}` IN ({placeholders})")
                    params.extend(value)
                elif operator in ['IS NULL', 'IS NOT NULL']:
                    where_conditions.append(f"`{field}` {operator}")
                else:
                    where_conditions.append(f"`{field}` {operator} %s")
                    params.append(value)
        
        if where_conditions:
            sql_parts.append(f"WHERE {' AND '.join(where_conditions)}")
        
        # GROUP BY 子句 - 支持时间粒度分组
        if group_by:
            processed_group_by = []
            for group_item in group_by:
                if isinstance(group_item, dict):
                    # 时间粒度分组格式: {"type": "time", "field": "created_at", "granularity": "day"}
                    group_type = group_item.get('type', 'field')
                    field = group_item.get('field', '')
                    granularity = group_item.get('granularity', 'day')
                    
                    if group_type == 'time' and field:
                        if granularity == 'day':
                            processed_group_by.append(f"DATE(`{field}`)")
                        elif granularity == 'hour':
                            processed_group_by.append(f"DATE_FORMAT(`{field}`, '%Y-%m-%d %H')")
                        elif granularity == 'month':
                            processed_group_by.append(f"DATE_FORMAT(`{field}`, '%Y-%m')")
                        elif granularity == 'year':
                            processed_group_by.append(f"YEAR(`{field}`)")
                        elif granularity == 'week':
                            processed_group_by.append(f"YEARWEEK(`{field}`)")
                        else:
                            return jsonify({'error': f'不支持的时间粒度: {granularity}'}), 400
                    else:
                        # 普通字段分组
                        processed_group_by.append(f"`{field}`")
                else:
                    # 简单字段名
                    processed_group_by.append(f"`{group_item}`")
            
            sql_parts.append(f"GROUP BY {', '.join(processed_group_by)}")
        
        # ORDER BY 子句
        if order_by:
            order_clauses = []
            for order_item in order_by:
                field = order_item.get('field')
                direction = order_item.get('direction', 'ASC')
                order_clauses.append(f"`{field}` {direction}")
            sql_parts.append(f"ORDER BY {', '.join(order_clauses)}")
        
        # LIMIT 子句
        sql_parts.append(f"LIMIT {limit} OFFSET {offset}")
        
        sql = ' '.join(sql_parts)
        
        # 执行查询
        conn, cursor = get_db()
        cursor.execute(sql, params)
        results = cursor.fetchall()
        
        # 获取总记录数（用于分页）
        # 如果有分组，需要计算分组后的记录数
        if group_by:
            count_sql_parts = ["SELECT COUNT(*) as total FROM ("]
            count_sql_parts.append(f"SELECT {', '.join(processed_fields)}")
            count_sql_parts.append(f"FROM `{table_name}`")
            if where_conditions:
                count_sql_parts.append(f"WHERE {' AND '.join(where_conditions)}")
            if group_by:
                count_sql_parts.append(f"GROUP BY {', '.join(processed_group_by)}")
            count_sql_parts.append(") as grouped_data")
            count_sql = ' '.join(count_sql_parts)
        else:
            count_sql = f"SELECT COUNT(*) as total FROM `{table_name}`"
            if where_conditions:
                count_sql += f" WHERE {' AND '.join(where_conditions)}"
        
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': results,
            'total': total_count,
            'sql': sql
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/variables')
@analyst_required
def variables():
    conn, cursor = get_db()
    
    # 获取所有变量
    cursor.execute('''
        SELECT v.*, u.username as creator_name
        FROM analysis_variables v
        LEFT JOIN user u ON v.user_id = u.id
        ORDER BY v.created_at DESC
    ''')
    variables = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # 检查是否是AJAX请求
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'variables': variables
        })
    
    return render_template('analytics/variables.html', variables=variables, now=datetime.now())

@analytics_bp.route('/variables/create', methods=['POST'])
@analyst_required
def create_variable():
    try:
        data = request.get_json()
        name = data.get('name')
        expression = data.get('expression')
        table_name = data.get('table_name')
        description = data.get('description', '')  # 添加描述字段支持
        
        if not name or not expression or not table_name:
            return jsonify({'error': '缺少必要参数'}), 400
        
        # 验证变量名格式
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            return jsonify({'error': '变量名格式无效'}), 400
        
        # 保存变量定义
        conn, cursor = get_db()
        cursor.execute('''
            INSERT INTO analysis_variables (user_id, name, expression, table_name, description)
            VALUES (%s, %s, %s, %s, %s)
        ''', (current_user.id, name, expression, table_name, description))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '变量创建成功'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/variables/<int:var_id>/delete', methods=['POST'])
@analyst_required
def delete_variable(var_id):
    try:
        conn, cursor = get_db()
        cursor.execute('DELETE FROM analysis_variables WHERE id = %s AND user_id = %s', 
                      (var_id, current_user.id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '变量删除成功'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/daily_sales')
@analyst_required
def api_daily_sales():
    conn, cursor = get_db()
    cursor.execute('''
        SELECT DATE(order_time) as date, 
               COUNT(*) as order_count, 
               SUM(total_price) as total_sales
        FROM `order` 
        WHERE order_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY DATE(order_time)
        ORDER BY date
    ''')
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify({
        'dates': [item['date'].strftime('%Y-%m-%d') for item in data],
        'order_counts': [item['order_count'] for item in data],
        'sales': [float(item['total_sales']) for item in data]
    })

@analytics_bp.route('/api/top_products')
@analyst_required
def api_top_products():
    conn, cursor = get_db()
    cursor.execute('''
        SELECT mi.name, SUM(oi.quantity) as total_quantity
        FROM order_item oi
        JOIN menu_item mi ON oi.menu_item_id = mi.id
        JOIN `order` o ON oi.order_id = o.id
        WHERE o.order_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY mi.id, mi.name
        ORDER BY total_quantity DESC
        LIMIT 10
    ''')
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify({
        'products': [item['name'] for item in data],
        'quantities': [item['total_quantity'] for item in data]
    })

# 导出数据功能
@analytics_bp.route('/export/<data_type>')
@analyst_required
def export_data(data_type):
    # 获取时间范围参数
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # 如果没有提供时间范围，默认使用最近30天
    if not start_date or not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    conn, cursor = get_db()
    
    try:
        if data_type == 'daily_sales':
            # 导出每日销售数据
            cursor.execute('''
                SELECT DATE(order_time) as date, 
                       COUNT(*) as order_count, 
                       SUM(total_price) as total_sales,
                       AVG(total_price) as avg_order_value
                FROM `order` 
                WHERE DATE(order_time) BETWEEN %s AND %s
                GROUP BY DATE(order_time)
                ORDER BY date
            ''', (start_date, end_date))
            data = cursor.fetchall()
            
            # 创建CSV
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['日期', '订单数', '销售额', '平均订单金额'])
            for row in data:
                cw.writerow([
                    row['date'],
                    row['order_count'],
                    f"¥{row['total_sales']:.2f}" if row['total_sales'] else "¥0.00",
                    f"¥{row['avg_order_value']:.2f}" if row['avg_order_value'] else "¥0.00"
                ])
            
            output = si.getvalue()
            return Response(
                output,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=daily_sales_{start_date}_to_{end_date}.csv'}
            )
            
        elif data_type == 'top_products':
            # 导出商品销量排行
            cursor.execute('''
                SELECT mi.name, mc.name as category_name,
                       SUM(oi.quantity) as total_quantity,
                       SUM(oi.subtotal) as total_revenue,
                       AVG(oi.unit_price) as avg_price
                FROM order_item oi
                JOIN menu_item mi ON oi.menu_item_id = mi.id
                JOIN menu_category mc ON mi.category_id = mc.id
                JOIN `order` o ON oi.order_id = o.id
                WHERE DATE(o.order_time) BETWEEN %s AND %s
                GROUP BY mi.id, mi.name, mc.name
                ORDER BY total_quantity DESC
            ''', (start_date, end_date))
            data = cursor.fetchall()
            
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['商品名称', '分类', '销量', '销售额', '平均单价'])
            for row in data:
                cw.writerow([
                    row['name'],
                    row['category_name'],
                    row['total_quantity'],
                    f"¥{row['total_revenue']:.2f}" if row['total_revenue'] else "¥0.00",
                    f"¥{row['avg_price']:.2f}" if row['avg_price'] else "¥0.00"
                ])
            
            output = si.getvalue()
            return Response(
                output,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=top_products_{start_date}_to_{end_date}.csv'}
            )
            
        elif data_type == 'category_sales':
            # 导出分类销量统计
            cursor.execute('''
                SELECT mc.name as category_name,
                       COUNT(DISTINCT o.id) as order_count,
                       SUM(oi.quantity) as total_quantity,
                       SUM(oi.subtotal) as total_revenue,
                       AVG(oi.subtotal) as avg_order_value
                FROM order_item oi
                JOIN menu_item mi ON oi.menu_item_id = mi.id
                JOIN menu_category mc ON mi.category_id = mc.id
                JOIN `order` o ON oi.order_id = o.id
                WHERE DATE(o.order_time) BETWEEN %s AND %s
                GROUP BY mc.id, mc.name
                ORDER BY total_revenue DESC
            ''', (start_date, end_date))
            data = cursor.fetchall()
            
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['分类', '订单数', '销量', '销售额', '平均订单金额'])
            for row in data:
                cw.writerow([
                    row['category_name'],
                    row['order_count'],
                    row['total_quantity'],
                    f"¥{row['total_revenue']:.2f}" if row['total_revenue'] else "¥0.00",
                    f"¥{row['avg_order_value']:.2f}" if row['avg_order_value'] else "¥0.00"
                ])
            
            output = si.getvalue()
            return Response(
                output,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=category_sales_{start_date}_to_{end_date}.csv'}
            )
            
        elif data_type == 'role_distribution':
            # 导出用户角色分布
            cursor.execute('''
                SELECT role, COUNT(*) as count,
                       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM user), 1) as percentage
                FROM user
                GROUP BY role
            ''')
            data = cursor.fetchall()
            
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['角色', '用户数量', '占比(%)'])
            for row in data:
                role_name = {
                    'admin': '管理员',
                    'customer': '顾客',
                    'analyst': '分析员'
                }.get(row['role'], row['role'])
                cw.writerow([role_name, row['count'], f"{row['percentage']}%"])
            
            output = si.getvalue()
            return Response(
                output,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=role_distribution.csv'}
            )
            
        elif data_type == 'active_users':
            # 导出活跃用户排行
            cursor.execute('''
                SELECT u.username, u.role, u.created_at,
                       COUNT(o.id) as order_count,
                       SUM(o.total_price) as total_spent,
                       AVG(o.total_price) as avg_order_value,
                       MAX(o.order_time) as last_order_date
                FROM user u
                LEFT JOIN `order` o ON u.id = o.user_id AND DATE(o.order_time) BETWEEN %s AND %s
                GROUP BY u.id, u.username, u.role, u.created_at
                HAVING order_count > 0
                ORDER BY order_count DESC, total_spent DESC
            ''', (start_date, end_date))
            data = cursor.fetchall()
            
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['用户名', '角色', '注册时间', '订单数', '总消费', '平均订单金额', '最后活跃'])
            for row in data:
                role_name = {
                    'admin': '管理员',
                    'customer': '顾客',
                    'analyst': '分析员'
                }.get(row['role'], row['role'])
                cw.writerow([
                    row['username'],
                    role_name,
                    row['created_at'].strftime('%Y-%m-%d') if row['created_at'] else '',
                    row['order_count'],
                    f"¥{row['total_spent']:.2f}" if row['total_spent'] else "¥0.00",
                    f"¥{row['avg_order_value']:.2f}" if row['avg_order_value'] else "¥0.00",
                    row['last_order_date'].strftime('%Y-%m-%d') if row['last_order_date'] else '无'
                ])
            
            output = si.getvalue()
            return Response(
                output,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=active_users_{start_date}_to_{end_date}.csv'}
            )
            
        elif data_type == 'new_users_trend':
            # 导出新用户注册趋势
            cursor.execute('''
                SELECT DATE(created_at) as date, COUNT(*) as new_users
                FROM user
                WHERE DATE(created_at) BETWEEN %s AND %s
                GROUP BY DATE(created_at)
                ORDER BY date
            ''', (start_date, end_date))
            data = cursor.fetchall()
            
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['日期', '新注册用户数', '累计用户数'])
            cumulative = 0
            for row in data:
                cumulative += row['new_users']
                cw.writerow([row['date'], row['new_users'], cumulative])
            
            output = si.getvalue()
            return Response(
                output,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=new_users_trend_{start_date}_to_{end_date}.csv'}
            )
            
        elif data_type == 'spending_distribution':
            # 导出用户消费金额分布
            cursor.execute('''
                SELECT 
                    CASE 
                        WHEN total_spent >= 500 THEN '高消费用户(≥500)'
                        WHEN total_spent >= 200 THEN '中消费用户(200-499)'
                        WHEN total_spent >= 50 THEN '低消费用户(50-199)'
                        ELSE '新用户(<50)'
                    END as spending_level,
                    COUNT(*) as user_count,
                    AVG(total_spent) as avg_spending
                FROM (
                    SELECT u.id, COALESCE(SUM(o.total_price), 0) as total_spent
                    FROM user u
                    LEFT JOIN `order` o ON u.id = o.user_id AND DATE(o.order_time) BETWEEN %s AND %s
                    GROUP BY u.id
                ) user_spending
                GROUP BY spending_level
                ORDER BY 
                    CASE spending_level
                        WHEN '高消费用户(≥500)' THEN 1
                        WHEN '中消费用户(200-499)' THEN 2
                        WHEN '低消费用户(50-199)' THEN 3
                        WHEN '新用户(<50)' THEN 4
                    END
            ''', (start_date, end_date))
            data = cursor.fetchall()
            
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['消费等级', '用户数量', '平均消费'])
            for row in data:
                cw.writerow([
                    row['spending_level'],
                    row['user_count'],
                    f"¥{row['avg_spending']:.2f}" if row['avg_spending'] else "¥0.00"
                ])
            
            output = si.getvalue()
            return Response(
                output,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=spending_distribution_{start_date}_to_{end_date}.csv'}
            )
            
        elif data_type == 'user_activity':
            # 导出用户活跃度分析
            cursor.execute('''
                SELECT 
                    CASE 
                        WHEN order_count >= 10 THEN '高度活跃(≥10单)'
                        WHEN order_count >= 5 THEN '中度活跃(5-9单)'
                        WHEN order_count >= 2 THEN '轻度活跃(2-4单)'
                        WHEN order_count = 1 THEN '偶尔活跃(1单)'
                        ELSE '不活跃(0单)'
                    END as activity_level,
                    COUNT(*) as user_count,
                    AVG(order_count) as avg_orders,
                    AVG(total_spent) as avg_spending
                FROM (
                    SELECT u.id, 
                           COALESCE(COUNT(o.id), 0) as order_count,
                           COALESCE(SUM(o.total_price), 0) as total_spent
                    FROM user u
                    LEFT JOIN `order` o ON u.id = o.user_id AND DATE(o.order_time) BETWEEN %s AND %s
                    GROUP BY u.id
                ) user_activity
                GROUP BY activity_level
                ORDER BY 
                    CASE activity_level
                        WHEN '高度活跃(≥10单)' THEN 1
                        WHEN '中度活跃(5-9单)' THEN 2
                        WHEN '轻度活跃(2-4单)' THEN 3
                        WHEN '偶尔活跃(1单)' THEN 4
                        WHEN '不活跃(0单)' THEN 5
                    END
            ''', (start_date, end_date))
            data = cursor.fetchall()
            
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['活跃度等级', '用户数量', '平均订单数', '平均消费'])
            for row in data:
                cw.writerow([
                    row['activity_level'],
                    row['user_count'],
                    f"{row['avg_orders']:.1f}" if row['avg_orders'] else "0.0",
                    f"¥{row['avg_spending']:.2f}" if row['avg_spending'] else "¥0.00"
                ])
            
            output = si.getvalue()
            return Response(
                output,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=user_activity_{start_date}_to_{end_date}.csv'}
            )
            
        else:
            return jsonify({'error': '不支持的数据类型'}), 400
            
    except Exception as e:
        return jsonify({'error': f'导出失败: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close() 