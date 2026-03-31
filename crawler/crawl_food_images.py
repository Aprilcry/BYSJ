import os
import requests
from bs4 import BeautifulSoup
import time
import random
from PIL import Image
from io import BytesIO

# 常见食材列表
food_list = [
    # '西红柿', '鸡蛋', '土豆', '胡萝卜', '洋葱',
    # '白菜', '黄瓜', '茄子', '辣椒',
    # '虾', '豆腐', '米饭', '面条',
    # '香菜', '青椒', '韭菜',
    # '冬瓜', '南瓜','莲藕', '豆角', '黄豆芽',
    # '香菇', '木耳', '豆腐', '腐竹','螃蟹',
    # '生羊肉','生鸭肉','生牛肉','生鸡肉','鲫鱼'
]

# 存储路径
# 获取脚本所在目录的绝对路径
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, 'origin')
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
print(f"图片存储目录: {output_dir}")

#  headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def download_image(url, save_path):
    max_retries = 3
    target_size = (640, 640)
    
    for retry in range(max_retries):
        try:
            print(f"    发送图片请求: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                print(f"    图片下载成功，开始调整大小")
                
                # 读取图片内容
                image_data = BytesIO(response.content)
                
                # 打开图片
                img = Image.open(image_data)
                print(f"    原始图片大小: {img.size}")
                
                # 调整图片大小
                resized_img = img.resize(target_size, Image.LANCZOS)
                print(f"    调整后图片大小: {resized_img.size}")
                
                # 保存调整后的图片
                resized_img.save(save_path, 'JPEG', quality=90)
                print(f"    图片保存成功: {save_path}")
                
                return True
            else:
                print(f"    下载失败，状态码: {response.status_code}, 重试 {retry+1}/{max_retries}")
                time.sleep(1)
        except Exception as e:
            print(f"    下载失败: {e}, 重试 {retry+1}/{max_retries}")
            time.sleep(1)
    return False

def crawl_bing_images(keyword, max_count=20):
    count = 0
    offset = 0
    max_retries = 3
    
    # 创建食材对应的文件夹
    food_dir = os.path.join(output_dir, keyword)
    if not os.path.exists(food_dir):
        os.makedirs(food_dir)
        print(f"创建食材文件夹: {food_dir}")
    
    while count < max_count:
        # 必应图片搜索URL
        url = f"https://www.bing.com/images/search?q={keyword}&first={offset}"
        print(f"\n开始爬取页面: {url}")
        
        for retry in range(max_retries):
            print(f"  尝试第 {retry+1}/{max_retries} 次请求")
            try:
                print(f"  发送HTTP请求...")
                start_time = time.time()
                response = requests.get(url, headers=headers, timeout=15)
                end_time = time.time()
                print(f"  请求完成，耗时: {end_time - start_time:.2f}秒")
                
                if response.status_code != 200:
                    print(f"  请求失败: {response.status_code}, 重试 {retry+1}/{max_retries}")
                    time.sleep(random.uniform(2, 3))
                    continue
                
                print(f"  开始解析HTML...")
                start_time = time.time()
                soup = BeautifulSoup(response.text, 'html.parser')
                end_time = time.time()
                print(f"  HTML解析完成，耗时: {end_time - start_time:.2f}秒")
                
                # 查找图片标签
                print(f"  查找图片标签...")
                # 尝试查找多种可能的图片标签
                # 1. 首先查找 class 为 'mimg' 的图片
                img_tags = soup.find_all('img', class_='mimg')
                print(f"  找到 {len(img_tags)} 个 class='mimg' 的图片标签")
                
                # 2. 如果找到的图片太少，尝试查找所有包含 'src' 属性的 img 标签
                if len(img_tags) < 50:
                    all_img_tags = soup.find_all('img', src=True)
                    # 过滤掉 base64 编码的图片和小图标
                    filtered_img_tags = [img for img in all_img_tags if img['src'].startswith('http') and not img['src'].startswith('data:image')]
                    print(f"  找到 {len(filtered_img_tags)} 个包含有效 src 的图片标签")
                    # 如果找到更多图片，使用这些
                    if len(filtered_img_tags) > len(img_tags):
                        img_tags = filtered_img_tags
                        print(f"  使用包含有效 src 的图片标签")
                
                print(f"  最终找到 {len(img_tags)} 个图片标签")
                
                if not img_tags:
                    print(f"  没有找到{keyword}的图片")
                    break
                
                print(f"  开始处理图片...")
                valid_images_found = 0
                
                for i, img in enumerate(img_tags):
                    if count >= max_count:
                        print(f"  已达到最大图片数量 {max_count}，停止处理")
                        break
                    
                    print(f"  处理第 {i+1}/{len(img_tags)} 个图片")
                    
                    # 尝试从多个属性获取图片URL
                    img_url = img.get('src') or img.get('data-src') or img.get('data-original')
                    print(f"  图片URL: {img_url}")
                    
                    if img_url and img_url.startswith('http') and not img_url.startswith('data:image'):
                        # 生成文件名
                        filename = f"{keyword}_{count+1}.jpg"
                        save_path = os.path.join(food_dir, filename)
                        print(f"  准备下载: {filename} 到 {food_dir}")
                        
                        # 下载图片
                        if download_image(img_url, save_path):
                            count += 1
                            valid_images_found += 1
                            print(f"  下载成功: {filename}")
                            # 随机延迟，避免被封
                            delay_time = random.uniform(1, 2)
                            print(f"  下载后延迟: {delay_time:.2f}秒")
                            time.sleep(delay_time)  
                        else:
                            print(f"  下载失败: {img_url}")
                    else:
                        print(f"  无效的图片URL: {img_url}")
                
                print(f"  页面处理完成，成功下载 {valid_images_found} 张有效图片")
                
                # 如果当前页面没有找到有效图片，停止爬取
                if valid_images_found == 0:
                    print(f"  当前页面没有找到有效图片，停止爬取 {keyword}")
                    break
                
                break  # 成功获取页面后跳出重试循环
            except Exception as e:
                print(f"  爬取失败: {e}")
                import traceback
                traceback.print_exc()
        
        offset += 35
        # 每页之间延迟
        delay_time = random.uniform(2, 3)
        print(f"  页面间延迟: {delay_time:.2f}秒")
        time.sleep(delay_time)
    
    return count

def main():
    total_count = 0
    images_per_food = 20
    
    print("开始爬取食材图片...")
    
    for food in food_list:
        print(f"\n爬取 {food} 的图片...")
        count = crawl_bing_images(food, images_per_food)
        total_count += count
        print(f"{food} 已下载 {count} 张图片")
    
    print(f"\n爬取完成！总共下载了 {total_count} 张食材图片")

if __name__ == "__main__":
    main()