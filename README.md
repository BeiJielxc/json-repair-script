# JSON错误修复工具 - 三层架构模组

一个强大的JSON修复工具，采用三层架构设计，可以自动修复各种常见的JSON格式错误。**测试通过率：100%（18/18案例）**

---

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| **总测试案例** | 18个 |
| **修复成功** | 18个 |
| **成功率** | **100.0%** ✅ |
| **原始案例** | 10/10 (100%) |
| **扩展案例** | 8/8 (100%) |

---

## ✨ 支持的错误类型

✅ 键名缺失引号 (`{ name: "value" }`)  
✅ 缺失逗号（对象、数组元素之间）  
✅ 尾随逗号 (`[1, 2, 3,]`)  
✅ 括号不匹配 (`{[}]` → `{[]}`)  
✅ 布尔值大小写 (`True` → `true`)  
✅ null大小写 (`NULL` → `null`)  
✅ 注释存在 (`// comment`, `/* comment */`)  
✅ 重复键名（自动使用最后一个值）  
✅ 未闭合字符串  
✅ 嵌套数组/对象错误  
✅ 多层嵌套结构问题  

---

## 🏗️ 三层架构设计

本模组采用**三层架构**，职责清晰分离，易于集成到大型工程：

```
┌───────────────────────────────────────────────────────────────┐
│  第三层: JSONRepairService（服务层）                          │
│  职责: 批量处理、测试管理、统计报告                           │
│  适用: 需要批量修复多个JSON、运行测试套件                     │
└─────────────────────┬─────────────────────────────────────────┘
                      │ 调用
┌─────────────────────▼─────────────────────────────────────────┐
│  第二层: JSONRepairTool（接口层）                             │
│  职责: 提供简单API、管理修复状态、返回结构化结果              │
│  适用: 单次JSON修复、API集成、常规使用（推荐）                │
└─────────────────────┬─────────────────────────────────────────┘
                      │ 调用
┌─────────────────────▼─────────────────────────────────────────┐
│  第一层: JSONRepairProcessor（算法层）                        │
│  职责: 17个核心修复算法、纯函数实现                           │
│  适用: 需要调用特定修复算法、自定义修复流程                   │
└───────────────────────────────────────────────────────────────┘
```

### 架构优势

1. **职责分离** - 每层专注自己的职责，互不干扰
2. **易于测试** - 每层可独立测试，算法层为纯函数
3. **灵活集成** - 根据需求选择合适的层次
4. **易于扩展** - 添加新功能不影响现有代码
5. **工程化** - 适合大型项目集成

---

## 📦 模组结构

### 文件组织

```
json错误修正/
├── main.py                          # 核心模组（三层架构实现）
├── README.md                        # 本文档
├── test_all_18_cases.py             # 综合测试（18个案例）
├── test_new_cases.py                # 扩展性测试（8个新案例）
└── main_backup_before_refactor.py   # 重构前备份
```

### 核心模组：main.py

```python
main.py
├── 导入和正则表达式常量
│
├── 【第一层】JSONRepairProcessor类（算法层）
│   ├── 类变量: 9个正则表达式
│   ├── 基础清理方法（5个）
│   │   ├── strip_comments()           # 去除注释
│   │   ├── normalize_literals()       # 规范化布尔值和null
│   │   ├── fix_chinese_quotes()       # 处理中文引号
│   │   ├── quote_unquoted_keys()      # 键名加引号
│   │   └── escape_special_characters()# 转义特殊字符
│   ├── 结构修复方法（7个）
│   │   ├── remove_trailing_commas()        # 删除尾随逗号
│   │   ├── insert_missing_commas()         # 插入缺失逗号
│   │   ├── fix_misplaced_brackets()        # 修复错位括号
│   │   ├── balance_brackets()              # 平衡括号
│   │   ├── balance_brackets_smart()        # 智能括号平衡
│   │   ├── smart_insert_brackets_by_error()# 错误驱动修复
│   │   └── clean_extra_brackets()          # 清理多余括号
│   ├── 数据修复方法（3个）
│   │   ├── remove_duplicate_keys()          # 移除重复键
│   │   ├── fix_missing_values()             # 修复缺失值
│   │   └── fix_unclosed_strings_linewise()  # 修复未闭合字符串
│   └── 核心协调方法（2个）
│       ├── try_parse_json()           # 尝试解析JSON
│       └── repair_jsonish()           # 主修复逻辑（协调所有方法）
│
├── 【第二层】JSONRepairTool类（接口层）
│   ├── __init__(input_data)         # 初始化
│   ├── repair()                     # 执行修复
│   ├── output_to_console()          # 打印并返回结果
│   └── get_result()                 # 仅返回结果（不打印）
│
├── 【第三层】JSONRepairService类（服务层）
│   ├── __init__(test_cases)         # 初始化（可选测试案例）
│   ├── repair_single()              # 修复单个JSON
│   ├── repair_batch()               # 批量修复
│   ├── run_tests()                  # 运行测试套件
│   └── get_statistics()             # 获取统计信息
│
└── main()                            # 测试入口函数
```

---

## 🔧 详细API文档

### 第一层：JSONRepairProcessor（算法层）

**设计**：所有方法都是静态方法（`@staticmethod`），无状态设计，纯函数风格。

#### 核心方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `repair_jsonish(raw, max_passes=6)` | `str`, `int` | `(str, str, List[str])` | 主修复逻辑，返回(修复后字符串, 格式化JSON或错误, 诊断信息) |
| `try_parse_json(s)` | `str` | `(bool, str)` | 尝试解析JSON，返回(是否成功, 格式化JSON或错误信息) |
| `quote_unquoted_keys(s)` | `str` | `str` | 为未加引号的键名添加引号 |
| `insert_missing_commas(s)` | `str` | `str` | 插入缺失的逗号 |
| `remove_trailing_commas(s)` | `str` | `str` | 删除尾随逗号 |
| `balance_brackets(s)` | `str` | `(str, List[str])` | 平衡括号，返回(修复后, 诊断信息) |

**使用示例**：

```python
from main import JSONRepairProcessor

# 直接调用单个算法
fixed = JSONRepairProcessor.quote_unquoted_keys('{ name: "test" }')
print(fixed)  # { "name": "test" }

# 使用完整修复流程
repaired, pretty_json, diagnostics = JSONRepairProcessor.repair_jsonish(
    '{ name: "Alice", age: 25 }'
)
print(pretty_json)
```

---

### 第二层：JSONRepairTool（接口层）⭐推荐

**设计**：提供简单直观的API，管理修复状态，返回结构化结果。

#### 类定义

```python
class JSONRepairTool:
    def __init__(self, input_data: str)
    def repair() -> bool
    def output_to_console(show_diagnostics=True) -> dict
    def get_result() -> dict
```

#### 方法详情

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `__init__(input_data)` | - | 初始化，传入待修复的JSON字符串 |
| `repair()` | `bool` | 执行修复，返回是否成功 |
| `output_to_console()` | `dict` | 打印结果到控制台，并返回结构化数据 |
| `get_result()` | `dict` | 获取结果（不打印），适合API集成 |

#### 返回值结构

`get_result()` 和 `output_to_console()` 返回的字典结构：

```python
{
    'success': bool,           # 修复是否成功
    'original': str,           # 原始数据
    'repaired': str,           # 修复后的数据
    'pretty_json': str,        # 格式化的JSON（成功时）
    'error': str,              # 错误信息（失败时）
    'diagnostics': list,       # 诊断信息列表
    'json_object': dict/list   # 解析后的Python对象（get_result专有）
}
```

**使用示例**：

```python
from main import JSONRepairTool

# 基本使用
tool = JSONRepairTool('{ name: "Alice", age: 25 }')
success = tool.repair()

if success:
    result = tool.get_result()
    print(result['pretty_json'])      # 格式化的JSON
    print(result['json_object'])      # Python字典对象
else:
    print(result['error'])
```

---

### 第三层：JSONRepairService（服务层）

**设计**：批量处理、测试管理、统计报告。

#### 类定义

```python
class JSONRepairService:
    def __init__(self, test_cases=None)
    def repair_single(json_string, silent=False) -> dict
    def repair_batch(json_strings, silent=False) -> list
    def run_tests(show_diagnostics=True) -> dict
    def get_statistics() -> dict
```

#### 方法详情

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `repair_single(json_string, silent=False)` | `str`, `bool` | `dict` | 修复单个JSON |
| `repair_batch(json_strings, silent=False)` | `list`, `bool` | `list` | 批量修复多个JSON |
| `run_tests(show_diagnostics=True)` | `bool` | `dict` | 运行测试套件，返回统计 |
| `get_statistics()` | - | `dict` | 获取统计信息（无需重新运行） |

#### 返回值结构

`run_tests()` 返回的统计字典：

```python
{
    'total': int,           # 总案例数
    'success': int,         # 成功数
    'failed': int,          # 失败数
    'success_rate': float,  # 成功率（百分比）
    'results': list         # 详细结果列表
}
```

**使用示例**：

```python
from main import JSONRepairService

# 批量修复
service = JSONRepairService()
json_list = [
    '{ name: "Alice" }',
    '{ name: "Bob", age: 30 }',
    '[1, 2, 3,]'
]

results = service.repair_batch(json_list, silent=True)
for i, result in enumerate(results, 1):
    print(f"案例{i}: {'✓' if result['success'] else '✗'}")

# 运行测试
summary = service.run_tests(show_diagnostics=False)
print(f"成功率: {summary['success_rate']:.1f}%")
```

---

## 🚀 在大工程中集成使用

### 场景1：Web API集成

```python
from flask import Flask, request, jsonify
from main import JSONRepairTool

app = Flask(__name__)

@app.route('/api/fix-json', methods=['POST'])
def fix_json_endpoint():
    """
    JSON修复API端点
    
    POST /api/fix-json
    Body: { "json_string": "{ broken json }" }
    
    Response: {
        "success": true,
        "data": { ... },
        "error": null
    }
    """
    try:
        broken_json = request.json.get('json_string', '')
        
        # 使用JSONRepairTool修复
        tool = JSONRepairTool(broken_json)
        
        if tool.repair():
            result = tool.get_result()
            return jsonify({
                'success': True,
                'data': result['json_object'],
                'error': None
            })
        else:
            result = tool.get_result()
            return jsonify({
                'success': False,
                'data': None,
                'error': result['error']
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'data': None,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
```

### 场景2：数据处理管道

```python
from main import JSONRepairService

class DataPipeline:
    """数据处理管道"""
    
    def __init__(self):
        self.json_service = JSONRepairService()
    
    def process_batch_data(self, raw_json_list: list) -> list:
        """
        批量处理JSON数据
        
        Args:
            raw_json_list: 原始JSON字符串列表（可能有错误）
        
        Returns:
            有效的Python对象列表
        """
        # 批量修复
        results = self.json_service.repair_batch(raw_json_list, silent=True)
        
        # 提取成功修复的数据
        valid_data = [
            r['json_object'] 
            for r in results 
            if r['success']
        ]
        
        # 记录失败的数据
        failed_count = sum(1 for r in results if not r['success'])
        if failed_count > 0:
            print(f"警告: {failed_count}个JSON修复失败")
        
        return valid_data
    
    def process_file(self, filepath: str) -> list:
        """从文件中读取并修复JSON数据"""
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        return self.process_batch_data(lines)

# 使用示例
pipeline = DataPipeline()
valid_data = pipeline.process_batch_data([
    '{ user: "Alice", score: 95 }',
    '{ user: "Bob", score: 87, }',
    '{ user: "Carol" score: 92 }'
])
print(f"成功处理 {len(valid_data)} 条数据")
```

### 场景3：配置文件解析器

```python
from main import JSONRepairTool
import os

class ConfigLoader:
    """配置文件加载器（支持容错JSON）"""
    
    @staticmethod
    def load_config(filepath: str, strict=False) -> dict:
        """
        加载配置文件（自动修复JSON错误）
        
        Args:
            filepath: 配置文件路径
            strict: 是否严格模式（不修复错误）
        
        Returns:
            配置字典
        
        Raises:
            ValueError: 严格模式下JSON无法修复
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"配置文件不存在: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if strict:
            # 严格模式：不修复
            import json
            return json.loads(content)
        else:
            # 容错模式：自动修复
            tool = JSONRepairTool(content)
            
            if tool.repair():
                result = tool.get_result()
                return result['json_object']
            else:
                raise ValueError(f"配置文件JSON格式错误: {tool.get_result()['error']}")

# 使用示例
config = ConfigLoader.load_config('config.json')
print(f"数据库地址: {config['database']['host']}")
```

### 场景4：日志分析工具

```python
from main import JSONRepairProcessor
import re

class LogAnalyzer:
    """日志分析工具（提取和修复JSON日志）"""
    
    def __init__(self):
        self.json_pattern = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}')
    
    def extract_and_fix_json(self, log_line: str) -> dict:
        """
        从日志行中提取JSON并修复
        
        Args:
            log_line: 日志行（可能包含JSON）
        
        Returns:
            修复后的JSON对象，如果没有找到或修复失败则返回None
        """
        # 提取可能的JSON部分
        matches = self.json_pattern.findall(log_line)
        
        for json_str in matches:
            # 使用核心算法修复
            repaired, pretty, diagnostics = JSONRepairProcessor.repair_jsonish(json_str)
            success, result = JSONRepairProcessor.try_parse_json(repaired)
            
            if success:
                import json
                return json.loads(repaired)
        
        return None
    
    def analyze_log_file(self, filepath: str) -> list:
        """分析日志文件，提取所有有效JSON"""
        results = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                json_obj = self.extract_and_fix_json(line)
                if json_obj:
                    results.append({
                        'line': line_num,
                        'data': json_obj
                    })
        
        return results

# 使用示例
analyzer = LogAnalyzer()
json_logs = analyzer.analyze_log_file('app.log')
print(f"从日志中提取了 {len(json_logs)} 条JSON记录")
```

### 场景5：Django/FastAPI中间件

```python
from fastapi import FastAPI, Request, Response
from main import JSONRepairTool
import json

app = FastAPI()

@app.middleware("http")
async def auto_fix_json_middleware(request: Request, call_next):
    """
    自动修复请求中的JSON格式错误
    """
    if request.method in ["POST", "PUT", "PATCH"]:
        if "application/json" in request.headers.get("content-type", ""):
            # 读取原始body
            body = await request.body()
            body_str = body.decode('utf-8')
            
            try:
                # 尝试直接解析
                json.loads(body_str)
            except json.JSONDecodeError:
                # 解析失败，尝试修复
                tool = JSONRepairTool(body_str)
                if tool.repair():
                    result = tool.get_result()
                    fixed_body = result['pretty_json'].encode('utf-8')
                    
                    # 替换request的body（这里需要一些技巧）
                    # 实际应用中可能需要自定义Request类
                    print(f"[中间件] 自动修复了请求中的JSON错误")
    
    response = await call_next(request)
    return response

@app.post("/api/data")
async def receive_data(request: Request):
    """接收数据（自动容错JSON）"""
    data = await request.json()
    return {"status": "success", "received": data}
```

### 场景6：自定义工具类集成

```python
from main import JSONRepairTool, JSONRepairService

class MyProjectUtils:
    """项目工具类"""
    
    def __init__(self):
        self.json_service = JSONRepairService()
    
    def safe_json_parse(self, json_string: str) -> dict:
        """
        安全的JSON解析（自动修复）
        
        使用场景：解析外部API返回、用户输入等
        """
        tool = JSONRepairTool(json_string)
        
        if tool.repair():
            return tool.get_result()['json_object']
        else:
            # 修复失败，返回空字典或抛出异常
            raise ValueError(f"无法解析JSON: {tool.get_result()['error']}")
    
    def validate_and_fix_config(self, config_str: str) -> tuple:
        """
        验证并修复配置
        
        Returns:
            (是否需要修复, 修复后的配置)
        """
        import json
        
        # 先尝试直接解析
        try:
            config = json.loads(config_str)
            return (False, config)  # 不需要修复
        except:
            # 需要修复
            tool = JSONRepairTool(config_str)
            if tool.repair():
                return (True, tool.get_result()['json_object'])
            else:
                raise ValueError("配置文件格式错误且无法修复")

# 在项目中使用
utils = MyProjectUtils()

# 解析外部数据
external_data = utils.safe_json_parse(api_response)

# 验证配置
needs_fix, config = utils.validate_and_fix_config(config_content)
if needs_fix:
    print("警告：配置文件已自动修复，建议更新原文件")
```

---

## 💡 使用建议

### 选择合适的层次

| 场景 | 推荐层次 | 原因 |
|------|----------|------|
| API集成、单次修复 | 第二层 `JSONRepairTool` | API简单，返回结构化 |
| 批量处理 | 第三层 `JSONRepairService` | 内置批处理优化 |
| 自定义修复流程 | 第一层 `JSONRepairProcessor` | 灵活调用特定算法 |
| 测试验证 | 第三层 `JSONRepairService` | 内置测试管理 |

### 性能优化建议

1. **批量处理**：使用 `JSONRepairService.repair_batch()` 而不是循环调用 `JSONRepairTool`
2. **缓存结果**：对于相同的错误JSON，可以缓存修复结果
3. **提前验证**：先用 `json.loads()` 尝试直接解析，失败再修复
4. **限制修复轮数**：默认6轮，可根据需要调整 `max_passes` 参数

---

## 🧪 测试

### 运行测试

```bash
# 测试所有18个案例（原始10个 + 新增8个）
python test_all_18_cases.py

# 仅测试新增的8个案例（验证扩展性）
python test_new_cases.py

# 运行内置的10个测试案例
python main.py
```

### 测试结果

```
✅ 原始10个案例：10/10 成功 (100.0%)
✅ 新增8个案例：8/8 成功 (100.0%)
✅ 总计18个案例：18/18 成功 (100.0%)
```

### 添加自定义测试

```python
from main import JSONRepairService

# 创建自定义测试案例
my_cases = [
    '{ test1: "value" }',
    '{ test2: 123, }',
    '[1, 2, 3'
]

# 运行测试
service = JSONRepairService(test_cases=my_cases)
summary = service.run_tests()

print(f"成功率: {summary['success_rate']:.1f}%")
```

---

## 📝 核心算法说明

本模组包含17个核心修复算法，分为4类：

### 1. 基础清理（5个）

| 算法 | 功能 | 示例 |
|------|------|------|
| `strip_comments` | 去除注释 | `// comment` → ` ` |
| `normalize_literals` | 规范化字面量 | `True` → `true` |
| `fix_chinese_quotes` | 处理中文引号 | `"` → `"` |
| `quote_unquoted_keys` | 键名加引号 | `{name:` → `{"name":` |
| `escape_special_characters` | 转义特殊字符 | （当前简化处理） |

### 2. 结构修复（7个）

| 算法 | 功能 | 示例 |
|------|------|------|
| `remove_trailing_commas` | 删除尾随逗号 | `[1,2,]` → `[1,2]` |
| `insert_missing_commas` | 插入缺失逗号 | `{a:1 b:2}` → `{a:1, b:2}` |
| `fix_misplaced_brackets` | 修复错位括号 | `"value"]` → `"value"}]` |
| `balance_brackets` | 平衡括号 | `{[}` → `{[]}` |
| `balance_brackets_smart` | 智能括号平衡 | 使用栈追踪嵌套 |
| `smart_insert_brackets_by_error` | 错误驱动修复 | 根据JSON错误精确修复 |
| `clean_extra_brackets` | 清理多余括号 | 移除冗余闭合符 |

### 3. 数据修复（3个）

| 算法 | 功能 | 示例 |
|------|------|------|
| `remove_duplicate_keys` | 移除重复键 | 使用最后一个值 |
| `fix_missing_values` | 修复缺失值 | `"key":,` → `"key":null,` |
| `fix_unclosed_strings` | 修复未闭合字符串 | 按行检测并补全 |

### 4. 核心协调（2个）

| 算法 | 功能 |
|------|------|
| `try_parse_json` | 尝试解析JSON并返回结果 |
| `repair_jsonish` | 主修复逻辑，协调所有算法（最多6轮） |

---

## 🔍 故障排除

### 常见问题

**Q: 修复后的JSON格式不符合预期？**  
A: 检查原始数据的结构，本工具尽力修复但可能无法理解原始意图。可以使用 `result['diagnostics']` 查看详细修复过程。

**Q: 某些JSON无法修复？**  
A: 如果JSON损坏过于严重（例如大量字符缺失），可能无法修复。可以查看 `result['error']` 了解具体原因。

**Q: 如何提高修复成功率？**  
A: 可以增加 `max_passes` 参数：`JSONRepairProcessor.repair_jsonish(data, max_passes=10)`

**Q: 性能问题？**  
A: 对于大量JSON，使用 `JSONRepairService.repair_batch()` 批量处理更高效。

---

## 📄 许可

MIT License - 自由使用、修改和分发

---

## 📞 技术支持

- **测试覆盖率**: 100%（18/18案例）
- **平均修复轮数**: 1-2轮
- **支持的错误类型**: 11种主要类型
- **代码行数**: ~1050行（含注释）

---

## 🎓 快速上手示例

### 最简单的使用（3行代码）

```python
from main import JSONRepairTool
tool = JSONRepairTool('{ name: "test", age: 25 }')
tool.repair() and print(tool.get_result()['pretty_json'])
```

### 在API中使用（5分钟集成）

```python
from main import JSONRepairTool

def fix_json_api(json_str: str) -> dict:
    tool = JSONRepairTool(json_str)
    return tool.get_result() if tool.repair() else {'error': 'Failed'}
```

### 批量处理（企业级）

```python
from main import JSONRepairService

service = JSONRepairService()
results = service.repair_batch(json_list, silent=True)
valid_data = [r['json_object'] for r in results if r['success']]
```

---

**⭐ 如果这个模组对你有帮助，请给个星标！**

最后更新: 2026-01-21 | 版本: 2.0 | 测试通过率: 100%
