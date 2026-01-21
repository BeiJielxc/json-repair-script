"""
综合测试 - 原始10个案例 + 新增8个案例 = 总共18个案例
验证三层架构重构后的功能完整性
"""

from main import JSONRepairService

# 新的8个测试案例
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
]

print("=" * 80)
print("三层架构重构后的综合测试")
print("=" * 80)

# 第一部分：测试原始10个案例
print("\n" + "=" * 80)
print("第一部分：测试原始10个案例（使用内置测试案例）")
print("=" * 80)

service_original = JSONRepairService()  # 使用默认的10个测试案例
summary_original = service_original.run_tests(show_diagnostics=False)

# 第二部分：测试新的8个案例
print("\n" + "=" * 80)
print("第二部分：测试新的8个案例")
print("=" * 80)

service_new = JSONRepairService(test_cases=new_test_cases)
summary_new = service_new.run_tests(show_diagnostics=False)

# 总结
print("\n" + "=" * 80)
print("总结 - 综合测试结果")
print("=" * 80)
print(f"\n原始10个案例:")
print(f"  [成功] {summary_original['success']}/{summary_original['total']}")
print(f"  [失败] {summary_original['failed']}/{summary_original['total']}")
print(f"  [成功率] {summary_original['success_rate']:.1f}%")

print(f"\n新增8个案例:")
print(f"  [成功] {summary_new['success']}/{summary_new['total']}")
print(f"  [失败] {summary_new['failed']}/{summary_new['total']}")
print(f"  [成功率] {summary_new['success_rate']:.1f}%")

total_count = summary_original['total'] + summary_new['total']
total_success = summary_original['success'] + summary_new['success']
total_failed = summary_original['failed'] + summary_new['failed']
overall_rate = (total_success / total_count * 100) if total_count > 0 else 0

print(f"\n综合统计（18个案例）:")
print(f"  [总成功] {total_success}/{total_count}")
print(f"  [总失败] {total_failed}/{total_count}")
print(f"  [总成功率] {overall_rate:.1f}%")
print("=" * 80)

# 如果有失败的案例，列出详情
if total_failed > 0:
    print("\n失败案例详情:")
    
    if summary_original['failed'] > 0:
        print("\n原始案例中的失败:")
        for i, result_item in enumerate(summary_original['results'], start=1):
            if not result_item['result']['success']:
                print(f"  - 案例 {i}: {result_item['result']['error'][:100]}...")
    
    if summary_new['failed'] > 0:
        print("\n新案例中的失败:")
        for i, result_item in enumerate(summary_new['results'], start=1):
            if not result_item['result']['success']:
                print(f"  - 新案例 {i}: {result_item['result']['error'][:100]}...")

print("\n[完成] 三层架构重构测试完成！")

