#!/usr/bin/env python3
"""
读取本地标注信息，执行SAM分割和合成
"""
import os
import json
import numpy as np
from PIL import Image
from segment_anything import SamPredictor, sam_model_registry
import torch
from pathlib import Path
import random
import math
import cv2
from tqdm import tqdm

# 配置
SAM_CHECKPOINT = "/root/autodl-tmp/crawler/SAM/sam_vit_h_4b8939.pth"
MODEL_TYPE = "vit_h"
ORIGIN_DIR = "/root/autodl-tmp/crawler/origin"
BACKGROUND_DIR = "/root/autodl-tmp/crawler/background"
OUTPUT_DIR = "/root/autodl-tmp/crawler/yolov8_dataset"
ANNOTATIONS_FILE = "/root/autodl-tmp/crawler/annotations.json"

TRAIN_RATIO = 0.9
OUTPUT_SIZE = (640, 640)
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}

# 确保输出目录存在
def setup_output_dirs(output_root: str):
    dirs = {}
    for sub in ('images', 'labels'):
        for split in ('train', 'val'):
            p = Path(output_root) / sub / split
            p.mkdir(parents=True, exist_ok=True)
            dirs[f'{split}_{sub}'] = p
    return dirs

def get_device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

def load_predictor():
    device = get_device()
    print(f"[SAM] Loading '{MODEL_TYPE}' on {device} …")
    sam = sam_model_registry[MODEL_TYPE](checkpoint=SAM_CHECKPOINT)
    sam.to(device)
    return SamPredictor(sam)

def segment_with_box(predictor, image, box):
    """使用边界框进行分割"""
    predictor.set_image(image)
    # 确保box是正确的格式
    if isinstance(box, list):
        # 如果是列表，转换为numpy数组
        box = np.array(box)
    elif isinstance(box, tuple):
        # 如果是元组，转换为numpy数组
        box = np.array(box)
    
    # 确保box是二维数组
    if box.ndim == 1:
        box = box[None, :]
    
    # 生成掩码
    masks, scores, logits = predictor.predict(
        box=box,
        multimask_output=True
    )
    
    # 选择得分最高的掩码
    best_mask_idx = np.argmax(scores)
    best_mask = masks[best_mask_idx]
    
    return best_mask

def post_process_mask(mask):
    """后处理掩码，填充空洞并确保完整"""
    # 转换为uint8
    mask_uint8 = mask.astype(np.uint8) * 255
    
    # 闭运算：先膨胀后腐蚀，填充小空洞
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_closed = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel)
    
    # 开运算：先腐蚀后膨胀，去除小噪点
    mask_opened = cv2.morphologyEx(mask_closed, cv2.MORPH_OPEN, kernel)
    
    # 膨胀操作，扩展掩码边界
    mask_dilated = cv2.dilate(mask_opened, kernel, iterations=1)
    
    return mask_dilated > 0

def extract_foreground(image, mask):
    """提取前景"""
    mask = mask.astype(bool)
    rgba = np.zeros((image.shape[0], image.shape[1], 4), dtype=np.uint8)
    rgba[:, :, :3] = image
    rgba[:, :, 3] = mask * 255
    return Image.fromarray(rgba, 'RGBA')

def tight_crop_foreground(fg: Image.Image):
    """裁剪前景"""
    arr = np.array(fg)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 10)
    if len(ys) == 0:
        return fg
    return fg.crop((int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1))

def resize_foreground(fg: Image.Image, target_area_px: int, max_w: int = 99999, max_h: int = 99999) -> Image.Image:
    """调整前景大小"""
    arr = np.array(fg)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 10)
    if len(ys) == 0:
        return fg
    h_box = int(ys.max() - ys.min() + 1)
    w_box = int(xs.max() - xs.min() + 1)
    cur = h_box * w_box
    if cur <= 0:
        return fg
    scale = math.sqrt(target_area_px / cur)
    nw = max(1, int(fg.width * scale))
    nh = max(1, int(fg.height * scale))
    if nw > max_w or nh > max_h:
        s = min(max_w / nw, max_h / nh) * 0.95
        nw = max(1, int(nw * s))
        nh = max(1, int(nh * s))
    return fg.resize((nw, nh), Image.LANCZOS)

def augment_foreground(fg: Image.Image) -> Image.Image:
    """增强前景"""
    if random.random() < 0.5:
        fg = fg.transpose(Image.FLIP_LEFT_RIGHT)
    angle = random.uniform(-30, 30)
    fg = fg.rotate(angle, resample=Image.BICUBIC, expand=True)
    return fg

def paste_foreground(bg: Image.Image, fg: Image.Image, cx: int, cy: int):
    """粘贴前景到背景"""
    x1 = cx - fg.width // 2
    y1 = cy - fg.height // 2
    x2, y2 = x1 + fg.width, y1 + fg.height
    x1c, y1c = max(0, x1), max(0, y1)
    x2c, y2c = min(bg.width, x2), min(bg.height, y2)
    fx1, fy1 = x1c - x1, y1c - y1
    fx2, fy2 = fx1 + (x2c - x1c), fy1 + (y2c - y1c)
    if fx2 <= fx1 or fy2 <= fy1:
        return bg, (0, 0, 0, 0)
    crop = fg.crop((fx1, fy1, fx2, fy2))
    canvas = bg.copy().convert('RGBA')
    canvas.paste(crop, (x1c, y1c), mask=crop.split()[3])
    return canvas.convert('RGB'), (x1c, y1c, x2c, y2c)

def composite_ingredient(bg: Image.Image, fg: Image.Image):
    """合成前景到背景"""
    r = random.random()
    bg_area = bg.width * bg.height
    if r < 0.60:
        # Centred
        fg2 = resize_foreground(fg, int(bg_area*0.40), bg.width, bg.height)
        fg2 = augment_foreground(fg2)
        cx = bg.width//2 + random.randint(-bg.width//16, bg.width//16)
        cy = bg.height//2 + random.randint(-bg.height//16, bg.height//16)
        comp, box = paste_foreground(bg, fg2, cx, cy)
        return comp, [box]
    elif r < 0.90:
        # Scattered 2-4
        n = random.randint(2, 4)
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        cw = bg.width // cols
        ch = bg.height // rows
        positions = [(c, r2) for r2 in range(rows) for c in range(cols)]
        random.shuffle(positions)
        comp = bg.copy()
        boxes = []
        for i in range(n):
            col, row = positions[i]
            p = resize_foreground(fg.copy(), int(bg_area*0.10), int(cw*0.9), int(ch*0.9))
            p = augment_foreground(p)
            hw, hh = p.width//2+1, p.height//2+1
            lo_x = col*cw + hw; hi_x = col*cw + cw - hw
            lo_y = row*ch + hh; hi_y = row*ch + ch - hh
            cx = random.randint(lo_x, max(lo_x, hi_x))
            cy = random.randint(lo_y, max(lo_y, hi_y))
            comp, box = paste_foreground(comp, p, cx, cy)
            if is_valid_box(box, bg.width, bg.height):
                boxes.append(box)
        return comp, boxes
    else:
        # Adjacent (off-centre)
        fg2 = resize_foreground(fg, int(bg_area*0.25), bg.width, bg.height)
        fg2 = augment_foreground(fg2)
        d = random.choice(['N','S','E','W','NE','NW','SE','SW'])
        sx = int(bg.width * random.uniform(0.15, 0.30))
        sy = int(bg.height * random.uniform(0.15, 0.30))
        cx, cy = bg.width//2, bg.height//2
        if 'N' in d: cy -= sy
        if 'S' in d: cy += sy
        if 'E' in d: cx += sx
        if 'W' in d: cx -= sx
        cx = max(fg2.width//2, min(bg.width - fg2.width//2 - 1, cx))
        cy = max(fg2.height//2, min(bg.height - fg2.height//2 - 1, cy))
        comp, box = paste_foreground(bg, fg2, cx, cy)
        return comp, [box]

def is_valid_box(box, img_w, img_h, min_ratio=0.002):
    """检查边界框是否有效"""
    x1, y1, x2, y2 = box
    return (x2-x1)*(y2-y1) >= min_ratio * img_w * img_h

def box_to_yolo(box, img_w, img_h):
    """转换为YOLO格式"""
    x1, y1, x2, y2 = box
    return ((x1+x2)/2/img_w, (y1+y2)/2/img_h, (x2-x1)/img_w, (y2-y1)/img_h)

def save_sample(img_pil: Image.Image, label_str: str, fname: str, dirs: dict, counters: dict):
    """保存样本"""
    split = 'train' if random.random() < TRAIN_RATIO else 'val'
    img_fp = dirs[f'{split}_images'] / f"{fname}.jpg"
    lbl_fp = dirs[f'{split}_labels'] / f"{fname}.txt"
    img_pil.save(str(img_fp), quality=95)
    lbl_fp.write_text(label_str)
    counters['total'] += 1
    counters[split] += 1

def derive_class(img_path):
    """推导类别"""
    img_path = Path(img_path)
    origin = Path(ORIGIN_DIR)
    try:
        rel = img_path.relative_to(origin)
        cls_name = rel.parts[0] if len(rel.parts) > 1 else img_path.parent.name
    except ValueError:
        cls_name = img_path.parent.name or 'ingredient'
    return cls_name

def main():
    # 加载背景图片
    bg_paths = sorted(
        p for p in Path(BACKGROUND_DIR).iterdir()
        if p.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not bg_paths:
        print(f"[ERROR] No backgrounds found in {BACKGROUND_DIR}")
        return

    print(f"[INFO] Loading {len(bg_paths)} background(s) …")
    backgrounds = []
    for bp in bg_paths:
        img = Image.open(bp).convert('RGB').resize(OUTPUT_SIZE, Image.LANCZOS)
        backgrounds.append((img, bp.stem))

    # 加载标注信息
    if not os.path.exists(ANNOTATIONS_FILE):
        print(f"[ERROR] Annotations file not found: {ANNOTATIONS_FILE}")
        return

    with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
        annotations = json.load(f)

    if not annotations:
        print("[ERROR] No annotations found in file")
        return

    # 构建类别映射
    class_names = []
    for ann in annotations:
        cls_name = ann['class_name']
        # 确保class_name是字符串
        if isinstance(cls_name, list):
            # 如果是列表，取第二个元素作为类别名称（格式：[0, "冬瓜"]）
            cls_name = cls_name[1] if len(cls_name) > 1 else (cls_name[0] if cls_name else 'unknown')
        elif not isinstance(cls_name, str):
            # 其他类型转换为字符串
            cls_name = str(cls_name)
        if cls_name not in class_names:
            class_names.append(cls_name)
    class_names.sort()
    class_map = {name: i for i, name in enumerate(class_names)}

    # 设置输出目录
    dirs = setup_output_dirs(OUTPUT_DIR)
    predictor = load_predictor()
    counters = {'total': 0, 'train': 0, 'val': 0}
    sample_idx = 0

    # 处理每个标注
    print(f"[INFO] Processing {len(annotations)} annotations …")
    for ann in tqdm(annotations, desc="Processing", unit="img"):
        # 构建图片路径
        rel_path = ann['relative_path']
        # 修复路径中的反斜杠，转换为正斜杠
        rel_path = rel_path.replace('\\', '/')
        img_path = Path(ORIGIN_DIR) / rel_path
        
        if not img_path.exists():
            print(f"[WARN] Image not found: {img_path}")
            continue
        
        # 获取类别
        cls_name = ann['class_name']
        # 确保cls_name是字符串
        if isinstance(cls_name, list):
            # 如果是列表，取第二个元素作为类别名称（格式：[0, "冬瓜"]）
            cls_name = cls_name[1] if len(cls_name) > 1 else (cls_name[0] if cls_name else 'unknown')
        elif not isinstance(cls_name, str):
            # 其他类型转换为字符串
            cls_name = str(cls_name)
        cls_id = class_map.get(cls_name, 0)
        
        # 读取图片
        image_bgr = cv2.imread(str(img_path))
        if image_bgr is None:
            print(f"[WARN] Cannot read {img_path}")
            continue
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        h, w = image_rgb.shape[:2]
        
        # 处理每个框
        for box in ann['boxes']:
            # SAM分割
            try:
                mask = segment_with_box(predictor, image_rgb, box)
                # 后处理掩码，填充空洞并确保完整
                mask = post_process_mask(mask)
            except Exception as e:
                print(f"[WARN] SAM failed on {img_path.name}: {e}")
                continue
            
            # 提取前景
            fg_rgba = tight_crop_foreground(extract_foreground(image_rgb, mask))
            
            # 保存原始图像
            orig_pil = Image.fromarray(image_rgb).resize(OUTPUT_SIZE, Image.LANCZOS)
            ys, xs = np.where(mask > 0)
            if len(ys) > 0:
                sx, sy = OUTPUT_SIZE[0]/w, OUTPUT_SIZE[1]/h
                orig_box = (int(xs.min()*sx), int(ys.min()*sy), int(xs.max()*sx), int(ys.max()*sy))
                if is_valid_box(orig_box, *OUTPUT_SIZE):
                    bx, by, bw, bh = box_to_yolo(orig_box, *OUTPUT_SIZE)
                    bx = max(0.0, min(1.0, bx)); by = max(0.0, min(1.0, by))
                    bw = max(0.0, min(1.0, bw)); bh = max(0.0, min(1.0, bh))
                    save_sample(
                        orig_pil,
                        f"{cls_id} {bx:.6f} {by:.6f} {bw:.6f} {bh:.6f}",
                        f"{img_path.stem}_original_{sample_idx:06d}",
                        dirs, counters
                    )
                    sample_idx += 1
            
            # 合成到每个背景
            saved_bg = 0
            for bg_img, bg_stem in backgrounds:
                composited, comp_boxes = composite_ingredient(bg_img, fg_rgba)
                valid_lines = []
                for cb in comp_boxes:
                    if not is_valid_box(cb, *OUTPUT_SIZE):
                        continue
                    bx, by, bw, bh = box_to_yolo(cb, *OUTPUT_SIZE)
                    bx = max(0.0, min(1.0, bx)); by = max(0.0, min(1.0, by))
                    bw = max(0.0, min(1.0, bw)); bh = max(0.0, min(1.0, bh))
                    if bw > 0 and bh > 0:
                        valid_lines.append(f"{cls_id} {bx:.6f} {by:.6f} {bw:.6f} {bh:.6f}")
                if not valid_lines:
                    continue
                save_sample(
                    composited,
                    '\n'.join(valid_lines),
                    f"{img_path.stem}_{bg_stem}_{sample_idx:06d}",
                    dirs, counters
                )
                sample_idx += 1
                saved_bg += 1
            
            print(f"  ✓ [{cls_name}] {img_path.name} → 1 original + {saved_bg}/{len(backgrounds)} composites")
    
    # 生成dataset.yaml
    yaml_path = Path(OUTPUT_DIR) / 'dataset.yaml'
    yaml_content = f"""# YOLOv8 Dataset
path: {OUTPUT_DIR}
train: images/train
val: images/val

nc: {len(class_names)}
names: {json.dumps(class_names, ensure_ascii=False)}
"""
    yaml_path.write_text(yaml_content)
    
    print(
        f"\n{'─'*52}\n"
        f"  Remote Processing — Done\n"
        f"{'─'*52}\n"
        f"  Output   : {OUTPUT_DIR}\n"
        f"  Train    : {counters['train']} images\n"
        f"  Val      : {counters['val']} images\n"
        f"  Total    : {counters['total']} images\n"
        f"  Classes  : {class_names}\n"
        f"{'─'*52}"
    )

if __name__ == "__main__":
    main()
