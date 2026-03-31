import requests
import mysql.connector
import urllib.parse

# 数据库连接信息
DB_CONFIG = {
    'host': 'mysql7.sqlpub.com',
    'port': 3312,
    'user': 'aocjor',
    'password': 'XxzAgt8llTP8dqDV',
    'database': 'ljb_bysj'
}

# 图片搜索API（使用Bing图片搜索）
def search_recipe_image(recipe_name):
    """搜索菜谱封面图片"""
    try:
        # 使用Bing图片搜索
        query = urllib.parse.quote(f"{recipe_name} 菜谱 封面")
        url = f"https://bing.com/images/search?q={query}&first=1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # 简单解析HTML获取图片
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找图片标签，优先查找有data-src属性的图片
        img_tags = soup.find_all('img')
        valid_images = []
        
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
                    valid_images.append(img_url)
        
        # 如果找到合适的图片，返回第一个
        if valid_images:
            return valid_images[0]
        
        # 如果没有找到合适的图片，尝试使用Trae API生成图片
        try:
            prompt = urllib.parse.quote(f"{recipe_name} 美食 菜谱 封面")
            return f"https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt={prompt}&image_size=landscape_16_9"
        except Exception as e:
            print(f"生成图片失败: {e}")
            # 最后返回一个更合适的默认图片
            return f"https://via.placeholder.com/600x400?text={urllib.parse.quote(recipe_name)}"
    except Exception as e:
        print(f"搜索图片失败: {e}")
        # 出错时尝试使用Trae API
        try:
            prompt = urllib.parse.quote(f"{recipe_name} 美食 菜谱 封面")
            return f"https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt={prompt}&image_size=landscape_16_9"
        except Exception as e2:
            print(f"生成图片失败: {e2}")
            # 最后返回默认图片
            return f"https://via.placeholder.com/600x400?text={urllib.parse.quote(recipe_name)}"

print("批量添加菜谱封面图片脚本")
print("=" * 50)

# 连接数据库
try:
    print("正在连接数据库...")
    cnx = mysql.connector.connect(**DB_CONFIG)
    cursor = cnx.cursor()
    print("数据库连接成功！")
    
    # 获取需要更新封面的菜谱：
    # 1. image_url为空或为空字符串
    # 2. image_url使用了placeholder默认图片
    # 3. image_url使用了Bing占位图片
    cursor.execute("SELECT id, title, image_url FROM recipe WHERE image_url IS NULL OR image_url = '' OR image_url LIKE '%via.placeholder.com%' OR image_url LIKE '%bing.com/rp/%'")
    recipes = cursor.fetchall()
    
    print(f"\n找到 {len(recipes)} 个缺少封面图片的菜谱")
    
    # 为每个菜谱添加封面图片
    updated = 0
    for recipe_id, recipe_title, current_image_url in recipes:
        print(f"\n处理菜谱: {recipe_title}")
        print(f"当前图片URL: {current_image_url if current_image_url else '空'}")
        
        # 搜索图片
        img_url = search_recipe_image(recipe_title)
        
        if img_url:
            print(f"找到图片: {img_url}")
            # 更新数据库
            cursor.execute("UPDATE recipe SET image_url = %s WHERE id = %s", (img_url, recipe_id))
            cnx.commit()
            updated += 1
            print(f"已更新菜谱 {recipe_title} 的封面图片")
        else:
            print(f"未找到菜谱 {recipe_title} 的图片")
    
    print(f"\n处理完成，成功更新 {updated} 个菜谱的封面图片")
    
    # 关闭连接
    cursor.close()
    cnx.close()
    print("数据库连接已关闭")
except Exception as e:
    print(f"数据库操作失败: {e}")
    import traceback
    traceback.print_exc()