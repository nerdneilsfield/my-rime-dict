import os
import sys
import re
import argparse
from pathlib import Path
import pypinyin
import itertools

# 定义中英文标点符号的正则表达式
# 中文标点：，。？！；：‘’"“（）【】《》、
# 英文标点：,.?!;:'"()[]<>
# PUNCTUATION_RE = re.compile(r'[\s,，.。？！；：‘’"“（）【】《》、,.?!;:\'"()\[\]<>]+')
PUNCTUATION_RE = re.compile(r'[\s,.。？！；：‘’"“（）【】、,.?!;:\'"()\[\]<>]+')

ONLY_ENGLISH_ALPHABET_RE = re.compile(r'^[a-zA-Z]+$')
    # 定义只匹配中文字符的正则表达式
CHINESE_CHAR_RE = re.compile(r'[\u4e00-\u9fff]+')

def check_valid_line(line):
    """检查行是否有效"""
    line = line.strip()
    if line.startswith("#"):
        return False
    if line == "":
        return False
    if ONLY_ENGLISH_ALPHABET_RE.match(line):
        return False
    return True

def only_keep_chinese_chars(line):
    """只保留中文字符"""
    chinese_chars = CHINESE_CHAR_RE.findall(line)
    return ''.join(chinese_chars)

def find_txt_files(input_dir):
    """递归查找指定目录下的所有 .txt 文件"""
    txt_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.txt'):
                txt_files.append(Path(root) / file)
    return txt_files

def process_line(line, unique_lines):
    """处理单行文本，根据标点和空格分割，并只保留中文部分"""
    line = line.strip()
    if not line:
        return

    # 统一使用正则表达式分割 (包含中英文标点和空格)
    segments = PUNCTUATION_RE.split(line)

    for segment in segments:
        segment = segment.strip()
        # 确保 segment 非空后再处理
        if segment:
            # 提取纯中文字符
            chinese_only_segment = only_keep_chinese_chars(segment)
            # 检查提取后的纯中文字符串是否有效，并添加到集合
            if chinese_only_segment and check_valid_line(chinese_only_segment):
                unique_lines.add(chinese_only_segment)

def merge_texts(input_dir, output_file, output_only_file):
    """合并文本文件""" 
    print(f"开始处理目录: {input_dir}")
    txt_files = find_txt_files(input_dir)
    if not txt_files:
        print("错误：在指定目录下未找到 .txt 文件。")
        sys.exit(1)

    print(f"找到 {len(txt_files)} 个 .txt 文件:")
    # for f in txt_files:
    #     print(f"  - {f}")

    unique_lines = set()
    
    comment_lines_num = 0
    empty_lines_num = 0
    english_lines_num = 0

    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as infile:
                for line in infile:
                    line_strip = line.strip()
                    if line_strip.startswith("#"):
                        comment_lines_num += 1
                        continue
                    if line_strip == "":
                        empty_lines_num += 1
                        continue
                    if ONLY_ENGLISH_ALPHABET_RE.match(line_strip):
                        english_lines_num += 1
                        continue
                    process_line(line_strip, unique_lines)
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")

    print(f"共找到 {len(unique_lines)} 条不重复的行。")
    print(f"注释行: {comment_lines_num}")
    print(f"空行: {empty_lines_num}")
    print(f"英文行: {english_lines_num}")

    try:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True) # 确保输出目录存在
        output_only_path = Path(output_only_file)
        output_only_path.parent.mkdir(parents=True, exist_ok=True) # 确保输出目录存在
        with open(output_path, 'w', encoding='utf-8') as outfile:
            output_lines = set() # 使用集合避免重复行
            for line in unique_lines:
                try:
                    # 生成拼音，包含多音字 heteronym=True
                    # 返回 [[读音1, 读音2], [读音]] 这样的列表
                    pinyin_lists = pypinyin.pinyin(line, style=pypinyin.Style.NORMAL, heteronym=False)

                    # 过滤掉非汉字字符导致的空列表（例如纯英文或数字行被意外加入）
                    valid_pinyin_lists = [p_list for p_list in pinyin_lists if p_list]
                    if not valid_pinyin_lists:
                        continue # 如果整行没有有效的拼音，跳过

                    # 使用 itertools.product 计算所有读音组合
                    # 例如: pinyin_lists = [['zhǎng', 'cháng'], ['zhě']] -> product -> (('zhǎng', 'zhě'), ('cháng', 'zhě'))
                    for pinyin_tuple in itertools.product(*valid_pinyin_lists):
                        # 将拼音元组连接成 'ni'hao' 这样的字符串
                        pinyin_str = "'".join(p for p in pinyin_tuple if p) # 过滤空拼音

                        if pinyin_str:
                            # 格式化输出： 文本	拼音	权重 (使用 Tab 分隔符)
                            formatted_line = f"{line} {pinyin_str} 0"
                            output_lines.add(formatted_line)
                except Exception as pinyin_error:
                    print(f"处理行 '{line}' 的拼音时出错: {pinyin_error}")
                    continue # 跳过出错的行

            # 对最终格式化的行进行排序
            sorted_lines = sorted(list(output_lines))
            print(f"整理后的行数: {len(sorted_lines)}")
            for formatted_line in sorted_lines:
                outfile.write(formatted_line + '\n')
        print(f"成功将结果写入: {output_path}")
        sorted_lines_only = sorted(list(unique_lines))
        with open(output_only_path, 'w', encoding='utf-8') as outfile:
            for formatted_line in sorted_lines_only:
                outfile.write(formatted_line + '\n')
        print(f"成功将结果写入: {output_only_path}")
    except Exception as e:
        print(f"写入输出文件 {output_file} 时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='递归合并目录下所有 txt 文件的行，去重并处理中英文标点。')
    parser.add_argument('input_dir', type=str, help='包含 txt 文件的输入目录路径')
    parser.add_argument('output_file', type=str, help='合并后的输出 txt 文件路径')
    parser.add_argument('output_only_file', type=str, help='合并后的输出不包含拼音的 txt 文件路径')

    args = parser.parse_args()

    input_directory = Path(args.input_dir)
    output_filepath = Path(args.output_file)
    output_only_filepath = Path(args.output_only_file)
    if not input_directory.is_dir():
        print(f"错误：输入路径 '{args.input_dir}' 不是一个有效的目录。")
        sys.exit(1)

    merge_texts(input_directory, output_filepath, output_only_filepath)
