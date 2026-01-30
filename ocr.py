from paddleocr import PaddleOCRVL
import os
import json
import re

input_file = r"./input/test.jpg"

pipeline = PaddleOCRVL()
output = pipeline.predict(input_file)

for res in output:
    res.print()
    res.save_to_json(save_path="output")

base_name = os.path.basename(input_file)
base_name_without_ext = os.path.splitext(base_name)[0]

output_json_file = f"output/{base_name_without_ext}_res.json"
output_text_file = f"output/{base_name_without_ext}_正文.txt"


def extract_text_content(json_file_path, text_save_path):
    if not os.path.exists(json_file_path):
        print(f"错误：JSON文件不存在 -> {json_file_path}")
        return

    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            json_content = json.load(f) 

        if "parsing_res_list" not in json_content:
            print("错误：JSON文件中未找到有效的parsing_res_list数据")
            return

        parsing_res_list = json_content["parsing_res_list"]
        extracted_texts = []
        for block in parsing_res_list:
            if block.get("block_label") == "text": 
                block_content = block.get("block_content", "") 
                extracted_texts.append(block_content)

        combined_text = "\n".join(extracted_texts)
        cleaned_text = re.sub(r"\n{2,}", "\n", combined_text) 
        cleaned_text = re.sub(
            r"^\s+|\s+$", "", cleaned_text, flags=re.MULTILINE
        )  
        cleaned_text = cleaned_text.strip()  

        with open(text_save_path, "w", encoding="utf-8") as f:
            f.write(cleaned_text)

        print(f"正文提取成功！")
        print(f"JSON文件路径：{json_file_path}")
        print(f"提取的正文保存路径：{text_save_path}")
        print(f"\n提取的正文：\n{cleaned_text}...") 

    except json.JSONDecodeError as e:
        print(f"错误：JSON文件格式解析失败 -> {e}")
    except Exception as e:
        print(f"提取正文时发生未知错误 -> {e}")

if os.path.exists(output_json_file):
    extract_text_content(output_json_file, output_text_file)
else:
    print(f"错误：未找到生成的JSON文件 -> {output_json_file}")
