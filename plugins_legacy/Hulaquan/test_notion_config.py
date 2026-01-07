#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Notion Token 配置和自动同步功能
"""

import os
import sys

def test_token_config():
    """测试 NOTION_TOKEN 配置"""
    print("="*60)
    print("🔍 检查 NOTION_TOKEN 配置")
    print("="*60)
    
    token = os.getenv('NOTION_TOKEN')
    
    if token:
        print(f"✅ NOTION_TOKEN 已配置")
        print(f"   Token 长度: {len(token)} 字符")
        print(f"   Token 前缀: {token[:10]}...")
        return True
    else:
        print("❌ 未找到 NOTION_TOKEN 环境变量")
        print("\n请按以下步骤配置：")
        print("Windows: $env:NOTION_TOKEN=\"ntn_xxx\"")
        print("Linux/Mac: export NOTION_TOKEN=ntn_xxx")
        return False

def test_notion_client():
    """测试 notion-client 库"""
    print("\n" + "="*60)
    print("🔍 检查 notion-client 库")
    print("="*60)
    
    try:
        import notion_client
        print(f"✅ notion-client 已安装")
        print(f"   版本: {notion_client.__version__ if hasattr(notion_client, '__version__') else 'unknown'}")
        return True
    except ImportError:
        print("❌ notion-client 未安装")
        print("\n请运行: pip install notion-client")
        return False

def test_notion_connection():
    """测试 Notion API 连接"""
    print("\n" + "="*60)
    print("🔍 测试 Notion API 连接")
    print("="*60)
    
    token = os.getenv('NOTION_TOKEN')
    if not token:
        print("⏭️  跳过（NOTION_TOKEN 未配置）")
        return False
    
    try:
        from notion_client import Client
        from notion_client import APIResponseError
        
        client = Client(auth=token)
        
        # 尝试列出用户（最简单的 API 调用）
        print("   正在连接 Notion API...")
        users = client.users.list()
        
        print(f"✅ Notion API 连接成功")
        print(f"   可访问用户数: {len(users.get('results', []))}")
        return True
        
    except APIResponseError as e:
        print(f"❌ Notion API 错误: {e.code}")
        print(f"   消息: {e.body}")
        return False
    except Exception as e:
        print(f"❌ 连接失败: {str(e)}")
        return False

def test_page_access():
    """测试页面访问权限"""
    print("\n" + "="*60)
    print("🔍 测试页面访问权限")
    print("="*60)
    
    token = os.getenv('NOTION_TOKEN')
    page_id = "286de516-043f-80c3-a177-ce09dda22d96"
    
    if not token:
        print("⏭️  跳过（NOTION_TOKEN 未配置）")
        return False
    
    try:
        from notion_client import Client
        from notion_client import APIResponseError, APIErrorCode
        
        client = Client(auth=token)
        
        print(f"   页面 ID: {page_id}")
        print("   正在获取页面信息...")
        
        page = client.pages.retrieve(page_id=page_id)
        
        print(f"✅ 页面访问成功")
        print(f"   页面标题: {page.get('properties', {}).get('title', 'N/A')}")
        print(f"   创建时间: {page.get('created_time', 'N/A')}")
        print(f"   上次编辑: {page.get('last_edited_time', 'N/A')}")
        return True
        
    except APIResponseError as e:
        if e.code == APIErrorCode.ObjectNotFound:
            print(f"❌ 页面未找到或 Integration 无访问权限")
            print("\n请确保：")
            print("1. 页面 ID 正确")
            print("2. 在 Notion 页面中添加了 Integration 连接")
        else:
            print(f"❌ API 错误: {e.code}")
            print(f"   消息: {e.body}")
        return False
    except Exception as e:
        print(f"❌ 访问失败: {str(e)}")
        return False

def main():
    """主测试流程"""
    print("\n" + "🧪 Notion 自动同步功能测试".center(60, "="))
    print()
    
    results = []
    
    # 测试 1: Token 配置
    results.append(("Token 配置", test_token_config()))
    
    # 测试 2: notion-client 库
    results.append(("notion-client 库", test_notion_client()))
    
    # 测试 3: API 连接
    results.append(("API 连接", test_notion_connection()))
    
    # 测试 4: 页面访问
    results.append(("页面访问权限", test_page_access()))
    
    # 汇总结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
    
    success_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print("\n" + "="*60)
    print(f"总结: {success_count}/{total_count} 测试通过")
    print("="*60)
    
    if success_count == total_count:
        print("\n🎉 所有测试通过！您可以使用 /sync_notion_help 命令了")
        return 0
    else:
        print("\n⚠️  部分测试失败，请按照上述提示修复配置")
        return 1

if __name__ == '__main__':
    sys.exit(main())
