#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
菜谱口味智能调整脚本
根据菜谱标题和描述自动判断并调整口味设置
"""

import re
import pymysql
from collections import defaultdict

# 数据库配置
DB_CONFIG = {
    'host': 'mysql7.sqlpub.com',
    'port': 3312,
    'user': 'aocjor',
    'password': 'XxzAgt8llTP8dqDV',
    'database': 'ljb_bysj',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# 口味关键词映射
taste_keywords = {
    '甜口': [
        '甜', '糖', '蜜', '蜂蜜', '焦糖', '巧克力', '蛋糕', '甜点', '甜品', '糖水',
        '冰淇淋', '布丁', '果冻', '果酱', '糖浆', '甜酒', '甜汤', '甜羹', '甜粥',
        '草莓', '蓝莓', '芒果', '榴莲', '荔枝', '龙眼', '蜜桃', '葡萄', '樱桃',
        '芝士', '奶酪', '奶油', '黄油', '奶昔', '奶茶', '奶糕', '酸奶', '奶豆腐',
        '红薯', '南瓜', '山药', '芋圆', '汤圆', '元宵', '月饼', '粽子', '八宝饭',
        '糖醋', '蜜汁', '甜辣', '甜酸', '甜鲜'
    ],
    '酸口': [
        '酸', '醋', '酸菜', '酸梅', '酸枣', '酸奶', '酸汤', '酸辣', '酸甜',
        '柠檬', '橙子', '橘子', '柚子', '菠萝', '猕猴桃', '山楂', '杨梅', '青梅',
        '泡菜', '醋溜', '醋酸', '酸乳', '酸酪', '酸豆', '酸角', '酸梅汤'
    ],
    '辣口': [
        '辣', '辣椒', '花椒', '胡椒', '姜', '蒜', '芥末', '咖喱', '麻辣', '香辣',
        '酸辣', '甜辣', '爆辣', '特辣', '中辣', '微辣', '辣椒面', '辣椒油', '辣椒酱',
        '火锅', '麻辣烫', '麻辣香锅', '酸辣粉', '螺蛳粉', '麻辣小龙虾'
    ],
    '咸口': [
        '咸', '盐', '酱油', '生抽', '老抽', '料酒', '蚝油', '豆瓣酱', '豆豉',
        '咸菜', '腌菜', '酱菜', '咸鱼', '咸肉', '咸蛋', '咸鸭蛋', '咸鸡', '咸鸭',
        '卤味', '卤肉', '卤蛋', '卤菜', '红烧肉', '红烧鱼', '红烧排骨', '清蒸', '清炒',
        '爆炒', '油炸', '煎炒', '炖煮', '煲汤', '熬汤', '炖汤'
    ]
}

# 特殊菜品映射（直接指定口味）
special_dishes = {
    '糖醋鲤鱼': '甜口',
    '糖醋排骨': '甜口',
    '糖醋里脊': '甜口',
    '糖醋藕片': '甜口',
    '芝士焗红薯': '甜口',
    '芝士蛋糕': '甜口',
    '提拉米苏': '甜口',
    '马卡龙': '甜口',
    '冰淇淋': '甜口',
    '布丁': '甜口',
    '果冻': '甜口',
    '奶茶': '甜口',
    '奶昔': '甜口',
    '酸奶': '酸口',
    '酸辣粉': '辣口',
    '螺蛳粉': '辣口',
    '麻辣烫': '辣口',
    '火锅': '辣口',
    '麻辣香锅': '辣口',
    '麻辣小龙虾': '辣口',
    '酸菜鱼': '酸口',
    '酸辣汤': '酸口',
    '醋溜白菜': '酸口',
    '糖醋里脊': '甜口',
    '蜜汁叉烧': '甜口',
    '拔丝地瓜': '甜口',
    '甜酒酿': '甜口',
    '八宝粥': '甜口',
    '银耳羹': '甜口',
    '绿豆汤': '甜口',
    '红豆沙': '甜口',
    '黑芝麻糊': '甜口'
}

def get_taste_score(text):
    """根据文本计算各口味的得分"""
    scores = defaultdict(int)
    
    # 检查特殊菜品
    for dish_name, taste in special_dishes.items():
        if dish_name in text:
            scores[taste] += 10  # 特殊菜品权重更高
    
    # 检查关键词
    for taste, keywords in taste_keywords.items():
        for keyword in keywords:
            if keyword in text:
                scores[taste] += 1
    
    return scores

def determine_taste(title, description):
    """根据标题和描述确定最合适的口味"""
    # 合并标题和描述进行分析
    text = (title + ' ' + description).lower()
    
    # 计算各口味得分
    scores = get_taste_score(text)
    
    # 特殊处理：如果甜口得分较高，优先选择甜口
    if scores['甜口'] > scores['咸口'] and scores['甜口'] > scores['酸口'] and scores['甜口'] > scores['辣口']:
        return '甜口'
    # 如果酸口得分较高
    elif scores['酸口'] > scores['咸口'] and scores['酸口'] > scores['甜口'] and scores['酸口'] > scores['辣口']:
        return '酸口'
    # 如果辣口得分较高
    elif scores['辣口'] > scores['咸口'] and scores['辣口'] > scores['甜口'] and scores['辣口'] > scores['酸口']:
        return '辣口'
    # 默认咸口
    else:
        return '咸口'

def main():
    """主函数"""
    print("开始调整菜谱口味...")
    
    # 连接数据库
    conn = pymysql.connect(**DB_CONFIG)
    
    try:
        with conn.cursor() as cursor:
            # 获取所有菜谱
            cursor.execute("SELECT id, title, description, taste FROM recipe")
            recipes = cursor.fetchall()
            
            print(f"共找到 {len(recipes)} 个菜谱")
            
            # 统计信息
            total_recipes = len(recipes)
            updated_count = 0
            taste_stats = defaultdict(int)
            old_taste_stats = defaultdict(int)
            
            # 分析并更新每个菜谱
            for recipe in recipes:
                recipe_id = recipe['id']
                title = recipe['title']
                description = recipe['description']
                old_taste = recipe['taste']
                
                # 统计原始口味分布
                old_taste_stats[old_taste] += 1
                
                # 确定新口味
                new_taste = determine_taste(title, description)
                
                # 如果口味发生变化，更新数据库
                if new_taste != old_taste:
                    cursor.execute(
                        "UPDATE recipe SET taste = %s WHERE id = %s",
                        (new_taste, recipe_id)
                    )
                    updated_count += 1
                    print(f"更新菜谱 {title}：{old_taste} -> {new_taste}")
                
                # 统计新口味分布
                taste_stats[new_taste] += 1
            
            # 提交更改
            conn.commit()
            
            # 打印统计结果
            print("\n=== 调整结果 ===")
            print(f"总菜谱数：{total_recipes}")
            print(f"更新菜谱数：{updated_count}")
            print("\n原始口味分布：")
            for taste, count in old_taste_stats.items():
                percentage = (count / total_recipes) * 100
                print(f"{taste}: {count} ({percentage:.1f}%)")
            print("\n新口味分布：")
            for taste, count in taste_stats.items():
                percentage = (count / total_recipes) * 100
                print(f"{taste}: {count} ({percentage:.1f}%)")
            
    except Exception as e:
        print(f"发生错误：{e}")
        conn.rollback()
    finally:
        conn.close()
    
    print("\n口味调整完成！")

if __name__ == "__main__":
    main()
