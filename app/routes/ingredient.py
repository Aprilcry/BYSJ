from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.models import Ingredient, UserIngredient, IngredientShelfLife, IngredientCategoryMap
from app import db
import os
import cv2
import torch
import numpy as np

# 创建蓝图
bp = Blueprint('ingredient', __name__)

# 导入YOLO模型
from ultralytics import YOLO

# 尝试加载训练好的模型
model_path = 'd:\BYSJ\yolov8_best.pt'
if os.path.exists(model_path):
    model = YOLO(model_path)
    print(f'Loaded trained model from: {model_path}')
else:
    # 如果没有训练好的模型，使用预训练模型
    model = YOLO('yolov8x.pt')
    print('Using pretrained YOLOv8x model')

@bp.route('/')
@login_required
def index():
    # 获取用户的食材列表
    from app.models import UserIngredient
    user_ingredients = UserIngredient.query.filter_by(user_id=current_user.id).all()
    return render_template('ingredient/index.html', ingredients=user_ingredients)

@bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        added_at = request.form.get('added_at')
        # 检查食材是否已存在
        existing_ingredient = Ingredient.query.filter_by(name=name).first()
        if existing_ingredient:
            # 食材已存在，直接添加到用户食材列表
            from app.models import UserIngredient, TZ
            user_ingredient = UserIngredient(user_id=current_user.id, ingredient_id=existing_ingredient.id)
            if added_at:
                from datetime import datetime
                user_ingredient.added_at = TZ.localize(datetime.strptime(added_at, '%Y-%m-%dT%H:%M'))
            db.session.add(user_ingredient)
        else:
            # 创建新食材
            new_ingredient = Ingredient(name=name, category=category)
            db.session.add(new_ingredient)
            db.session.flush()  # 获取食材ID
            # 添加到用户食材列表
            from app.models import UserIngredient, TZ
            user_ingredient = UserIngredient(user_id=current_user.id, ingredient_id=new_ingredient.id)
            if added_at:
                from datetime import datetime
                user_ingredient.added_at = TZ.localize(datetime.strptime(added_at, '%Y-%m-%dT%H:%M'))
            db.session.add(user_ingredient)
        db.session.commit()
        return redirect(url_for('ingredient.index'))
    return render_template('ingredient/add.html')

@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    from app.models import UserIngredient
    ingredient = Ingredient.query.get(id)
    # 获取用户食材记录
    user_ingredient = UserIngredient.query.filter_by(user_id=current_user.id, ingredient_id=id).first()
    
    if request.method == 'POST':
        # 更新食材基本信息
        ingredient.name = request.form['name']
        ingredient.category = request.form['category']
        
        # 更新用户食材时间
        if user_ingredient:
            added_at = request.form.get('added_at')
            if added_at:
                from datetime import datetime
                from app.models import TZ
                user_ingredient.added_at = TZ.localize(datetime.strptime(added_at, '%Y-%m-%dT%H:%M'))
        
        db.session.commit()
        return redirect(url_for('ingredient.index'))
    
    # 传递用户食材对象，以便在模板中显示时间
    return render_template('ingredient/edit.html', ingredient=ingredient, user_ingredient=user_ingredient)

@bp.route('/delete/<int:id>')
def delete(id):
    ingredient = Ingredient.query.get(id)
    if not ingredient:
        return redirect(url_for('ingredient.index'))
    # 删除引用这个食材的recipe_ingredient记录
    from app.models import RecipeIngredient, UserIngredient
    recipe_ingredients = RecipeIngredient.query.filter_by(ingredient_id=id).all()
    for recipe_ingredient in recipe_ingredients:
        db.session.delete(recipe_ingredient)
    # 删除引用这个食材的user_ingredient记录
    user_ingredients = UserIngredient.query.filter_by(ingredient_id=id).all()
    for user_ingredient in user_ingredients:
        db.session.delete(user_ingredient)
    # 删除食材
    db.session.delete(ingredient)
    db.session.commit()
    return redirect(url_for('ingredient.index'))

@bp.route('/batch-delete', methods=['POST'])
def batch_delete():
    data = request.get_json()
    ingredient_ids = data.get('ingredient_ids', [])
    
    if not ingredient_ids:
        return {'success': False, 'message': '请选择要删除的食材'}
    
    try:
        # 删除引用这些食材的记录
        from app.models import RecipeIngredient, UserIngredient
        for ingredient_id in ingredient_ids:
            # 删除recipe_ingredient记录
            recipe_ingredients = RecipeIngredient.query.filter_by(ingredient_id=ingredient_id).all()
            for recipe_ingredient in recipe_ingredients:
                db.session.delete(recipe_ingredient)
            # 删除user_ingredient记录
            user_ingredients = UserIngredient.query.filter_by(ingredient_id=ingredient_id).all()
            for user_ingredient in user_ingredients:
                db.session.delete(user_ingredient)
            # 删除食材
            ingredient = Ingredient.query.get(ingredient_id)
            if ingredient:
                db.session.delete(ingredient)
        
        db.session.commit()
        return {'success': True, 'message': '删除成功'}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'删除失败: {str(e)}'}

@bp.route('/camera')
@login_required
def camera():
    return render_template('ingredient/camera.html')

@bp.route('/detect-ingredient', methods=['POST'])
def detect_ingredient():
    try:
        # 获取前端发送的图像数据
        import base64
        data = request.get_json()
        image_data = data.get('image')
        
        # 解码Base64图像
        image_data = image_data.split(',')[1]  # 移除前缀
        image_bytes = base64.b64decode(image_data)
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        
        # 使用YOLO模型进行检测
        results = model(image)
        
        # 提取检测结果
        detected_ingredients = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = model.names[class_id]
                confidence = float(box.conf[0])
                
                # 只添加置信度大于0.5的结果
                if confidence > 0.5 and class_name and class_name.strip() != '':
                    detected_ingredients.append({
                        'name': class_name,
                        'confidence': confidence
                    })
        
        # 如果没有检测到食材，返回空结果
        if not detected_ingredients:
            return {'success': True, 'result': None}
        
        # 返回第一个检测到的食材
        return {'success': True, 'result': detected_ingredients[0]}
    except Exception as e:
        print(f'识别失败: {str(e)}')
        return {'success': False, 'message': f'识别失败: {str(e)}'}

@bp.route('/add-from-camera', methods=['POST'])
def add_from_camera():
    data = request.get_json()
    ingredient_name = data.get('name')
    category = data.get('category', '其他')
    
    if not ingredient_name:
        return {'success': False, 'message': '请提供食材名称'}
    
    try:
        # 查找或创建食材
        ingredient = Ingredient.query.filter_by(name=ingredient_name).first()
        if not ingredient:
            ingredient = Ingredient(name=ingredient_name, category=category)
            db.session.add(ingredient)
            db.session.commit()
        
        # 添加到用户食材列表
        user_ingredient = UserIngredient(user_id=current_user.id, ingredient_id=ingredient.id)
        db.session.add(user_ingredient)
        db.session.commit()
        
        return {'success': True, 'message': '食材添加成功'}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'添加失败: {str(e)}'}

# 管理保质期映射
@bp.route('/shelf-life')
@login_required
def manage_shelf_life():
    # 检查是否是管理员
    if not current_user.is_admin:
        return render_template('403.html'), 403
    
    # 获取所有保质期映射
    shelf_life_mappings = IngredientShelfLife.query.all()
    return render_template('ingredient/shelf_life.html', mappings=shelf_life_mappings)

@bp.route('/shelf-life/add', methods=['GET', 'POST'])
@login_required
def add_shelf_life():
    # 检查是否是管理员
    if not current_user.is_admin:
        return render_template('403.html'), 403
    
    if request.method == 'POST':
        ingredient_name = request.form['ingredient_name']
        shelf_life_days = request.form['shelf_life_days']
        
        # 检查是否已存在
        existing = IngredientShelfLife.query.filter_by(ingredient_name=ingredient_name).first()
        if existing:
            existing.shelf_life_days = shelf_life_days
        else:
            new_mapping = IngredientShelfLife(ingredient_name=ingredient_name, shelf_life_days=shelf_life_days)
            db.session.add(new_mapping)
        
        db.session.commit()
        return redirect(url_for('ingredient.manage_shelf_life'))
    
    return render_template('ingredient/add_shelf_life.html')

@bp.route('/shelf-life/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_shelf_life(id):
    # 检查是否是管理员
    if not current_user.is_admin:
        return render_template('403.html'), 403
    
    mapping = IngredientShelfLife.query.get(id)
    if not mapping:
        return redirect(url_for('ingredient.manage_shelf_life'))
    
    if request.method == 'POST':
        mapping.ingredient_name = request.form['ingredient_name']
        mapping.shelf_life_days = request.form['shelf_life_days']
        db.session.commit()
        return redirect(url_for('ingredient.manage_shelf_life'))
    
    return render_template('ingredient/edit_shelf_life.html', mapping=mapping)

@bp.route('/shelf-life/delete/<int:id>')
@login_required
def delete_shelf_life(id):
    # 检查是否是管理员
    if not current_user.is_admin:
        return render_template('403.html'), 403
    
    mapping = IngredientShelfLife.query.get(id)
    if mapping:
        db.session.delete(mapping)
        db.session.commit()
    return redirect(url_for('ingredient.manage_shelf_life'))

@bp.route('/shelf-life/batch-delete', methods=['POST'])
@login_required
def batch_delete_shelf_life():
    # 检查是否是管理员
    if not current_user.is_admin:
        return {'success': False, 'message': '无权限操作'}
    
    data = request.get_json()
    mapping_ids = data.get('mapping_ids', [])
    
    if not mapping_ids:
        return {'success': False, 'message': '请选择要删除的记录'}
    
    try:
        for mapping_id in mapping_ids:
            mapping = IngredientShelfLife.query.get(mapping_id)
            if mapping:
                db.session.delete(mapping)
        db.session.commit()
        return {'success': True, 'message': '删除成功'}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'删除失败: {str(e)}'}

# 管理食材分类映射
@bp.route('/category-map')
@login_required
def manage_category_map():
    # 检查是否是管理员
    if not current_user.is_admin:
        return render_template('403.html'), 403
    
    # 获取所有食材
    all_ingredients = Ingredient.query.all()
    # 获取所有分类映射
    category_mappings = IngredientCategoryMap.query.all()
    
    # 创建食材名称到分类的映射
    mapping_dict = {mapping.ingredient_name: mapping for mapping in category_mappings}
    
    # 准备展示数据
    display_data = []
    for ingredient in all_ingredients:
        # 检查食材是否已有映射
        if ingredient.name in mapping_dict:
            # 已有映射，使用现有映射
            display_data.append(mapping_dict[ingredient.name])
        else:
            # 没有映射，创建临时对象用于展示
            from collections import namedtuple
            TempMapping = namedtuple('TempMapping', ['id', 'ingredient_name', 'category'])
            display_data.append(TempMapping(id=None, ingredient_name=ingredient.name, category='未分类'))
    
    return render_template('ingredient/category_map.html', mappings=display_data)

@bp.route('/category-map/add', methods=['GET', 'POST'])
@login_required
def add_category_map():
    # 检查是否是管理员
    if not current_user.is_admin:
        return render_template('403.html'), 403
    
    # 获取URL参数中的食材名称
    ingredient_name = request.args.get('ingredient_name', '')
    
    if request.method == 'POST':
        ingredient_name = request.form['ingredient_name']
        category = request.form['category']
        
        # 检查是否已存在
        existing = IngredientCategoryMap.query.filter_by(ingredient_name=ingredient_name).first()
        if existing:
            existing.category = category
        else:
            new_mapping = IngredientCategoryMap(ingredient_name=ingredient_name, category=category)
            db.session.add(new_mapping)
        
        db.session.commit()
        return redirect(url_for('ingredient.manage_category_map'))
    
    return render_template('ingredient/add_category_map.html', ingredient_name=ingredient_name)

@bp.route('/category-map/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category_map(id):
    # 检查是否是管理员
    if not current_user.is_admin:
        return render_template('403.html'), 403
    
    mapping = IngredientCategoryMap.query.get(id)
    if not mapping:
        return redirect(url_for('ingredient.manage_category_map'))
    
    if request.method == 'POST':
        mapping.ingredient_name = request.form['ingredient_name']
        mapping.category = request.form['category']
        db.session.commit()
        return redirect(url_for('ingredient.manage_category_map'))
    
    return render_template('ingredient/edit_category_map.html', mapping=mapping)

@bp.route('/category-map/delete/<int:id>')
@login_required
def delete_category_map(id):
    # 检查是否是管理员
    if not current_user.is_admin:
        return render_template('403.html'), 403
    
    mapping = IngredientCategoryMap.query.get(id)
    if mapping:
        db.session.delete(mapping)
        db.session.commit()
    return redirect(url_for('ingredient.manage_category_map'))

@bp.route('/category-map/batch-delete', methods=['POST'])
@login_required
def batch_delete_category_map():
    # 检查是否是管理员
    if not current_user.is_admin:
        return {'success': False, 'message': '无权限操作'}
    
    data = request.get_json()
    mapping_ids = data.get('mapping_ids', [])
    
    if not mapping_ids:
        return {'success': False, 'message': '请选择要删除的记录'}
    
    try:
        for mapping_id in mapping_ids:
            mapping = IngredientCategoryMap.query.get(mapping_id)
            if mapping:
                db.session.delete(mapping)
        db.session.commit()
        return {'success': True, 'message': '删除成功'}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'删除失败: {str(e)}'}

@bp.route('/delete-ingredient/<string:name>')
@login_required
def delete_ingredient_by_name(name):
    # 检查是否是管理员
    if not current_user.is_admin:
        return render_template('403.html'), 403
    
    try:
        # 查找食材
        ingredient = Ingredient.query.filter_by(name=name).first()
        if not ingredient:
            return redirect(url_for('ingredient.manage_category_map'))
        
        # 删除引用这个食材的记录
        from app.models import RecipeIngredient, UserIngredient, IngredientCategoryMap, IngredientShelfLife
        
        # 删除recipe_ingredient记录
        recipe_ingredients = RecipeIngredient.query.filter_by(ingredient_id=ingredient.id).all()
        for recipe_ingredient in recipe_ingredients:
            db.session.delete(recipe_ingredient)
        
        # 删除user_ingredient记录
        user_ingredients = UserIngredient.query.filter_by(ingredient_id=ingredient.id).all()
        for user_ingredient in user_ingredients:
            db.session.delete(user_ingredient)
        
        # 删除ingredient_category_map记录
        category_mappings = IngredientCategoryMap.query.filter_by(ingredient_name=name).all()
        for mapping in category_mappings:
            db.session.delete(mapping)
        
        # 删除ingredient_shelf_life记录
        shelf_life_mappings = IngredientShelfLife.query.filter_by(ingredient_name=name).all()
        for mapping in shelf_life_mappings:
            db.session.delete(mapping)
        
        # 删除食材
        db.session.delete(ingredient)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'删除食材失败: {str(e)}')
    
    return redirect(url_for('ingredient.manage_category_map'))
