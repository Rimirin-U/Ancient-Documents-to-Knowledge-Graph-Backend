import re

ERA_START_YEARS = {
    "顺治": 1644,
    "康熙": 1662,
    "雍正": 1723,
    "乾隆": 1736,
    "嘉庆": 1796,
    "道光": 1821,
    "咸丰": 1851,
    "同治": 1862,
    "光绪": 1875,
    "宣统": 1909,
    "民国": 1912,
}

CHINESE_DIGITS = {
    '零': 0, '〇': 0,
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
    '陆': 6, '柒': 7, '捌': 8, '玖': 9, '拾': 10,
    '廿': 20, '卅': 30, 'Mz': 30  # Common variant
}

def chinese_to_int(text: str) -> int:
    """
    Parses a Chinese number string (e.g. "十二", "二十五") into an integer.
    Simple implementation for years.
    """
    if not text:
        return 0
    
    if text == "元":
        return 1
        
    total = 0
    r = 0 # current digit
    
    for char in text:
        val = CHINESE_DIGITS.get(char)
        if val is None:
            continue
            
        if val == 10:
            if r == 0:
                total += 10
            else:
                total += r * 10
                r = 0
        elif val >= 20: # 廿, 卅
             total += val
             r = 0
        else:
            r = val
            
    total += r
    return total

def convert_time(era_string: str) -> str:
    """
    Converts a traditional Chinese era date string to an AD year string.
    Example: "道光十二年二月初二" -> "1832年"
    """
    if not era_string:
        return ""

    # Regex to capture Era + Year
    # Matches: "道光" + "十二" + "年"
    pattern = r"([顺治|康熙|雍正|乾隆|嘉庆|道光|咸丰|同治|光绪|宣统|民国]+)(.+?)年"
    match = re.search(pattern, era_string)
    
    if not match:
        return era_string

    era_name = match.group(1)
    year_str = match.group(2)
    
    start_year = ERA_START_YEARS.get(era_name)
    if not start_year:
        return era_string

    year_val = chinese_to_int(year_str)

    if year_val > 0:
        ad_year = start_year + year_val - 1
        return f"{ad_year}年"
    
    return era_string
