"""
Manual Box-Prompt Annotation Tool
==================================
For images where the automatic SAM segmentation produced poor results,
this tool lets you draw a bounding box around the ingredient manually.
SAM then uses that box as a prompt for a precise segmentation.

Workflow:
  1. Launch → a file-selector dialog appears.
  2. Click "Add Images" to pick one or more original ingredient images.
     You can add images from multiple folders / classes in one session.
  3. Click "OK" to begin annotating.
  4. For each image:
       • Left-click and drag to draw a box around the ingredient.
       • The green box shows your current selection.
       • Click "Redo" to redraw the box on the current image.
       • Click "Next →" (or "Finish ✓" on the last image) to confirm and advance.
  5. After all images are annotated, SAM runs on each with your box prompt,
     composites the foreground onto all backgrounds, and saves everything
     to OUTPUT_DIR in the same format as sam_augmentation.py.

Dependencies:
  pip install torch torchvision segment-anything opencv-python Pillow numpy tqdm
  pip install git+https://github.com/facebookresearch/segment-anything.git
"""

import os
import sys
import random
import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageTk
from tqdm import tqdm

# ─────────────────────────── CONFIG (must match sam_augmentation.py) ────────
# 配置 - 本地和远程保持一致的目录结构
SAM_CHECKPOINT = "/root/autodl-tmp/crawler/SAM/sam_vit_h_4b8939.pth"
MODEL_TYPE      = "vit_h"
BACKGROUND_DIR  = "/root/autodl-tmp/crawler/background"
OUTPUT_DIR      = "/root/autodl-tmp/crawler/yolov8_dataset"
ORIGIN_DIR      = "/root/autodl-tmp/crawler/origin"

# 本地配置（用于框选）
LOCAL_BACKGROUND_DIR = r"D:\BYSJ\crawler\background"
LOCAL_OUTPUT_DIR = r"D:\BYSJ\crawler\yolov8_dataset"
LOCAL_ORIGIN_DIR = r"D:\BYSJ\crawler\origin"
LOCAL_ANNOTATIONS_FILE = os.path.join(LOCAL_OUTPUT_DIR, "annotations.json")

TRAIN_RATIO   = 0.9
OUTPUT_SIZE   = (640, 640)
EDGE_FEATHER  = 3
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}

# Max canvas size for display (image is scaled to fit, coords mapped back)
CANVAS_W = 800
CANVAS_H = 800

# ─────────────────────────── SHARED UTILITIES ───────────────────────────────

def feather_mask(mask: np.ndarray, radius: int = EDGE_FEATHER) -> np.ndarray:
    if radius <= 0:
        return mask.astype(np.float32)
    blurred = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), radius)
    return np.clip(blurred, 0, 1)

def largest_connected_component(mask: np.ndarray) -> np.ndarray:
    mask_u8 = mask.astype(np.uint8) * 255
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if n <= 1:
        return mask
    biggest = int(np.argmax(stats[1:, cv2.CC_STAT_AREA])) + 1
    return (labels == biggest).astype(np.uint8)

def extract_foreground(image_rgb: np.ndarray, mask: np.ndarray) -> Image.Image:
    alpha = feather_mask(mask)
    rgba  = np.dstack([image_rgb, (alpha * 255).astype(np.uint8)])
    return Image.fromarray(rgba, 'RGBA')

def tight_crop_foreground(fg: Image.Image) -> Image.Image:
    arr   = np.array(fg)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 10)
    if len(ys) == 0:
        return fg
    return fg.crop((int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1))

def resize_foreground(fg: Image.Image, target_area_px: int,
                      max_w: int = 99999, max_h: int = 99999) -> Image.Image:
    arr   = np.array(fg)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 10)
    if len(ys) == 0:
        return fg
    h_box = int(ys.max() - ys.min() + 1)
    w_box = int(xs.max() - xs.min() + 1)
    cur   = h_box * w_box
    if cur <= 0:
        return fg
    scale = math.sqrt(target_area_px / cur)
    nw = max(1, int(fg.width  * scale))
    nh = max(1, int(fg.height * scale))
    if nw > max_w or nh > max_h:
        s  = min(max_w / nw, max_h / nh) * 0.95
        nw = max(1, int(nw * s))
        nh = max(1, int(nh * s))
    return fg.resize((nw, nh), Image.LANCZOS)

def augment_foreground(fg: Image.Image) -> Image.Image:
    if random.random() < 0.5:
        fg = fg.transpose(Image.FLIP_LEFT_RIGHT)
    angle = random.uniform(-30, 30)
    fg    = fg.rotate(angle, resample=Image.BICUBIC, expand=True)
    return fg

def paste_foreground(bg: Image.Image, fg: Image.Image,
                     cx: int, cy: int):
    x1 = cx - fg.width  // 2
    y1 = cy - fg.height // 2
    x2, y2 = x1 + fg.width, y1 + fg.height
    x1c, y1c = max(0, x1), max(0, y1)
    x2c, y2c = min(bg.width, x2), min(bg.height, y2)
    fx1, fy1 = x1c - x1, y1c - y1
    fx2, fy2 = fx1 + (x2c - x1c), fy1 + (y2c - y1c)
    if fx2 <= fx1 or fy2 <= fy1:
        return bg, (0, 0, 0, 0)
    crop   = fg.crop((fx1, fy1, fx2, fy2))
    canvas = bg.copy().convert('RGBA')
    canvas.paste(crop, (x1c, y1c), mask=crop.split()[3])
    return canvas.convert('RGB'), (x1c, y1c, x2c, y2c)

def box_to_yolo(box, img_w, img_h):
    x1, y1, x2, y2 = box
    return ((x1+x2)/2/img_w, (y1+y2)/2/img_h,
            (x2-x1)/img_w,   (y2-y1)/img_h)

def is_valid_box(box, img_w, img_h, min_ratio=0.002):
    x1, y1, x2, y2 = box
    return (x2-x1)*(y2-y1) >= min_ratio * img_w * img_h

def save_annotations(annotations, output_file):
    """保存标注信息到JSON文件"""
    import json
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(annotations, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Annotations saved to {output_file}")

def derive_class(img_path):
    """从图片路径推导类别"""
    img_path = Path(img_path)
    origin = Path(LOCAL_ORIGIN_DIR)
    try:
        rel = img_path.relative_to(origin)
        cls_name = rel.parts[0] if len(rel.parts) > 1 else img_path.parent.name
    except ValueError:
        cls_name = img_path.parent.name or 'ingredient'
    return cls_name

def composite_ingredient(bg: Image.Image, fg: Image.Image):
    """Randomly place fg on bg using the same 3-strategy distribution."""
    r = random.random()
    bg_area = bg.width * bg.height
    if r < 0.60:
        # Centred
        fg2 = resize_foreground(fg, int(bg_area*0.40), bg.width, bg.height)
        fg2 = augment_foreground(fg2)
        cx  = bg.width//2  + random.randint(-bg.width//16,  bg.width//16)
        cy  = bg.height//2 + random.randint(-bg.height//16, bg.height//16)
        comp, box = paste_foreground(bg, fg2, cx, cy)
        return comp, [box]
    elif r < 0.90:
        # Scattered 2-4
        n   = random.randint(2, 4)
        cols= math.ceil(math.sqrt(n))
        rows= math.ceil(n / cols)
        cw  = bg.width  // cols
        ch  = bg.height // rows
        positions = [(c, r2) for r2 in range(rows) for c in range(cols)]
        random.shuffle(positions)
        comp  = bg.copy()
        boxes = []
        for i in range(n):
            col, row = positions[i]
            p  = resize_foreground(fg.copy(), int(bg_area*0.10),
                                   int(cw*0.9), int(ch*0.9))
            p  = augment_foreground(p)
            hw, hh = p.width//2+1, p.height//2+1
            lo_x = col*cw + hw;  hi_x = col*cw + cw - hw
            lo_y = row*ch + hh;  hi_y = row*ch + ch - hh
            cx   = random.randint(lo_x, max(lo_x, hi_x))
            cy   = random.randint(lo_y, max(lo_y, hi_y))
            comp, box = paste_foreground(comp, p, cx, cy)
            if is_valid_box(box, bg.width, bg.height):
                boxes.append(box)
        return comp, boxes
    else:
        # Adjacent (off-centre)
        fg2 = resize_foreground(fg, int(bg_area*0.25), bg.width, bg.height)
        fg2 = augment_foreground(fg2)
        d   = random.choice(['N','S','E','W','NE','NW','SE','SW'])
        sx  = int(bg.width  * random.uniform(0.15, 0.30))
        sy  = int(bg.height * random.uniform(0.15, 0.30))
        cx, cy = bg.width//2, bg.height//2
        if 'N' in d: cy -= sy
        if 'S' in d: cy += sy
        if 'E' in d: cx += sx
        if 'W' in d: cx -= sx
        cx = max(fg2.width//2,  min(bg.width  - fg2.width//2  - 1, cx))
        cy = max(fg2.height//2, min(bg.height - fg2.height//2 - 1, cy))
        comp, box = paste_foreground(bg, fg2, cx, cy)
        return comp, [box]

def setup_output_dirs(output_root: str):
    dirs = {}
    for sub in ('images', 'labels'):
        for split in ('train', 'val'):
            p = Path(output_root) / sub / split
            p.mkdir(parents=True, exist_ok=True)
            dirs[f'{split}_{sub}'] = p
    return dirs

def derive_class(img_path: Path) -> tuple[int, str]:
    """
    Guess class id / name from folder structure matching ORIGIN_DIR.
    Falls back to folder name, then to 'ingredient'.
    """
    origin = Path(ORIGIN_DIR)
    try:
        rel = img_path.relative_to(origin)
        cls_name = rel.parts[0] if len(rel.parts) > 1 else img_path.parent.name
    except ValueError:
        cls_name = img_path.parent.name or 'ingredient'
    # Build or look up class id from existing labels/train *.txt files
    yaml_path = Path(OUTPUT_DIR) / 'dataset.yaml'
    class_names: list[str] = []
    if yaml_path.exists():
        for line in yaml_path.read_text().splitlines():
            line = line.strip()
            if line and line[0].isdigit() and ':' in line:
                class_names.append(line.split(':', 1)[1].strip())
    if cls_name in class_names:
        return class_names.index(cls_name), cls_name
    # Not found: assign next available id (won't update yaml automatically)
    return len(class_names), cls_name


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 1 — FILE SELECTOR WINDOW
# ═══════════════════════════════════════════════════════════════════════════

class FileSelectorApp:
    """
    Simple window: a listbox of selected files, Add / Remove buttons, OK / Cancel.
    Returns the chosen file paths via self.result after mainloop exits.
    """

    def __init__(self, root: tk.Tk):
        self.root   = root
        self.result : list[Path] = []
        root.title("Manual Annotator — Select Images")
        root.resizable(False, False)
        self._build()

    def _build(self):
        root = self.root
        root.configure(padx=12, pady=12)

        tk.Label(root, text="Images to manually annotate:",
                 font=("Helvetica", 11, "bold")).grid(row=0, column=0,
                 columnspan=3, sticky='w', pady=(0, 6))

        # Listbox + scrollbar
        frame = tk.Frame(root)
        frame.grid(row=1, column=0, columnspan=3, sticky='nsew')
        sb = tk.Scrollbar(frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.lb = tk.Listbox(frame, width=72, height=16,
                             yscrollcommand=sb.set, selectmode=tk.EXTENDED)
        self.lb.pack(side=tk.LEFT, fill=tk.BOTH)
        sb.config(command=self.lb.yview)

        # Buttons row
        btn_frame = tk.Frame(root)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=8)
        tk.Button(btn_frame, text="➕  Add Images", width=16,
                  command=self._add).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="📁  Add Folders", width=16,
                  command=self._add_folders).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="➖  Remove Selected", width=18,
                  command=self._remove).pack(side=tk.LEFT, padx=4)

        # OK / Cancel
        ok_frame = tk.Frame(root)
        ok_frame.grid(row=3, column=0, columnspan=3)
        tk.Button(ok_frame, text="  OK  ", width=12, bg="#4CAF50", fg="white",
                  font=("Helvetica", 10, "bold"),
                  command=self._ok).pack(side=tk.LEFT, padx=8)
        tk.Button(ok_frame, text="Cancel", width=10,
                  command=self._cancel).pack(side=tk.LEFT, padx=8)

        self._paths: list[Path] = []

    def _add(self):
        files = filedialog.askopenfilenames(
            title="Select ingredient images",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff"),
                       ("All files", "*.*")]
        )
        for f in files:
            p = Path(f)
            if p not in self._paths:
                self._paths.append(p)
                self.lb.insert(tk.END, str(p))

    def _add_folders(self):
        """Add all images from selected folders (recursive)."""
        import tkinter.messagebox as messagebox
        # 使用askdirectory而不是askdirectories
        folder = filedialog.askdirectory(
            title="Select folder containing images"
        )
        if not folder:
            return
        
        # 支持的图片扩展名
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.gif'}
        added_count = 0
        
        folder_path = Path(folder)
        # 递归遍历文件夹
        for ext in image_extensions:
            for img_path in folder_path.rglob(f"*{ext}"):
                if img_path not in self._paths:
                    self._paths.append(img_path)
                    self.lb.insert(tk.END, str(img_path))
                    added_count += 1
        
        if added_count > 0:
            messagebox.showinfo("Added Images", f"Added {added_count} images from selected folder.")
        else:
            messagebox.showinfo("No Images Found", "No images found in selected folder.")

    def _remove(self):
        for idx in reversed(self.lb.curselection()):
            self.lb.delete(idx)
            self._paths.pop(idx)

    def _ok(self):
        if not self._paths:
            messagebox.showwarning("No images", "Please add at least one image.")
            return
        self.result = self._paths
        self.root.destroy()

    def _cancel(self):
        self.root.destroy()


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 2 — PER-IMAGE BOX DRAWING WINDOW
# ═══════════════════════════════════════════════════════════════════════════

class AnnotatorApp:
    """
    Shows images one by one; user draws a bounding box by clicking+dragging.
    Stores results as {img_path: (x1, y1, x2, y2)} in original image coords.
    """

    def __init__(self, root: tk.Tk, image_paths: list[Path]):
        self.root        = root
        self.paths       = image_paths
        self.idx         = 0
        self.boxes       : dict[Path, tuple] = {}   # path → (x1,y1,x2,y2) orig coords
        self._rect_id    = None
        self._start      = None          # canvas coords when drag started
        self._cur_box    = None          # current canvas box (x1,y1,x2,y2)
        self._scale      = 1.0
        self._img_offset = (0, 0)        # (pad_x, pad_y) if image is letterboxed
        self._tk_img     = None          # keep reference so GC doesn't collect it

        root.title("Manual Annotator — Draw Box Around Ingredient")
        root.resizable(True, True)
        self._build()
        self._load_image()

    # ── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        root = self.root

        # Top info bar
        top = tk.Frame(root)
        top.pack(fill=tk.X, padx=8, pady=4)
        self.lbl_progress = tk.Label(top, text="", font=("Helvetica", 10))
        self.lbl_progress.pack(side=tk.LEFT)
        self.lbl_hint = tk.Label(
            top,
            text="  ←  Left-click and drag to draw a box around the ingredient",
            fg="#555", font=("Helvetica", 10, "italic")
        )
        self.lbl_hint.pack(side=tk.LEFT)

        # Canvas
        self.canvas = tk.Canvas(root, width=CANVAS_W, height=CANVAS_H,
                                bg="#1e1e1e", cursor="crosshair")
        self.canvas.pack(padx=8, pady=4)
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # File name label
        self.lbl_file = tk.Label(root, text="", fg="#333",
                                 font=("Helvetica", 9))
        self.lbl_file.pack()

        # Buttons
        btn = tk.Frame(root)
        btn.pack(pady=8)
        self.btn_redo = tk.Button(btn, text="↺  Redo box", width=12,
                                  command=self._redo)
        self.btn_redo.pack(side=tk.LEFT, padx=6)
        self.btn_next = tk.Button(btn, text="Next  →", width=14,
                                  bg="#2196F3", fg="white",
                                  font=("Helvetica", 10, "bold"),
                                  command=self._next)
        self.btn_next.pack(side=tk.LEFT, padx=6)
        self.btn_skip = tk.Button(btn, text="Skip (no box)", width=14,
                                  fg="#888", command=self._skip)
        self.btn_skip.pack(side=tk.LEFT, padx=6)
        self.btn_delete = tk.Button(btn, text="🗑️  Delete", width=12,
                                    fg="red", command=self._delete)
        self.btn_delete.pack(side=tk.LEFT, padx=6)

    # ── Image loading ────────────────────────────────────────────────────────

    def _load_image(self):
        """Display the current image, scaled to fit CANVAS_W×CANVAS_H."""
        path = self.paths[self.idx]
        img  = Image.open(path).convert('RGB')
        self._orig_w, self._orig_h = img.size

        # Scale to fit canvas while preserving aspect ratio
        scale = min(CANVAS_W / img.width, CANVAS_H / img.height)
        self._scale = scale
        dw = int(img.width  * scale)
        dh = int(img.height * scale)
        pad_x = (CANVAS_W - dw) // 2
        pad_y = (CANVAS_H - dh) // 2
        self._img_offset = (pad_x, pad_y)

        disp = img.resize((dw, dh), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(disp)

        self.canvas.delete("all")
        self.canvas.create_image(pad_x, pad_y, anchor='nw', image=self._tk_img)
        self._rect_id = None
        self._cur_box = None

        n = len(self.paths)
        self.lbl_progress.config(text=f"Image {self.idx+1} / {n}")
        self.lbl_file.config(text=str(path))
        label = "Finish ✓" if self.idx == n - 1 else "Next  →"
        self.btn_next.config(text=label,
                             bg="#4CAF50" if self.idx == n-1 else "#2196F3")

    # ── Mouse events ─────────────────────────────────────────────────────────

    def _on_press(self, event):
        self._start = (event.x, event.y)
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_drag(self, event):
        if self._start is None:
            return
        if self._rect_id:
            self.canvas.delete(self._rect_id)
        x0, y0 = self._start
        self._rect_id = self.canvas.create_rectangle(
            x0, y0, event.x, event.y,
            outline="#00FF00", width=2
        )

    def _on_release(self, event):
        if self._start is None:
            return
        x0, y0 = self._start
        x1, y1 = event.x, event.y
        # Normalise so top-left < bottom-right
        cx1, cx2 = min(x0, x1), max(x0, x1)
        cy1, cy2 = min(y0, y1), max(y0, y1)
        if cx2 - cx1 < 4 or cy2 - cy1 < 4:
            return  # too small, ignore
        self._cur_box = (cx1, cy1, cx2, cy2)  # canvas coords
        self._start   = None

    # ── Actions ──────────────────────────────────────────────────────────────

    def _redo(self):
        """Clear current box and let user draw again."""
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None
        self._cur_box = None
        self._start   = None

    def _canvas_to_orig(self, cx1, cy1, cx2, cy2):
        """Convert canvas coordinates back to original image pixel coordinates."""
        px, py = self._img_offset
        s      = self._scale
        ox1 = max(0, int((cx1 - px) / s))
        oy1 = max(0, int((cy1 - py) / s))
        ox2 = min(self._orig_w, int((cx2 - px) / s))
        oy2 = min(self._orig_h, int((cy2 - py) / s))
        return ox1, oy1, ox2, oy2

    def _next(self):
        if self._cur_box is None:
            messagebox.showwarning(
                "No box drawn",
                "Please draw a bounding box around the ingredient first.\n"
                "Use 'Skip' if you want to leave this image without a box."
            )
            return
        path = self.paths[self.idx]
        self.boxes[path] = self._canvas_to_orig(*self._cur_box)
        self._advance()

    def _skip(self):
        """Advance without recording a box — image will be skipped in processing."""
        self._advance()

    def _delete(self):
        """Delete the current image and advance."""
        import tkinter.messagebox as messagebox
        path = self.paths[self.idx]
        
        # 显示确认对话框
        confirm = messagebox.askyesno(
            "Delete Image",
            f"Are you sure you want to delete:\n{path}"
        )
        
        if confirm:
            try:
                # 删除文件
                import os
                os.remove(path)
                print(f"[INFO] Deleted: {path}")
                # 从路径列表中移除
                self.paths.pop(self.idx)
                # 如果删除后没有图片了，退出
                if not self.paths:
                    self.root.destroy()
                    return
                # 重新加载当前索引的图片
                self._load_image()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete image: {e}")
        
    def _advance(self):
        self.idx += 1
        if self.idx >= len(self.paths):
            self.root.destroy()
        else:
            self._load_image()


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 3 — SAM PROCESSING + COMPOSITING
# ═══════════════════════════════════════════════════════════════════════════

def load_predictor():
    try:
        from segment_anything import sam_model_registry, SamPredictor
    except ImportError:
        sys.exit("[ERROR] segment-anything not installed.")
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[SAM] Loading '{MODEL_TYPE}' on {device} …")
    sam = sam_model_registry[MODEL_TYPE](checkpoint=SAM_CHECKPOINT)
    sam.to(device=device)
    return SamPredictor(sam)


def segment_with_box(predictor, image_rgb: np.ndarray,
                     box: tuple[int,int,int,int]) -> np.ndarray:
    """
    Run SAM with a single box prompt.  Returns the best binary mask.
    box = (x1, y1, x2, y2) in original image pixel coordinates.
    """
    predictor.set_image(image_rgb)
    x1, y1, x2, y2 = box
    input_box = np.array([[x1, y1, x2, y2]], dtype=float)
    masks, scores, _ = predictor.predict(
        box              = input_box,
        multimask_output = True,
    )
    best = masks[int(np.argmax(scores))].astype(np.uint8)
    return largest_connected_component(best)


def save_sample(img_pil: Image.Image, label_str: str,
                fname: str, dirs: dict, counters: dict):
    split  = 'train' if random.random() < TRAIN_RATIO else 'val'
    img_fp = dirs[f'{split}_images'] / f"{fname}.jpg"
    lbl_fp = dirs[f'{split}_labels'] / f"{fname}.txt"
    img_pil.save(str(img_fp), quality=95)
    lbl_fp.write_text(label_str)
    counters['total']  += 1
    counters[split]    += 1


def process_annotations(boxes: dict[Path, tuple]):
    """
    保存标注信息到JSON文件，供远程电脑处理
    """
    if not boxes:
        print("[INFO] No annotations to process.")
        return

    # 构建标注信息
    annotations = []
    for img_path, box in tqdm(boxes.items(), desc="Saving annotations", unit="img"):
        # 确保框选数据有效
        valid_boxes = []
        if isinstance(box, (list, tuple)) and len(box) == 4:
            # 确保框选坐标有效
            x1, y1, x2, y2 = box
            if x1 < x2 and y1 < y2:
                valid_boxes.append(box)
        
        if not valid_boxes:
            print(f"[INFO] Skipping {img_path} - no valid boxes")
            continue
        
        # 推导类别
        cls_name = derive_class(img_path)
        
        # 构建标注项
        annotation = {
            'image_path': str(img_path),
            'relative_path': str(img_path.relative_to(LOCAL_ORIGIN_DIR)),
            'boxes': valid_boxes,
            'class_name': cls_name
        }
        annotations.append(annotation)
    
    # 保存标注信息
    if annotations:
        save_annotations(annotations, LOCAL_ANNOTATIONS_FILE)
        print(f"\n[INFO] Total {len(annotations)} images annotated")
        print("[INFO] Please transfer the following files to your cloud server:")
        print(f"1. Annotations file: {LOCAL_ANNOTATIONS_FILE}")
        print(f"2. All annotated images in: {LOCAL_ORIGIN_DIR}")
        print(f"3. Background images in: {LOCAL_BACKGROUND_DIR}")
        print("\n[INFO] Then run the remote processing script on the cloud server.")
    else:
        print("[INFO] No valid annotations to save")


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    random.seed(None)   # use OS entropy so each run is different

    # ── Phase 1: select files ──────────────────────────────────────────────
    root1 = tk.Tk()
    app1  = FileSelectorApp(root1)
    root1.mainloop()

    if not app1.result:
        print("[INFO] No images selected. Exiting.")
        return

    print(f"[INFO] {len(app1.result)} image(s) selected for manual annotation.")

    # ── Phase 2: draw boxes ────────────────────────────────────────────────
    root2 = tk.Tk()
    app2  = AnnotatorApp(root2, app1.result)
    root2.mainloop()

    if not app2.boxes:
        print("[INFO] No boxes were drawn. Exiting.")
        return

    print(f"[INFO] {len(app2.boxes)} image(s) annotated. Starting SAM + compositing …\n")

    # ── Phase 3: SAM + composite + save ───────────────────────────────────
    process_annotations(app2.boxes)


if __name__ == '__main__':
    main()