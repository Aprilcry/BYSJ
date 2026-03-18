from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Recipe, RecipeIngredient, Ingredient, RecipeView, User, Favorite
from app import db
import os
import requests
from bs4 import BeautifulSoup
import functools
from datetime import datetime

# 管理员权限装饰器
def admin_required(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('您没有权限执行此操作', 'danger')
            return redirect(url_for('recipe.index'))
        return func(*args, **kwargs)
    return wrapper

# 创建蓝图
bp = Blueprint('recipe', __name__)

@bp.route('/')
def index():
    # 获取筛选参数
    category = request.args.get('category')
    taste = request.args.get('taste')
    difficulty = request.args.get('difficulty')
    
    # 构建查询
    query = Recipe.query
    
    # 应用筛选条件
    if category:
        query = query.filter_by(category=category)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if taste:
        query = query.filter_by(taste=taste)
    
    # 执行查询
    recipes = query.all()
    
    return render_template('recipe/index.html', recipes=recipes)

@bp.route('/add', methods=['GET', 'POST'])
@admin_required
def add():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        instructions = request.form['instructions']
        prep_time = int(request.form['prep_time'])
        cook_time = int(request.form['cook_time'])
        difficulty = request.form['difficulty']
        category = request.form['category']
        
        # 处理图片
        if 'image' in request.files and request.files['image'].filename != '':
            image = request.files['image']
            image_filename = f"{title.replace(' ', '_')}.jpg"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
            image_url = f"/static/uploads/{image_filename}"
        elif 'image_url' in request.form and request.form['image_url'] != '':
            image_url = request.form['image_url']
        else:
            image_url = None
        
        # 处理视频
        if 'video' in request.files and request.files['video'].filename != '':
            video = request.files['video']
            video_filename = f"{title.replace(' ', '_')}.mp4"
            video_path = os.path.join(app.config['VIDEO_FOLDER'], video_filename)
            video.save(video_path)
            video_url = f"/static/videos/{video_filename}"
        elif 'video_url' in request.form and request.form['video_url'] != '':
            video_url = request.form['video_url']
        else:
            video_url = None
        
        # 创建菜谱
        new_recipe = Recipe(
            title=title,
            description=description,
            instructions=instructions,
            video_url=video_url,
            image_url=image_url,
            prep_time=prep_time,
            cook_time=cook_time,
            difficulty=difficulty,
            category=category
        )
        db.session.add(new_recipe)
        db.session.flush()  # 获取菜谱ID
        
        # 添加食材
        ingredients = request.form.getlist('ingredients[]')
        quantities = request.form.getlist('quantities[]')
        for ingredient_name, quantity in zip(ingredients, quantities):
            if ingredient_name:
                # 查找或创建食材
                ingredient = Ingredient.query.filter_by(name=ingredient_name).first()
                if not ingredient:
                    ingredient = Ingredient(name=ingredient_name, category='其他')
                    db.session.add(ingredient)
                    db.session.flush()
                # 创建菜谱食材关联
                recipe_ingredient = RecipeIngredient(
                    recipe_id=new_recipe.id,
                    ingredient_id=ingredient.id,
                    quantity=quantity
                )
                db.session.add(recipe_ingredient)
        
        db.session.commit()
        return redirect(url_for('recipe.index'))
    ingredients = Ingredient.query.all()
    return render_template('recipe/add.html', ingredients=ingredients)

@bp.route('/detail/<int:id>')
def detail(id):
    recipe = Recipe.query.get(id)
    # 增加浏览量
    recipe.views += 1
    recipe.month_views += 1
    recipe.day_views += 1
    
    # 记录浏览历史
    from flask_login import current_user
    if current_user.is_authenticated:
        # 检查是否已经存在相同的浏览记录
        existing_view = RecipeView.query.filter_by(user_id=current_user.id, recipe_id=id).first()
        if existing_view:
            # 更新浏览时间
            existing_view.viewed_at = datetime.utcnow()
        else:
            # 创建新的浏览记录
            new_view = RecipeView(user_id=current_user.id, recipe_id=id)
            db.session.add(new_view)
    
    # 检查是否已收藏
    favorited = False
    if current_user.is_authenticated:
        existing_favorite = Favorite.query.filter_by(user_id=current_user.id, target_type='recipe', target_id=id).first()
        if existing_favorite:
            favorited = True
    
    db.session.commit()
    return render_template('recipe/detail.html', recipe=recipe, favorited=favorited)

@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit(id):
    recipe = Recipe.query.get(id)
    if request.method == 'POST':
        recipe.title = request.form['title']
        recipe.description = request.form['description']
        recipe.instructions = request.form['instructions']
        recipe.prep_time = int(request.form['prep_time'])
        recipe.cook_time = int(request.form['cook_time'])
        recipe.difficulty = request.form['difficulty']
        recipe.category = request.form['category']
        
        # 处理图片
        if 'image' in request.files and request.files['image'].filename != '':
            image = request.files['image']
            image_filename = f"{recipe.title.replace(' ', '_')}.jpg"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
            recipe.image_url = f"/static/uploads/{image_filename}"
        elif 'image_url' in request.form and request.form['image_url'] != '':
            recipe.image_url = request.form['image_url']
        
        # 处理视频
        if 'video' in request.files and request.files['video'].filename != '':
            video = request.files['video']
            video_filename = f"{recipe.title.replace(' ', '_')}.mp4"
            video_path = os.path.join(app.config['VIDEO_FOLDER'], video_filename)
            video.save(video_path)
            recipe.video_url = f"/static/videos/{video_filename}"
        elif 'video_url' in request.form and request.form['video_url'] != '':
            recipe.video_url = request.form['video_url']
        
        # 更新食材
        RecipeIngredient.query.filter_by(recipe_id=recipe.id).delete()
        ingredients = request.form.getlist('ingredients[]')
        quantities = request.form.getlist('quantities[]')
        for ingredient_name, quantity in zip(ingredients, quantities):
            if ingredient_name:
                # 查找或创建食材
                ingredient = Ingredient.query.filter_by(name=ingredient_name).first()
                if not ingredient:
                    ingredient = Ingredient(name=ingredient_name, category='其他')
                    db.session.add(ingredient)
                    db.session.flush()
                # 创建菜谱食材关联
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient.id,
                    quantity=quantity
                )
                db.session.add(recipe_ingredient)
        
        db.session.commit()
        return redirect(url_for('recipe.detail', id=recipe.id))
    ingredients = Ingredient.query.all()
    return render_template('recipe/edit.html', recipe=recipe, ingredients=ingredients)

@bp.route('/delete/<int:id>')
@admin_required
def delete(id):
    recipe = Recipe.query.get(id)
    # 删除相关的RecipeView和RecipeIngredient记录
    RecipeView.query.filter_by(recipe_id=id).delete()
    RecipeIngredient.query.filter_by(recipe_id=id).delete()
    # 删除菜谱
    db.session.delete(recipe)
    db.session.commit()
    return redirect(url_for('recipe.index'))

@bp.route('/search')
def search():
    keyword = request.args.get('keyword')
    recipes = Recipe.query.filter(Recipe.title.contains(keyword) | Recipe.description.contains(keyword)).all()
    return render_template('recipe/index.html', recipes=recipes)

# 导入 app
from app import app
