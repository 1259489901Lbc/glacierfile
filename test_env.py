#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试环境变量是否正确加载
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("=== 环境变量检查 ===\n")

# 检查.env文件是否存在
if os.path.exists('.env'):
    print("✓ .env文件已找到")
else:
    print("❌ .env文件未找到！")
    print("请在项目根目录创建.env文件")

print("\n=== AI配置 ===")
print(f"AI_MODEL_PROVIDER: {os.getenv('AI_MODEL_PROVIDER', '未设置')}")
print(f"当前工作目录: {os.getcwd()}")

# 检查各种AI服务配置
providers = {
    'openai': ['OPENAI_API_KEY'],
    'tencent': ['TENCENT_SECRET_ID', 'TENCENT_SECRET_KEY'],
    'mock': []
}

current_provider = os.getenv('AI_MODEL_PROVIDER', 'openai')
print(f"\n当前使用的AI提供商: {current_provider}")

if current_provider == 'mock':
    print("✓ Mock模式不需要API密钥")
elif current_provider in providers:
    required_keys = providers[current_provider]
    missing_keys = []

    for key in required_keys:
        value = os.getenv(key)
        if value:
            print(f"✓ {key}: {'*' * 10}...")  # 隐藏真实密钥
        else:
            print(f"❌ {key}: 未设置")
            missing_keys.append(key)

    if missing_keys:
        print(f"\n⚠️  警告: {current_provider}需要设置以下环境变量:")
        for key in missing_keys:
            print(f"   - {key}")
else:
    print(f"⚠️  未知的AI提供商: {current_provider}")

print("\n=== 建议 ===")
if current_provider != 'mock':
    print("如果还没有API密钥，建议先使用mock模式测试：")
    print("在.env文件中设置: AI_MODEL_PROVIDER=mock")

# 测试config.py是否能正确读取
print("\n=== 测试Config类 ===")
try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from config import Config

    print(f"Config.AI_MODEL_PROVIDER: {Config.AI_MODEL_PROVIDER}")
    print("✓ Config类可以正常加载")
except Exception as e:
    print(f"❌ Config类加载失败: {e}")

print("\n测试完成！")