#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI角色扮演网站 - 一键安装脚本
"""

import os
import sys
import subprocess


def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{description}...")
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"✓ {description}完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description}失败: {e}")
        return False


def main():
    print("=" * 60)
    print("AI角色扮演网站 - 安装脚本")
    print("Python版本:", sys.version)
    print("=" * 60)

    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 错误: 需要Python 3.8或更高版本")
        sys.exit(1)

    # 升级pip
    run_command("python -m pip install --upgrade pip", "升级pip")

    # 安装依赖
    if os.path.exists("requirements.txt"):
        run_command("pip install -r requirements.txt", "安装依赖")
    else:
        print("❌ requirements.txt文件不存在")
        sys.exit(1)

    # 创建必要的目录
    dirs = ["templates", "uploads"]
    for dir_name in dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"✓ 创建目录: {dir_name}")

    # 检查.env文件
    if not os.path.exists(".env"):
        print("\n创建.env文件...")
        env_content = """# Flask配置
SECRET_KEY=dev-secret-key-change-in-production
FLASK_DEBUG=True
FLASK_ENV=development

# AI模型配置 - 使用mock模式测试
AI_MODEL_PROVIDER=mock

# 语音服务配置
VOICE_SERVICE_PROVIDER=browser

# 性能配置
RESPONSE_TIMEOUT=30
MAX_CONVERSATION_LENGTH=50
MAX_MESSAGE_LENGTH=2000
"""
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        print("✓ .env文件已创建（使用mock模式）")
    else:
        print("✓ .env文件已存在")

    # 测试导入
    print("\n测试模块导入...")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ python-dotenv加载成功")

        import flask
        print(f"✓ Flask {flask.__version__} 加载成功")

        import werkzeug
        print(f"✓ Werkzeug {werkzeug.__version__} 加载成功")

        import requests
        print(f"✓ Requests {requests.__version__} 加载成功")

    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        sys.exit(1)

    # 测试应用
    print("\n测试应用导入...")
    try:
        import models
        print("✓ models.py 加载成功")

        import services
        print("✓ services.py 加载成功")

        import config
        print("✓ config.py 加载成功")

        import app
        print("✓ app.py 加载成功")

    except Exception as e:
        print(f"❌ 应用模块加载失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ 安装完成！")
    print("\n现在可以运行以下命令启动应用：")
    print("  python app.py")
    print("\n或使用简化版本：")
    print("  python app_simple.py")
    print("\n访问: http://localhost:5000")
    print("=" * 60)


if __name__ == "__main__":
    main()