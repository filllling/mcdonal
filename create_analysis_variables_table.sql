-- 创建分析变量表
CREATE TABLE IF NOT EXISTS analysis_variables (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '变量ID',
    user_id INT NOT NULL COMMENT '创建者用户ID',
    name VARCHAR(64) NOT NULL COMMENT '变量名',
    expression TEXT NOT NULL COMMENT '变量表达式',
    table_name VARCHAR(64) NOT NULL COMMENT '适用表名',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_variable (user_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分析变量表'; 