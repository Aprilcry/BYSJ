import csv
import os

# 定义文件路径
input_file = 'd:\\BYSJ\\caipu_crawler\\caipu_ultimate_final.csv'
output_file = 'd:\\BYSJ\\caipu_crawler\\caipu_ultimate_final_cleaned.csv'

print(f"正在读取文件: {input_file}")

# 读取CSV文件并清洗数据
with open(input_file, 'r', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames
    
    # 统计数据行数和空值行数
    total_rows = 0
    empty_rows = 0
    cleaned_rows = []
    
    for row in reader:
        total_rows += 1
        # 检查是否存在空值
        has_empty = False
        for key, value in row.items():
            if not value.strip():
                has_empty = True
                break
        
        if has_empty:
            empty_rows += 1
        else:
            cleaned_rows.append(row)

print(f"读取完成，总数据行数: {total_rows}")
print(f"含有空值的行数: {empty_rows}")
print(f"清洗后剩余行数: {len(cleaned_rows)}")

# 保存清洗后的数据
with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(cleaned_rows)

print(f"清洗后的数据已保存至: {output_file}")
print("数据预处理完成！")