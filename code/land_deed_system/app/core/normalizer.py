import re
from typing import Optional, Tuple, Dict

QING_EMPERORS = {
    "顺治": 1644,
    "康熙": 1662,
    "雍正": 1723,
    "乾隆": 1736,
    "嘉庆": 1796,
    "道光": 1821,
    "咸丰": 1851,
    "同治": 1862,
    "光绪": 1875,
    "宣统": 1909
}

CHINESE_NUMERALS = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '廿': 20, '卅': 30, '百': 100, '千': 1000, '万': 10000,
    '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
    '陆': 6, '柒': 7, '捌': 8, '玖': 9, '拾': 10,
    '元': 1, '正': 1
}

def parse_chinese_number(text: str) -> int:
    """
    Parses Chinese numerals into integers.
    Handles basic patterns like "二十三", "一百零五", "光绪三年".
    """
    if not text:
        return 0
        
    # Check if text is purely digits
    if text.isdigit():
        return int(text)
        
    result = 0
    temp = 0
    unit = 1
    
    # Simple left-to-right parsing for dates (often just digits)
    # But for "二十三" we need value * unit logic
    
    # Simplified approach for years/months/days (usually < 100)
    # If "十" is at start: "十二" -> 10 + 2
    # If "十" is in middle: "二十二" -> 2*10 + 2
    
    current_val = 0
    
    for char in text:
        if char in CHINESE_NUMERALS:
            digit = CHINESE_NUMERALS[char]
            
            if digit >= 10:
                if digit > unit:
                    unit = digit
                    if temp == 0:
                        temp = 1
                    result += temp * unit
                    temp = 0
                    unit = 1 # Reset unit for next part
                else:
                    # Case like "二十"
                    if temp == 0:
                        temp = 1
                    result += temp * digit
                    temp = 0
            else:
                temp = digit
        else:
            continue
            
    result += temp
    return result if result > 0 else 0

def normalize_date(date_str: str) -> Tuple[str, str, float]:
    """
    Normalizes a Qing dynasty date string to Gregorian YYYY-MM-DD.
    Returns: (Original Date, Normalized Date, Confidence)
    """
    normalized_val = ""
    confidence = 0.0
    
    # Try to find Emperor Year
    for emperor, start_year in QING_EMPERORS.items():
        if emperor in date_str:
            # Extract year
            # Match "光绪三年", "光绪3年", "光绪乙亥年" (cyclic not supported yet)
            year_match = re.search(f"{emperor}(.*?)年", date_str)
            if year_match:
                year_part = year_match.group(1).strip()
                offset = parse_chinese_number(year_part)
                if offset > 0:
                    gregorian_year = start_year + offset - 1
                    normalized_val = f"{gregorian_year}"
                    confidence = 0.9
                
                # Extract Month
                month_match = re.search(r"[年\s](.*?)月", date_str)
                month = 1
                if month_match:
                    month_part = month_match.group(1).strip()
                    m = parse_chinese_number(month_part)
                    if 1 <= m <= 12:
                        month = m
                        normalized_val += f"-{month:02d}"
                    else:
                        normalized_val += "-01"
                else:
                     normalized_val += "-01"

                # Extract Day
                day_match = re.search(r"[月\s](.*?)日", date_str)
                day = 1
                if day_match:
                    day_part = day_match.group(1).strip()
                    d = parse_chinese_number(day_part)
                    if 1 <= d <= 31:
                        day = d
                        normalized_val += f"-{day:02d}"
                    else:
                        normalized_val += "-01"
                else:
                    normalized_val += "-01"
                    
                return date_str, normalized_val, confidence
                
    return date_str, normalized_val, confidence

def normalize_currency(amount_str: str) -> Tuple[str, str, float]:
    """
    Normalizes currency to 2023 RMB.
    Base assumption: 1 Tael Silver (清代) ≈ 750 RMB (2023).
    """
    normalized_val = ""
    confidence = 0.0
    
    # Extract number and unit
    # "纹银五十两" -> 50, 两
    match = re.search(r"([零一二三四五六七八九十百千万\d\.]+)\s*(两|元|圆|千文|吊)", amount_str)
    
    unit_map = {
        "两": 750.0,   # Tael Silver
        "元": 150.0,   # Silver Dollar
        "圆": 150.0,
        "千文": 200.0, # 1000 Cash
        "吊": 200.0
    }
    
    if match:
        num_str = match.group(1)
        unit = match.group(2)
        
        try:
            val = float(parse_chinese_number(num_str))
            rate = unit_map.get(unit, 0)
            if rate > 0:
                rmb = val * rate
                normalized_val = f"{rmb:.2f} RMB (2023 Est.)"
                confidence = 0.85
        except:
            pass
            
    return amount_str, normalized_val, confidence
