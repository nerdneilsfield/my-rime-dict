import argparse
import jieba
import jieba.analyse
import re
import os
from typing import Set, List
import jieba.posseg as pseg # 导入词性标注模块
from concurrent.futures import ProcessPoolExecutor, as_completed # Use ProcessPoolExecutor
from pathlib import Path
from opencc import OpenCC


MIN_WORD_LENGTH = 2
CHINESE_WORD_REGEX = re.compile(r'^[\u4e00-\u9fa5]+$')
# CHINESE_WORD_REGEX = re.compile(r'[\u4e00-\u9fa5]')
TOPK = 200

EXTENSIONS = ['.txt', '.md']
ALLOW_POS = ('n', 'v', 'vn', 'vg', 'vs', 'nr', 'ns', 'nt', 'nz','a','c')
LCUT_OPS = ('n', 'ns','nr','nt','nz','v', 'vn')

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
# --- 工作函数 ---
# This function remains the same as it's designed for parallel execution.
def process_paragraph_with_rank(paragraph_text: str) -> Set[str]:
    """
    处理单个段落/行，提取关键词并过滤。
    Suitable for use with ProcessPoolExecutor.
    """
    local_dictionary_words = set()
    if not paragraph_text:
        return local_dictionary_words

    try:
        # 使用 TextRank 提取 (或者 TF-IDF)
        keywords_tr = jieba.analyse.textrank(paragraph_text,
                                             topK=TOPK,
                                             withWeight=False,
                                             allowPOS=ALLOW_POS)

        for word in keywords_tr:
            word = word.strip()
            # --- 词语过滤条件 ---
            if len(word) >= MIN_WORD_LENGTH and \
               CHINESE_WORD_REGEX.search(word) and \
               not word.isdigit():
                local_dictionary_words.add(word)
    except Exception as e:
        # Log or print error from within the process if needed
        # print(f"Error processing chunk: {e}")
        pass # Continue processing other chunks

    return local_dictionary_words

def process_paragprah_with_lcut(paragraph_text: str) -> Set[str]:
    """
    使用 jieba.lcut 分词，提取关键词并过滤。
    """
    lines = paragraph_text.splitlines()
    total_lines = len(lines)
    local_dictionary_words = set()
    for line in lines:
        words = pseg.lcut(line)
        for word, flag in words:
            if flag in LCUT_OPS and len(word) >= MIN_WORD_LENGTH and CHINESE_WORD_REGEX.search(word) and not word.isdigit():
                local_dictionary_words.add(word)
    # print(f"使用 jieba.lcut 分词，共找到 {len(local_dictionary_words)} 个不重复的候选词语。")
    return local_dictionary_words

def process_paragraph(paragraph_text: str, use_rank=False) -> Set[str]:
    """
    处理单个段落/行，提取关键词并过滤。
    """
    if use_rank:
        return process_paragraph_with_rank(paragraph_text)
    else:
        return process_paragprah_with_lcut(paragraph_text)

def process_paragraphs(paragraphs: List[str], use_rank=False) -> Set[str]:
    """
    处理多个段落/行，提取关键词并过滤。
    Suitable for use with ProcessPoolExecutor.
    """
    local_dictionary_words = set()
    for paragraph in paragraphs:
        local_dictionary_words.update(process_paragraph(paragraph, use_rank))
    return local_dictionary_words

def extract_dictionary_words(input_filepath, use_rank=False) -> Set[str]:
    """
    读取文本文件，使用 jieba 分词，提取常见的、适合做词典的词语，
    去重后存入新文件，每行一个词。

    Args:
        input_filepath (str): 输入的 txt 文件路径。
        output_filepath (str): 输出的词语文件路径。
    """
    dictionary_words = set()

    print(f"正在读取文件: {input_filepath}")
    try:
        # with open(input_filepath, 'r', encoding='utf-8') as infile:
        #     for i, line in enumerate(infile):
        #         # 去除行首尾空白
        #         line = line.strip()
        #         if not line:
        #             continue

        #         # 使用 jieba 精确模式分词
        #         # lcut 返回列表
        #         words = jieba.lcut(line)

        #         for word in words:
        #             word = word.strip() # 去除词语本身可能带有的空白

        #             # --- 词语过滤条件 ---
        #             # 1. 长度大于等于 MIN_WORD_LENGTH
        #             # 2. 包含至少一个汉字 (通过正则判断)
        #             # 3. 不是纯数字 (可选，jieba 通常会分开，但以防万一)
        #             if len(word) >= MIN_WORD_LENGTH and \
        #                CHINESE_WORD_REGEX.search(word) and \
        #                not word.isdigit():
        #                 dictionary_words.add(word)

        #         if (i + 1) % 1000 == 0: # 每处理 1000 行给个提示
        #             print(f"已处理 {i + 1} 行...")
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            # 关键词提取通常需要整个文本内容
            content = infile.read()
        print("文件读取完毕，开始提取关键词/短语...")
        
        lines = content.split("\n\n")
        total_lines = len(lines)
        
        print(f"找到 {total_lines} 个段落")
        max_workers = os.cpu_count()
        print(f"自动检测到 {max_workers} 个 CPU 核心。")

        processed_count = 0
        # --- Change Executor ---
        # Executor = ThreadPoolExecutor
        Executor = ProcessPoolExecutor # Use ProcessPoolExecutor
        total_items = len(lines)
        futures = {}

        # IMPORTANT: Ensure the code using ProcessPoolExecutor is under `if __name__ == "__main__":`
        with Executor(max_workers=max_workers) as executor:
            # Submit all tasks
            # Calculate base chunk size and remainder for even distribution
            base_chunk_size = total_items // max_workers
            remainder = total_items % max_workers
            start_index = 0

            print(f"基础块大小: {base_chunk_size}, 剩余项: {remainder}")
            
            
            for i in range(max_workers):
                # Distribute the remainder: the first 'remainder' chunks get 1 extra item
                current_chunk_size = base_chunk_size + (1 if i < remainder else 0)
                end_index = start_index + current_chunk_size

                # Slice the list to get the chunk for this worker
                # Ensure end_index doesn't exceed total_items (shouldn't with this logic)
                chunk_of_lines = lines[start_index:end_index]

                # Only submit if the chunk is not empty
                if chunk_of_lines:
                    print(f"提交块 {i}: 索引 {start_index} 到 {end_index-1} (大小: {len(chunk_of_lines)})")
                    # Submit the entire chunk to the modified process_paragraphs function
                    # The key 'i' helps map the future back to the chunk index if needed later
                    futures[executor.submit(process_paragraphs, chunk_of_lines)] = i
                else:
                     print(f"块 {i} 为空，跳过提交。") # Should not happen with correct logic

                # Move start_index for the next chunk
                start_index = end_index
            # --- End of Chunking and Submission Logic ---

            print(f"已提交 {len(futures)} 个任务块，等待结果...")
            total_tasks = len(futures)

            for future in as_completed(futures):
                try:
                    result_set = future.result() # Get the set returned by the worker process
                    dictionary_words.update(result_set) # Merge results in the main process
                except Exception as e:
                    task_index = futures[future]
                    print(f"\n获取任务 {task_index} 结果时出错: {e}")

                processed_count += 1
                # Update progress
                print(f"\r已处理: {processed_count}/{total_tasks} ({processed_count/total_tasks:.1%})", end="")

        print("\n并行处理完成。") # Newline after progress indicator
    except FileNotFoundError:
        print(f"错误：找不到输入文件 '{input_filepath}'")
        return
    except Exception as e:
        print(f"读取或处理文件时出错：{e}")
        return

    print(f"分词和筛选完成，共找到 {len(dictionary_words)} 个不重复的候选词语。")
    return dictionary_words
        
def write_to_file(words: Set[str], output_filepath: str):
    """
    将词语写入到文件中。

    Args:
        words (Set[str]): 词语集合。
        output_filepath (str): 输出的词语文件路径。
    """
    print(f"正在写入文件: {output_filepath}")
    try:
        # 对词语进行排序，让输出文件更规整 (可选)
        sorted_words = sorted(list(words))

        with open(output_filepath, 'w', encoding='utf-8') as outfile:
            for word in sorted_words:
                outfile.write(word + '\n') # 每个词占一行
        print(f"成功将词语写入到: {output_filepath}")
    except Exception as e:
        print(f"写入文件时出错：{e}")
        
def list_files(directory: str) -> List[Path]:
    """
    列出指定目录下的所有 txt 文件。

    Args:
        directory (str): 要列出文件的目录路径。

    Returns:
        List[str]: 包含所有 txt 文件路径的列表。
    """
    txt_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(tuple(EXTENSIONS)):
                txt_files.append(Path(root) / file)
    return txt_files


def extract_words_from_files(input_dir: str, output_file: str, use_rank=False):
    """
    从指定目录下的所有 txt 文件中提取词语，并写入到输出文件中。

    Args:
        input_dir (str): 输入的 txt 文件目录路径。
        output_file (str): 输出的词语文件路径。
    """
    print(f"开始处理目录: {input_dir}")
    txt_files = list_files(input_dir)
    print(f"找到 {len(txt_files)} 个文件")
    if not txt_files:
        print("错误：在指定目录下未找到 .txt 文件。")
        return

    all_words = set()
    for txt_file in txt_files:
        print(f"正在处理文件: {txt_file}")
        words = extract_dictionary_words(txt_file)
        if words:
            all_words.update(words)
    print(f"找到 {len(all_words)} 个不重复的候选词语。")
    all_words = {to_simplified(word) for word in list(all_words)}
    all_words = {word.strip() for word in all_words}
    all_words = set(all_words)
    print(f"转换为简体中文后，共找到 {len(all_words)} 个不重复的候选词语。")
    write_to_file(all_words, output_file)

# --- 主程序 ---
if __name__ == "__main__":
    print("--- 中文词典提取工具 ---")
    
    args_parser = argparse.ArgumentParser(description="从指定目录下的所有 txt 文件中提取词语，并写入到输出文件中。")
    args_parser.add_argument("input_dir", type=str, help="输入的 txt 文件目录路径。")
    args_parser.add_argument("output_file", type=str, help="输出的词语文件路径。")
    args_parser.add_argument("--use_rank", action="store_true", help="是否使用 TextRank 提取关键词。")
    args = args_parser.parse_args()

    extract_words_from_files(args.input_dir, args.output_file, args.use_rank)

    