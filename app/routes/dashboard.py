from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import User, Post, Recipe, PostLike, PostView, RecipeView, Favorite, UserActivity, SearchRecord, Comment
from app import db
from datetime import datetime, timedelta
import json

dashboard = Blueprint('dashboard', __name__)

@dashboard.route('/dashboard/data')
def get_dashboard_data():
    # 检查用户是否为管理员
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # 获取数据
    data = {
        'recipe_taste': get_recipe_taste_data(),
        'content_views': get_content_views_data(),
        'views_trend': get_views_trend_data(),
        'content_distribution': get_content_distribution_data(),
        'user_growth': get_user_growth_data(),
        'search_keywords': get_search_keywords_data(),
        'engagement_rate': get_engagement_rate_data(),
        'cooking_time_analysis': get_cooking_time_analysis_data(),
        'stats': get_stats_data()
    }
    
    return jsonify(data)

@dashboard.route('/dashboard')
def index():
    # 检查用户是否为管理员
    if not current_user.is_authenticated or not current_user.is_admin:
        return render_template('403.html'), 403
    
    return render_template('dashboard/index.html')

def get_stats_data():
    # 获取统计数据
    user_count = User.query.count()
    recipe_count = Recipe.query.count()
    post_count = Post.query.count()
    
    # 获取浏览量
    post_views = db.session.query(db.func.sum(Post.views)).scalar() or 0
    recipe_views = db.session.query(db.func.sum(Recipe.views)).scalar() or 0
    total_views = post_views + recipe_views
    
    return {
        'user_count': user_count,
        'recipe_count': recipe_count,
        'post_count': post_count,
        'total_views': total_views
    }

def get_recipe_taste_data():
    # 获取菜谱口味分布
    tastes = db.session.query(
        Recipe.taste,
        db.func.count(Recipe.id).label('count')
    ).group_by(Recipe.taste).all()
    
    return {
        'categories': [taste.taste for taste in tastes],
        'data': [taste.count for taste in tastes]
    }

def get_content_views_data():
    # 获取内容浏览量
    post_views = db.session.query(db.func.sum(Post.views)).scalar() or 0
    recipe_views = db.session.query(db.func.sum(Recipe.views)).scalar() or 0
    
    return {
        'post_views': post_views,
        'recipe_views': recipe_views
    }

def get_views_trend_data():
    # 获取近30天的浏览量趋势
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # 获取每天的帖子浏览量
    post_views = db.session.query(
        db.func.date(PostView.viewed_at).label('date'),
        db.func.count(PostView.id).label('count')
    ).filter(
        PostView.viewed_at >= start_date,
        PostView.viewed_at <= end_date
    ).group_by(db.func.date(PostView.viewed_at)).all()
    
    # 获取每天的菜谱浏览量
    recipe_views = db.session.query(
        db.func.date(RecipeView.viewed_at).label('date'),
        db.func.count(RecipeView.id).label('count')
    ).filter(
        RecipeView.viewed_at >= start_date,
        RecipeView.viewed_at <= end_date
    ).group_by(db.func.date(RecipeView.viewed_at)).all()
    
    # 生成日期序列
    date_range = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(31)]
    
    # 构建日期到浏览量的映射
    post_views_map = {view.date.strftime('%Y-%m-%d'): view.count for view in post_views}
    recipe_views_map = {view.date.strftime('%Y-%m-%d'): view.count for view in recipe_views}
    
    return {
        'dates': date_range,
        'post_views': [post_views_map.get(date, 0) for date in date_range],
        'recipe_views': [recipe_views_map.get(date, 0) for date in date_range]
    }

def get_content_distribution_data():
    # 获取内容分类分布
    recipe_categories = db.session.query(
        Recipe.category,
        db.func.count(Recipe.id).label('count')
    ).group_by(Recipe.category).all()
    
    return {
        'categories': [cat.category for cat in recipe_categories],
        'data': [cat.count for cat in recipe_categories]
    }

def get_user_growth_data():
    # 获取用户增长趋势
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    users = db.session.query(
        db.func.date(User.created_at).label('date'),
        db.func.count(User.id).label('count')
    ).filter(
        User.created_at >= start_date,
        User.created_at <= end_date
    ).group_by(db.func.date(User.created_at)).all()
    
    # 生成日期序列
    date_range = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(31)]
    date_to_count = {user.date.strftime('%Y-%m-%d'): user.count for user in users}
    
    return {
        'dates': date_range,
        'data': [date_to_count.get(date, 0) for date in date_range]
    }

def get_search_keywords_data():
    # 获取热门搜索关键词
    keywords = db.session.query(
        SearchRecord.keyword,
        SearchRecord.count
    ).order_by(SearchRecord.count.desc()).limit(10).all()
    
    return {
        'keywords': [kw.keyword for kw in keywords],
        'counts': [kw.count for kw in keywords]
    }

def get_engagement_rate_data():
    # 获取内容互动率
    posts = Post.query.all()
    engagement_data = []
    
    for post in posts:
        if post.views > 0:
            # 计算评论数
            comment_count = Comment.query.filter_by(post_id=post.id).count()
            engagement_rate = (post.likes + comment_count) / post.views * 100
            engagement_data.append({
                'title': post.title[:20] + '...' if len(post.title) > 20 else post.title,
                'engagement_rate': round(engagement_rate, 2)
            })
    
    # 按互动率排序，取前10个
    engagement_data.sort(key=lambda x: x['engagement_rate'], reverse=True)
    top_engagement = engagement_data[:10]
    
    return {
        'titles': [item['title'] for item in top_engagement],
        'rates': [item['engagement_rate'] for item in top_engagement]
    }

def get_cooking_time_analysis_data():
    # 获取烹饪时间分析
    recipes = Recipe.query.all()
    cooking_times = []
    
    for recipe in recipes:
        total_time = (recipe.prep_time or 0) + (recipe.cook_time or 0)
        cooking_times.append({
            'title': recipe.title[:20] + '...' if len(recipe.title) > 20 else recipe.title,
            'prep_time': recipe.prep_time or 0,
            'cook_time': recipe.cook_time or 0,
            'total_time': total_time
        })
    
    # 按总时间排序，取前10个
    cooking_times.sort(key=lambda x: x['total_time'], reverse=True)
    top_cooking = cooking_times[:10]
    
    return {
        'titles': [item['title'] for item in top_cooking],
        'prep_times': [item['prep_time'] for item in top_cooking],
        'cook_times': [item['cook_time'] for item in top_cooking]
    }