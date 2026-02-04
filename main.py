import sys
import re
import json
from typing import Tuple, List


# ============================================================================
# 第一层：核心处理器类 - 封装所有JSON修复算法
# ============================================================================

class JSONRepairProcessor:
    """
    JSON修复核心处理器
    
    职责：
    - 包含所有修复算法
    - 无状态设计（所有方法都是静态的）
    - 可以独立使用，也可以被其他类调用
    - 易于测试和维护
    
    架构：采用静态方法，避免全局命名空间污染
    """
    
    # ========== 正则表达式（类变量） ==========
    RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
    RE_LINE_COMMENT = re.compile(r"//.*?$", re.M)
    RE_UNQUOTED_KEY = re.compile(
        r'([{\[,\n]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)',
        flags=re.M
    )
    RE_TRAILING_COMMA = re.compile(r",\s*([}\]])")
    RE_MISSING_COMMA_1 = re.compile(r"(\}|\]|\")\s*(\{|\[|\")")
    RE_MISSING_COMMA_OBJ = re.compile(r"(\})\s*(\{)")
    RE_TRUE = re.compile(r"\bTrue\b")
    RE_FALSE = re.compile(r"\bFalse\b")
    RE_NULL_UPPER = re.compile(r"\bNULL\b")

    RE_BARE_KV_SNIPPET = re.compile(r'^\s*"\s*[^"]+\s*"\s*:\s*', re.S)
    RE_REMOVE_QUOTE_AFTER_CONTAINER = re.compile(r'([}\]])\s*"\s*(?=,|\}|\]|$)')
    
    # ========== 基础清理方法 ==========

    @staticmethod
    def _compute_string_ranges(s: str) -> List[Tuple[int, int]]:
        """
        计算 JSON 文本中字符串字面量的区间（包含引号本身）。
        注意：该方法基于 JSON 的转义规则（\\ 和 \") 做近似扫描；
        对“未闭合字符串”会把区间延伸到文本末尾。
        """
        ranges: List[Tuple[int, int]] = []
        in_string = False
        escape_next = False
        start = -1

        for i, ch in enumerate(s):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"':
                if not in_string:
                    in_string = True
                    start = i
                else:
                    in_string = False
                    ranges.append((start, i))
                    start = -1

        if in_string and start >= 0:
            ranges.append((start, len(s) - 1))

        return ranges

    @staticmethod
    def _index_in_ranges(idx: int, ranges: List[Tuple[int, int]]) -> bool:
        """idx 是否落在任一 (start, end) 闭区间内"""
        # ranges 通常很少，用线性扫描即可；如后续性能需要再做二分
        for a, b in ranges:
            if a <= idx <= b:
                return True
        return False

    @staticmethod
    def _sub_outside_strings(s: str, regex: re.Pattern, repl) -> str:
        """
        仅对“字符串字面量之外”的匹配进行替换。
        repl 可为字符串或 callable(match) -> str，行为类似 re.sub。
        """
        ranges = JSONRepairProcessor._compute_string_ranges(s)
        out = []
        last = 0

        for m in regex.finditer(s):
            if JSONRepairProcessor._index_in_ranges(m.start(), ranges):
                continue
            out.append(s[last:m.start()])
            if callable(repl):
                out.append(repl(m))
            else:
                out.append(m.expand(repl))
            last = m.end()

        out.append(s[last:])
        return "".join(out)
    
    @staticmethod
    def strip_comments(s: str) -> str:
        """去除JSON字符串中的注释"""
        # 仅在字符串之外去注释，避免误删 URL/路径等文本
        s2 = JSONRepairProcessor._sub_outside_strings(s, JSONRepairProcessor.RE_BLOCK_COMMENT, "")
        s3 = JSONRepairProcessor._sub_outside_strings(s2, JSONRepairProcessor.RE_LINE_COMMENT, "")
        return s3
    
    @staticmethod
    def normalize_literals(s: str) -> str:
        """规范化布尔值和null字面量"""
        # 只在字符串之外规范化，避免把业务文本里的 True/False/NULL 改掉
        s = JSONRepairProcessor._sub_outside_strings(s, JSONRepairProcessor.RE_TRUE, "true")
        s = JSONRepairProcessor._sub_outside_strings(s, JSONRepairProcessor.RE_FALSE, "false")
        s = JSONRepairProcessor._sub_outside_strings(s, JSONRepairProcessor.RE_NULL_UPPER, "null")
        return s
    
    @staticmethod
    def fix_chinese_quotes(s: str) -> str:
        """将中文引号替换为对应的英文符号（作为普通字符）"""
        s = s.replace('"', '＂')  # 中文左引号 -> 全角双引号
        s = s.replace('"', '＂')  # 中文右引号 -> 全角双引号
        s = s.replace(''', "'")   # 中文左单引号 -> 英文单引号
        s = s.replace(''', "'")   # 中文右单引号 -> 英文单引号
        return s
    
    @staticmethod
    def quote_unquoted_keys(s: str) -> str:
        """为未加引号的键名添加引号"""
        def replacer(match):
            return f'{match.group(1)}"{match.group(2)}"{match.group(3)}'
        
        max_iterations = 10
        for _ in range(max_iterations):
            new_s = JSONRepairProcessor._sub_outside_strings(s, JSONRepairProcessor.RE_UNQUOTED_KEY, replacer)
            if new_s == s:
                break
            s = new_s
        return s
    
    @staticmethod
    def escape_special_characters(s: str) -> str:
        """转义特殊字符（当前版本简化处理）"""
        # 简化版本：不进行额外转义，因为大多数情况下字符串已经正确
        # 过度转义会导致问题（如反斜杠指数增长）
        return s
    
    @staticmethod
    def remove_trailing_commas(s: str) -> str:
        """删除尾随逗号"""
        prev = None
        while prev != s:
            prev = s
            s = JSONRepairProcessor._sub_outside_strings(s, JSONRepairProcessor.RE_TRAILING_COMMA, r"\1")
        return s
    
    @staticmethod
    def fix_misplaced_brackets(s: str) -> Tuple[str, List[str]]:
        """修复错位的括号，例如: "key": "value"] 应该是 "key": "value" }]"""
        diagnostics = []
        lines = s.split('\n')
        
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            
            if stripped.endswith(']') and not stripped.endswith(']]'):
                before_bracket = stripped[:-1].rstrip()
                if not before_bracket:
                    continue
                
                # 检查是否是对象值后面跟着 ]（例如 "key": "value"]）
                # 排除嵌套数组的情况（例如 [1, 2, 3]）
                is_after_object_value = (
                    before_bracket.endswith('"') or 
                    before_bracket.endswith('}') or 
                    before_bracket.endswith('true') or 
                    before_bracket.endswith('false') or 
                    before_bracket.endswith('null')
                )
                
                # 如果是数字结尾，检查是否在数组上下文中
                if before_bracket and before_bracket[-1].isdigit():
                    # 检查这一行是否包含逗号或数组开始符号，这通常意味着是数组元素
                    if '[' in stripped or ',' in stripped:
                        # 这很可能是数组元素，不需要修复
                        continue
                    is_after_object_value = True
                
                if is_after_object_value:
                    content_before = '\n'.join(lines[:i]) + '\n' + before_bracket
                    
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
                    
                    # 只有当有未闭合的对象且数组也未闭合，并且看起来像对象值时才插入 }
                    if open_obj > 0 and open_arr > 0:
                        indent = len(line) - len(line.lstrip())
                        new_line = before_bracket + '\n' + ' ' * indent + '}\n' + ' ' * max(0, indent-4) + ']'
                        lines[i] = new_line
                        diagnostics.append(f"Inserted '}}' before ']' on line {i+1}")
                        return '\n'.join(lines), diagnostics
        
        return s, diagnostics
    
    @staticmethod
    def insert_missing_commas(s: str) -> str:
        """插入缺失的逗号"""
        max_iterations = 10
        for _ in range(max_iterations):
            prev = s
            
            s = JSONRepairProcessor._sub_outside_strings(
                s, JSONRepairProcessor.RE_MISSING_COMMA_OBJ, r"\1, \2"
            )
            s = JSONRepairProcessor._sub_outside_strings(
                s, JSONRepairProcessor.RE_MISSING_COMMA_1, r"\1, \2"
            )
            
            s = JSONRepairProcessor._sub_outside_strings(
                s, re.compile(r'(\}|\])\s*\n\s*(\{|\[)'), r'\1,\n\2'
            )
            s = JSONRepairProcessor._sub_outside_strings(
                s, re.compile(r'(\}|\])\s+(")'), r'\1, \2'
            )
            s = JSONRepairProcessor._sub_outside_strings(
                s, re.compile(r'(\d+|"[^"]*")\s+("[\w]+"\s*:)'), r'\1, \2'
            )
            s = JSONRepairProcessor._sub_outside_strings(
                s,
                re.compile(r'(\d+|"[^"]*"|true|false|null)\s*\n\s*("[\w]+"\s*:)'),
                r'\1,\n\2'
            )
            s = JSONRepairProcessor._sub_outside_strings(
                s, re.compile(r'(\}|\])\s*\n\s*("[\w]+"\s*:)'), r'\1,\n\2'
            )
            
            if s == prev:
                break
        
        return s
    
    @staticmethod
    def remove_duplicate_keys(s: str) -> str:
        """移除重复的键名"""
        try:
            obj = json.loads(s)
            return json.dumps(obj, ensure_ascii=False)
        except:
            return s
    
    @staticmethod
    def fix_missing_values(s: str) -> str:
        """修复键值对中缺失的值"""
        return JSONRepairProcessor._sub_outside_strings(
            s, re.compile(r'"(\w+)":\s*,'), r'"\1": null,'
        )

    @staticmethod
    def wrap_bare_kv_snippet(s: str) -> Tuple[str, List[str]]:
        """
        如果输入是 `"key": value` 这样的片段（缺少最外层 `{}`），自动包一层对象壳。
        这类输入在日志/截断文本里很常见。
        """
        diagnostics: List[str] = []
        t = s.lstrip()
        if not t:
            return s, diagnostics

        if t[0] not in "{[" and JSONRepairProcessor.RE_BARE_KV_SNIPPET.search(t):
            diagnostics.append("wrapped bare key/value snippet with surrounding '{ }'")
            return "{\n" + s + "\n}", diagnostics
        return s, diagnostics

    @staticmethod
    def promote_stringified_json_values(s: str) -> Tuple[str, List[str]]:
        """
        处理一种非常常见的“粘贴错误”：
        外层 JSON 里 `"result": "{ ... }"` 这样的字段，本应是字符串化 JSON，
        但由于粘贴/转义丢失，导致字符串里出现未转义的 `"` 和裸换行，
        使得外层 JSON 直接不合法。

        策略：
        - 当检测到值形如 `"key": "{ <换行/空格> "<something>": ...`（即 `{` 后面很快就出现未转义 `"`）
          认为这是“被错误加引号的 JSON”，将其提升为真正的对象/数组：把 `:"{` 变为 `:{`
        - 随后删除容器闭合后的残留 `"`（例如 `}"` / `]"`）
        """
        diagnostics: List[str] = []
        out: List[str] = []
        last = 0

        # 匹配 `"key": "`（值的 opening quote）
        for m in re.finditer(r'"([^"]+)"\s*:\s*"', s):
            open_quote_pos = m.end() - 1
            brace_pos = m.end()
            if brace_pos >= len(s):
                continue
            if s[brace_pos] not in "{[":
                continue

            # lookahead: `{`/`[` 后跳过空白，看是否立刻遇到未转义引号 "
            j = brace_pos + 1
            while j < len(s) and s[j] in " \t\r\n":
                j += 1
            if j < len(s) and s[j] == '"':
                # 这是“字符串化 JSON 但转义丢失”的典型特征：字符串里出现未转义的键引号
                out.append(s[last:open_quote_pos])  # 不包含 opening quote
                last = open_quote_pos + 1  # 跳过 opening quote
                diagnostics.append(f"promoted stringified JSON value for key '{m.group(1)}' to real container")

        if not out:
            return s, diagnostics

        out.append(s[last:])
        s2 = "".join(out)

        # 删除容器闭合后的残留引号，例如 `}"` / `]"`
        s2 = JSONRepairProcessor._sub_outside_strings(s2, JSONRepairProcessor.RE_REMOVE_QUOTE_AFTER_CONTAINER, r"\1")

        return s2, diagnostics

    @staticmethod
    def remove_stray_quote_after_number_token(s: str) -> Tuple[str, List[str]]:
        """
        移除一种典型的截断/拼接残片：数字 token 后面紧跟一个多余的 `"`，例如 `...[2", ...` 或 `... 123" ]`。
        这个 `"` 会把后续文本错误地带入字符串，造成连锁解析失败。

        规则（仅在字符串之外生效）：
        - 遇到 `"` 时，若其前一个非空白字符属于数字 token（0-9 或 token 内字符 .+-eE），
          且该数字 token 的起始前一字符不是 `"`（避免误伤 `"123"` 这类合法字符串），
          且 `"` 后一个非空白字符是 `,` / `]` / `}`，则删除该 `"`。
        """
        diagnostics: List[str] = []
        chars = list(s)
        in_string = False
        escape_next = False
        removed = 0

        def is_num_char(ch: str) -> bool:
            return ch.isdigit() or ch in ".+-eE"

        i = 0
        while i < len(chars):
            ch = chars[i]
            if escape_next:
                escape_next = False
                i += 1
                continue
            if ch == "\\":
                escape_next = True
                i += 1
                continue
            if ch == '"':
                if not in_string:
                    # 可能是“数字后多余的引号”
                    # 向左找前一个非空白字符
                    k = i - 1
                    while k >= 0 and chars[k] in " \t\r\n":
                        k -= 1
                    if k >= 0 and is_num_char(chars[k]):
                        # 找到数字 token 的起始
                        start = k
                        while start - 1 >= 0 and is_num_char(chars[start - 1]):
                            start -= 1
                        # token 起始前一个字符不能是引号（避免误伤字符串 "123"）
                        prev = start - 1
                        while prev >= 0 and chars[prev] in " \t\r\n":
                            prev -= 1
                        if prev < 0 or chars[prev] != '"':
                            # 向右找后一个非空白字符
                            j = i + 1
                            while j < len(chars) and chars[j] in " \t\r\n":
                                j += 1
                            if j < len(chars) and chars[j] in ",]}":
                                chars.pop(i)
                                removed += 1
                                # 不递增 i，继续检查当前位置
                                continue
                    # 普通开引号
                    in_string = True
                    i += 1
                    continue
                else:
                    in_string = False
                    i += 1
                    continue
            i += 1

        if removed:
            diagnostics.append(f"removed {removed} stray quote(s) after number token")
        return "".join(chars), diagnostics

    @staticmethod
    def fix_unclosed_strings_global(s: str) -> Tuple[str, List[str]]:
        """
        全局修复未闭合字符串/末尾悬挂反斜杠，并把字符串中的“裸换行”转成 \\n。
        这比逐行补引号更稳健，尤其适用于超长或跨行字符串（例如字段里塞了大段 JSON 文本）。
        """
        diagnostics: List[str] = []
        out_chars: List[str] = []

        in_string = False
        escape_next = False

        for ch in s:
            if escape_next:
                escape_next = False
                out_chars.append(ch)
                continue

            if ch == "\\":
                escape_next = True
                out_chars.append(ch)
                continue

            if ch == '"':
                in_string = not in_string
                out_chars.append(ch)
                continue

            if in_string and ch == "\n":
                out_chars.append("\\n")
                diagnostics.append("escaped raw newline inside string as '\\n'")
                continue

            out_chars.append(ch)

        if escape_next:
            # 最末尾是悬挂的反斜杠，属于非法转义；保守起见移除
            if out_chars and out_chars[-1] == "\\":
                out_chars.pop()
                diagnostics.append("removed dangling backslash at end of text")

        if in_string:
            out_chars.append('"')
            diagnostics.append("appended missing '\"' at end (unterminated string)")

        return "".join(out_chars), diagnostics

    @staticmethod
    def truncate_after_last_container_close(s: str) -> Tuple[str, List[str]]:
        """
        截断“尾部垃圾/截断残片”：
        如果文本末尾因为复制截断导致出现半个 token（例如 `"coord": [2",` / 缺半个对象），
        可尝试把内容截断到最后一个在字符串之外出现的 `}` 或 `]` 之后，
        再交给括号平衡逻辑补齐外层结构。

        这不会恢复缺失的数据，但能让 JSON 重新可解析（尽可能保留前面完整部分）。
        """
        diagnostics: List[str] = []
        in_string = False
        escape_next = False
        last_close = -1

        for i, ch in enumerate(s):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string and ch in "}]":
                last_close = i

        if last_close >= 0 and last_close < len(s) - 1:
            tail = s[last_close + 1 :]
            if tail.strip():
                diagnostics.append("truncated trailing garbage after last '}'/']'")
                return s[: last_close + 1], diagnostics

        return s, diagnostics

    @staticmethod
    def truncate_around_error_position(s: str, error_msg: str) -> Tuple[str, List[str]]:
        """
        当解析错误指向某个 char 位置时，尝试从该位置起丢弃尾部，
        并进一步截断到最后一个 `}`/`]`，用来应对“中途截断/半个 token”。
        """
        diagnostics: List[str] = []
        m = re.search(r"\(char (\d+)\)", error_msg)
        if not m:
            return s, diagnostics
        try:
            pos = int(m.group(1))
        except Exception:
            return s, diagnostics
        if pos <= 0 or pos >= len(s):
            return s, diagnostics

        prefix = s[:pos]
        prefix2, diags2 = JSONRepairProcessor.truncate_after_last_container_close(prefix)
        if prefix2 != prefix:
            diagnostics.extend(diags2)
        if prefix2 != s:
            diagnostics.append("truncated text around JSON parse error position")
            return prefix2, diagnostics
        return s, diagnostics
    
    @staticmethod
    def fix_unclosed_strings_linewise(s: str) -> Tuple[str, List[str]]:
        """修复未闭合的字符串"""
        diagnostics = []
        lines = s.splitlines()
        fixed_lines = []
        
        for i, line in enumerate(lines, start=1):
            tmp = re.sub(r'\\"', '', line)
            quote_count = tmp.count('"')
            if quote_count % 2 == 1:
                diagnostics.append(f"Line {i}: suspected unclosed string; appended '\"'")
                fixed_lines.append(line + '"')
            else:
                fixed_lines.append(line)
        
        return "\n".join(fixed_lines), diagnostics
    
    @staticmethod
    def balance_brackets_smart(s: str) -> Tuple[str, List[str]]:
        """智能平衡括号：使用栈追踪嵌套结构"""
        diagnostics = []
        
        def strip_strings(text: str) -> str:
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
        
        stack = []
        positions = []
        
        for i, char in enumerate(stripped):
            if char in '{[':
                stack.append(char)
                positions.append(i)
            elif char in '}]':
                expected = '{' if char == '}' else '['
                if stack and stack[-1] == expected:
                    stack.pop()
                    positions.pop()
        
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
    
    @staticmethod
    def smart_insert_brackets_by_error(s: str, error_msg: str) -> Tuple[str, List[str]]:
        """根据JSON解析错误信息，智能地在指定位置插入缺失的括号"""
        diagnostics = []
        
        match = re.search(r'line (\d+) column (\d+)', error_msg)
        if not match:
            return s, diagnostics
        
        error_line = int(match.group(1))
        error_col = int(match.group(2))
        
        lines = s.split('\n')
        if error_line > len(lines):
            return s, diagnostics
        
        content_before = '\n'.join(lines[:error_line])
        
        def analyze_brackets(text: str) -> List[str]:
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
        
        if "Expecting ','" in error_msg:
            error_line_idx = error_line - 1
            if error_line_idx < len(lines):
                error_line_text = lines[error_line_idx].strip()
                
                if re.search(r'[,\}]\s+"[\w]+"\s*:', error_line_text):
                    parts = error_line_text.rsplit(',', 1)
                    if len(parts) == 2:
                        left_part = parts[0]
                        right_part = parts[1]
                        
                        new_line = lines[error_line_idx].replace(error_line_text, 
                                                                  f"{left_part}\n    ], {right_part.strip()}")
                        lines[error_line_idx] = new_line
                        diagnostics.append(f"Split line {error_line_idx+1} and inserted ']'")
                        
                        result = '\n'.join(lines)
                        result = JSONRepairProcessor.clean_extra_brackets(result)
                        return result, diagnostics
                
                if '[' in unclosed:
                    for i in range(error_line_idx - 1, -1, -1):
                        line = lines[i].strip()
                        if line.endswith('}') or line.endswith(']'):
                            lines[i] = lines[i].rstrip() + ']'
                            diagnostics.append(f"Inserted ']' after line {i+1} to close array")
                            
                            result = '\n'.join(lines)
                            result = JSONRepairProcessor.clean_extra_brackets(result)
                            
                            return result, diagnostics
                
                elif error_line_idx > 0:
                    prev_line_idx = error_line_idx - 1
                    prev_line = lines[prev_line_idx].rstrip()
                    
                    if (prev_line.endswith(']') or prev_line.endswith('}')) and \
                       (error_line_text.startswith('"') or error_line_text.startswith('{')):
                        lines[prev_line_idx] = prev_line + ','
                        diagnostics.append(f"Inserted ',' after line {prev_line_idx+1}")
                        return '\n'.join(lines), diagnostics
        
        return s, diagnostics
    
    @staticmethod
    def clean_extra_brackets(s: str) -> str:
        """清理末尾可能多余的括号"""
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
        
        stack = []
        for char in stripped:
            if char in '{[':
                stack.append(char)
            elif char in '}]':
                expected = '{' if char == '}' else '['
                if stack and stack[-1] == expected:
                    stack.pop()
        
        if not stack:
            try:
                json.loads(s)
                return s
            except:
                s_stripped = s.rstrip()
                while s_stripped and s_stripped[-1] in '}]':
                    test_s = s_stripped[:-1]
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
                        try:
                            json.loads(test_s)
                            return test_s
                        except:
                            s_stripped = test_s.rstrip()
                    else:
                        break
        
        return s
    
    @staticmethod
    def balance_brackets(s: str) -> Tuple[str, List[str]]:
        """改进的括号平衡函数：结合简单计数和智能栈追踪"""
        # 先使用智能方法
        s_new, diags1 = JSONRepairProcessor.balance_brackets_smart(s)
        
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
    
    @staticmethod
    def try_parse_json(s: str) -> Tuple[bool, str]:
        """尝试解析JSON字符串"""
        try:
            obj = json.loads(s)
            return True, json.dumps(obj, ensure_ascii=False, indent=2)
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def repair_jsonish(raw: str, max_passes: int = 6) -> Tuple[str, str, List[str]]:
        """
        主修复逻辑 - 协调所有修复方法
        
        Args:
            raw: 原始JSON字符串
            max_passes: 最大修复轮数，默认6
        
        Returns:
            (repaired_str, pretty_json_or_error, diagnostics)
        """
        diagnostics: List[str] = []
        s = raw
        
        # Pass 0: normalize line endings
        s = s.replace("\r\n", "\n").replace("\r", "\n")

        # Pre-pass: handle common snippet / pasted-string issues early
        s, diags0a = JSONRepairProcessor.wrap_bare_kv_snippet(s)
        diagnostics.extend([f"pre: {d}" for d in diags0a])

        s, diags0b = JSONRepairProcessor.promote_stringified_json_values(s)
        diagnostics.extend([f"pre: {d}" for d in diags0b])

        s, diags0c = JSONRepairProcessor.remove_stray_quote_after_number_token(s)
        diagnostics.extend([f"pre: {d}" for d in diags0c])
        
        # Apply a series of repair passes; attempt parse after each full pass
        for p in range(1, max_passes + 1):
            # Repeat these cheap pre-fixes; earlier passes may expose new structure
            s, diags_pre1 = JSONRepairProcessor.wrap_bare_kv_snippet(s)
            diagnostics.extend([f"pass{p}: {d}" for d in diags_pre1])
            s, diags_pre2 = JSONRepairProcessor.promote_stringified_json_values(s)
            diagnostics.extend([f"pass{p}: {d}" for d in diags_pre2])

            s, diags_pre3 = JSONRepairProcessor.remove_stray_quote_after_number_token(s)
            diagnostics.extend([f"pass{p}: {d}" for d in diags_pre3])

            s = JSONRepairProcessor.strip_comments(s)
            s = JSONRepairProcessor.normalize_literals(s)
            s = JSONRepairProcessor.quote_unquoted_keys(s)
            s = JSONRepairProcessor.escape_special_characters(s)
            s = JSONRepairProcessor.remove_duplicate_keys(s)
            s = JSONRepairProcessor.fix_missing_values(s)
            s = JSONRepairProcessor.insert_missing_commas(s)
            s = JSONRepairProcessor.remove_trailing_commas(s)
            
            s, diags1 = JSONRepairProcessor.fix_unclosed_strings_global(s)
            diagnostics.extend([f"pass{p}: {d}" for d in diags1])
            
            s, diags2 = JSONRepairProcessor.balance_brackets(s)
            diagnostics.extend([f"pass{p}: {d}" for d in diags2])
            
            s, diags3 = JSONRepairProcessor.fix_misplaced_brackets(s)
            diagnostics.extend([f"pass{p}: {d}" for d in diags3])
            
            # 清理可能多余的括号
            if diags3:
                s = JSONRepairProcessor.clean_extra_brackets(s)
            
            ok, out = JSONRepairProcessor.try_parse_json(s)
            if ok:
                diagnostics.append(f"pass{p}: parsed successfully")
                return s, out, diagnostics
            else:
                error_msg = str(out)
                diagnostics.append(f"pass{p}: still invalid JSON -> {error_msg}")

                # 先按错误位置截断（适配“中途截断/半 token”）
                s_cut, diags_cut = JSONRepairProcessor.truncate_around_error_position(s, error_msg)
                if s_cut != s:
                    diagnostics.extend([f"pass{p}: {d}" for d in diags_cut])
                    s = s_cut
                    s = JSONRepairProcessor.remove_trailing_commas(s)
                    s, diags_b0 = JSONRepairProcessor.balance_brackets(s)
                    diagnostics.extend([f"pass{p}: {d}" for d in diags_b0])
                    ok_cut, out_cut = JSONRepairProcessor.try_parse_json(s)
                    if ok_cut:
                        diagnostics.append(f"pass{p}: parsed successfully after error-position truncation")
                        return s, out_cut, diagnostics

                # 截断尾部残片（常见于复制/日志截断），再尝试一次
                s_trunc, diags_trunc = JSONRepairProcessor.truncate_after_last_container_close(s)
                if s_trunc != s:
                    diagnostics.extend([f"pass{p}: {d}" for d in diags_trunc])
                    s = s_trunc
                    # 再做一次轻量清理 + 括号补齐
                    s = JSONRepairProcessor.remove_trailing_commas(s)
                    s, diags_b = JSONRepairProcessor.balance_brackets(s)
                    diagnostics.extend([f"pass{p}: {d}" for d in diags_b])
                    ok2, out2 = JSONRepairProcessor.try_parse_json(s)
                    if ok2:
                        diagnostics.append(f"pass{p}: parsed successfully after truncation")
                        return s, out2, diagnostics
                
                # 基于错误信息的智能修复
                if "Expecting ','" in error_msg or "Expecting ':'" in error_msg:
                    s_fixed, diags4 = JSONRepairProcessor.smart_insert_brackets_by_error(s, error_msg)
                    if s_fixed != s:
                        diagnostics.extend([f"pass{p}: {d}" for d in diags4])
                        s = s_fixed
                        ok, out = JSONRepairProcessor.try_parse_json(s)
                        if ok:
                            diagnostics.append(f"pass{p}: parsed successfully after smart fix")
                            return s, out, diagnostics
        
        # Final failure
        ok, out = JSONRepairProcessor.try_parse_json(s)
        return s, out, diagnostics


# ============================================================================
# 第二层：用户接口类 - 简化的API
# ============================================================================

class JSONRepairTool:
    """
    JSON修复工具 - 用户友好接口
    
    职责：
    - 提供简单直观的API
    - 管理修复状态
    - 内部使用 JSONRepairProcessor 进行实际修复
    - 支持打印和返回结果
    
    使用示例：
        >>> tool = JSONRepairTool('{ name: "test" }')
        >>> tool.repair()
        >>> result = tool.get_result()
    """
    def __init__(self, input_data: str):
        self.raw_data = input_data
        self.repaired = None
        self.pretty_or_err = None
        self.diagnostics = []
        self.success = False

    def repair(self) -> bool:
        """
        执行JSON修复
        
        Returns:
            bool: 修复是否成功
        """
        repaired, pretty_or_err, diagnostics = JSONRepairProcessor.repair_jsonish(
            self.raw_data
        )
        self.repaired = repaired
        self.pretty_or_err = pretty_or_err
        self.diagnostics = diagnostics
        self.success = JSONRepairProcessor.try_parse_json(self.repaired)[0]
        return self.success

    def output_to_console(self, show_diagnostics=True):
        """
        输出修复结果到控制台（保留原有打印功能）
        同时返回结构化的结果数据
        
        Args:
            show_diagnostics: 是否显示诊断信息，默认True
        
        Returns:
            dict: 包含修复结果的字典
            {
                'success': bool,           # 修复是否成功
                'original': str,           # 原始数据
                'repaired': str,           # 修复后的数据
                'pretty_json': str,        # 格式化的JSON（如果成功）
                'error': str,              # 错误信息（如果失败）
                'diagnostics': list        # 诊断信息列表
            }
        """
        # 原有的打印逻辑
        if show_diagnostics:
            print("=== Diagnostics ===")
            for d in self.diagnostics:
                print(d)

        if self.success:
            print(self.pretty_or_err)
        else:
            print("=== Repaired (but still not valid JSON) ===")
            print(self.repaired)
            print("\n=== Last parse error ===")
            print(self.pretty_or_err)
        
        # 新增：返回结构化数据
        result = {
            'success': self.success,
            'original': self.raw_data,
            'repaired': self.repaired,
            'diagnostics': self.diagnostics.copy()
        }
        
        if self.success:
            result['pretty_json'] = self.pretty_or_err
            result['error'] = None
        else:
            result['pretty_json'] = None
            result['error'] = self.pretty_or_err
        
        return result

    def get_result(self):
        """
        获取修复结果（不打印，只返回数据）
        适用于工程化调用
        
        Returns:
            dict: 包含修复结果的字典
        """
        result = {
            'success': self.success,
            'original': self.raw_data,
            'repaired': self.repaired,
            'diagnostics': self.diagnostics.copy()
        }
        
        if self.success:
            result['pretty_json'] = self.pretty_or_err
            result['error'] = None
            # 解析为Python对象
            try:
                result['json_object'] = json.loads(self.repaired)
            except:
                result['json_object'] = None
        else:
            result['pretty_json'] = None
            result['error'] = self.pretty_or_err
            result['json_object'] = None
        
        return result

# ============================================================================
# 第三层：服务类 - 批处理和测试管理
# ============================================================================

class JSONRepairService:
    """
    JSON修复服务 - 高级封装
    
    职责：
    - 批量处理多个JSON字符串
    - 管理测试案例和运行测试
    - 生成统计报告
    - 提供工程化API
    
    使用示例：
        >>> service = JSONRepairService()
        >>> summary = service.run_tests()  # 运行所有测试
        >>> result = service.repair_single('{ broken json }')  # 单个修复
        >>> results = service.repair_batch([json1, json2, json3])  # 批量修复
    """
    
    def __init__(self, test_cases=None):
        """
        初始化修复服务
        
        Args:
            test_cases: 可选的测试案例列表，如果不提供则使用默认测试案例
        """
        if test_cases is None:
            self.test_cases = self._get_default_test_cases()
        else:
            self.test_cases = test_cases
        
        self.results = []  # 存储所有修复结果
    
    def _get_default_test_cases(self):
        """获取默认的测试案例"""
        return [
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
    
    def repair_single(self, json_string: str, silent=False):
        """
        修复单个JSON字符串
        
        Args:
            json_string: 需要修复的JSON字符串
            silent: 是否静默模式（不打印），默认False
        
        Returns:
            dict: 修复结果
        """
        tool = JSONRepairTool(input_data=json_string)
        tool.repair()
        
        if not silent:
            tool.output_to_console()
        
        return tool.get_result()
    
    def repair_batch(self, json_strings: list, silent=False):
        """
        批量修复多个JSON字符串
        
        Args:
            json_strings: JSON字符串列表
            silent: 是否静默模式（不打印），默认False
        
        Returns:
            list: 修复结果列表
        """
        results = []
        for i, json_str in enumerate(json_strings, start=1):
            if not silent:
                print(f"\n=== 处理案例 {i}/{len(json_strings)} ===")
            
            result = self.repair_single(json_str, silent=silent)
            results.append(result)
        
        return results
    
    def run_tests(self, show_diagnostics=True):
        """
        运行所有测试案例
        
        Args:
            show_diagnostics: 是否显示诊断信息
        
        Returns:
            dict: 包含统计信息和详细结果
            {
                'total': int,           # 总案例数
                'success': int,         # 成功数
                'failed': int,          # 失败数
                'success_rate': float,  # 成功率
                'results': list         # 详细结果列表
            }
        """
        self.results = []
        success_count = 0
        
        for i, case in enumerate(self.test_cases, start=1):
            print(f"\n=== 测试案例 {i} ===")
            print(f"测试案例 {i} 的修复结果：")
            
            tool = JSONRepairTool(input_data=case)
            tool.repair()
            result = tool.output_to_console(show_diagnostics=show_diagnostics)
            
            self.results.append({
                'case_number': i,
                'result': result
            })
            
            if result['success']:
                success_count += 1
        
        # 统计信息
        total = len(self.test_cases)
        summary = {
            'total': total,
            'success': success_count,
            'failed': total - success_count,
            'success_rate': (success_count / total * 100) if total > 0 else 0,
            'results': self.results
        }
        
        # 打印统计
        print(f"\n{'='*70}")
        print(f"测试完成统计:")
        print(f"  总案例数: {summary['total']}")
        print(f"  成功: {summary['success']}")
        print(f"  失败: {summary['failed']}")
        print(f"  成功率: {summary['success_rate']:.1f}%")
        print(f"{'='*70}")
        
        return summary
    
    def get_statistics(self):
        """
        获取统计信息（无需重新运行测试）
        
        Returns:
            dict: 统计信息
        """
        if not self.results:
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'success_rate': 0,
                'message': '还未运行测试'
            }
        
        total = len(self.results)
        success = sum(1 for r in self.results if r['result']['success'])
        
        return {
            'total': total,
            'success': success,
            'failed': total - success,
            'success_rate': (success / total * 100) if total > 0 else 0
        }


def main():
    """
    主函数 - 用于直接运行测试
    """
    service = JSONRepairService()
    service.run_tests()


if __name__ == "__main__":
    main()
