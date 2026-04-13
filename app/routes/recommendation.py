from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Recipe, Ingredient, UserIngredient, RecipeView
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func
import json
import os

# 创建蓝图
bp = Blueprint('recommendation', __name__)

@bp.route('/')
@login_required
def index():
    # 尝试加载保存的推荐结果
    user_recommendations = None
    try:
        # 构建保存文件路径
        save_dir = os.path.join(os.getcwd(), 'recommender_data', 'user_recommendations')
        os.makedirs(save_dir, exist_ok=True)
        save_file = os.path.join(save_dir, f'{current_user.id}.json')
        
        # 检查文件是否存在
        if os.path.exists(save_file):
            with open(save_file, 'r', encoding='utf-8') as f:
                user_recommendations = json.load(f)
    except Exception as e:
        print(f'加载保存的推荐结果失败: {e}')
    
    # 传递推荐结果到模板
    return render_template('recommendation/index.html', user_recommendations=user_recommendations)

@bp.route('/api/personalized')
@login_required
def api_personalized():
    # 获取用户食材
    user_ingredients = UserIngredient.query.filter_by(user_id=current_user.id).all()
    user_ingredient_names = [ui.ingredient.name for ui in user_ingredients]
    
    # 推荐菜谱
    recommended_recipes = []
    
    # 优化：使用join查询减少数据库访问
    from sqlalchemy import func
    
    # 先获取所有菜谱及其食材
    all_recipes = Recipe.query.all()
    
    for recipe in all_recipes:
        # 优化：使用缓存的食材列表，避免重复查询
        recipe_ingredients = [ri.ingredient.name for ri in recipe.ingredients]
        # 计算匹配度
        match_count = len(set(user_ingredient_names) & set(recipe_ingredients))
        if match_count > 0:
            recommended_recipes.append({
                'id': recipe.id,
                'title': recipe.title,
                'description': recipe.description,
                'image_url': recipe.image_url,
                'match_count': match_count
            })
    
    # 按匹配度排序
    recommended_recipes.sort(key=lambda x: x['match_count'], reverse=True)
    
    # 限制返回结果数量
    result = recommended_recipes[:6]
    
    # 保存推荐结果
    try:
        # 构建保存文件路径
        save_dir = os.path.join(os.getcwd(), 'recommender_data', 'user_recommendations')
        os.makedirs(save_dir, exist_ok=True)
        save_file = os.path.join(save_dir, f'{current_user.id}.json')
        
        # 保存结果到文件
        with open(save_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f'推荐结果已保存到: {save_file}')
    except Exception as e:
        print(f'保存推荐结果失败: {e}')
    
    return jsonify(result)

@bp.route('/api/recommend')
def api_recommend():
    # 获取用户食材
    user_ingredient_names = request.args.getlist('ingredients')
    
    # 推荐菜谱
    recommended_recipes = []
    all_recipes = Recipe.query.all()
    
    for recipe in all_recipes:
        recipe_ingredients = [ri.ingredient.name for ri in recipe.ingredients]
        # 计算匹配度
        match_count = len(set(user_ingredient_names) & set(recipe_ingredients))
        if match_count > 0:
            recommended_recipes.append({
                'id': recipe.id,
                'title': recipe.title,
                'description': recipe.description,
                'image_url': recipe.image_url,
                'match_count': match_count
            })
    
    # 按匹配度排序
    recommended_recipes.sort(key=lambda x: x['match_count'], reverse=True)
    
    return jsonify(recommended_recipes)

@bp.route('/api/ranking')
def api_ranking():
    try:
        # 获取排行榜类型
        ranking_type = request.args.get('type', 'total')
        
        # 转换为JSON格式
        result_list = []
        
        if ranking_type == 'total':
            # 按总浏览量排序
            recipes = Recipe.query.order_by(Recipe.views.desc()).limit(5).all()
            for recipe in recipes:
                # 计算最近30天的浏览量
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                month_views = db.session.query(func.count(RecipeView.id)).filter(
                    RecipeView.recipe_id == recipe.id,
                    RecipeView.viewed_at >= thirty_days_ago
                ).scalar() or 0
                
                recipe_data = {
                    'id': recipe.id,
                    'title': recipe.title,
                    'description': recipe.description,
                    'image_url': recipe.image_url,
                    'views': recipe.views,
                    'month_views': month_views,
                    'day_views': recipe.day_views
                }
                result_list.append(recipe_data)
        elif ranking_type == 'month':
            # 按最近30天浏览量排序
            # 计算每个菜谱的最近30天浏览量
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            # 使用子查询计算每个菜谱的最近30天浏览量
            monthly_views = db.session.query(
                RecipeView.recipe_id,
                func.count(RecipeView.id).label('monthly_count')
            ).filter(
                RecipeView.viewed_at >= thirty_days_ago
            ).group_by(
                RecipeView.recipe_id
            ).subquery()
            
            # 按最近30天浏览量排序
            recipes = db.session.query(
                Recipe,
                monthly_views.c.monthly_count
            ).outerjoin(
                monthly_views, Recipe.id == monthly_views.c.recipe_id
            ).order_by(
                (monthly_views.c.monthly_count or 0).desc()
            ).limit(5).all()
            
            for recipe, month_views in recipes:
                recipe_data = {
                    'id': recipe.id,
                    'title': recipe.title,
                    'description': recipe.description,
                    'image_url': recipe.image_url,
                    'views': recipe.views,
                    'month_views': month_views or 0,
                    'day_views': recipe.day_views
                }
                result_list.append(recipe_data)
        elif ranking_type == 'day':
            # 按日浏览量排序
            recipes = Recipe.query.order_by(Recipe.day_views.desc()).limit(5).all()
            for recipe in recipes:
                # 计算最近30天的浏览量
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                month_views = db.session.query(func.count(RecipeView.id)).filter(
                    RecipeView.recipe_id == recipe.id,
                    RecipeView.viewed_at >= thirty_days_ago
                ).scalar() or 0
                
                recipe_data = {
                    'id': recipe.id,
                    'title': recipe.title,
                    'description': recipe.description,
                    'image_url': recipe.image_url,
                    'views': recipe.views,
                    'month_views': month_views,
                    'day_views': recipe.day_views
                }
                result_list.append(recipe_data)
        else:
            # 默认按总浏览量排序
            recipes = Recipe.query.order_by(Recipe.views.desc()).limit(5).all()
            for recipe in recipes:
                # 计算最近30天的浏览量
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                month_views = db.session.query(func.count(RecipeView.id)).filter(
                    RecipeView.recipe_id == recipe.id,
                    RecipeView.viewed_at >= thirty_days_ago
                ).scalar() or 0
                
                recipe_data = {
                    'id': recipe.id,
                    'title': recipe.title,
                    'description': recipe.description,
                    'image_url': recipe.image_url,
                    'views': recipe.views,
                    'month_views': month_views,
                    'day_views': recipe.day_views
                }
                result_list.append(recipe_data)
        
        return jsonify(result_list)
    except Exception as e:
        print(f'API错误: {e}')
        import traceback
        traceback.print_exc()
        return jsonify([]), 500
