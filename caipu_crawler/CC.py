import requests
import csv
import os
import time

def main():
    # 配置保存路径
    save_dir = r"D:\BYSJ\caipu_crawler"
    os.makedirs(save_dir, exist_ok=True)
    csv_path = os.path.join(save_dir, "caipu_data.csv")

    # 初始化CSV文件并写入表头
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["caipu.title", "caipu.zuofa", "category_2.title", "category_1.title"])

    # 基础URL模板
    base_url = "https://songer.datasn.com/data/api/v1/u_4db7936df78dfe468fc2/caipu_daquan_1/main/list/{}/?app=json"
    page = 1
    max_pages = 10  # 示例：限制爬取前10页（可根据需要调整或删除此限制）

    while page <= max_pages:
        # 构造当前页URL
        if page == 1:
            url = "https://songer.datasn.com/data/api/v1/u_4db7936df78dfe468fc2/caipu_daquan_1/main/list/?app=json"
        else:
            url = base_url.format(page)

        try:
            # 发送请求
            print(f"\n正在请求第 {page} 页数据...")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"第 {page} 页请求失败: {str(e)}")
            break

        # 解析数据
        rows = data.get("output", {}).get("rows", {})
        if not rows:
            print(f"第 {page} 页无数据，停止爬取")
            break

        # 遍历当前页的菜谱
        for key in rows:
            recipe = rows[key]
            title = recipe.get("caipu.title", "")
            zuofa = recipe.get("caipu.zuofa", "")

            # 提取分类信息
            cat2_title = ""
            cat1_title = ""
            category_data = recipe.get("caipu.category_2_x_caipu_id", {})
            if category_data:
                first_cat_key = next(iter(category_data.keys()), None)
                if first_cat_key:
                    first_cat = category_data[first_cat_key]
                    cat2_title = first_cat.get("category_2.title", "")
                    cat1_title = first_cat.get("category_1.title", "")

            # 输出爬取过程
            print(f"正在爬取：{title}，zuofa...")

            # 写入CSV
            try:
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow([title, zuofa, cat2_title, cat1_title])
                print("爬取成功")
            except Exception as e:
                print(f"爬取失败: {str(e)}")

            # 轻微延迟避免请求过快
            time.sleep(0.1)

        # 检查是否有下一页（根据API返回的next链接）
        next_link = data.get("links", {}).get("next", {}).get("href")
        if not next_link:
            print("\n已到达最后一页，爬取完成")
            break

        page += 1

    print(f"\n所有数据已保存至: {csv_path}")

if __name__ == "__main__":
    main()