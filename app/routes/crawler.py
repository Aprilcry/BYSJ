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
            from flask import abort
            abort(403)  # 403 Forbidden
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
        
        # 运行爬虫，添加超时处理
        try:
            result = subprocess.run([sys.executable, script_path], 
                                  capture_output=True, text=True, 
                                  cwd=os.path.dirname(script_path),
                                  timeout=300)  # 5分钟超时
        except subprocess.TimeoutExpired:
            return jsonify({
                'success': False,
                'error': '爬取超时，请尝试减少食材数量或稍后再试'
            })
        
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
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    recipes = []
    if keyword:
        recipes = Recipe.query.filter(Recipe.title.contains(keyword)).offset((page-1)*per_page).limit(per_page).all()
    else:
        recipes = Recipe.query.offset((page-1)*per_page).limit(per_page).all()
    
    # 获取总数量
    if keyword:
        total = Recipe.query.filter(Recipe.title.contains(keyword)).count()
    else:
        total = Recipe.query.count()
    
    return jsonify({
        'recipes': [{
            'id': recipe.id,
            'title': recipe.title,
            'current_image': recipe.image_url
        } for recipe in recipes],
        'total': total,
        'page': page,
        'per_page': per_page
    })

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
    
    # 直接实现图片搜索逻辑，避免调用脚本
    import requests
    from bs4 import BeautifulSoup
    import urllib.parse
    
    def search_recipe_images(recipe_name, offset=0, count=10):
        """搜索菜谱图片"""
        images = []
        try:
            # 使用Bing图片搜索
            query = urllib.parse.quote(f"{recipe_name} 菜谱 封面")
            # 添加偏移量参数
            url = f"https://bing.com/images/search?q={query}&first={offset+1}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            img_tags = soup.find_all('img')
            
            for img in img_tags:
                # 优先使用data-src属性
                img_url = img.get('data-src') or img.get('src')
                if img_url and 'http' in img_url:
                    # 过滤掉小图标、SVG和占位符
                    if ('thumbnail' not in img_url.lower() and 
                        'icon' not in img_url.lower() and 
                        '.svg' not in img_url.lower() and
                        'bing.com/rp/' not in img_url and
                        'via.placeholder.com' not in img_url):
                        images.append(img_url)
                        if len(images) >= count:
                            break
            
            # 如果没有找到足够的图片，尝试使用Trae API生成图片
            if len(images) < count:
                for i in range(count - len(images)):
                    try:
                        prompt = urllib.parse.quote(f"{recipe_name} 美食 菜谱 封面 {i+1}")
                        images.append(f"https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt={prompt}&image_size=landscape_16_9")
                    except Exception:
                        pass
            
        except Exception as e:
            print(f"搜索图片失败: {e}")
            # 出错时尝试使用Trae API
            try:
                for i in range(count):
                    prompt = urllib.parse.quote(f"{recipe_name} 美食 菜谱 封面 {i+1}")
                    images.append(f"https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt={prompt}&image_size=landscape_16_9")
            except Exception:
                pass
        
        return images
    
    # 搜索图片
    images = search_recipe_images(recipe.title, offset, 10)
    
    return jsonify({
        'recipe': {
            'id': recipe.id,
            'title': recipe.title,
            'current_image': recipe.image_url
        },
        'images': images,
        'offset': offset,
        'total': len(images)
    })

@bp.route('/video_crawler')
def video_crawler():
    """菜谱视频爬取"""
    return render_template('crawler/video_crawler.html')

@bp.route('/api/videos/search')
def search_videos():
    """搜索视频"""
    recipe_id = request.args.get('recipe_id', type=int)
    page = request.args.get('page', 1, type=int)
    video_index = request.args.get('video_index', 0, type=int)
    
    if not recipe_id:
        return jsonify({'error': '缺少菜谱ID'})
    
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        return jsonify({'error': '菜谱不存在'})
    
    # 直接实现视频搜索逻辑，避免模块导入错误
    import requests
    from bs4 import BeautifulSoup
    
    # 构建搜索关键词
    search_keyword = f"{recipe.title} 做法 教程 菜谱"
    url = f"https://search.bilibili.com/all?keyword={requests.utils.quote(search_keyword)}&page={page}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    output = []
    output.append(f"搜索关键词: {search_keyword}")
    output.append(f"搜索URL: {url}")
    output.append(f"当前页码: {page}")
    output.append(f"视频索引: {video_index}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        output.append(f"响应状态码: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        page_title = soup.title.text if soup.title else '无标题'
        output.append(f"页面标题: {page_title}")
        
        # 查找视频列表
        video_items = soup.select('.bili-video-card__wrap')
        output.append(f"找到 .bili-video-card__wrap 数量: {len(video_items)}")
        if not video_items:
            video_items = soup.select('.video-card')
            output.append(f"找到 .video-card 数量: {len(video_items)}")
        if not video_items:
            video_items = soup.select('.video-item')
            output.append(f"找到 .video-item 数量: {len(video_items)}")
        
        if not video_items:
            output.append(f"未找到视频列表: {page_title}")
            return jsonify({
                'recipe': {
                    'id': recipe.id,
                    'title': recipe.title,
                    'video_url': recipe.video_url
                },
                'page': page,
                'video_index': video_index,
                'output': '\n'.join(output),
                'error': '未找到视频列表'
            })
        
        # 确保索引不超出范围
        if video_index >= len(video_items):
            output.append(f"视频索引 {video_index} 超出范围，使用最后一个视频")
            video_index = len(video_items) - 1
        
        # 选择指定索引的视频
        selected_item = video_items[video_index]
        link = selected_item.select_one('a')['href']
        
        # 尝试不同的选择器提取标题
        title_elem = selected_item.select_one('.bili-video-card__info__title')
        if not title_elem:
            title_elem = selected_item.select_one('.video-card__info__title')
        if not title_elem:
            title_elem = selected_item.select_one('.title')
        if not title_elem:
            title_elem = selected_item.select_one('h3')
        if not title_elem:
            title_elem = selected_item.select_one('a')
        title = title_elem.text.strip() if title_elem else '无标题'
        title = title.replace('\n', '').replace('\t', '').strip()
        output.append(f"选择视频 {video_index+1}: {title} - {link}")
        
        # 构建完整的视频URL
        if not link.startswith('https:'):
            link = 'https:' + link
        output.append(f"最终选择视频: {title} - {link}")
        output.append(f"注意：视频URL未更新到数据库，需要点击'使用此视频'按钮才会更新")
        
        return jsonify({
            'recipe': {
                'id': recipe.id,
                'title': recipe.title,
                'video_url': link  # 返回爬取到的视频URL，但不更新数据库
            },
            'page': page,
            'video_index': video_index,
            'output': '\n'.join(output),
            'error': ''
        })
    except Exception as e:
        import traceback
        error_message = f"{e}\n{traceback.format_exc()}"
        output.append(f"搜索B站视频失败: {e}")
        return jsonify({
            'recipe': {
                'id': recipe.id,
                'title': recipe.title,
                'video_url': recipe.video_url
            },
            'page': page,
            'video_index': video_index,
            'output': '\n'.join(output),
            'error': error_message
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
