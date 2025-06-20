-- 修复订单表的外键约束
-- 删除错误的外键约束（指向user_backup）
ALTER TABLE `order` DROP FOREIGN KEY order_ibfk_1;

-- 添加正确的外键约束（指向user表）
ALTER TABLE `order` ADD CONSTRAINT order_ibfk_1 
FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE;

-- 验证修复结果
SHOW CREATE TABLE `order`; 