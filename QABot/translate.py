# Rn7d_d52bhcq5aift16l9ufu0


import os
import pandas as pd
import csv
import hashlib
import random
import time
import json
from urllib import parse
import requests
from typing import List, Dict, Any, Optional
import chardet
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaiduTranslator:
    """百度翻译API封装类"""
    
    def __init__(self, app_id: str, secret_key: str):
        self.app_id = app_id
        self.secret_key = secret_key
        self.base_url = "https://fanyi-api.baidu.com/ait/api/aiTextTranslate"
        
    def translate(self, text: str, from_lang: str = 'zh', to_lang: str = 'en') -> Optional[str]:
        """
        翻译单条文本
        """
        if not text or not text.strip():
            return text
            
        try:
            # 生成签名
            salt = str(random.randint(32768, 65536))
            sign_str = self.app_id + text + salt + self.secret_key
            sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
            
            # 构建请求参数
            params = {
                'q': text,
                'from': from_lang,
                'to': to_lang,
                'appid': self.app_id,
                'salt': salt,
                'sign': sign
            }
            
            # 发送请求
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            # 检查是否有错误
            if 'error_code' in result:
                logger.error(f"翻译错误: {result.get('error_msg', 'Unknown error')}")
                return None
                
            # 提取翻译结果
            translated_text = result.get('trans_result', [{}])[0].get('dst', '')
            return translated_text
            
        except Exception as e:
            logger.error(f"翻译失败: {str(e)}")
            return None
    
    def translate_batch(self, texts: List[str], from_lang: str = 'zh', to_lang: str = 'en') -> List[Optional[str]]:
        """
        批量翻译文本
        注意：百度API有限制，每次最多2000字符
        """
        results = []
        for text in texts:
            # 避免频繁请求
            time.sleep(0.1)  # 控制请求频率
            translated = self.translate(text, from_lang, to_lang)
            results.append(translated)
        return results


class CSVTranslator:
    """CSV文件翻译处理器"""
    
    def __init__(self, translator: BaiduTranslator):
        self.translator = translator
        
    def detect_encoding(self, file_path: str) -> str:
        """
        检测文件编码
        """
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # 读取前10000字节用于检测
                result = chardet.detect(raw_data)
                encoding = result['encoding'] if result['encoding'] else 'utf-8'
                
                # 处理常见的编码别名
                encoding_map = {
                    'GB2312': 'gbk',
                    'GBK': 'gbk',
                    'GB18030': 'gb18030',
                    'Big5': 'big5',
                    'UTF-8': 'utf-8',
                    'UTF-16': 'utf-16',
                    'UTF-16LE': 'utf-16-le',
                    'UTF-16BE': 'utf-16-be',
                    'ISO-8859-1': 'latin1',
                    'Windows-1252': 'cp1252'
                }
                
                return encoding_map.get(encoding, 'utf-8')
                
        except Exception as e:
            logger.warning(f"检测编码失败 {file_path}: {str(e)}，使用utf-8")
            return 'utf-8'
    
    def read_csv_with_encoding(self, file_path: str) -> pd.DataFrame:
        """
        自动检测编码并读取CSV文件
        """
        encoding = self.detect_encoding(file_path)
        logger.info(f"检测到文件编码: {encoding} - {file_path}")
        
        try:
            # 尝试多种读取方式
            df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip')
            return df
        except Exception as e:
            logger.error(f"读取CSV失败 {file_path}: {str(e)}")
            # 尝试其他可能的编码
            fallback_encodings = ['utf-8-sig', 'gbk', 'gb18030', 'latin1']
            for enc in fallback_encodings:
                try:
                    df = pd.read_csv(file_path, encoding=enc, on_bad_lines='skip')
                    logger.info(f"使用备选编码 {enc} 成功读取")
                    return df
                except:
                    continue
            raise Exception(f"无法读取文件 {file_path}")
    
    def needs_translation(self, value: Any) -> bool:
        """
        判断是否需要翻译
        """
        if pd.isna(value):
            return False
        if isinstance(value, (int, float)):
            return False
        if isinstance(value, str) and value.strip() == '':
            return False
        # 检查是否已经是英文（简单判断）
        if isinstance(value, str):
            # 如果大部分字符是ASCII，可能已经是英文
            ascii_count = sum(1 for c in value if ord(c) < 128)
            if ascii_count / len(value) > 0.7:
                return False
        return True
    
    def translate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        翻译DataFrame中的所有文本列
        """
        df_translated = df.copy()
        total_cells = df.size
        translated_count = 0
        
        logger.info(f"开始翻译，共 {total_cells} 个单元格")
        
        for col in df.columns:
            logger.info(f"处理列: {col}")
            for idx, value in enumerate(df[col]):
                if self.needs_translation(value):
                    try:
                        translated = self.translator.translate(str(value))
                        if translated:
                            df_translated.at[idx, col] = translated
                            translated_count += 1
                        
                        # 显示进度
                        if (idx + 1) % 10 == 0:
                            logger.info(f"列 {col}: 已处理 {idx + 1}/{len(df)} 行")
                            
                        # 避免请求过于频繁
                        time.sleep(0.2)
                        
                    except Exception as e:
                        logger.error(f"翻译失败 ({col}, 行{idx}): {str(e)}")
                        # 保留原始值
                        df_translated.at[idx, col] = value
        
        logger.info(f"翻译完成，共翻译了 {translated_count} 个单元格")
        return df_translated
    
    def save_csv_with_original_format(self, df: pd.DataFrame, output_path: str, original_df: pd.DataFrame):
        """
        按照原始格式保存CSV文件
        """
        try:
            # 使用与原始DataFrame相同的参数保存
            df.to_csv(output_path, index=False, encoding='utf-8')
            logger.info(f"已保存: {output_path}")
        except Exception as e:
            logger.error(f"保存文件失败 {output_path}: {str(e)}")
            # 尝试其他保存方式
            try:
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
            except Exception as e2:
                logger.error(f"备用保存方式也失败: {str(e2)}")


def process_folder(source_folder: str, target_folder: str, translator: BaiduTranslator):
    """
    处理整个文件夹
    """
    csv_translator = CSVTranslator(translator)
    
    # 遍历源文件夹
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            if file.lower().endswith('.csv'):
                # 构建完整路径
                source_path = os.path.join(root, file)
                
                # 构建目标路径，保持原有目录结构
                relative_path = os.path.relpath(root, source_folder)
                target_dir = os.path.join(target_folder, relative_path)
                target_path = os.path.join(target_dir, file)
                
                # 创建目标目录
                os.makedirs(target_dir, exist_ok=True)
                
                logger.info(f"处理文件: {source_path}")
                logger.info(f"保存到: {target_path}")
                
                try:
                    # 读取原始文件
                    df_original = csv_translator.read_csv_with_encoding(source_path)
                    logger.info(f"文件形状: {df_original.shape}")
                    logger.info(f"列名: {list(df_original.columns)}")
                    
                    # 翻译数据
                    df_translated = csv_translator.translate_dataframe(df_original)
                    
                    # 保存翻译后的文件
                    csv_translator.save_csv_with_original_format(
                        df_translated, 
                        target_path, 
                        df_original
                    )
                    
                    logger.info(f"完成处理: {file}\n")
                    
                except Exception as e:
                    logger.error(f"处理文件失败 {file}: {str(e)}\n")


def main():
    # 配置信息 - 请替换为您的百度翻译API信息
    BAIDU_APP_ID = "20251219002522466"  # 请替换
    # BAIDU_SECRET_KEY = "Rn7d_d52bhcq5aift16l9ufu0"  # 请替换
    BAIDU_SECRET_KEY = "Ca0y9plcUFKIakegFCrR"  # 请替换
    # Ca0y9plcUFKIakegFCrR
    
    # 路径配置
    SOURCE_FOLDER = r"G:\Workspace\Pycharm\PythonProject\QABot\doctor"
    TARGET_FOLDER = r"G:\Workspace\Pycharm\PythonProject\QABot\doctor_en"
    
    # 检查源文件夹是否存在
    if not os.path.exists(SOURCE_FOLDER):
        logger.error(f"源文件夹不存在: {SOURCE_FOLDER}")
        return
    
    # 创建目标文件夹
    os.makedirs(TARGET_FOLDER, exist_ok=True)
    
    # 初始化翻译器
    translator = BaiduTranslator(BAIDU_APP_ID, BAIDU_SECRET_KEY)
    
    # 测试翻译器连接
    logger.info("测试翻译API连接...")
    test_result = translator.translate("你好")
    if test_result:
        logger.info(f"API连接成功，测试翻译: 你好 -> {test_result}")
    else:
        logger.error("API连接失败，请检查APP ID和密钥")
        return
    
    # 处理nodes和relations文件夹
    subfolders = ['nodes', 'relations']
    
    for subfolder in subfolders:
        source_subfolder = os.path.join(SOURCE_FOLDER, subfolder)
        target_subfolder = os.path.join(TARGET_FOLDER, subfolder)
        
        if os.path.exists(source_subfolder):
            logger.info(f"\n{'='*50}")
            logger.info(f"开始处理文件夹: {subfolder}")
            logger.info(f"{'='*50}")
            
            process_folder(source_subfolder, target_subfolder, translator)
        else:
            logger.warning(f"文件夹不存在: {source_subfolder}")
    
    logger.info("\n" + "="*50)
    logger.info("所有文件处理完成！")
    logger.info(f"源文件夹: {SOURCE_FOLDER}")
    logger.info(f"目标文件夹: {TARGET_FOLDER}")
    logger.info("="*50)


if __name__ == "__main__":
    main()