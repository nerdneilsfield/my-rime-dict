import os
import sys
import re
import argparse
from pathlib import Path
import pypinyin
import time
from datetime import datetime
from typing import List, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

# 定义中英文标点符号的正则表达式
# 中文标点：，。？！；：""（）【】《》、
# 英文标点：,.?!;:'"()[]<>
# PUNCTUATION_RE = re.compile(r'[\s,，.。？！；：""（）【】《》、,.?!;:\'"()\[\]<>]+')
PUNCTUATION_RE = re.compile(r'[\s,.。？！；：，·""（）【】、,.?!;:\'"()\[\]<>]+')

ONLY_ENGLISH_ALPHABET_RE = re.compile(r'^[a-zA-Z]+$')
ONLY_NUMBER_RE = re.compile(r'^[0-9]+$')
ONLY_FLOAT_NUMBER_RE = re.compile(r'^[0-9]+\.[0-9]+$')
ONLY_ENGLISH_ALPHABET_AND_NUMBER_RE = re.compile(r'^[a-zA-Z0-9]+$')
ONLY_ENGLISH_ALPHABET_AND_NUMBER_AND_PUNCTUATION_RE = re.compile(r'^[a-zA-Z0-9,.?!;:\'"()\[\]<>-\u2013\u2014\u2212]+$')
    # 定义只匹配中文字符的正则表达式
NO_CHINESE_CHAR_RE = re.compile(r'^[^\u4e00-\u9fff]+$')
CHINESE_CHAR_RE = re.compile(r'[\u4e00-\u9fff]+')

#包含日文平假名和片假名
HAVE_JAPANESE_CHAR_RE = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]+')

ONLY_CHINESE_CHAR_RE = re.compile(r'^[\u4e00-\u9fff]+$')

CHINESE_PUNCTUATIONS = ["，", "。", "！", "？", "；", "：", "“", "”", "（", "）", "【", "】", "《", "》", "、"]

COMMENT_LINE_STARTS = ["#", "&", "*", "-", "=", "//"]

KEEP_REGEX = re.compile(r'^[A-Za-z0-9\u4e00-\u9fff，]+$')

start_time = 0
read_time = 0
set_time = 0
valid_time = 0
to_py_time = 0
from opencc import OpenCC
# 创建全局转换器（避免重复创建）
try:
    cc_t2s = OpenCC('t2s')
except Exception as e:
    print(f"Error initializing OpenCC: {e}")
    print("Please make sure you have installed 'opencc-python-reimplemented' and the dictionary files are accessible.")
    cc_t2s = None # 设置为 None，以便后续检查

def to_simplified(text: str) -> str:
    """将文本转换为简体中文，如果转换器初始化失败则返回原文"""
    if cc_t2s:
        try:
            return cc_t2s.convert(text)
        except Exception as e:
            print(f"Error converting text '{text[:20]}...': {e}")
            return text # 转换出错时返回原文
    else:
        return text

def remove_english_alphabet(line: str) -> str:
    """删除行中的英文单词"""
    return ONLY_ENGLISH_ALPHABET_RE.sub("", line)

def remove_english_alphabet_and_number(line: str) -> str:
    """删除行中的英文单词和数字"""
    return ONLY_ENGLISH_ALPHABET_AND_NUMBER_RE.sub("", line)

def remove_punctuation(line: str) -> str:
    """删除行中的标点符号"""
    res = line
    # res =  PUNCTUATION_RE.sub("", line)
    res = res.replace("♂", "")
    res = res.replace("♀", "")
    res = res.replace("《", "")
    res = res.replace("》", "")
    res = res.replace("【", "")
    res = res.replace("】", "")
    res = res.replace("（", "")
    res = res.replace("）", "")
    return res

def remove_english_alphabet_and_number_and_punctuation(line: str) -> str:
    """删除行中的英文单词、数字和标点符号"""
    return ONLY_ENGLISH_ALPHABET_AND_NUMBER_AND_PUNCTUATION_RE.sub("", line)

def remove_number(line: str) -> str:
    """删除行中的数字"""
    return ONLY_NUMBER_RE.sub("", line)

def remove_float_number(line: str) -> str:
    """删除行中的浮点数"""
    return ONLY_FLOAT_NUMBER_RE.sub("", line)

def check_valid_line(line) -> bool:
    """检查行是否有效"""
    line = line.strip()
    if NO_CHINESE_CHAR_RE.match(line):
        return False
    if any(line.startswith(start) for start in COMMENT_LINE_STARTS):
        return False
    if line == "":
        return False
    if ONLY_ENGLISH_ALPHABET_RE.match(line):
        return False
    if ONLY_NUMBER_RE.match(line):
        return False
    if ONLY_FLOAT_NUMBER_RE.match(line):
        return False
    if ONLY_ENGLISH_ALPHABET_AND_NUMBER_RE.match(line):
        return False
    if ONLY_ENGLISH_ALPHABET_AND_NUMBER_AND_PUNCTUATION_RE.match(line):
        return False
    if HAVE_JAPANESE_CHAR_RE.match(line):
        return False
    line = remove_english_alphabet(line)
    line = remove_english_alphabet_and_number(line)
    line = remove_english_alphabet_and_number_and_punctuation(line)
    line = remove_number(line)
    line = remove_float_number(line)
    if line == "":
        return False
    return True

def is_chinese_only(line) -> bool:
    """检查行是否只包含中文字符"""
    if ONLY_CHINESE_CHAR_RE.match(line):
        if not any(punctuation in line for punctuation in CHINESE_PUNCTUATIONS):
            return True
    return False

def only_keep_chinese_chars(line) -> str:
    """只保留中文字符"""
#     chinese_chars = CHINESE_CHAR_RE.findall(line)
    chinese_chars = KEEP_REGEX.findall(line)
    return ''.join(chinese_chars)

def find_txt_files(input_dir) -> List[Path]:
    """递归查找指定目录下的所有 .txt 文件"""
    txt_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.txt'):
                txt_files.append(Path(root) / file)
    return txt_files

def string_to_pinyin_list(line: str) -> List[str]:
    """将字符串转换为拼音列表"""
    pinyin_lists = []
    for i in pypinyin.pinyin(line, style=pypinyin.Style.NORMAL, heteronym=False):
        pinyin_lists.append(i[0])
    return pinyin_lists

def pinyin_to_xiaohe(pinyins: List[str]) -> List[str]:
    """将拼音列表转换为小鹤双拼编码列表"""
    initial_map = {
        **dict.fromkeys("bpmfdtngkhjqxrzcs", None),  # 占位
        "b":"b","p":"p","m":"m","f":"f","d":"d","t":"t","n":"n","l":"l",
        "g":"g","k":"k","h":"h","j":"j","q":"q","x":"x","r":"r",
        "z":"z","c":"c","s":"s","y":"y","w":"w",
        "zh":"v","ch":"i","sh":"u","":""  # "" 表示零声母
    }

    final_map = {
        # 单韵母
        "a":"a","o":"o","e":"e","i":"i","u":"u","v":"v",
        # 双、三韵母
        "ai":"d","ei":"w","ao":"c","ou":"z","an":"j","en":"f","ang":"h","eng":"g","er":"r",
        "ong":"s","iong":"s",
        "ia":"x","ua":"x","iao":"n","uai":"k","iai":"d",
        "ian":"m","iang":"l","iang":"l","ing":"k",
        "ie":"p","in":"b","iu":"q",
        "uo":"o","ue":"t","ve":"t","ui":"v",
        "uan":"r","uang":"l","uen":"y","un":"y",
        # 只在 zhi/chi/shi/ri/zi/ci/si 中出现的特殊韵母
        "i":"i","ng":"g"
    }

    multi_initials = ("zh", "ch", "sh")
    abbreviations = {"iou":"iu", "uei":"ui", "uen":"un"}

    codes = []
    for syl in pinyins:
        if ONLY_NUMBER_RE.match(syl):
            codes.append(syl)
            continue
        if ONLY_ENGLISH_ALPHABET_RE.match(syl):
            codes.append(syl)
            continue
        if ONLY_FLOAT_NUMBER_RE.match(syl):
            codes.append(syl)
            continue
        if ONLY_ENGLISH_ALPHABET_AND_NUMBER_RE.match(syl):
            codes.append(syl)
            continue
        try:
                if syl in ("-", "—", "~", "~", "，", ".", "/", "、"):
                    continue
                s = syl.lower().replace("ü", "v").replace("u:", "v")
                # 1) 切分
                if s.startswith(multi_initials):
                        ini, rest = s[:2], s[2:]
                else:
                        ini, rest = (s[0], s[1:]) if s[0] in initial_map and s[0] not in "aeo" else ("", s)
                rest = abbreviations.get(rest, rest)  # 缩写

                # 2) 映射

                key1 = initial_map.get(ini, ini if ini else s[0])
                key2 = final_map[rest]

                codes.append(f"{key1}{key2}")
        except Exception as e:
            print(f"处理 {syl} 时出错: {e}")
            continue
    return codes

def clean_pinyin(pinyins: List[str]) -> List[str]:
    """清理拼音列表"""
    result = []
    for pinyin in pinyins:
        if pinyin == "":
            continue
        if pinyin == "·":
            continue
        if pinyin == "，":
            continue
        result.append(pinyin)
    return result

def process_line(line: str) -> Tuple[str, int]:
    """处理单行文本，根据标点和空格分割，并只保留中文部分"""
    line = line.strip()
    if not line:
        return "", 0

    if not check_valid_line(line):
        return "", 0

    if HAVE_JAPANESE_CHAR_RE.match(line):
        return "", 0

    line = remove_punctuation(line)
    
    total_long_sentence_num = 0

    # 统一使用正则表达式分割 (包含中英文标点和空格)
    segments = PUNCTUATION_RE.split(line)
    
    final_str = ""
    
    if len(segments) > 1:
        total_long_sentence_num += len(segments)

    for segment in segments:
        segment = segment.strip()
        # 确保 segment 非空后再处理
        if segment:
            segment = segment.strip().replace(" ", "").replace("oo", "").replace("oo", "")
            # 提取纯中文字符
            segment = remove_punctuation(segment)
            segment = to_simplified(segment)
            chinese_only_segment = only_keep_chinese_chars(segment)
            # 检查提取后的纯中文字符串是否有效，并添加到集合
            if chinese_only_segment and check_valid_line(chinese_only_segment):
                final_str = chinese_only_segment
    return final_str, total_long_sentence_num

def load_batch_files(txt_files: List[Path]) -> Tuple[List[str], List[int]]:
    """合并文本文件""" 
    unique_lines = []
    comment_lines_num = 0
    empty_lines_num = 0
    english_lines_num = 0
    japanese_lines_num = 0
    number_lines_num = 0
    float_number_lines_num = 0
    english_and_number_lines_num = 0
    total_lines_num = 0
    total_long_sentence_num = 0
    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as infile:
                for line in infile:
                    total_lines_num += 1
                    line_strip = line.strip()
                    if any(line_strip.startswith(start) for start in COMMENT_LINE_STARTS):
                        comment_lines_num += 1
                        continue
                    if line_strip == "":
                        empty_lines_num += 1
                        continue
                    if ONLY_ENGLISH_ALPHABET_RE.match(line_strip):
                        english_lines_num += 1
                        continue
                    if HAVE_JAPANESE_CHAR_RE.match(line_strip):
                        japanese_lines_num += 1
                        continue
                    if ONLY_NUMBER_RE.match(line_strip):
                        number_lines_num += 1
                        continue
                    if ONLY_FLOAT_NUMBER_RE.match(line_strip):
                        float_number_lines_num += 1
                        continue
                    if ONLY_ENGLISH_ALPHABET_AND_NUMBER_RE.match(line_strip):
                        english_and_number_lines_num += 1
                        continue
                    line_strip = remove_punctuation(line_strip)
                    # total_long_sentence_num += process_line(line_strip, unique_lines)
                    final_str, long_sentence_num = process_line(line_strip)
                    if final_str and len(final_str) > 0:
                        unique_lines.append(final_str)
                    total_long_sentence_num += long_sentence_num
                    
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
    
    return_statics = [
        comment_lines_num,
        empty_lines_num,
        english_lines_num,
        japanese_lines_num,
        number_lines_num,
        float_number_lines_num,
        english_and_number_lines_num,
        total_lines_num,
        total_long_sentence_num
    ]
    
    return unique_lines, return_statics

def split_into_batch(txt_files: List[Path], batch_num:  int) -> List[List[Path]]:
    """将 txt 文件列表分割成多个批次"""
    txt_size = len(txt_files)
    batch_size = txt_size // batch_num
    if txt_size % batch_num != 0:
        batch_size += 1
    return [txt_files[i:i + batch_size] for i in range(0, txt_size, batch_size)]
    
    
def load_all_lines(input_dir: str) -> List[str]:
    """合并文本文件""" 
    global valid_time, set_time, read_time
    print(f"开始处理目录: {input_dir}")
    txt_files = find_txt_files(input_dir)
    if not txt_files:
        print("错误：在指定目录下未找到 .txt 文件。")
        sys.exit(1)

    print(f"找到 {len(txt_files)} 个 .txt 文件:")
    # for f in txt_files:
    #     print(f"  - {f}")

    unique_lines = set()
    unique_lines_list = []
    
    comment_lines_num = 0
    empty_lines_num = 0
    english_lines_num = 0
    japanese_lines_num = 0
    number_lines_num = 0
    float_number_lines_num = 0
    english_and_number_lines_num = 0
    total_lines_num = 0
    total_long_sentence_num = 0
    
    batch_files = split_into_batch(txt_files, os.cpu_count())
    
    total_batch_num = sum([len(batch_file) for batch_file in batch_files])
    print(f"batch 之后的文件总数是: {total_batch_num} == {len(txt_files)}")
    
    batch_num = os.cpu_count()
    
    Executor = ProcessPoolExecutor
    futures = {}
    
    # for batch_file in batch_files:
    #     batch_unique_lines, return_statics = load_batch_files(batch_file)
    #     unique_lines.update(batch_unique_lines)
    #     comment_lines_num += return_statics[0]
    #     empty_lines_num += return_statics[1]
    #     english_lines_num += return_statics[2]
    #     japanese_lines_num += return_statics[3]
    #     number_lines_num += return_statics[4]
    #     float_number_lines_num += return_statics[5]
    #     english_and_number_lines_num += return_statics[6]
    #     total_lines_num += return_statics[7]
    #     total_long_sentence_num += return_statics[8]
    
    with Executor(max_workers=batch_num) as executor:
        for batch_file in batch_files:
            futures[executor.submit(load_batch_files, batch_file)] = batch_file
            
        for future in as_completed(futures):
            batch_unique_lines, return_statics = future.result()
            unique_lines_list.extend(batch_unique_lines)
            comment_lines_num += return_statics[0]
            empty_lines_num += return_statics[1]
            english_lines_num += return_statics[2]
            japanese_lines_num += return_statics[3]
            number_lines_num += return_statics[4]
            float_number_lines_num += return_statics[5]
            english_and_number_lines_num += return_statics[6]
            total_lines_num += return_statics[7]
            total_long_sentence_num += return_statics[8]
            
    read_time = time.time()
    print(f"读取文件时间: {read_time - start_time} s")
    
    unique_lines = set(unique_lines_list)
    
    set_time = time.time()
    
    print(f"合并set 时间: {set_time - read_time} s")

    print(f"共找到 {len(unique_lines)} / {total_lines_num} 条不重复的行。")
    print(f"注释行: {comment_lines_num}")
    print(f"空行: {empty_lines_num}")
    print(f"英文行: {english_lines_num}")
    print(f"日文行: {japanese_lines_num}")
    print(f"数字行: {number_lines_num}")
    print(f"浮点数行: {float_number_lines_num}")
    print(f"英文和数字行: {english_and_number_lines_num}")
    print(f"长句行: {total_long_sentence_num}")
    unique_lines = list(unique_lines)
    unique_lines.sort()
    unique_lines = [line.strip() for line in unique_lines if check_valid_line(line)]
    valid_time = time.time()
    print(f"check valid 时间 {valid_time - read_time} s")
    return unique_lines

def generate_ime_lines(lines_with_pinyin: List[Tuple[str, List[str]]]) -> List[str]:
    """生成适用于 fcitx5输入法的行"""
    output_lines = []
    for line, pinyin_list in lines_with_pinyin:
        pinyin_str = "'".join(pinyin_list)
        output_lines.append(f"{line} {pinyin_str}")
    return output_lines

def generate_rime_lines(lines_with_pinyin: List[Tuple[str, List[str]]]) -> List[str]:
    """生成适用于 rime 的行"""
    output_lines = []
    for line, pinyin_list in lines_with_pinyin:
        if is_chinese_only(line):
            pinyin_str = "".join(pinyin_list)
            output_lines.append(f"{line} {pinyin_str}")
    return output_lines

def generate_only_text_lines(lines_with_pinyin: List[Tuple[str, List[str]]]) -> List[str]:
    """单纯生成文本行"""
    output_lines = []
    for line, _ in lines_with_pinyin:
        output_lines.append(line)
    return output_lines

def generate_shouxing_lines(lines_with_pinyin: List[Tuple[str, List[str]]]) -> List[str]:
    """生成适用于手心的行"""
    output_lines = []
    for line, pinyin_list in lines_with_pinyin:
        if is_chinese_only(line):
            pinyin_str = "'".join(pinyin_list)
            output_lines.append(f"{line} {pinyin_str} 1")
    return output_lines

def generate_qq_pinyin_lines(lines_with_pinyin: List[Tuple[str, List[str]]]) -> List[str]:
    """生成适用于 QQ 拼音的行"""
    output_lines = []
    for line, pinyin_list in lines_with_pinyin:
        if is_chinese_only(line):
            pinyin_str = "'".join(pinyin_list)
            output_lines.append(f"{pinyin_str} {line} 1")
    return output_lines

def generate_rime_flypy_lines(lines_with_pinyin: List[Tuple[str, List[str]]]) -> List[str]:
    """生成适用于小鹤双拼的 rime 词库"""
    output_lines = []
    for line, pinyin_list in lines_with_pinyin:
        if is_chinese_only(line):
            pinyin_list = pinyin_to_xiaohe(pinyin_list)
            pinyin_str = "".join(pinyin_list)
            output_lines.append(f"{line} {pinyin_str}")
    return output_lines


def generate_batch_lines(lines: List[str], batch_num: int) -> List[List[str]]:
    """生成批量行"""
    batch_size = len(lines) // batch_num
    if len(lines) % batch_num != 0:
        batch_size += 1
    return [lines[i:i + batch_size] for i in range(0, len(lines), batch_size)]

def generate_pinyin_list_batch(lines: List[str]) -> List[Tuple[str, List[str]]]:
    """生成拼音列表"""
    return [(line.strip(), string_to_pinyin_list(line.strip())) for line in lines]

def write_ime_file(output_file_prefix: str, lines_with_pinyin) -> str:
    """写入 ime 文件"""
    ime_lines = generate_ime_lines(lines_with_pinyin)
    ime_file = f"{output_file_prefix}_ime.txt"
    with open(ime_file, 'w', encoding='utf-8') as f:
        for line in ime_lines:
            f.write(f"{line}\n")
    return ime_file
            
def write_only_file(output_file_prefix: str, lines_with_pinyin) -> str:
    """写入 纯汉字 文件"""
    only_file = f"{output_file_prefix}_only.txt"
    with open(only_file, 'w', encoding='utf-8') as f:
        for line, _ in lines_with_pinyin:
            if is_chinese_only(line):
                f.write(f"{line}\n")
    return only_file
def write_rime_file(output_file_prefix: str, lines_with_pinyin) -> str:
    """写入 rime 文件"""
    rime_lines = generate_rime_lines(lines_with_pinyin)
    rime_file = f"{output_file_prefix}_rime.txt"
    with open(rime_file, 'w', encoding='utf-8') as f:
        for line in rime_lines:
            f.write(f"{line}\n")
    return rime_file
            
def write_shouxing_file(output_file_prefix: str, lines_with_pinyin) -> str:
    """写入 手心 文件"""
    shouxing_lines = generate_shouxing_lines(lines_with_pinyin)
    shouxing_file = f"{output_file_prefix}_shouxing.txt"
    with open(shouxing_file, 'w', encoding='utf-8') as f:
        for line in shouxing_lines:
            f.write(f"{line}\n")
    return shouxing_file
def write_rime_flypy_file(output_file_prefix: str, lines_with_pinyin) -> str:
    """写入适用于小鹤双拼的"""
    rime_flypy_file = f"{output_file_prefix}_rime_flypy.txt"
    rime_flypy_lines = generate_rime_flypy_lines(lines_with_pinyin)
    with open(rime_flypy_file, 'w', encoding='utf-8') as f:
        for line in rime_flypy_lines:
            f.write(f"{line}\n")
    return rime_flypy_file
            
def write_qq_pinyin_file(output_file_prefix: str, lines_with_pinyin) -> str:
    """写入适用于 QQ 拼音的文件"""
    qq_pinyin_file = f"{output_file_prefix}_qq.txt"
    qq_pinyin_lines = generate_qq_pinyin_lines(lines_with_pinyin)
    with open(qq_pinyin_file, 'w', encoding='utf-8') as f:
        for line in qq_pinyin_lines:
            f.write(f"{line}\n")
    return qq_pinyin_file

def merge_texts(input_dir, output_file_prefix, enable_rime, enable_rime_flypy, enable_rime_py, enable_shouxing, enable_qqpinyin) -> int:
        
    unique_lines = load_all_lines(input_dir)
    
    batch_num = os.cpu_count()
    batch_lines = generate_batch_lines(unique_lines, batch_num)
    
    futures = {}
    pinyin_lines = []
    with ProcessPoolExecutor(max_workers=batch_num) as executor:
        for batch_line in batch_lines:
            futures[executor.submit(generate_pinyin_list_batch, batch_line)] = 1
        for future in as_completed(futures):
            pinyin_lines.extend(future.result())
    
    to_py_time = time.time()
    print(f"to pinyin 时间 {to_py_time - valid_time} s")
    
    # lines_with_pinyin = map(lambda line, pinyin_list: (line, pinyin_list), unique_lines, pinyin_lines)
    lines_with_pinyin = pinyin_lines
    
    lines_with_pinyin = list(filter(lambda line: line[1] and len(line[1]) > 0 , lines_with_pinyin))
    
    print(f"Type of lines_with_pinyin: {type(lines_with_pinyin)}")
    
    print(f"最后剩下 {len(lines_with_pinyin)} 行")
    
    task_num = 2
    if enable_rime:
        task_num += 1
    if enable_rime_flypy:
        task_num += 1
    if enable_shouxing:
        task_num += 1
    if enable_qqpinyin:
        task_num += 1


    # output_ime_path = f"{output_file_prefix}_ime.txt"
    
    # ime_lines = generate_ime_lines(lines_with_pinyin)
    # with open(output_ime_path, 'w', encoding='utf-8') as f:
    #     for line in ime_lines:
    #         f.write(line + "\n")
    # print(f"生成 ime 词库文件 {output_ime_path} 成功")
    
    # # 纯汉字
    # output_only_text_path = f"{output_file_prefix}_only.txt"
    # only_text_lines = generate_only_text_lines(lines_with_pinyin)
    # with open(output_only_text_path, 'w', encoding='utf-8') as f:
    #     for line in only_text_lines:
    #         if is_chinese_only(line):
    #             f.write(line + "\n")
    # print(f"生成 纯汉字 词库文件 {output_only_text_path} 成功")
        
    # if enable_rime:
    #     output_rime_path = f"{output_file_prefix}_rime.txt"
    #     rime_lines = generate_rime_lines(lines_with_pinyin)
    #     with open(output_rime_path, 'w', encoding='utf-8') as f:
    #         for line in rime_lines:
    #             f.write(line + "\n")
    #     print(f"生成 rime 词库文件 {output_rime_path} 成功")
            
    # if enable_shouxing:
    #     output_shouxing_path = f"{output_file_prefix}_shouxing.txt"
    #     shouxing_lines = generate_shouxing_lines(lines_with_pinyin)
    #     with open(output_shouxing_path, 'w', encoding='utf-8') as f:
    #         for line in shouxing_lines:
    #             f.write(line + "\n")
    #     print(f"生成 手心 词库文件 {output_shouxing_path} 成功")
        
    # if enable_rime_flypy:
    #     output_rime_flypy_path = f"{output_file_prefix}_rime_flypy.txt"
    #     rime_flypy_lines = generate_rime_flypy_lines(lines_with_pinyin)
    #     with open(output_rime_flypy_path, 'w', encoding='utf-8') as f:
    #         for line in rime_flypy_lines:
    #             f.write(line + "\n")
    #     print(f"生成使用于 rime 的小鹤双拼词库文件 {output_rime_flypy_path} 成功")
    # if enable_qqpinyin:
    #     output_qqpinyin_path = f"{output_file_prefix}_qq.txt"
    #     qqpinyin_lines = generate_qq_pinyin_lines(lines_with_pinyin)
    #     with open(output_qqpinyin_path, 'w', encoding='utf-8') as f:
    #         for line in qqpinyin_lines:
    #             f.write(line + "\n")
    #     print(f"生成适用于 QQ 拼音的词库文件 {output_qqpinyin_path} 成功")
    
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {}
        futures[executor.submit(write_ime_file, output_file_prefix, lines_with_pinyin)] = 1
        futures[executor.submit(write_only_file, output_file_prefix, lines_with_pinyin)] = 2
        if enable_rime:
            futures[executor.submit(write_rime_file, output_file_prefix, lines_with_pinyin)] = 3
        if enable_rime_flypy:
            futures[executor.submit(write_rime_flypy_file, output_file_prefix, lines_with_pinyin)] = 4
        if enable_shouxing:
            futures[executor.submit(write_shouxing_file, output_file_prefix, lines_with_pinyin)] = 5
        if enable_qqpinyin:
            futures[executor.submit(write_qq_pinyin_file, output_file_prefix, lines_with_pinyin)] = 6
        for future in as_completed(futures):
            print(f"写入 {future.result()} 成功")
        
        
    write_time = time.time()
    print(f"写入时间: {write_time - to_py_time} s")
    return len(lines_with_pinyin)
            

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='递归合并目录下所有 txt 文件的行，去重并处理中英文标点。')
    parser.add_argument('input_dir', type=str, help='包含 txt 文件的输入目录路径')
    parser.add_argument('output_file_prefix', type=str, help='合并后的输出 txt 文件路径前缀')
    parser.add_argument('--enable_rime', action='store_true', help='是否生成适用于 rime 的文本词库')
    parser.add_argument('--enable_rime_flypy', action='store_true', help='是否生成适用于小鹤双拼的 rime 词库')
    parser.add_argument('--enable_rime_py', action='store_true', help='是否生成适用于拼音输入法的 rime 词库')
    parser.add_argument('--enable_shouxing', action='store_true', help='是否只生成适用于手心的 txt 文件')
    parser.add_argument('--enable_qqpinyin', action='store_true', help='是否只生成适用于 QQ 拼音的 txt 文件')

    args = parser.parse_args()
    
    dir_name = os.path.dirname(args.output_file_prefix)
    print(f"输出文件夹: {dir_name}")

    if not os.path.exists(dir_name):
        print(f"Warning：输出路径 '{dir_name}' 不是一个有效的目录。")
        os.makedirs(dir_name, exist_ok=True)
        
    start_time = time.time()
    print(f"开始时间: {start_time}")

    lines_num = merge_texts(args.input_dir, args.output_file_prefix, args.enable_rime, args.enable_rime_flypy, args.enable_rime_py, args.enable_shouxing, args.enable_qqpinyin)
    print(f"共处理 {lines_num} 行")
    end_time = time.time()
    print(f"结束时间: {end_time}")
    elapsed_time = end_time - start_time
    print(f"总时间: {elapsed_time} s")
    if elapsed_time > 0:
        print(f"速度: {lines_num / elapsed_time} 行/秒")
    
