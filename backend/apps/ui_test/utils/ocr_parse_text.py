# -*- coding: utf-8 -*-
import cv2
import numpy as np
from PIL import Image, ImageEnhance
import os
import logging
from time import sleep, time
from airtest.core.api import G, sleep as airtest_sleep
import re
import hashlib
from functools import lru_cache
from typing import List, Optional
import easyocr


# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def scale_coordinates(dic, ref_resolution=(1920, 1080)):
    """
    动态缩放坐标以适配不同分辨率
    """
    # 获取当前设备分辨率
    current_resolution = G.DEVICE.display_info['width'], G.DEVICE.display_info['height']
    current_w, current_h = current_resolution
    ref_w, ref_h = ref_resolution

    # 计算缩放比例
    scale_x = current_w / ref_w
    scale_y = current_h / ref_h

    # 缩放坐标
    x1, y1, x2, y2 = dic
    scaled_x1 = int(x1 * scale_x)
    scaled_y1 = int(y1 * scale_y)
    scaled_x2 = int(x2 * scale_x)
    scaled_y2 = int(y2 * scale_y)

    return scaled_x1, scaled_y1, scaled_x2, scaled_y2


def crop_image(img, dic):
    """
    裁剪图像
    """
    x1, y1, x2, y2 = dic
    return img[y1:y2, x1:x2]


def cv2_2_pil(cv2_image):
    """
    将OpenCV图像转换为PIL图像
    """
    return Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB))

class OCRParseText:
    # OCR结果缓存：key为(坐标区域hash, 图片hash)，value为(识别结果, 时间戳)
    _ocr_cache = {}
    _cache_ttl = 2.0  # 缓存有效期2秒
    _cache_max_size = 50  # 最大缓存条目数
    
    # 仅使用 EasyOCR 作为 OCR 引擎
    _ocr_engine = 'easyocr'
    
    # EasyOCR reader实例（延迟初始化）
    _easyocr_reader = None
    
    @classmethod
    def _get_easyocr_reader(cls):
        """获取或创建EasyOCR reader实例（延迟初始化）"""
        if cls._easyocr_reader is None:
            try:
                logger.info("初始化EasyOCR reader（首次使用会下载模型，可能需要一些时间）...")
                cls._easyocr_reader = easyocr.Reader(['en'], gpu=False)  # 只使用英文，不使用GPU
                logger.info("EasyOCR reader初始化完成")
            except Exception as e:
                logger.error(f"EasyOCR初始化失败: {e}")
                raise
        return cls._easyocr_reader
    
    @classmethod
    def _get_image_hash(cls, img):
        """计算图片的hash值用于缓存"""
        if isinstance(img, Image.Image):
            img_array = np.array(img)
        else:
            img_array = img
        return hashlib.md5(img_array.tobytes()).hexdigest()
    
    @classmethod
    def _get_cache_key(cls, dic, img_hash):
        """生成缓存key"""
        return (tuple(dic), img_hash)
    
    @classmethod
    def _clean_cache(cls):
        """清理过期缓存"""
        current_time = time()
        expired_keys = [
            key for key, (_, timestamp) in cls._ocr_cache.items()
            if current_time - timestamp > cls._cache_ttl
        ]
        for key in expired_keys:
            cls._ocr_cache.pop(key, None)
        
        # 如果缓存仍然太大，删除最旧的条目
        if len(cls._ocr_cache) > cls._cache_max_size:
            sorted_items = sorted(
                cls._ocr_cache.items(),
                key=lambda x: x[1][1]  # 按时间戳排序
            )
            # 删除最旧的一半
            for key, _ in sorted_items[:len(sorted_items)//2]:
                cls._ocr_cache.pop(key, None)

    def process_red_background_image(self, img_cv, mode='auto', use_binary2=False):

        """
        处理红色背景上的白色文字（如BET图片）
        使用简单有效的图像处理方法，确保数字能够被正确识别
        """
        # 转换为灰度图
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 针对数字识别优化，特别是5和2的区分
        # 计算图片统计信息
        mean_val = np.mean(gray)
        std_val = np.std(gray)
        # 减少日志输出以提高性能
        # logger.info(f"图片像素统计 - 平均值: {mean_val:.2f}, 标准差: {std_val:.2f}")
        
        mode = (mode or 'auto').lower()
        if mode == 'otsu':
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            logger.debug("预处理模式: otsu")
        elif mode == 'fixed150':
            _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
            logger.debug("预处理模式: fixed150")
        elif mode == 'high180':
            _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
            logger.debug("预处理模式: high180")
        else:
            if mean_val > 70:
                _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
                logger.debug("预处理模式: auto -> high180")
            else:
                if mean_val > 200:
                    adaptive_thresh = min(220, mean_val - std_val * 0.1)
                elif mean_val > 150:
                    adaptive_thresh = mean_val - std_val * 0.1
                else:
                    adaptive_thresh = mean_val + std_val * 0.1
                _, binary = cv2.threshold(gray, adaptive_thresh, 255, cv2.THRESH_BINARY_INV)
                logger.debug(f"预处理模式: auto -> adaptive ({adaptive_thresh:.2f})")
        
        # 适度缩放以提高分辨率
        height, width = binary.shape
        processed = cv2.resize(binary, (width*4, height*4), interpolation=cv2.INTER_CUBIC)
        
        
        return Image.fromarray(processed)

    def easyocr_ocr(self, img, ref_resolution=(1920, 1080), cache_key=None, bet_mode=False):
        """
        使用EasyOCR识别图片中的文字。
        
        Args:
            img: PIL Image对象或OpenCV图像
            ref_resolution: 参考分辨率
            cache_key: 缓存key，如果提供则使用缓存
            bet_mode: 是否使用bet模式（目前EasyOCR不需要特殊配置）
        Returns:
            str: 识别出的文本
        """
        # 检查缓存
        if cache_key and cache_key in self._ocr_cache:
            result, timestamp = self._ocr_cache[cache_key]
            if time() - timestamp < self._cache_ttl:
                logger.debug(f"使用缓存OCR结果: {result}")
                return result
        
        try:
            reader = self._get_easyocr_reader()
            if reader is None:
                raise RuntimeError("EasyOCR reader 初始化失败")
            
            # 转换为numpy数组并进行预处理
            if isinstance(img, Image.Image):
                # 使用 PIL 转换，避免依赖 OpenCV 的 cvtColor
                if img.mode == 'RGBA':
                    # RGBA 转 RGB
                    img = img.convert('RGB')
                elif img.mode == 'L':
                    # 灰度图转 RGB
                    img = img.convert('RGB')
                elif img.mode != 'RGB':
                    # 其他模式转 RGB
                    img = img.convert('RGB')
                
                # 图像预处理：放大以提高识别准确率
                # 如果图片较小，放大2倍
                width, height = img.size
                if width < 1000 or height < 200:
                    scale_factor = 2
                    # 使用 Resampling.LANCZOS（PIL 10.0+）或回退到 LANCZOS
                    resampling = getattr(Image, 'Resampling', Image).LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS  # type: ignore[attr-defined]
                    img = img.resize((width * scale_factor, height * scale_factor), resampling)
                    logger.debug(f"EasyOCR预处理：图片放大 {scale_factor} 倍 ({width}x{height} -> {width*scale_factor}x{height*scale_factor})")
                
                img_array = np.array(img)
            else:
                img_array = img
                # 如果是 numpy 数组，确保是 RGB 格式
                if len(img_array.shape) == 2:
                    # 灰度图，转换为 RGB
                    img_array = np.stack([img_array] * 3, axis=-1)
                elif img_array.shape[2] == 4:
                    # RGBA，转换为 RGB
                    img_array = img_array[:, :, :3]
            
            # EasyOCR识别
            results = reader.readtext(img_array)
            
            # 提取文本，只保留数字和逗号，并按从左到右的顺序排序
            text_items = []
            for (bbox, text, confidence) in results:
                # 对于数字识别，统一使用更低的置信度阈值（0.3）
                # 因为数字相对简单，即使置信度较低也可能是正确的
                # 特别是对于大数字（如 150,000,000），后面的部分可能被识别为多个区域，
                # 每个区域的置信度可能较低，但组合起来是正确的
                # 使用 0.3 的阈值可以捕获这些低置信度但正确的数字区域
                min_confidence = 0.3
                # 确保 confidence 是数字类型
                confidence_float = float(confidence) if not isinstance(confidence, (int, float)) else confidence
                if confidence_float < min_confidence:
                    continue
                # 只保留包含数字的文本
                if any(ch.isdigit() for ch in text):
                    # 计算 bbox 的 x 坐标（使用左上角的 x 坐标）
                    # bbox 格式：[[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                    x_coord = bbox[0][0]  # 左上角的 x 坐标
                    text_items.append((x_coord, text, confidence_float))
                    logger.info(f"EasyOCR识别 | 文本: '{text}', 置信度: {confidence:.2f}, x坐标: {x_coord:.1f}")
            
            # 按照 x 坐标从左到右排序
            text_items.sort(key=lambda x: x[0])
            
            # 提取排序后的文本
            texts = [item[1] for item in text_items]
            
            # 合并所有文本
            combined_text = ' '.join(texts)
            
            # 后处理：修复常见的识别错误
            # 1. 将常见的误识别字符替换为数字
            #    'o' 或 'O' 在数字上下文中很可能是 '0'
            #    'l' 或 'I' 在数字上下文中很可能是 '1'
            #    '?' 在数字上下文中很可能是 '1'（数字1的误识别）
            if any(ch.isdigit() for ch in combined_text):
                # 在数字上下文中，将 '?' 替换为 '1'（数字1的误识别）
                combined_text = re.sub(r'(\d)\?+(\d)', r'\g<1>1\g<2>', combined_text)
                combined_text = re.sub(r'\?(\d)', r'1\g<1>', combined_text)
                combined_text = re.sub(r'(\d)\?', r'\g<1>1', combined_text)
                # 在数字上下文中，将所有的 'o' 和 'O' 替换为 '0'
                # 因为这是数字识别场景，'o'/'O' 都应该是 '0'
                combined_text = combined_text.replace('o', '0').replace('O', '0')
                # 将空格替换为逗号（在数字上下文中）
                combined_text = re.sub(r'(\d)\s+(\d)', r'\g<1>,\g<2>', combined_text)
            
            # 如果bet_mode，只保留数字和逗号（此时o已经被替换为0）
            if bet_mode:
                combined_text = re.sub(r'[^0-9,]', '', combined_text)
            
            # 缓存结果
            if cache_key:
                self._ocr_cache[cache_key] = (combined_text, time())
                self._clean_cache()
            
            logger.info(f"EasyOCR最终结果: '{combined_text.strip()}'")
            return combined_text.strip()
            
        except Exception as e:
            logger.error(f"EasyOCR识别失败: {e}")
            return ""
    
    # 处理图片颜色并识别
    def screen_info(self, dic, ref_resolution=(1920, 1080), output_dir=None):
        """
        截取屏幕指定区域并保存图像，适配分辨率。
        统一使用对比度增强处理，不使用红色背景处理。

        Args:
            dic: 坐标元组 (x1, y1, x2, y2)
            ref_resolution: 参考分辨率，默认为 (1920, 1080)
            output_dir: 保存图像的目录，如果为None则使用默认路径（game_test/images）
        Returns:
            PIL.Image: 裁剪后的图像
        """
        # 如果未指定输出目录，使用默认路径（game_test/images）
        if output_dir is None:
            # 获取当前文件所在目录，然后找到 game_test/images
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # current_dir 是 backend/apps/game_test/utils，需要向上一级到 game_test
            game_test_dir = os.path.dirname(current_dir)
            output_dir = os.path.join(game_test_dir, "images")
        try:
            # 优化：减少等待时间，从1秒减少到0.3秒
            airtest_sleep(0.5)
            screen = G.DEVICE.snapshot()
            if screen is None:
                raise RuntimeError("截图失败，snapshot 返回 None")

            # 动态缩放坐标
            scaled_dic = scale_coordinates(dic, ref_resolution)
            # 减少日志输出
            # logging.info(f"原始坐标: {dic}, 缩放后坐标: {scaled_dic}")

            # 验证坐标
            h, w = screen.shape[:2]
            x1, y1, x2, y2 = scaled_dic
            if x1 < 0 or y1 < 0 or x2 > w or y2 > h or x1 >= x2 or y1 >= y2:
                raise ValueError(f"裁剪坐标无效: {scaled_dic}, 屏幕尺寸: {w}x{h}")

            # 裁剪图像
            screen_img = crop_image(screen, scaled_dic)
            screen_img = cv2_2_pil(screen_img)
            
            # 保存原始图片副本（在任何处理之前）
            original_screen_img = screen_img.copy()
            
            # 统一使用对比度增强处理
            img = ImageEnhance.Contrast(screen_img).enhance(2.5)

            if screen_img.mode == 'RGBA':
                img = screen_img.convert('RGB')

            # 保存裁剪图像（可选，减少I/O操作）
            os.makedirs(output_dir, exist_ok=True)
            # 使用设备ID作为文件名标识
            engineer = os.environ.get('TEST_ENGINEER')
            if not engineer:
                raise ValueError("未设置环境变量 TEST_ENGINEER，必须提供工程师名称")
            # 尝试从G.DEVICE获取设备ID
            try:
                device_id = G.DEVICE.uuid if hasattr(G.DEVICE, 'uuid') and G.DEVICE.uuid else (G.DEVICE.serialno if hasattr(G.DEVICE, 'serialno') else 'unknown')
                # 将设备ID中的特殊字符替换为下划线（文件名安全）
                device_id = device_id.replace(':', '_').replace('/', '_')
            except Exception:
                device_id = 'unknown'
            output_path = f'{output_dir}/tpl_admin_img_{engineer}_{device_id}.png'
            img.save(output_path, quality=99, optimize=True)
            logging.info(f"已保存截图: {output_path}")
            

            # 将原始图片副本保存到img对象中，以便后续备用逻辑使用
            img.original_copy = original_screen_img  # type: ignore[attr-defined]

            return img

        except Exception as e:
            logging.error(f"截图失败: {str(e)}")
            raise

    def ocr_for_num(self, text, bet_mode: bool = False) -> int:
        """
        将图片中的文字转换为数字
        功能：识别BET图片（红色背景白色文字）中的文本，提取其中的数字
        
        优化：如果图片包含"BET"，只识别BET后面的数字；否则维持原逻辑
        """
        # 初始化cleaned_text变量
        cleaned_text = text
        try:
            not_get_gift = "GOODLUCK"
            if not_get_gift in cleaned_text:
                print("GOODLUCK")
                logger.info("此局未中奖--未获取到奖励")
                return 0

            if bet_mode:
                logger.info("包含BET字符模式：解析BET后面的数字")
                cleaned_text = re.sub(r'[^0-9,]', '', text)
            else:
                logger.info("通用模式：清理文本后解析数字")
                # 先将 '?' 替换为 '1'（数字1的误识别），然后再清理
                text_with_1 = re.sub(r'(\d)\?+(\d)', r'\g<1>1\g<2>', text)
                text_with_1 = re.sub(r'\?(\d)', r'1\g<1>', text_with_1)
                text_with_1 = re.sub(r'(\d)\?', r'\g<1>1', text_with_1)
                cleaned_text = re.sub(r'[^一-龥\w,]', '', text_with_1.replace('\n', ''))

            digits = ''.join(filter(lambda x: x.isdigit() or x == ',', cleaned_text))
            try:
                number = int(digits.replace(',', '')) if digits else 0
                print(f"提取的数字: {number}")
                return number
            except ValueError:
                print(f"清理后的文本: {cleaned_text}")
                if digits:
                    logging.error(f"无法将提取的数字字符串转为整数: {digits}")
                else:
                    logging.error(f"未提取到有效数字: {cleaned_text}")
                return 0
        except Exception as e:
            logging.error(f"处理文本时发生错误: {str(e)}")
            return 0
        
    # 图片处理成文字是否成功
    def ocr_for_num_method(self, dic, ref_resolution=(1920, 1080), bet_mode=False):
        """
        调用screen_info获取图片，并通过OCR引擎和ocr_for_num识别图片中的数字。
        仅使用 EasyOCR 进行识别。
        优化：添加缓存机制，避免重复识别相同区域。
        统一使用对比度增强处理，不使用红色背景处理。
        
        Args:
            dic: 坐标元组 (x1, y1, x2, y2)
            ref_resolution: 参考分辨率，默认为 (1920, 1080)
            bet_mode: 是否使用bet模式（影响文本后处理逻辑），默认为False
        """
        try:
            # 统一使用对比度增强处理，不使用红色背景处理
            img = self.screen_info(dic, ref_resolution=ref_resolution)
            img_hash = self._get_image_hash(img)
            cache_key = self._get_cache_key(dic, img_hash)
            
            text = self.easyocr_ocr(img, ref_resolution=ref_resolution, cache_key=cache_key, bet_mode=bet_mode)
            
            # 调用ocr_for_num提取文字中的数字
            result = self.ocr_for_num(text, bet_mode=bet_mode)
            return result
        except Exception as e:
            logging.error(f"识别图片中的数字失败: {str(e)}")
            raise
    

    def capture_multiple_screenshots(self, dic=(190, 15, 490, 60), count=5, output_dir=None, ref_resolution=(1920, 1080)):
        """
        进行多次截图并保存到指定目录
        
        Args:
            dic: 坐标元组 (x1, y1, x2, y2)，默认为(190, 15, 490, 60)
            count: 截图次数，默认为5次
            output_dir: 保存图像的目录，如果为None则使用默认路径（game_test/images）
            ref_resolution: 参考分辨率，默认为(1920, 1080)
        """
        try:
            # 如果未指定输出目录，使用默认路径（game_test/images）
            if output_dir is None:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # current_dir 是 backend/apps/game_test/utils，需要向上一级到 game_test
                game_test_dir = os.path.dirname(current_dir)
                output_dir = os.path.join(game_test_dir, "images")
            
            os.makedirs(output_dir, exist_ok=True)
            
            for i in range(count):
                # 使用现有的screen_info方法进行截图
                img = self.screen_info(dic, ref_resolution=ref_resolution, output_dir=output_dir)
                
                # 保存截图，文件名包含序号
                output_path = f'{output_dir}/screenshot_{i+1}.png'
                img.save(output_path, quality=99, optimize=True)
                logging.info(f"已保存截图 {i+1}/{count}: {output_path}")
                
                # 等待一段时间再进行下一次截图
                airtest_sleep(1)
                
            logging.info(f"完成 {count} 次截图，保存在 {output_dir} 目录中")
            
        except Exception as e:
            logging.error(f"截图过程中发生错误: {str(e)}")
            raise

   