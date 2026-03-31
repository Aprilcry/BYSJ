#!/usr/bin/env python3
"""
YOLOv8 训练脚本
用于在云电脑上训练食材检测模型
"""

import os
import time
import argparse
from ultralytics import YOLO

def parse_args():
    parser = argparse.ArgumentParser(description='YOLOv8 训练脚本')
    parser.add_argument('--data', type=str, default='yolov8_dataset/data.yaml',
                        help='数据集配置文件路径')
    parser.add_argument('--model', type=str, default='yolov8x.pt',
                        help='预训练模型路径')
    parser.add_argument('--epochs', type=int, default=100,
                        help='训练轮数')
    parser.add_argument('--batch', type=int, default=16,
                        help='批次大小')
    parser.add_argument('--imgsz', type=int, default=640,
                        help='输入图像大小')
    parser.add_argument('--name', type=str, default='yolov8_ingredient',
                        help='训练结果保存名称')
    parser.add_argument('--device', type=str, default='0',
                        help='使用的设备 (0 for GPU, cpu for CPU)')
    return parser.parse_args()

def train_yolov8(args):
    """训练YOLOv8模型"""
    print("=" * 80)
    print("开始YOLOv8训练")
    print(f"数据集: {args.data}")
    print(f"预训练模型: {args.model}")
    print(f"训练轮数: {args.epochs}")
    print(f"批次大小: {args.batch}")
    print(f"输入大小: {args.imgsz}")
    print(f"保存名称: {args.name}")
    print(f"使用设备: {args.device}")
    print("=" * 80)
    
    # 加载模型
    model = YOLO(args.model)
    
    # 训练模型
    start_time = time.time()
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        name=args.name,
        device=args.device,
        exist_ok=True,
        pretrained=True,
        patience=10,  # 早停耐心值
        save_period=10  # 每10个epoch保存一次
    )
    
    end_time = time.time()
    training_time = end_time - start_time
    
    print("\n" + "=" * 80)
    print("训练完成！")
    print(f"总训练时间: {training_time:.2f}秒 ({training_time/3600:.2f}小时)")
    print("\n训练结果:")
    print(f"最佳模型: {results.best}")
    print(f"最终模型: {results.last}")
    
    # 打印评价指标
    if hasattr(results, 'metrics'):
        print("\n评价指标:")
        print(f"mAP@0.5: {results.metrics['map50']:.4f}")
        print(f"mAP@0.5:0.95: {results.metrics['map']:.4f}")
        print(f"精确率: {results.metrics['precision']:.4f}")
        print(f"召回率: {results.metrics['recall']:.4f}")
        print(f"F1分数: {results.metrics['f1']:.4f}")
    
    print("\n" + "=" * 80)
    print("训练完成。最佳模型已保存到 runs/detect/ 目录下。")
    print("请将最佳模型下载到本地使用。")
    print("=" * 80)

def main():
    args = parse_args()
    train_yolov8(args)

if __name__ == '__main__':
    main()
