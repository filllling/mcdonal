# 分组聚合功能使用指南

## 🎯 功能概述

重构后的分组聚合功能支持：
- **时间粒度分组**：按天、小时、月、年、周进行分组
- **多聚合函数**：SUM、AVG、MAX、MIN、COUNT
- **自定义字段分组**：按任意字段进行分组
- **组合分析**：时间分组 + 字段分组 + 聚合函数

## 📊 使用场景示例

### 1. 每日销售统计
**目标**：统计每天的总销售额和订单数量

**配置步骤**：
1. 选择表：`order`
2. 添加聚合字段：
   - SUM(`total_price`) AS `daily_sales`
   - COUNT(*) AS `order_count`
3. 添加时间分组：
   - 字段：`order_time`
   - 粒度：按天
4. 执行查询

**生成的SQL**：
```sql
SELECT SUM(`total_price`) AS `daily_sales`, COUNT(*) AS `order_count`
FROM `order`
GROUP BY DATE(`order_time`)
ORDER BY DATE(`order_time`)
```

### 2. 每小时订单分析
**目标**：分析每小时的订单分布

**配置步骤**：
1. 选择表：`order`
2. 添加聚合字段：
   - COUNT(*) AS `hourly_orders`
3. 添加时间分组：
   - 字段：`order_time`
   - 粒度：按小时
4. 执行查询

**生成的SQL**：
```sql
SELECT COUNT(*) AS `hourly_orders`
FROM `order`
GROUP BY DATE_FORMAT(`order_time`, '%Y-%m-%d %H')
ORDER BY DATE_FORMAT(`order_time`, '%Y-%m-%d %H')
```

### 3. 用户消费分析
**目标**：按用户分组，统计每个用户的消费情况

**配置步骤**：
1. 选择表：`order`
2. 添加聚合字段：
   - SUM(`total_price`) AS `total_spent`
   - COUNT(*) AS `order_count`
   - AVG(`total_price`) AS `avg_order_value`
3. 添加字段分组：
   - 字段：`user_id`
4. 执行查询

**生成的SQL**：
```sql
SELECT SUM(`total_price`) AS `total_spent`, 
       COUNT(*) AS `order_count`, 
       AVG(`total_price`) AS `avg_order_value`
FROM `order`
GROUP BY `user_id`
```

### 4. 商品销量分析
**目标**：按商品分类统计销量和收入

**配置步骤**：
1. 选择表：`order_item`（需要关联查询）
2. 添加聚合字段：
   - SUM(`quantity`) AS `total_quantity`
   - SUM(`subtotal`) AS `total_revenue`
3. 添加字段分组：
   - 字段：`menu_item_id`
4. 执行查询

## 🔧 功能详解

### 时间粒度选项

| 粒度 | SQL函数 | 说明 |
|------|---------|------|
| 按天 | `DATE(field)` | 按日期分组，忽略时间 |
| 按小时 | `DATE_FORMAT(field, '%Y-%m-%d %H')` | 按小时分组 |
| 按月 | `DATE_FORMAT(field, '%Y-%m')` | 按月份分组 |
| 按年 | `YEAR(field)` | 按年份分组 |
| 按周 | `YEARWEEK(field)` | 按周分组 |

### 聚合函数

| 函数 | 说明 | 适用字段类型 |
|------|------|-------------|
| SUM() | 求和 | 数值型字段 |
| AVG() | 平均值 | 数值型字段 |
| MAX() | 最大值 | 数值型、日期型 |
| MIN() | 最小值 | 数值型、日期型 |
| COUNT() | 计数 | 任意字段 |

### 字段别名

为聚合字段设置别名可以：
- 提高结果可读性
- 避免字段名冲突
- 便于后续分析

**示例**：
- `SUM(total_price) AS daily_sales`
- `COUNT(*) AS order_count`
- `AVG(total_price) AS avg_order_value`

## 💡 最佳实践

### 1. 性能优化
- 对分组字段建立索引
- 合理使用筛选条件减少数据量
- 避免在大量数据上使用复杂聚合

### 2. 数据准确性
- 确保时间字段格式正确
- 注意NULL值的处理
- 验证聚合结果的合理性

### 3. 查询设计
- 先确定分析目标
- 选择合适的聚合函数
- 合理设置分组粒度

## 🚀 高级用法

### 组合分组
可以同时使用时间分组和字段分组：

**示例**：按天和用户分组统计
```sql
SELECT DATE(order_time) as date, 
       user_id,
       SUM(total_price) as daily_user_sales
FROM `order`
GROUP BY DATE(order_time), user_id
```

### 多聚合函数
一个查询可以使用多个聚合函数：

**示例**：
```sql
SELECT DATE(order_time) as date,
       SUM(total_price) as total_sales,
       COUNT(*) as order_count,
       AVG(total_price) as avg_order_value,
       MAX(total_price) as max_order_value
FROM `order`
GROUP BY DATE(order_time)
```

### 条件聚合
结合筛选条件进行聚合分析：

**示例**：统计已完成订单的销售情况
```sql
SELECT DATE(order_time) as date,
       SUM(total_price) as completed_sales
FROM `order`
WHERE status = 'completed'
GROUP BY DATE(order_time)
```

## 🔍 常见问题

### Q: 如何处理时区问题？
A: 确保数据库和应用程序使用相同的时区设置，或使用 `CONVERT_TZ()` 函数进行时区转换。

### Q: 聚合结果为空怎么办？
A: 检查筛选条件是否过于严格，确认数据源中确实存在符合条件的数据。

### Q: 如何优化查询性能？
A: 在分组字段上建立索引，使用适当的筛选条件，避免在大量数据上进行复杂聚合。

### Q: 支持哪些数据类型？
A: 时间分组支持 DATETIME、TIMESTAMP 类型，聚合函数支持数值型字段。

---

通过这个重构的分组聚合功能，你可以进行更灵活和强大的数据分析，满足各种业务分析需求。 