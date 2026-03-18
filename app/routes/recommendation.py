from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Recipe, Ingredient, UserIngredient
from app import db

# 创建蓝图
bp = Blueprint('recommendation', __name__)

@bp.route('/')
@login_required
def index():
    # 获取用户食材
    user_ingredients = UserIngredient.query.filter_by(user_id=current_user.id).all()
    user_ingredient_names = [ui.ingredient.name for ui in user_ingredients]
    
    # 推荐菜谱
    recommended_recipes = []
    all_recipes = Recipe.query.all()
    
    for recipe in all_recipes:
        recipe_ingredients = [ri.ingredient.name for ri in recipe.ingredients]
        # 计算匹配度
        match_count = len(set(user_ingredient_names) & set(recipe_ingredients))
        if match_count > 0:
            recommended_recipes.append((recipe, match_count))
    
    # 按匹配度排序
    recommended_recipes.sort(key=lambda x: x[1], reverse=True)
    
    return render_template('recommendation/index.html', recommended_recipes=recommended_recipes)

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
        
        # 使用ORM查询
        # 按不同类型排序
        if ranking_type == 'total':
            # 按总浏览量排序
            recipes = Recipe.query.order_by(Recipe.views.desc()).limit(5).all()
        elif ranking_type == 'month':
            # 按月浏览量排序
            recipes = Recipe.query.order_by(Recipe.month_views.desc()).limit(5).all()
        elif ranking_type == 'day':
            # 按日浏览量排序
            recipes = Recipe.query.order_by(Recipe.day_views.desc()).limit(5).all()
        else:
            # 默认按总浏览量排序
            recipes = Recipe.query.order_by(Recipe.views.desc()).limit(5).all()
        
        # 转换为JSON格式
        result_list = []
        for recipe in recipes:
            # 构建响应数据
            recipe_data = {
                'id': recipe.id,
                'title': recipe.title,
                'description': recipe.description,
                'image_url': recipe.image_url,
                'views': recipe.views,
                'month_views': recipe.month_views,
                'day_views': recipe.day_views
            }
            result_list.append(recipe_data)
        
        return jsonify(result_list)
    except Exception as e:
        print(f'API错误: {e}')
        import traceback
        traceback.print_exc()
        return jsonify([]), 500
