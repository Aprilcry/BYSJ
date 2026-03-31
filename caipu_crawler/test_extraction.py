import pandas as pd
import re

# 读取原始CSV文件
df = pd.read_csv('D:\BYSJ\caipu_crawler\caipu_data.csv')

# 处理title字段，提取“菜谱名称”
def extract_dish_name(title):
    """从title中提取菜谱名称，无“的做法”则返回原标题"""
    if pd.isna(title):
        return ""
    title_str = str(title).strip()
    if "的做法" in title_str:
        return title_str.split("的做法")[0].strip()
    return title_str

df['菜谱名称'] = df['caipu.title'].apply(extract_dish_name)

# 提取主料
def extract_zhu_liao(content):
    """提取主料"""
    if pd.isna(content):
        return "无"
    
    content_str = str(content).strip()
    # 找到最后一个主料位置，避免提取到前面的介绍内容
    zhu_liao_pos = content_str.rfind("主料")
    if zhu_liao_pos == -1:
        return "无"
    
    # 提取主料内容，直到遇到辅料、做法步骤或小贴士
    start_pos = zhu_liao_pos + 2
    # 查找结束位置
    end_markers = ["辅料", "的做法", "1.", "小贴士", "温馨提示", "注意事项"]
    min_end_pos = len(content_str)
    
    for marker in end_markers:
        pos = content_str.find(marker, start_pos)
        if pos != -1 and pos < min_end_pos:
            min_end_pos = pos
    
    zhu_liao_content = content_str[start_pos:min_end_pos].strip()
    # 清理多余的空格
    zhu_liao_content = re.sub(r'\s+', ' ', zhu_liao_content)
    return zhu_liao_content if zhu_liao_content else "无"

# 提取辅料
def extract_fu_liao(content):
    """提取辅料"""
    if pd.isna(content):
        return "无"
    
    content_str = str(content).strip()
    fu_liao_pos = content_str.find("辅料")
    if fu_liao_pos == -1:
        return "无"
    
    # 提取辅料内容，直到遇到做法步骤或小贴士
    start_pos = fu_liao_pos + 2
    # 查找结束位置
    end_markers = ["的做法", "1.", "小贴士", "温馨提示", "注意事项"]
    min_end_pos = len(content_str)
    
    for marker in end_markers:
        pos = content_str.find(marker, start_pos)
        if pos != -1 and pos < min_end_pos:
            min_end_pos = pos
    
    fu_liao_content = content_str[start_pos:min_end_pos].strip()
    # 清理多余的空格
    fu_liao_content = re.sub(r'\s+', ' ', fu_liao_content)
    # 移除可能的菜谱名称
    fu_liao_content = re.sub(r'\s*[\u4e00-\u9fa5]+$', '', fu_liao_content)
    return fu_liao_content if fu_liao_content else "无"

# 提取简介和做法步骤
def extract_intro(content):
    """提取简介"""
    if pd.isna(content):
        return ""
    
    content_str = str(content).strip()
    # 简介是从开始到主料之前的内容
    zhu_liao_pos = content_str.find("主料")
    if zhu_liao_pos == -1:
        return ""
    
    intro = content_str[:zhu_liao_pos].strip()
    # 清理多余的空格
    intro = re.sub(r'\s+', ' ', intro)
    return intro

def extract_steps(content):
    """提取做法步骤"""
    if pd.isna(content):
        return ""
    
    content_str = str(content).strip()
    # 找到做法开始的位置
    steps_start = content_str.find("的做法")
    if steps_start == -1:
        return ""
    
    steps_start += 3  # 跳过“的做法”
    steps_content = content_str[steps_start:].strip()
    
    # 移除小贴士
    tips_pos = steps_content.find("小贴士")
    if tips_pos != -1:
        steps_content = steps_content[:tips_pos].strip()
    
    # 提取步骤内容（从第一个数字步骤开始）
    step_pattern = r'1\..*'
    step_match = re.search(step_pattern, steps_content)
    if step_match:
        steps_content = step_match.group(0)
    
    # 清理多余的空格
    steps_content = re.sub(r'\s+', ' ', steps_content)
    return steps_content

# 提取主料和辅料
df['主料'] = df['caipu.zuofa'].apply(extract_zhu_liao)
df['辅料'] = df['caipu.zuofa'].apply(extract_fu_liao)

# 查看提取结果（前10条）
print("=== 主料和辅料提取结果（前10条）===")
for i in range(10):
    print(f"\n【第{i+1}个菜谱：{df['菜谱名称'].iloc[i]}】")
    print(f"主料：{df['主料'].iloc[i] if df['主料'].iloc[i] != '无' else '未找到主料信息'}")
    print(f"辅料：{df['辅料'].iloc[i] if df['辅料'].iloc[i] != '无' else '未找到辅料信息'}")

# 提取简介和做法步骤
df['简介'] = df['caipu.zuofa'].apply(extract_intro)
df['做法步骤'] = df['caipu.zuofa'].apply(extract_steps)

# 提取标题
df['标题'] = df['菜谱名称']

# 生成最终表格
final_df = df[[
    "标题", "主料", "辅料", "简介", "做法步骤",
    "category_1.title", "category_2.title"
]].copy()

# 重命名分类字段
final_df.rename(columns={
    "category_1.title": "一级分类",
    "category_2.title": "二级分类"
}, inplace=True)

# 保存结果
final_df.to_csv("caipu_ultimate_final.csv", index=False, encoding="utf-8-sig")

# 验证关键案例（以“葱烧蹄筋”为例）
test_case = final_df[final_df["标题"] == "葱烧蹄筋"]
if not test_case.empty:
    print("\n✅ 关键案例验证（葱烧蹄筋）：")
    print(f"标题：{test_case['标题'].iloc[0]}")
    print(f"主料：{test_case['主料'].iloc[0]}")
    print(f"辅料：{test_case['辅料'].iloc[0]}")
    print(f"做法步骤：\n{test_case['做法步骤'].iloc[0]}")

print("\n🎉 处理完成！")
print("✅ 输出文件：caipu_ultimate_final.csv")
print("✅ 字段：标题、主料、辅料、简介、做法步骤、一级分类、二级分类")
