import csv
import mysql.connector
import os

# 数据库连接信息
DB_CONFIG = {
    'host': 'mysql7.sqlpub.com',
    'port': 3312,
    'user': 'aocjor',
    'password': 'XxzAgt8llTP8dqDV',
    'database': 'ljb_bysj'
}

# 定义默认值
DEFAULT_PREP_TIME = 10
DEFAULT_COOK_TIME = 20
DEFAULT_DIFFICULTY = '简单'
DEFAULT_TASTE = '咸口'

print("批量导入菜谱脚本")
print("=" * 50)

# 读取CSV文件
csv_file = 'd:\\BYSJ\\caipu_crawler\\caipu_ultimate_final_cleaned.csv'
print(f"正在读取文件: {csv_file}")

if not os.path.exists(csv_file):
    print(f"错误: 文件 {csv_file} 不存在！")
    exit(1)

# 准备数据
recipes = []
with open(csv_file, 'r', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    
    for i, row in enumerate(reader, 1):
        # 检查必要字段
        if not row['﻿标题']:
            print(f"第{i}行: 缺少标题字段，跳过")
            continue
        if not row['简介']:
            print(f"第{i}行: 缺少简介字段，跳过")
            continue
        if not row['做法步骤']:
            print(f"第{i}行: 缺少做法步骤字段，跳过")
            continue
        if not row['一级分类']:
            print(f"第{i}行: 缺少一级分类字段，跳过")
            continue
        
        # 处理做法步骤，确保分行显示
        instructions = row['做法步骤']
        # 将数字编号的步骤分开
        import re
        # 查找数字编号的步骤
        steps = re.split(r'(\d+\.)', instructions)
        # 重新组合步骤，确保每个步骤独占一行
        formatted_instructions = []
        for i in range(1, len(steps), 2):
            if i + 1 < len(steps):
                step_number = steps[i]
                step_content = steps[i + 1].strip()
                if step_content:
                    formatted_instructions.append(f"{step_number} {step_content}")
        # 如果没有数字编号，按句分割
        if not formatted_instructions:
            # 按句号分割
            sentences = instructions.split('。')
            for i, sentence in enumerate(sentences, 1):
                sentence = sentence.strip()
                if sentence:
                    formatted_instructions.append(f"{i}. {sentence}")
        # 组合成多行文本
        formatted_instructions_text = '\n'.join(formatted_instructions)
        
        # 构建菜谱数据
        recipe = {
            'title': row['﻿标题'],
            'description': row['简介'],
            'instructions': formatted_instructions_text,
            'category': row['二级分类'],
            'prep_time': DEFAULT_PREP_TIME,
            'cook_time': DEFAULT_COOK_TIME,
            'difficulty': DEFAULT_DIFFICULTY,
            'taste': DEFAULT_TASTE,
            'views': 0,
            'month_views': 0,
            'day_views': 0,
            'main_ingredients': row['主料'],
            'auxiliary_ingredients': row['辅料']
        }
        recipes.append(recipe)

print(f"\n读取完成，共收集到 {len(recipes)} 个有效菜谱")

if not recipes:
    print("没有有效菜谱数据，退出")
    exit(1)

# 连接数据库并导入数据
try:
    print("\n正在连接数据库...")
    cnx = mysql.connector.connect(**DB_CONFIG)
    cursor = cnx.cursor()
    print("数据库连接成功！")
    
    # 导入数据
    inserted = 0
    for i, recipe in enumerate(recipes, 1):
        try:
            # 检查是否已存在
            cursor.execute("SELECT id FROM recipe WHERE title = %s", (recipe['title'],))
            if cursor.fetchone():
                print(f"第{i}个菜谱 '{recipe['title']}' 已存在，跳过")
                continue
            
            # 插入数据
            query = """
                INSERT INTO recipe (title, description, instructions, category, prep_time, cook_time, difficulty, taste, views, month_views, day_views)
                VALUES (%(title)s, %(description)s, %(instructions)s, %(category)s, %(prep_time)s, %(cook_time)s, %(difficulty)s, %(taste)s, %(views)s, %(month_views)s, %(day_views)s)
            """
            cursor.execute(query, recipe)
            recipe_id = cursor.lastrowid
            cnx.commit()
            
            # 解析并插入食材
            def parse_ingredients(ingredient_text):
                """解析食材文本，返回食材列表"""
                if not ingredient_text:
                    return []
                ingredients = []
                # 按空格分割
                items = ingredient_text.split(' ')
                
                for item in items:
                    item = item.strip()
                    if not item:
                        continue
                    
                    # 常见的数量词
                    quantity_words = ['适量', '少许', '一些', '一把', '一点', '若干']
                    
                    # 检查是否包含数量词
                    quantity = '适量'
                    ingredient_name = item
                    
                    for word in quantity_words:
                        if word in item:
                            # 分离食材名和数量词
                            ingredient_name = item.replace(word, '').strip()
                            quantity = word
                            break
                    
                    # 如果没有找到数量词，尝试查找数字
                    if quantity == '适量':
                        import re
                        match = re.search(r'\d', item)
                        if match:
                            # 找到数字，分离食材名和数量
                            ingredient_name = item[:match.start()].strip()
                            quantity = item[match.start():].strip()
                    
                    if ingredient_name:
                        ingredients.append((ingredient_name, quantity))
                
                return ingredients
            
            # 处理主料
            main_ingredients = parse_ingredients(recipe.get('main_ingredients', ''))
            # 处理辅料
            auxiliary_ingredients = parse_ingredients(recipe.get('auxiliary_ingredients', ''))
            
            # 合并所有食材
            all_ingredients = main_ingredients + auxiliary_ingredients
            
            # 插入食材和关联
            for ingredient_name, quantity in all_ingredients:
                if not ingredient_name:
                    continue
                
                # 检查食材是否已存在
                cursor.execute("SELECT id FROM ingredient WHERE name = %s", (ingredient_name,))
                ingredient = cursor.fetchone()
                
                if not ingredient:
                    # 创建新食材
                    cursor.execute("INSERT INTO ingredient (name, category) VALUES (%s, %s)", (ingredient_name, '其他'))
                    ingredient_id = cursor.lastrowid
                else:
                    ingredient_id = ingredient[0]
                
                # 插入菜谱-食材关联
                cursor.execute(
                    "INSERT INTO recipe_ingredient (recipe_id, ingredient_id, quantity) VALUES (%s, %s, %s)",
                    (recipe_id, ingredient_id, quantity)
                )
            
            cnx.commit()
            inserted += 1
            print(f"第{i}个菜谱 '{recipe['title']}' 导入成功，包含 {len(all_ingredients)} 个食材")
            
        except Exception as e:
            print(f"第{i}个菜谱导入失败: {e}")
            cnx.rollback()
    
    print(f"\n导入完成，成功导入 {inserted} 个菜谱")
    
    # 关闭连接
    cursor.close()
    cnx.close()
    print("数据库连接已关闭")
except Exception as e:
    print(f"数据库操作失败: {e}")
    import traceback
    traceback.print_exc()