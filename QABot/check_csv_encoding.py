# check_csv_encoding.py
"""
检查CSV文件编码的工具
用于检测doctor/nodes和doctor/relations目录下所有CSV文件的编码格式
"""

import os
import csv
import chardet
from pathlib import Path


class CSVEncodingChecker:
    """CSV文件编码检测器"""

    def __init__(self):
        self.encodings_to_try = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'utf-16le', 'utf-16be', 'cp1252', 'latin1']

    def detect_encoding_chardet(self, file_path):
        """使用chardet库检测文件编码"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                return result['encoding'], result['confidence']
        except Exception as e:
            return None, 0.0

    def try_read_with_encoding(self, file_path, encoding, max_lines=5):
        """尝试用指定编码读取文件"""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                lines = []
                for i, row in enumerate(reader):
                    if i >= max_lines:
                        break
                    lines.append(row)
                return True, lines, None
        except UnicodeDecodeError as e:
            return False, None, str(e)
        except Exception as e:
            return False, None, str(e)

    def check_file_encoding(self, file_path):
        """检查单个文件的编码"""
        print(f"\n{'='*60}")
        print(f"检查文件: {file_path}")
        print(f"{'='*60}")

        # 首先使用chardet检测
        detected_encoding, confidence = self.detect_encoding_chardet(file_path)
        print(f"chardet检测结果: {detected_encoding} (置信度: {confidence:.2f})")

        # 尝试不同的编码
        successful_encodings = []

        for encoding in self.encodings_to_try:
            success, lines, error = self.try_read_with_encoding(file_path, encoding)
            if success:
                successful_encodings.append(encoding)
                print(f"\n✅ {encoding} 编码读取成功!")
                print("前几行内容:")
                for i, row in enumerate(lines):
                    print(f"  行 {i+1}: {row}")
            else:
                print(f"❌ {encoding} 编码读取失败: {error}")

        if successful_encodings:
            print(f"\n🎯 成功编码: {', '.join(successful_encodings)}")
            return successful_encodings[0]  # 返回第一个成功的编码
        else:
            print("\n❌ 所有编码都无法正确读取文件")
            return None

    def check_directory(self, directory_path):
        """检查目录下所有CSV文件的编码"""
        directory = Path(directory_path)

        if not directory.exists():
            print(f"目录不存在: {directory_path}")
            return

        print(f"\n{'='*80}")
        print(f"检查目录: {directory_path}")
        print(f"{'='*80}")

        csv_files = list(directory.glob("*.csv"))
        print(f"发现 {len(csv_files)} 个CSV文件")

        results = {}

        for csv_file in csv_files:
            encoding = self.check_file_encoding(csv_file)
            results[str(csv_file)] = encoding

        return results

    def analyze_all_directories(self):
        """分析所有相关目录"""
        base_dir = Path(__file__).parent

        directories_to_check = [
            base_dir / "doctor" / "nodes",
            base_dir / "doctor" / "relations"
        ]

        all_results = {}

        for directory in directories_to_check:
            if directory.exists():
                results = self.check_directory(directory)
                all_results[str(directory)] = results
            else:
                print(f"目录不存在: {directory}")

        return all_results


def main():
    """主函数"""
    print("CSV文件编码检测工具")
    print("=" * 80)

    checker = CSVEncodingChecker()
    results = checker.analyze_all_directories()

    print("\n" + "="*80)
    print("总结报告")
    print("="*80)

    encoding_stats = {}

    for dir_path, file_results in results.items():
        print(f"\n目录: {dir_path}")
        if file_results:
            for file_path, encoding in file_results.items():
                print(f"  {Path(file_path).name}: {encoding}")
                if encoding:
                    encoding_stats[encoding] = encoding_stats.get(encoding, 0) + 1
        else:
            print("  无CSV文件")

    print("\n编码使用统计:")
    for encoding, count in encoding_stats.items():
        print(f"  {encoding}: {count} 个文件")

    # 给出建议
    print("\n建议:")
    if encoding_stats.get('gbk', 0) > 0:
        print("  - 大部分文件使用GBK编码，这是中文Windows系统的常见编码")
    if encoding_stats.get('utf-8', 0) > 0:
        print("  - 部分文件使用UTF-8编码")
    if len(encoding_stats) > 1:
        print("  - 文件编码不统一，建议在导入时使用自动检测编码的功能")


if __name__ == "__main__":
    main()
