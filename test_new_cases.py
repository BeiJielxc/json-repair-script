"""
测试程序的通用性 - 使用全新的测试案例
可以修改此文件添加更多测试案例来验证程序的扩展性
"""
import sys
sys.path.insert(0, '.')
from main import JSONRepairTool

# 全新的测试案例，与原来的10个完全不同
new_test_cases = [
    # 新案例1: 电商订单数据 - 缺少逗号和引号
    """
    {
        product: "iPhone 15",
        price: 5999
        quantity: 2
        "total": 11998
    }
    """,
    
    # 新案例2: 用户评论数据 - 数组缺闭合括号
    """
    {
        "comments": [
            {"user": "Alice", "rating": 5},
            {"user": "Bob", "rating": 4}
        "timestamp": "2026-01-21"
    }
    """,
    
    # 新案例3: 配置文件 - 多层嵌套缺括号
    """
    {
        "database": {
            "host": "localhost",
            "port": 3306,
            "credentials": {
                "username": "admin",
                "password": "secret123"
        }
        "cache": {
            "enabled": True,
            "ttl": 3600
        }
    }
    """,
    
    # 新案例4: API响应 - 布尔值和null混用
    """
    {
        "success": true,
        "data": NULL,
        "error": False,
        "code": 200
    }
    """,
    
    # 新案例5: 嵌套数组 - 缺少多个逗号
    """
    {
        "matrix": [
            [1, 2, 3]
            [4, 5, 6]
            [7, 8, 9]
        ]
        "size": 9
    }
    """,
    
    # 新案例6: 日志数据 - 注释和尾随逗号
    """
    {
        "level": "error",  // 错误级别
        "message": "Connection timeout",
        "stack": [
            "line 1",
            "line 2",  // 堆栈信息
        ],
    }
    """,
    
    # 新案例7: 混合错误 - 多种问题组合
    """
    [
        {
            id: 1,
            name: "Task 1"
            status: "pending"
        }
        {
            id: 2
            name: "Task 2",
            status: "done",
        ]
    """,
    
    # 新案例8: 深层嵌套 - 括号不匹配
    """
    {
        "company": {
            "departments": [
                {
                    "name": "Engineering",
                    "teams": [
                        {"name": "Frontend", "size": 5},
                        {"name": "Backend", "size": 8}
                    "budget": 100000
                }
            ]
        }
    }
    """,

    # 新案例9: 超长字符串字段被截断（类似 "result" 内嵌JSON文本，末尾缺引号/括号）
    """
    {
      "status": "ok",
      "result": "{\n  \\"total_rows\\": 2,\n  \\"rows\\": [\n    {\\"row_num\\": 1, \\"交易日期\\": {\\"content\\": \\"20210107\\"}},\n    {\\"row_num\\": 2, \\"交易日期\\": {\\"content\\": \\"20210112\\"}}\n  ]\n"
    """
]

print("=" * 70)
print("测试程序的通用性 - 全新测试案例")
print("=" * 70)

success_count = 0
total_count = len(new_test_cases)

for i, case in enumerate(new_test_cases, start=1):
    print(f"\n{'='*70}")
    print(f"新测试案例 {i}/{total_count}")
    print(f"{'='*70}")
    
    tool = JSONRepairTool(input_data=case)
    tool.repair()
    
    # 检查是否成功
    import json
    try:
        json.loads(tool.repaired)
        success_count += 1
        print("[OK] 修复成功！")
        print(tool.pretty_or_err)
    except:
        print("[FAIL] 修复失败")
        print("=== Diagnostics ===")
        for d in tool.diagnostics[-6:]:  # 只显示最后6条诊断
            print(d)
        print("\n=== Repaired (but still not valid) ===")
        print(tool.repaired[:500])

print(f"\n{'='*70}")
print(f"最终统计: {success_count}/{total_count} 个案例成功修复")
print(f"成功率: {success_count/total_count*100:.1f}%")
print(f"{'='*70}")
print("\n提示: 可以修改此文件添加更多测试案例来验证程序的扩展性")

