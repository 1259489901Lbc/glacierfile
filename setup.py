#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI角色扮演网站 - 一键安装脚本（支持语音通话）
"""

import os
import sys
import subprocess
import platform


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


def check_node_npm():
    """检查Node.js和npm是否安装（用于Socket.IO）"""
    try:
        node_version = subprocess.check_output("node --version", shell=True).decode().strip()
        npm_version = subprocess.check_output("npm --version", shell=True).decode().strip()
        print(f"✓ Node.js {node_version} 已安装")
        print(f"✓ npm {npm_version} 已安装")
        return True
    except:
        print("⚠️  未检测到Node.js/npm，Socket.IO可能需要Node.js支持")
        print("   请访问 https://nodejs.org 下载安装")
        return False


def main():
    print("=" * 60)
    print("AI角色扮演网站 - 安装脚本（含语音通话功能）")
    print("Python版本:", sys.version)
    print("操作系统:", platform.system(), platform.release())
    print("=" * 60)

    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 错误: 需要Python 3.8或更高版本")
        sys.exit(1)

    # 检查Node.js（可选）
    check_node_npm()

    # 升级pip
    run_command("python -m pip install --upgrade pip", "升级pip")

    # 安装依赖
    if os.path.exists("requirements.txt"):
        run_command("pip install -r requirements.txt", "安装Python依赖")
    else:
        print("❌ requirements.txt文件不存在")
        sys.exit(1)

    # 创建必要的目录
    dirs = ["templates", "uploads", "static", "logs"]
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

# AI模型配置 - 使用OpenAI兼容API
AI_MODEL_PROVIDER=openai
OPENAI_API_KEY=your-api-key-here
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo

# 语音服务配置
VOICE_SERVICE_PROVIDER=browser

# WebSocket配置
SOCKETIO_ASYNC_MODE=threading

# 性能配置
RESPONSE_TIMEOUT=30
MAX_CONVERSATION_LENGTH=50
MAX_MESSAGE_LENGTH=2000
"""
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        print("✓ .env文件已创建")
        print("⚠️  请编辑.env文件，添加您的API密钥")
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

        import flask_socketio
        print(f"✓ Flask-SocketIO 加载成功")

        import werkzeug
        print(f"✓ Werkzeug {werkzeug.__version__} 加载成功")

        import requests
        print(f"✓ Requests {requests.__version__} 加载成功")

        import eventlet
        print(f"✓ Eventlet 加载成功（用于WebSocket）")

    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        print("\n请尝试手动安装缺失的模块:")
        print("  pip install flask flask-socketio python-socketio eventlet")
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

    # 显示语音通话功能提示
    print("\n" + "=" * 60)
    print("语音通话功能说明：")
    print("- 支持实时语音对话")
    print("- WebSocket连接用于低延迟通信")
    print("- 浏览器原生语音识别和合成")
    print("- 支持多语言（中文、英文、日语）")
    print("=" * 60)

    print("\n" + "=" * 60)
    print("✅ 安装完成！")
    print("\n现在可以运行以下命令启动应用：")
    print("  python app.py")
    print("\n访问: http://localhost:5000")
    print("\n功能特性：")
    print("  - 文字聊天")
    print("  - 语音输入（长按说话）")
    print("  - 语音播放")
    print("  - 🆕 实时语音通话")
    print("=" * 60)

    # 提示配置
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            env_content = f.read()
            if "your-api-key-here" in env_content:
                print("\n⚠️  提醒：请先在.env文件中配置您的API密钥")
                print("   编辑.env文件，将'your-api-key-here'替换为实际的API密钥")


if __name__ == "__main__":
    main()
