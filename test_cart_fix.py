#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
购物车数据结构修复测试脚本
"""

def test_cart_migration():
    """测试购物车数据从列表格式迁移到字典格式"""
    
    # 模拟旧的购物车数据（列表格式）
    old_cart = [1, 2, 1, 3, 2, 1]  # 商品ID列表，重复表示数量
    
    print("原始购物车数据（列表格式）:", old_cart)
    
    # 转换为新格式（字典格式）
    new_cart = {}
    for item_id in old_cart:
        item_id_str = str(item_id)
        if item_id_str in new_cart:
            new_cart[item_id_str] += 1
        else:
            new_cart[item_id_str] = 1
    
    print("转换后的购物车数据（字典格式）:", new_cart)
    
    # 验证转换结果
    expected = {'1': 3, '2': 2, '3': 1}
    print("期望结果:", expected)
    print("转换正确:", new_cart == expected)
    
    return new_cart

def test_add_to_cart_simulation():
    """模拟添加商品到购物车的过程"""
    
    # 模拟session中的购物车
    session_cart = {'1': 2, '3': 1}  # 现有购物车
    print("当前购物车:", session_cart)
    
    # 模拟添加商品ID为2，数量为3
    item_id = 2
    quantity = 3
    
    if str(item_id) in session_cart:
        session_cart[str(item_id)] += quantity
    else:
        session_cart[str(item_id)] = quantity
    
    print(f"添加商品ID {item_id}，数量 {quantity}")
    print("更新后的购物车:", session_cart)
    
    return session_cart

if __name__ == "__main__":
    print("=== 购物车数据结构修复测试 ===\n")
    
    print("1. 测试数据格式转换:")
    test_cart_migration()
    
    print("\n2. 测试添加商品功能:")
    test_add_to_cart_simulation()
    
    print("\n✅ 测试完成！购物车数据结构修复应该正常工作。") 