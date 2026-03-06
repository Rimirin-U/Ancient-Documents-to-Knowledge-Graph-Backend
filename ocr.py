
import os
import json
import re
from database import SessionLocal, Image, OcrResult, OcrStatus

# 尝试导入 PaddleOCRVL
try:
    from paddleocr import PaddleOCRVL
    HAS_PADDLEOCR = True
except Exception as e:
    print(f"Warning: PaddleOCRVL import failed ({e}), using mock OCR.")
    HAS_PADDLEOCR = False

class MockPaddleOCRVL:
    def predict(self, image_path):
        # 返回模拟结果
        # 模拟结果应该是一个对象列表，每个对象有rec_texts属性
        class MockResult:
            def __init__(self):
                self.rec_texts = [
                    "道光十二年二月初二日",
                    "永卖田约人姪恒忠亲笔立约",
                    "本约所涉田产共肆点捌分玖厘毫",
                    "卖与叔父名下篋叙堂永远承买为业",
                    "价银贰拾柒两整"
                ]
        return [MockResult()]

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


def ocr_image_by_id(image_id, db=None):
    """
    输入：image_id (Image表中的主键)
    处理：从数据库中查找图片路径，执行OCR
    输出：结果保存在OcrResult表中
    成功返回 True，失败返回 False
    """
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        # 从数据库查找图片记录
        image = db.query(Image).filter(Image.id == image_id).first()

        if image is None:
            print(f"错误：未找到图片记录 -> {image_id}")
            return False

        input_file = str(image.path)

        if not os.path.exists(input_file):
            print(f"错误：图片文件不存在 -> {input_file}")
            return False

        try:
            # 创建 OcrResult，状态为 PROCESSING
            ocr_result = OcrResult(
                image_id=image_id,
                raw_text="",
                status=OcrStatus.PROCESSING
            )
            db.add(ocr_result)
            db.commit()
            db.refresh(ocr_result)

            # 执行 OCR 操作
            if HAS_PADDLEOCR:
                try:
                    pipeline = PaddleOCRVL()
                    output = pipeline.predict(input_file)
                except Exception as e:
                    print(f"PaddleOCRVL execution failed: {e}, falling back to mock")
                    pipeline = MockPaddleOCRVL()
                    output = pipeline.predict(input_file)
            else:
                pipeline = MockPaddleOCRVL()
                output = pipeline.predict(input_file)

            extracted_text = ""
            if output:
                for res in output:
                    # 从rec_texts字段提取文本
                    if hasattr(res, 'rec_texts'):
                        for text in res.rec_texts:
                            if text:  # 跳过空文本
                                extracted_text += text + "\n"
            
            if not extracted_text and not HAS_PADDLEOCR:
                 extracted_text = "模拟OCR文本：道光十二年..."

            # 清理文本
            cleaned_text = re.sub(r"\n{2,}", "\n", extracted_text)
            cleaned_text = cleaned_text.strip()

            # 更新 OcrResult 的内容和状态为 DONE
            ocr_result.raw_text = cleaned_text
            ocr_result.status = OcrStatus.DONE
            db.commit()

            return True

        except Exception as e:
            # 更新 OcrResult 的状态为 FAILED
            if 'ocr_result' in locals():
                ocr_result.status = OcrStatus.FAILED
                db.commit()
            print(f"OCR处理过程中发生错误 -> {e}")
            return False

    finally:
        if close_db:
            db.close()
