from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import User, UserIngredient, Ingredient, RecipeView, Recipe, Favorite, Post, PostView
from app import db
from datetime import datetime, timedelta

# 创建蓝图
bp = Blueprint('user', __name__, template_folder='templates')

@bp.route('/')
@login_required
def index():
    # 获取用户食材
    user_ingredients = UserIngredient.query.filter_by(user_id=current_user.id).all()
    # 获取最近浏览记录
    recent_views = []
    viewed_items = set()  # 用于去重
    
    # 获取菜谱浏览记录，按时间倒序排序
    recipe_views = RecipeView.query.filter_by(user_id=current_user.id).order_by(RecipeView.viewed_at.desc()).all()
    for view in recipe_views:
        if view.recipe_id not in viewed_items:
            recipe = Recipe.query.get(view.recipe_id)
            if recipe:
                # 将 UTC 时间转换为东八区时间
                recipe.viewed_at = view.viewed_at + timedelta(hours=8)
                recent_views.append(recipe)
                viewed_items.add(view.recipe_id)
    
    # 获取帖子浏览记录，按时间倒序排序
    post_views = PostView.query.filter_by(user_id=current_user.id).order_by(PostView.viewed_at.desc()).all()
    for view in post_views:
        if view.post_id not in viewed_items:
            post = Post.query.get(view.post_id)
            if post:
                # 将 UTC 时间转换为东八区时间
                post.viewed_at = view.viewed_at + timedelta(hours=8)
                recent_views.append(post)
                viewed_items.add(view.post_id)
    
    # 按浏览时间排序
    recent_views.sort(key=lambda x: x.viewed_at, reverse=True)
    # 限制显示5条
    recent_views = recent_views[:5]
    
    # 获取收藏记录
    favorites = []
    favorite_records = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).limit(5).all()
    for fav in favorite_records:
        if fav.target_type == 'recipe':
            item = Recipe.query.get(fav.target_id)
        else:
            item = Post.query.get(fav.target_id)
        if item:
            favorites.append(item)
    
    return render_template('user/index.html', user_ingredients=user_ingredients, recent_views=recent_views, favorites=favorites)

@bp.route('/ingredients')
@login_required
def ingredients():
    user_ingredients = UserIngredient.query.filter_by(user_id=current_user.id).all()
    return render_template('user/ingredients.html', user_ingredients=user_ingredients)

@bp.route('/add_ingredient', methods=['GET', 'POST'])
@login_required
def add_ingredient():
    if request.method == 'POST':
        ingredient_name = request.form['ingredient_name']
        category = request.form['category']
        quantity = request.form['quantity']
        # 查找或创建食材
        ingredient = Ingredient.query.filter_by(name=ingredient_name).first()
        if not ingredient:
            ingredient = Ingredient(name=ingredient_name, category=category)
            db.session.add(ingredient)
            db.session.commit()
        # 添加到用户食材
        user_ingredient = UserIngredient(user_id=current_user.id, ingredient_id=ingredient.id, quantity=quantity)
        db.session.add(user_ingredient)
        db.session.commit()
        return redirect(url_for('ingredient.index'))
    return render_template('user/add_ingredient.html')

@bp.route('/remove_ingredient/<int:id>')
@login_required
def remove_ingredient(id):
    user_ingredient = UserIngredient.query.filter_by(id=id, user_id=current_user.id).first()
    if user_ingredient:
        db.session.delete(user_ingredient)
        db.session.commit()
    return redirect(url_for('user.ingredients'))

@bp.route('/favorites')
@login_required
def favorites():
    # 获取收藏记录
    page = request.args.get('page', 1, type=int)
    per_page = 5
    favorite_records = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    favorites = []
    for fav in favorite_records.items:
        if fav.target_type == 'recipe':
            item = Recipe.query.get(fav.target_id)
        else:
            item = Post.query.get(fav.target_id)
        if item:
            favorites.append(item)
    return render_template('user/favorites.html', favorites=favorites, pagination=favorite_records)

@bp.route('/favorite/<string:target_type>/<int:target_id>')
@login_required
def favorite(target_type, target_id):
    print(f"收藏请求: target_type={target_type}, target_id={target_id}, user_id={current_user.id}")
    
    # 检查目标类型是否有效
    if target_type not in ['recipe', 'post']:
        print(f"无效的目标类型: {target_type}")
        return jsonify({'success': False, 'message': '无效的目标类型'})
    
    # 检查目标是否存在
    if target_type == 'recipe':
        target = Recipe.query.get(target_id)
        if target:
            print(f"找到菜谱: {target.title}")
        else:
            print(f"菜谱不存在: {target_id}")
    else:
        target = Post.query.get(target_id)
        if target:
            print(f"找到帖子: {target.title}")
        else:
            print(f"帖子不存在: {target_id}")
    
    if not target:
        return jsonify({'success': False, 'message': '目标不存在'})
    
    # 检查是否已经收藏
    existing_favorite = Favorite.query.filter_by(user_id=current_user.id, target_type=target_type, target_id=target_id).first()
    print(f"现有收藏: {existing_favorite}")
    
    favorited = False
    
    if existing_favorite:
        # 已收藏，取消收藏
        print(f"取消收藏: {target_type} {target_id}")
        db.session.delete(existing_favorite)
    else:
        # 未收藏，添加收藏
        print(f"添加收藏: {target_type} {target_id}")
        new_favorite = Favorite(user_id=current_user.id, target_type=target_type, target_id=target_id)
        db.session.add(new_favorite)
        favorited = True
    
    # 提交事务
    try:
        db.session.commit()
        print(f"事务提交成功，favorited={favorited}")
    except Exception as e:
        print(f"事务提交失败: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': '操作失败'})
    
    # 再次检查收藏状态
    check_favorite = Favorite.query.filter_by(user_id=current_user.id, target_type=target_type, target_id=target_id).first()
    print(f"操作后收藏状态: {check_favorite}")
    
    return jsonify({'success': True, 'favorited': favorited})

@bp.route('/settings')
@login_required
def settings():
    return render_template('user/settings.html')
