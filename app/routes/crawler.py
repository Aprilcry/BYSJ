from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app import app, db
from app.models import Recipe
import os
import sys
import subprocess
import json
import tempfile
from datetime import datetime

# 创建蓝图
bp = Blueprint('crawler', __name__)

# 管理员权限装饰器
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('main.index'))
        return func(*args, **kwargs)
    return wrapper

@bp.route('/')
@login_required
@admin_required
def index():
    """爬虫功能首页"""
    return render_template('crawler/index.html')

@bp.route('/food_images', methods=['GET', 'POST'])
def food_images():
    """爬取食材图片"""
    if request.method == 'POST':
        foods = request.form.get('foods', '').strip()
        if not foods:
            return jsonify({'error': '请输入食材名称'})
        
        # 分割食材列表
        food_list = [food.strip() for food in foods.split(',') if food.strip()]
        
        # 运行爬虫脚本
        script_path = os.path.join(app.root_path, '..', 'crawler', 'crawl_food_images.py')
        
        # 创建临时文件存储食材列表
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
        temp_file.write(f"food_list = {food_list}\n")
        temp_file.close()
        
        # 替换爬虫脚本中的food_list
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换food_list部分
        import re
        new_content = re.sub(r'food_list = \[.*?\]', f'food_list = {food_list}', content, flags=re.DOTALL)
        
        # 写回修改后的内容
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 运行爬虫
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, 
                              cwd=os.path.dirname(script_path))
        
        # 恢复原始food_list
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 删除临时文件
        os.unlink(temp_file.name)
        
        return jsonify({
            'success': True,
            'output': result.stdout,
            'error': result.stderr
        })
    return render_template('crawler/food_images.html')

@bp.route('/recipe_covers')
def recipe_covers():
    """爬取菜谱封面"""
    return render_template('crawler/recipe_covers.html')

@bp.route('/api/recipes/search')
def search_recipes():
    """搜索菜谱"""
    keyword = request.args.get('keyword', '').strip()
    recipes = []
    if keyword:
        recipes = Recipe.query.filter(Recipe.title.contains(keyword)).limit(10).all()
    else:
        recipes = Recipe.query.limit(10).all()
    
    return jsonify([{
        'id': recipe.id,
        'title': recipe.title,
        'current_image': recipe.image_url
    } for recipe in recipes])

@bp.route('/api/recipe_images')
def get_recipe_images():
    """获取菜谱图片"""
    recipe_id = request.args.get('recipe_id', type=int)
    offset = request.args.get('offset', 0, type=int)
    
    if not recipe_id:
        return jsonify({'error': '缺少菜谱ID'})
    
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        return jsonify({'error': '菜谱不存在'})
    
    # 运行批量添加菜谱封面图片脚本
    script_path = os.path.join(app.root_path, '..', 'crawler', '批量添加菜谱封面图片.py')
    
    # 临时修改脚本，只处理指定菜谱
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换查询部分
    import re
    new_content = re.sub(r'cursor.execute\("SELECT id, title, image_url FROM recipe WHERE.*?"\)', 
                        f"cursor.execute(\"SELECT id, title, image_url FROM recipe WHERE id = {recipe_id}\")", 
                        content)
    
    # 写回修改后的内容
    temp_script = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    temp_script.write(new_content)
    temp_script.close()
    
    # 运行脚本
    result = subprocess.run([sys.executable, temp_script.name], 
                          capture_output=True, text=True, 
                          cwd=os.path.dirname(script_path))
    
    # 删除临时脚本
    os.unlink(temp_script.name)
    
    # 重新获取菜谱信息
    recipe = Recipe.query.get(recipe_id)
    
    return jsonify({
        'recipe': {
            'id': recipe.id,
            'title': recipe.title,
            'current_image': recipe.image_url
        },
        'output': result.stdout,
        'error': result.stderr
    })

@bp.route('/video_crawler')
def video_crawler():
    """菜谱视频爬取"""
    return render_template('crawler/video_crawler.html')

@bp.route('/api/videos/search')
def search_videos():
    """搜索视频"""
    recipe_id = request.args.get('recipe_id', type=int)
    
    if not recipe_id:
        return jsonify({'error': '缺少菜谱ID'})
    
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        return jsonify({'error': '菜谱不存在'})
    
    # 运行视频爬虫脚本
    script_path = os.path.join(app.root_path, '..', 'crawler', 'video_crawler.py')
    
    # 临时修改脚本，只处理指定菜谱
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换获取菜谱部分
    import re
    new_content = re.sub(r'recipes = Recipe.query.all\(\)', 
                        f'recipes = [Recipe.query.get({recipe_id})] if Recipe.query.get({recipe_id}) else []', 
                        content)
    
    # 写回修改后的内容
    temp_script = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    temp_script.write(new_content)
    temp_script.close()
    
    # 运行脚本
    result = subprocess.run([sys.executable, temp_script.name], 
                          capture_output=True, text=True, 
                          cwd=os.path.dirname(script_path))
    
    # 删除临时脚本
    os.unlink(temp_script.name)
    
    # 重新获取菜谱信息
    recipe = Recipe.query.get(recipe_id)
    
    return jsonify({
        'recipe': {
            'id': recipe.id,
            'title': recipe.title,
            'video_url': recipe.video_url
        },
        'output': result.stdout,
        'error': result.stderr
    })

@bp.route('/douguo_crawler')
def douguo_crawler():
    """豆果菜谱爬取"""
    return render_template('crawler/douguo_crawler.html')

@bp.route('/api/douguo/start')
def start_douguo_crawler():
    """启动豆果爬虫"""
    # 运行豆果爬虫脚本
    script_path = os.path.join(app.root_path, '..', 'caipu_crawler', 'douguo.py')
    
    # 运行脚本
    result = subprocess.run([sys.executable, script_path], 
                          capture_output=True, text=True, 
                          cwd=os.path.dirname(script_path))
    
    # 检查是否生成了CSV文件
    csv_path = os.path.join(os.path.dirname(script_path), 'douguo_jingxuan_caipu.csv')
    csv_exists = os.path.exists(csv_path)
    
    return jsonify({
        'success': True,
        'output': result.stdout,
        'error': result.stderr,
        'csv_exists': csv_exists,
        'csv_path': csv_path if csv_exists else None
    })

@bp.route('/api/recipe/update_image', methods=['POST'])
def update_recipe_image():
    """更新菜谱封面"""
    recipe_id = request.json.get('recipe_id')
    image_url = request.json.get('image_url')
    
    if not recipe_id or not image_url:
        return jsonify({'error': '缺少必要参数'})
    
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        return jsonify({'error': '菜谱不存在'})
    
    recipe.image_url = image_url
    db.session.commit()
    
    return jsonify({'success': True, 'message': '封面更新成功'})

@bp.route('/api/recipe/update_video', methods=['POST'])
def update_recipe_video():
    """更新菜谱视频"""
    recipe_id = request.json.get('recipe_id')
    video_url = request.json.get('video_url')
    
    if not recipe_id or not video_url:
        return jsonify({'error': '缺少必要参数'})
    
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        return jsonify({'error': '菜谱不存在'})
    
    recipe.video_url = video_url
    db.session.commit()
    
    return jsonify({'success': True, 'message': '视频更新成功'})
