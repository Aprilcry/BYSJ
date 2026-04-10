import requests
from bs4 import BeautifulSoup
import json
import os
import sys

# 添加上级目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from app.models import Recipe

# 创建视频存储目录
VIDEO_DIR = os.path.join(os.getcwd(), 'videos')
if not os.path.exists(VIDEO_DIR):
    os.makedirs(VIDEO_DIR)

# B站搜索API
def search_bilibili(keyword, page=1, video_index=0):
    # 构建更精确的搜索关键词
    search_keyword = f"{keyword} 做法 教程 菜谱"
    # 添加分页参数，每页36个视频
    url = f"https://search.bilibili.com/all?keyword={requests.utils.quote(search_keyword)}&page={page}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    print(f"搜索关键词: {search_keyword}")
    print(f"搜索URL: {url}")
    print(f"当前页码: {page}")
    print(f"视频索引: {video_index}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"响应状态码: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        print(f"页面标题: {soup.title.text if soup.title else '无标题'}")
        
        # 查找视频列表（尝试不同的选择器）
        video_items = soup.select('.bili-video-card__wrap')
        print(f"找到 .bili-video-card__wrap 数量: {len(video_items)}")
        if not video_items:
            video_items = soup.select('.video-card')
            print(f"找到 .video-card 数量: {len(video_items)}")
        if not video_items:
            video_items = soup.select('.video-item')
            print(f"找到 .video-item 数量: {len(video_items)}")
        
        if not video_items:
            print(f"未找到视频列表: {soup.title.text if soup.title else '无标题'}")
            return None
        
        # 确保索引不超出范围
        if video_index >= len(video_items):
            print(f"视频索引 {video_index} 超出范围，使用最后一个视频")
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
        # 清理标题
        title = title.replace('\n', '').replace('\t', '').strip()
        print(f"选择视频 {video_index+1}: {title} - {link}")
        
        relevant_video = {'title': title, 'url': link}
        
        # 构建完整的视频URL
        if not relevant_video['url'].startswith('https:'):
            relevant_video['url'] = 'https:' + relevant_video['url']
        
        print(f"最终选择视频: {relevant_video['title']} - {relevant_video['url']}")
        return relevant_video
    except Exception as e:
        print(f"搜索B站视频失败: {e}")
        import traceback
        traceback.print_exc()
        return None

# 爬取视频并更新数据库
def crawl_videos(recipe_id=None, page=1, video_index=0):
    with app.app_context():
        # 获取指定菜谱或所有菜谱
        if recipe_id:
            recipes = [Recipe.query.get(recipe_id)] if Recipe.query.get(recipe_id) else []
            print(f"开始为指定菜谱爬取视频...")
        else:
            recipes = Recipe.query.all()
            print(f"开始为 {len(recipes)} 个菜谱爬取视频...")
        
        for recipe in recipes:
            print(f"正在为 {recipe.title} 爬取视频...")
            
            # 搜索视频，传递page和video_index参数
            video_info = search_bilibili(recipe.title, page, video_index)
            
            if video_info:
                print(f"找到视频: {video_info['title']} - {video_info['url']}")
                
                # 更新数据库
                recipe.video_url = video_info['url']
                db.session.commit()
                print(f"已更新 {recipe.title} 的视频URL")
            else:
                print(f"未找到 {recipe.title} 的视频")
        
        print("视频爬取完成！")

if __name__ == "__main__":
    crawl_videos()
