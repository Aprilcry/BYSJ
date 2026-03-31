import time
import random
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By

# 核心配置
BASE_URL = "https://www.douguo.com/jingxuan/{page}"   # ← 改成模板
START_PAGE = 0          # 起始页码
MAX_EMPTY_PAGES = 3     # 连续几页没有新菜谱就停止
SAVE_DIR = r"D:\BYSJ\caipu_crawler"
CSV_FILE = os.path.join(SAVE_DIR, "douguo_jingxuan_caipu.csv")
DRIVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "msedgedriver.exe")


def init_browser():
    options = webdriver.EdgeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
    )
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-popup-blocking")

    if not os.path.exists(DRIVER_PATH):
        raise FileNotFoundError(f"请把 msedgedriver.exe 放到同目录: {DRIVER_PATH}")

    driver = webdriver.Edge(service=Service(executable_path=DRIVER_PATH), options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    driver.maximize_window()
    return driver


def get_recipe_urls_on_page(driver, crawled_urls):
    recipe_urls = []
    a_tags = driver.find_elements(By.XPATH, "//a[contains(@href, '/cookbook/')]")
    for a in a_tags:
        href = a.get_attribute("href")
        if (href
                and "douguo.com/cookbook/" in href
                and not href.rstrip('/').endswith('/cookbook')
                and href not in crawled_urls):
            recipe_urls.append(href)
    return list(set(recipe_urls))


def parse_detail_page(driver, detail_url):
    try:
        driver.get(detail_url)
        time.sleep(random.uniform(2.5, 4))

        title = "无标题"
        try:
            title_elem = driver.find_element(
                By.CSS_SELECTOR, "h1.title, .cp-header h1, .recipe-header h1, h1"
            )
            title = title_elem.text.strip()
        except Exception as e:
            print(f"  提取标题失败: {e}")

        materials_text = "无材料"
        try:
            mat_list = []
            main_mats = driver.find_elements(By.CSS_SELECTOR, ".main-material li, .retamr .scname")
            sub_mats  = driver.find_elements(By.CSS_SELECTOR, ".sub-material li")
            for item in main_mats + sub_mats:
                text = item.text.strip()
                if text:
                    scnum_elems = item.find_elements(By.CSS_SELECTOR, ".scnum")
                    if scnum_elems:
                        text = f"{text}{scnum_elems[0].text.strip()}"
                    mat_list.append(text)
            if not mat_list:
                try:
                    metarial_table = driver.find_element(By.CSS_SELECTOR, ".metarial table")
                    for row in metarial_table.find_elements(By.TAG_NAME, "tr"):
                        for cell in row.find_elements(By.TAG_NAME, "td"):
                            t = cell.text.strip()
                            if t:
                                mat_list.append(t)
                except Exception:
                    pass
            if mat_list:
                materials_text = "、".join(mat_list)
        except Exception as e:
            print(f"  提取材料失败: {e}")

        steps_text = "无步骤"
        try:
            steps = []
            step_items = driver.find_elements(By.CSS_SELECTOR, ".step li, .stepinfo")
            for idx, item in enumerate(step_items, 1):
                text = item.text.strip().replace(f"步骤{idx}", "").strip()
                if text:
                    steps.append(f"{idx}. {text}")
            if not steps:
                try:
                    container = driver.find_element(By.CSS_SELECTOR, ".cookstep")
                    for idx, item in enumerate(container.find_elements(By.CSS_SELECTOR, "li, div"), 1):
                        text = item.text.strip()
                        if text and not text.startswith("步骤"):
                            steps.append(f"{idx}. {text}")
                except Exception:
                    pass
            if steps:
                steps_text = "\n".join(steps)
        except Exception as e:
            print(f"  提取步骤失败: {e}")

        return title, materials_text, steps_text

    except Exception as e:
        print(f"  详情页解析失败: {e}")
        return None, None, None


def main():
    os.makedirs(SAVE_DIR, exist_ok=True)

    all_data = []
    crawled_urls = set()
    if os.path.exists(CSV_FILE):
        print("发现已存在的CSV文件，继续追加数据...")
        try:
            df_exist = pd.read_csv(CSV_FILE)
            all_data = df_exist.values.tolist()
            crawled_urls = set(df_exist["来源URL"].tolist())
            print(f"已加载 {len(crawled_urls)} 条历史记录，将跳过已爬链接。")
        except Exception:
            print("CSV文件格式错误，重新创建")

    driver = init_browser()

    try:
        empty_page_count = 0   # 连续空页计数
        page_num = START_PAGE

        while True:
            page_url = BASE_URL.format(page=page_num)
            print(f"\n{'='*50}")
            print(f"【第 {page_num} 页】{page_url}")
            print(f"{'='*50}")

            driver.get(page_url)
            time.sleep(random.uniform(3, 5))

            page_urls = get_recipe_urls_on_page(driver, crawled_urls)
            print(f"  本页新增链接数: {len(page_urls)}")

            if not page_urls:
                empty_page_count += 1
                print(f"  ⚠️  本页无新菜谱（连续空页: {empty_page_count}/{MAX_EMPTY_PAGES}）")
                if empty_page_count >= MAX_EMPTY_PAGES:
                    print("\n连续多页无新数据，判定爬取完毕。")
                    break
                page_num += 1
                continue
            else:
                empty_page_count = 0   # 有数据就重置计数

            success_count = 0
            for idx, detail_url in enumerate(page_urls, 1):
                print(f"  --- {idx}/{len(page_urls)} | {detail_url}")
                title, materials, steps = parse_detail_page(driver, detail_url)

                if title and title != "无标题":
                    print(f"  ✅ {title}")
                    all_data.append([title, materials, steps, detail_url])
                    crawled_urls.add(detail_url)
                    success_count += 1
                    df = pd.DataFrame(all_data, columns=["菜谱标题", "所需材料", "制作步骤", "来源URL"])
                    df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
                else:
                    print(f"  ❌ 爬取失败")

                time.sleep(random.uniform(1, 2.5))

            print(f"  第 {page_num} 页完成，新增 {success_count} 条，累计 {len(all_data)} 条")
            page_num += 1
            time.sleep(random.uniform(2, 4))

    except KeyboardInterrupt:
        print("\n用户手动停止爬取")
    finally:
        print("\n正在关闭浏览器...")
        try:
            driver.quit()
        except Exception:
            pass
        print(f"数据已保存到: {CSV_FILE}，共 {len(all_data)} 条")


if __name__ == "__main__":
    main()