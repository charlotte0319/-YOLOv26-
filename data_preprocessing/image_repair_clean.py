"""
data_preprocessing/image_repair_clean.py

作用：
- 清理 SKU110K 图片中的损坏文件，并重写可读图片以修复异常字节。

实现方式：
- 遍历 train/val/test 的 jpg 文件。
- 使用 OpenCV 读取并回写；读取失败视为损坏并跳过。

关键函数：
- repair_and_validate_image(img_path)
- collect_images()
- main()

调用方式：
- python data_preprocessing/image_repair_clean.py
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOT_DIR = PROJECT_ROOT / "data" / "SKU110K_fixed" / "images"


def repair_and_validate_image(img_path: Path) -> int:
    """修复单张图像：可读返回 1，不可读返回 0。"""
    image = cv2.imread(str(img_path))
    if image is None:
        print(f"[修复] 检测到损坏图片，已跳过：{img_path.name}")
        return 0

    cv2.imwrite(str(img_path), image)
    return 1


def collect_images() -> list[Path]:
    """收集 train/val/test 下所有 jpg 图片。"""
    images = []
    for split in ("train", "val", "test"):
        split_dir = ROOT_DIR / split
        if split_dir.exists():
            images.extend(split_dir.glob("*.jpg"))
    return images


def main() -> None:
    """脚本入口。"""
    print("[修复] 图片修复任务启动。")
    all_images = collect_images()
    print(f"[修复] 共发现 {len(all_images)} 张图片。")

    with ThreadPoolExecutor(max_workers=16) as executor:
        processed = list(
            tqdm(
                executor.map(repair_and_validate_image, all_images),
                total=len(all_images),
                desc="修复进度",
                unit="张",
            )
        )

    print(f"[修复] 完成，成功重写 {sum(processed)} 张可读图片。")


if __name__ == "__main__":
    main()
