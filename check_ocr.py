
try:
    from paddleocr import PaddleOCRVL
    print("Import PaddleOCRVL success")
except ImportError:
    print("ImportError: PaddleOCRVL not found in paddleocr")
    try:
        from paddleocr import PaddleOCR
        print("Import PaddleOCR success")
    except ImportError:
        print("ImportError: PaddleOCR not found in paddleocr")
except Exception as e:
    print(f"Other error: {e}")
