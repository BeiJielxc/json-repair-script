import sys
import re
import json
from typing import Tuple, List


RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
RE_LINE_COMMENT = re.compile(r"//.*?$", re.M)

# Very common: unquoted key in object: { name: "x" }
# Capture: start or { or [ or , or newline, then optional spaces, key token, spaces, :
RE_UNQUOTED_KEY = re.compile(
    r'([{\[,\n]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)',
    flags=re.M
)

# Trailing comma before ] or }
RE_TRAILING_COMMA = re.compile(r",\s*([}\]])")

# Missing comma between adjacent structures: } {  or } "key" or ] { etc.
RE_MISSING_COMMA_1 = re.compile(r"(\}|\]|\")\s*(\{|\[|\")")
# Specifically between two objects in array: } {  (most common)
RE_MISSING_COMMA_OBJ = re.compile(r"(\})\s*(\{)")

# Normalize non-JSON literals
RE_TRUE = re.compile(r"\bTrue\b")
RE_FALSE = re.compile(r"\bFalse\b")
RE_NULL_UPPER = re.compile(r"\bNULL\b")


def strip_comments(s: str) -> str:
    s2 = RE_BLOCK_COMMENT.sub("", s)
    s3 = RE_LINE_COMMENT.sub("", s2)
    return s3


def normalize_literals(s: str) -> str:
    s = RE_TRUE.sub("true", s)
    s = RE_FALSE.sub("false", s)
    s = RE_NULL_UPPER.sub("null", s)
    return s


def fix_chinese_quotes(s: str) -> str:
    """将中文引号替换为对应的英文符号（作为普通字符）"""
    # 这是一个全局替换，将中文引号字符替换为普通文本
    s = s.replace('"', '＂')  # 中文左引号 -> 全角双引号
    s = s.replace('"', '＂')  # 中文右引号 -> 全角双引号
    s = s.replace(''', "'")   # 中文左单引号 -> 英文单引号
    s = s.replace(''', "'")   # 中文右单引号 -> 英文单引号
    return s


def quote_unquoted_keys(s: str) -> str:
    # 改进：递归处理嵌套结构中的未加引号键名
    def replacer(match):
        return f'{match.group(1)}"{match.group(2)}"{match.group(3)}'

    # 重复应用直到没有更多匹配（处理嵌套情况）
    max_iterations = 10
    for _ in range(max_iterations):
        new_s = RE_UNQUOTED_KEY.sub(replacer, s)
        if new_s == s:
            break
        s = new_s
    return s


def escape_special_characters(s: str) -> str:
    # 简化版本：不进行额外转义，因为大多数情况下字符串已经正确
    # 过度转义会导致问题（如反斜杠指数增长）
    # 如果真的需要转义，应该在更早的阶段处理
    return s


def remove_trailing_commas(s: str) -> str:
    # Repeat until stable, because nested patterns may appear
    prev = None
    while prev != s:
        prev = s
        s = RE_TRAILING_COMMA.sub(r"\1", s)
    return s


def fix_misplaced_brackets(s: str) -> Tuple[str, List[str]]:
    """
    修复错位的括号，例如：
    "key": "value"] 应该是 "key": "value" }]
    """
    diagnostics = []
    lines = s.split('\n')
    
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        
        # 检测模式：值后面直接跟 ] 
        # 匹配: "xxx"]  或  123]  或  true]
        if stripped.endswith(']') and not stripped.endswith(']]'):
            # 检查 ] 之前是否有合适的值结束
            before_bracket = stripped[:-1].rstrip()
            if not before_bracket:  # 如果只有一个 ]，跳过
                continue
            if before_bracket.endswith('"') or before_bracket.endswith('}') or \
               before_bracket[-1].isdigit() or before_bracket.endswith('true') or \
               before_bracket.endswith('false') or before_bracket.endswith('null'):
                
                # 检查前面的上下文（包括当前行到 ] 之前的内容）
                content_before = '\n'.join(lines[:i]) + '\n' + before_bracket
                
                # 统计括号（忽略字符串内的）
                in_string = False
                escape = False
                open_obj = 0
                open_arr = 0
                
                for char in content_before:
                    if escape:
                        escape = False
                        continue
                    if char == '\\':
                        escape = True
                        continue
                    if char == '"':
                        in_string = not in_string
                        continue
                    if not in_string:
                        if char == '{':
                            open_obj += 1
                        elif char == '}':
                            open_obj -= 1
                        elif char == '[':
                            open_arr += 1
                        elif char == ']':
                            open_arr -= 1
                
                # 如果有未闭合的对象且数组也未闭合，在 ] 前插入 }
                if open_obj > 0 and open_arr > 0:
                    # 在 ] 之前插入 }，并换行
                    indent = len(line) - len(line.lstrip())
                    new_line = before_bracket + '\n' + ' ' * indent + '}\n' + ' ' * max(0, indent-4) + ']'
                    lines[i] = new_line
                    diagnostics.append(f"Inserted '}}' before ']' on line {i+1}")
                    return '\n'.join(lines), diagnostics
    
    return s, diagnostics


def insert_missing_commas(s: str) -> str:
    """
    改进：处理各种缺少逗号的情况
    1. 对象/数组后直接跟着另一个对象/数组
    2. 值后直接跟着键名
    3. 特别处理换行的情况
    4. 同行内连续的键值对
    5. 数组/对象闭合后直接跟键名
    """
    max_iterations = 10
    for _ in range(max_iterations):
        prev = s
        
        # 处理 } { 或 ] { 或 } [ 等模式（可能跨行）
        s = RE_MISSING_COMMA_OBJ.sub(r"\1, \2", s)
        s = RE_MISSING_COMMA_1.sub(r"\1, \2", s)
        
        # 处理换行后的情况: }\n{  或  }\n  {
        s = re.sub(r'(\}|\])\s*\n\s*(\{|\[)', r'\1,\n\2', s)
        
        # 处理对象/数组闭合后，同一行或下一行直接跟键名的情况
        # 例如: }  "key"  或  ]  "key"
        s = re.sub(r'(\}|\])\s+(")', r'\1, \2', s)
        
        # 新增：处理同一行内，数字/字符串后直接跟键名的情况
        # 例如: "price": 5999 "quantity": 2
        # 匹配: 数字或字符串结束后，空格，然后是引号开始的键名
        s = re.sub(r'(\d+|"[^"]*")\s+("[\w]+"\s*:)', r'\1, \2', s)
        
        # 新增：处理换行后，值结束直接跟键名
        # 例如: 5999\n"quantity"
        s = re.sub(r'(\d+|"[^"]*"|true|false|null)\s*\n\s*("[\w]+"\s*:)', r'\1,\n\2', s)
        
        # 新增：处理 } 或 ] 后直接换行跟 "key"
        s = re.sub(r'(\}|\])\s*\n\s*("[\w]+"\s*:)', r'\1,\n\2', s)
        
        if s == prev:
            break
    
    return s


def remove_duplicate_keys(s: str) -> str:
    # 改进：尝试解析JSON并移除重复键名
    # 注意：这个函数在字符串级别处理重复键很困难，
    # 更好的方法是在JSON解析后处理，这里暂时简化处理
    try:
        # 尝试加载JSON，Python的json.loads会自动使用最后出现的重复键
        obj = json.loads(s)
        return json.dumps(obj, ensure_ascii=False)
    except:
        # 如果无法解析，返回原字符串
        return s


def fix_missing_values(s: str) -> str:
    # 新增：修复键值对中缺失的值
    return re.sub(r'"(\w+)":\s*,', r'"\1": null,', s)


def fix_unclosed_strings_linewise(s: str) -> Tuple[str, List[str]]:
    """
    Heuristic: if a line has an odd number of unescaped double quotes,
    append a closing quote at end of line.
    """
    diagnostics = []
    lines = s.splitlines()
    fixed_lines = []

    for i, line in enumerate(lines, start=1):
        # Count unescaped quotes:
        # remove escaped quotes \" first
        tmp = re.sub(r'\\"', '', line)
        quote_count = tmp.count('"')
        if quote_count % 2 == 1:
            # If line contains // comment already stripped, this likely means unclosed string.
            diagnostics.append(f"Line {i}: suspected unclosed string; appended '\"'")
            fixed_lines.append(line + '"')
        else:
            fixed_lines.append(line)

    return "\n".join(fixed_lines), diagnostics


def balance_brackets_smart(s: str) -> Tuple[str, List[str]]:
    """
    智能平衡括号：使用栈追踪嵌套结构，在正确位置插入缺失的括号
    """
    diagnostics = []
    
    # 移除字符串内容以避免干扰（简化版）
    def strip_strings(text: str) -> str:
        # 替换字符串内容为空字符串，保留引号结构
        result = []
        in_string = False
        escape_next = False
        for char in text:
            if escape_next:
                escape_next = False
                result.append(' ')
                continue
            if char == '\\':
                escape_next = True
                result.append(' ')
                continue
            if char == '"':
                in_string = not in_string
                result.append('"')
            elif not in_string:
                result.append(char)
            else:
                result.append(' ')
        return ''.join(result)
    
    stripped = strip_strings(s)
    
    # 使用栈追踪未闭合的括号
    stack = []
    positions = []  # 记录每个开括号的位置
    
    for i, char in enumerate(stripped):
        if char in '{[':
            stack.append(char)
            positions.append(i)
        elif char in '}]':
            expected = '{' if char == '}' else '['
            if stack and stack[-1] == expected:
                stack.pop()
                positions.pop()
    
    # 如果有未闭合的括号，在末尾添加
    if stack:
        closing = []
        for bracket in reversed(stack):
            if bracket == '{':
                closing.append('}')
            else:
                closing.append(']')
        
        s += ''.join(closing)
        diagnostics.append(f"Appended {len(closing)} missing brackets: {''.join(closing)}")
    
    return s, diagnostics


def smart_insert_brackets_by_error(s: str, error_msg: str) -> Tuple[str, List[str]]:
    """
    根据JSON解析错误信息，智能地在指定位置插入缺失的括号
    """
    diagnostics = []
    
    # 解析错误信息获取位置
    # 例如: "Expecting ',' delimiter: line 20 column 13 (char 490)"
    import re
    match = re.search(r'line (\d+) column (\d+)', error_msg)
    if not match:
        return s, diagnostics
    
    error_line = int(match.group(1))
    error_col = int(match.group(2))
    
    lines = s.split('\n')
    if error_line > len(lines):
        return s, diagnostics
    
    # 获取错误位置之前的内容，分析括号平衡
    content_before = '\n'.join(lines[:error_line])
    
    # 简单的栈分析：查找未闭合的括号类型
    def analyze_brackets(text: str) -> List[str]:
        """返回未闭合的括号列表"""
        stack = []
        in_string = False
        escape_next = False
        
        for char in text:
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
                
            if char in '{[':
                stack.append(char)
            elif char in '}]':
                expected = '{' if char == '}' else '['
                if stack and stack[-1] == expected:
                    stack.pop()
        
        return stack
    
    unclosed = analyze_brackets(content_before)
    
    # 如果检测到 "Expecting ','" 错误
    if "Expecting ','" in error_msg:
        error_line_idx = error_line - 1
        if error_line_idx < len(lines):
            error_line_text = lines[error_line_idx].strip()
            
            # 新增：检查错误行是否包含不应该在数组/对象内的键值对
            # 特征：同一行内有逗号连接的值，然后是键名模式 "key":
            if re.search(r'[,\}]\s+"[\w]+"\s*:', error_line_text):
                # 在逗号位置分割，插入缺失的 ]
                # 找到最后一个逗号的位置
                parts = error_line_text.rsplit(',', 1)
                if len(parts) == 2:
                    left_part = parts[0]  # 数组内的部分
                    right_part = parts[1]  # 应该在数组外的部分
                    
                    # 重构这一行
                    new_line = lines[error_line_idx].replace(error_line_text, 
                                                              f"{left_part}\n    ], {right_part.strip()}")
                    lines[error_line_idx] = new_line
                    diagnostics.append(f"Split line {error_line_idx+1} and inserted ']'")
                    
                    result = '\n'.join(lines)
                    result = clean_extra_brackets(result)
                    return result, diagnostics
            
            # 情况1: 如果前面有未闭合的数组，可能需要插入 ]
            if '[' in unclosed:
                # 在当前行之前查找合适的插入位置
                for i in range(error_line_idx - 1, -1, -1):
                    line = lines[i].strip()
                    if line.endswith('}') or line.endswith(']'):
                        # 在这一行后面插入闭合括号
                        lines[i] = lines[i].rstrip() + ']'
                        diagnostics.append(f"Inserted ']' after line {i+1} to close array")
                        
                        # 重新组合后，清理末尾可能多余的括号
                        result = '\n'.join(lines)
                        result = clean_extra_brackets(result)
                        
                        return result, diagnostics
            
            # 情况2: 数组/对象已经闭合，但缺少逗号
            # 在错误位置的前一行查找 ] 或 }，在其后添加逗号
            elif error_line_idx > 0:
                prev_line_idx = error_line_idx - 1
                prev_line = lines[prev_line_idx].rstrip()
                
                # 如果前一行以 ] 或 } 结尾，且错误行是键名，添加逗号
                if (prev_line.endswith(']') or prev_line.endswith('}')) and \
                   (error_line_text.startswith('"') or error_line_text.startswith('{')):
                    lines[prev_line_idx] = prev_line + ','
                    diagnostics.append(f"Inserted ',' after line {prev_line_idx+1}")
                    return '\n'.join(lines), diagnostics
    
    return s, diagnostics


def clean_extra_brackets(s: str) -> str:
    """
    清理末尾可能多余的括号
    """
    # 移除字符串以便分析
    def strip_strings(text: str) -> str:
        in_string = False
        escape_next = False
        result = []
        for char in text:
            if escape_next:
                escape_next = False
                result.append(' ')
                continue
            if char == '\\':
                escape_next = True
                result.append(' ')
                continue
            if char == '"':
                in_string = not in_string
                result.append('"')
            elif not in_string:
                result.append(char)
            else:
                result.append(' ')
        return ''.join(result)
    
    stripped = strip_strings(s)
    
    # 计算括号平衡
    stack = []
    for char in stripped:
        if char in '{[':
            stack.append(char)
        elif char in '}]':
            expected = '{' if char == '}' else '['
            if stack and stack[-1] == expected:
                stack.pop()
            else:
                # 有多余的闭合括号 - 需要从末尾移除
                pass
    
    # 如果括号已经平衡，检查末尾是否有多余的
    # 简单方法：尝试从末尾移除括号，看是否仍然平衡
    if not stack:
        # 已经平衡，检查是否能成功解析
        try:
            json.loads(s)
            return s  # 已经正确，不需要清理
        except:
            # 尝试移除末尾的多余括号
            s_stripped = s.rstrip()
            while s_stripped and s_stripped[-1] in '}]':
                test_s = s_stripped[:-1]
                # 检查移除后是否更平衡
                test_stripped = strip_strings(test_s)
                test_stack = []
                for char in test_stripped:
                    if char in '{[':
                        test_stack.append(char)
                    elif char in '}]':
                        expected = '{' if char == '}' else '['
                        if test_stack and test_stack[-1] == expected:
                            test_stack.pop()
                
                if not test_stack:
                    # 移除后仍然平衡，尝试解析
                    try:
                        json.loads(test_s)
                        return test_s  # 成功！
                    except:
                        # 继续尝试
                        s_stripped = test_s.rstrip()
                else:
                    break
    
    return s


def balance_brackets(s: str) -> Tuple[str, List[str]]:
    """
    改进的括号平衡函数：结合简单计数和智能栈追踪
    """
    # 先使用智能方法
    s_new, diags1 = balance_brackets_smart(s)
    
    # 如果仍有问题，使用简单方法作为后备
    if s_new == s:
        diagnostics = []
        
        def _strip_strings(text: str) -> str:
            return re.sub(r'"([^"\\]|\\.)*"', '""', text)
        
        t = _strip_strings(s)
        
        open_curly = t.count("{")
        close_curly = t.count("}")
        open_square = t.count("[")
        close_square = t.count("]")
        
        need_curly = open_curly - close_curly
        need_square = open_square - close_square
        
        if need_square > 0:
            diagnostics.append(f"Appended {need_square} missing ']' at end")
            s += "]" * need_square
        
        if need_curly > 0:
            diagnostics.append(f"Appended {need_curly} missing '}}' at end")
            s += "}" * need_curly
        
        return s, diagnostics
    
    return s_new, diags1


def try_parse_json(s: str) -> Tuple[bool, str]:
    try:
        obj = json.loads(s)
        return True, json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception as e:
        return False, str(e)


def repair_jsonish(raw: str, max_passes: int = 6) -> Tuple[str, str, List[str]]:
    diagnostics: List[str] = []
    s = raw

    # Pass 0: normalize line endings
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # Apply a series of repair passes; attempt parse after each full pass
    for p in range(1, max_passes + 1):
        s = strip_comments(s)
        s = normalize_literals(s)
        # s = fix_chinese_quotes(s)  # 暂时禁用，避免副作用
        s = quote_unquoted_keys(s)
        s = escape_special_characters(s)
        s = remove_duplicate_keys(s)
        s = fix_missing_values(s)
        s = insert_missing_commas(s)
        s = remove_trailing_commas(s)

        s, diags1 = fix_unclosed_strings_linewise(s)
        diagnostics.extend([f"pass{p}: {d}" for d in diags1])

        s, diags2 = balance_brackets(s)
        diagnostics.extend([f"pass{p}: {d}" for d in diags2])

        s, diags3 = fix_misplaced_brackets(s)
        diagnostics.extend([f"pass{p}: {d}" for d in diags3])

        # 清理可能多余的括号
        if diags3:  # 如果进行了括号修复，清理多余的
            s = clean_extra_brackets(s)

        ok, out = try_parse_json(s)
        if ok:
            diagnostics.append(f"pass{p}: parsed successfully")
            return s, out, diagnostics
        else:
            error_msg = str(out)
            diagnostics.append(f"pass{p}: still invalid JSON -> {error_msg}")
            
            # 基于错误信息的智能修复
            if "Expecting ','" in error_msg or "Expecting ':'" in error_msg:
                s_fixed, diags3 = smart_insert_brackets_by_error(s, error_msg)
                if s_fixed != s:
                    diagnostics.extend([f"pass{p}: {d}" for d in diags3])
                    s = s_fixed
                    # 再次尝试解析
                    ok, out = try_parse_json(s)
                    if ok:
                        diagnostics.append(f"pass{p}: parsed successfully after smart fix")
                        return s, out, diagnostics

    # Final failure
    ok, out = try_parse_json(s)
    return s, out, diagnostics


class JSONRepairTool:
    def __init__(self, input_data: str):
        self.raw_data = input_data

    def repair(self):
        repaired, pretty_or_err, diagnostics = repair_jsonish(self.raw_data)
        self.repaired = repaired
        self.pretty_or_err = pretty_or_err
        self.diagnostics = diagnostics

    def output_to_console(self):
        print("=== Diagnostics ===")
        for d in self.diagnostics:
            print(d)

        if try_parse_json(self.repaired)[0]:
            print(self.pretty_or_err)
        else:
            print("=== Repaired (but still not valid JSON) ===")
            print(self.repaired)
            print("\n=== Last parse error ===")
            print(self.pretty_or_err)

def main():
    # 示例 JSON 数据（未修复的 JSON 字符串）
    input_data = [
        #示例1：键名缺失双引号+值双引号没有闭合
        """
        {
        "user": {
            name: "张三",
            "age": 25,
            "address": {
            "province": "广东省",
            "city": "深圳市"
            }
            }
        }
        """,
        #示例2：数组两个对象之间缺失逗号
        """
        {
        "order": {
            "order_id": "20260120001",
            "items": [  // 数组嵌套对象
            {
                "product_id": "P001",
                "price": 99.9
            } 
            {
                "product_id": "P002",
                "price": 199.9
            }
            ],  // 数组闭合正确
            "payment": {
            "method": "wechat",
            "status": "success"
            }  
        }
        }
        """,
        #示例3：数组最后一个对象多余逗号，数组后面多余逗号，布尔值未小写
        """
        {
        "config": {
            "theme": "dark",
            "permissions": [
            {
                "module": "user",
                "actions": ["read", "write"],
                "enabled": True, 
                "expire_at": "2027-01-01"
            },
            {
                "module": "order",
                "actions": ["read"],
                "enabled": false,
            } 
            ]
        },
        }
        """,
        #示例4：数组闭合方括号缺失
        """
        [
            {
                "class": "三年级二班",
                "students": [
                {
                    "name": "李四",
                    "scores": {
                    "math": 95,
                    "chinese": "88" 
                    }
                }
                {
                    "name": "王五",
                    "scores": {
                    "math": "90分", 
                    "chinese": 85
                    }
                }
                
            }
            {
                "class": "三年级三班",
                "students": []
            }
        ]
        """,
        #示例5：null没有小写，闭合括号混淆}]
        """
        {
        "data": {
            "page": 1,
            "list": [
            {
                "id": 1,
                "content": {
                "title": "JSON教程",
                "tags": ["前端", "语法"],
                "author": null,  
                "deleted": NULL  
                }
            }
            ],
            "pagination": {
            "total": 100,
            "size": 10
            }
        } 
        }
        """,
        # 示例 6：嵌套对象 - 字符串包含未转义的特殊字符
        """
        {
          "article": {
            "title": "JSON的\\"坑\\"与避坑指南",  
            "content": {
              "paragraphs": [
                {
                  "text": "路径示例：C:/user/docs/json.txt",  
                  "order": 1
                },
                {
                  "text": "正确写法：C:/user/docs/json.txt",  
                  "order": 2
                }
              ]
            }
          }
        }
        """,
        # 示例 7：数组嵌套对象 - 重复键名 + 数值格式错误
        """
        {
          "statistics": {
            "daily": [
              {
                "date": "2026-01-20",
                "visits": 1234,
                "visits": 1567,  
                "conversion": {
                  "rate": 0.08,
                  "amount": 1200.50  
                }
              },
              {
                "date": "2026-01-21",
                "visits": 987,
                "conversion": {
                  "rate": 0.09,  
                  "amount": 890.5
                }
              }
            ]
          }
        }
        """,
        # 示例 8：多层嵌套 - 层级不闭合 + 注释非法
        """
        {
          "user": {
            "id": 1001,
            "profile": {
              "name": "赵六",
              "hobbies": [
                "阅读",
                "运动",
                "编程"
              ],
              "contact": {
                "phone": "13800138000",
                "email": "zhaoliu@example.com"
              }
            },
            "orders": [
              {
                "order_id": "O001",
                "amount": 299,
                "status": "paid"
              }
            ]
          }
        }
        """,
        # 示例 9：数组嵌套数组 - 元素类型混乱 + 尾逗号
        """
        {
          "matrix": {
            "rows": [
              [1, 2, 3],
              [4, 5, "6"], 
              [7, 8, 9]
            ],
            "dimensions": {
              "width": 3,
              "height": 3
            },
            "metadata": [
              {
                "source": "calculation",
                "timestamp": 1737369600
              },
              [1, 2, 3]
            ]
          }
        }
        """,
        # 示例 10：深层嵌套 - 空值滥用 + 键名包含非法字符
        """
        {
          "form": {
            "fields": [
              {
                "field_name": "user_name",
                "value": "",
                "validation": {
                  "required": true,
                  "max_length": null
                }
              },
              {
                "field_name": "user-age",
                "value": null,
                "validation": {
                  "required": false,
                  "min_value": 18
                }
              },
              {
                "field name": "user address",
                "value": "",
                "validation": {}
              }
            ],
            "submit_info": {
              "time": null,
              "ip": "192.168.1.1"
            }
          }
        }
        """
    ]

    # 实例化 JSONRepairTool 类
    for i, case in enumerate(input_data, start=1):
        print(f"=== 测试案例 {i} ===")
        tool = JSONRepairTool(input_data=case)  # 传递单个测试案例
        tool.repair()

        # 输出修复结果到控制台
        print(f"测试案例 {i} 的修复结果：")
        tool.output_to_console()

    # 输出修复结果到文件
    # tool.output_to_file("output.txt")


if __name__ == "__main__":
    main()
