from paddleocr import PaddleOCRVL
import os
import json
import re


def extract_text_content(json_file_path, text_save_path):
    if not os.path.exists(json_file_path):
        print(f"错误：JSON文件不存在 -> {json_file_path}")
        return False

    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            json_content = json.load(f)

        if "parsing_res_list" not in json_content:
            print("错误：JSON文件中未找到有效的parsing_res_list数据")
            return False

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

        os.makedirs(os.path.dirname(text_save_path), exist_ok=True)
        with open(text_save_path, "w", encoding="utf-8") as f:
            f.write(cleaned_text)

        return True

    except json.JSONDecodeError as e:
        print(f"错误：JSON文件格式解析失败 -> {e}")
        return False
    except Exception as e:
        print(f"提取正文时发生未知错误 -> {e}")
        return False


def ocr_image_by_id(image_id):
    """
    输入：image_id
    处理：./pic/{image_id}.{图片后缀}
    输出：./output/text/{image_id}.txt
    成功返回 True，失败返回 False
    """

    pic_dir = "./pic"
    output_json_dir = "./output"
    output_text_dir = "./output/text"

    # 查找图片
    image_exts = [".jpg", ".png", ".jpeg", ".bmp", ".webp"]
    input_file = None
    for ext in image_exts:
        candidate = os.path.join(pic_dir, f"{image_id}{ext}")
        if os.path.exists(candidate):
            input_file = candidate
            break

    if input_file is None:
        print(f"错误：未找到图片文件 -> {image_id}")
        return False

    try:
        pipeline = PaddleOCRVL()
        output = pipeline.predict(input_file)

        for res in output:
            res.save_to_json(save_path=output_json_dir)

        base_name_without_ext = os.path.splitext(os.path.basename(input_file))[0]
        output_json_file = os.path.join(
            output_json_dir, f"{base_name_without_ext}_res.json"
        )
        output_text_file = os.path.join(
            output_text_dir, f"{image_id}.txt"
        )

        if not os.path.exists(output_json_file):
            print(f"错误：未生成JSON文件 -> {output_json_file}")
            return False

        return extract_text_content(output_json_file, output_text_file)

    except Exception as e:
        print(f"OCR处理过程中发生错误 -> {e}")
        return False
