#!/usr/bin/env python3
"""
Aider 离线 Windows 二进制包构建脚本
自动下载依赖、打包成可执行文件，供内网环境使用
"""

import os
import sys
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
import json
import argparse

class AiderOfflineBuilder:
    def __init__(self, output_dir="dist"):
        self.output_dir = Path(output_dir)
        self.temp_dir = None
        self.venv_dir = None
        
    def log(self, message):
        print(f"[INFO] {message}")
        
    def error(self, message):
        print(f"[ERROR] {message}")
        sys.exit(1)
        
    def run_command(self, cmd, cwd=None, check=True):
        self.log(f"执行命令: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd, 
                check=check, 
                capture_output=True, 
                text=True,
                shell=True if isinstance(cmd, str) else False
            )
            if result.stdout:
                print(result.stdout)
            return result
        except subprocess.CalledProcessError as e:
            self.error(f"命令执行失败: {e}\n{e.stderr}")
            
    def setup_temp_environment(self):
        """设置临时构建环境"""
        self.log("设置临时构建环境...")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aider_build_"))
        self.venv_dir = self.temp_dir / "venv"
        
        # 创建虚拟环境
        self.run_command([sys.executable, "-m", "venv", str(self.venv_dir)])
        
        # 获取虚拟环境的python和pip路径
        if os.name == 'nt':
            self.venv_python = self.venv_dir / "Scripts" / "python.exe"
            self.venv_pip = self.venv_dir / "Scripts" / "pip.exe"
        else:
            self.venv_python = self.venv_dir / "bin" / "python"
            self.venv_pip = self.venv_dir / "bin" / "pip"
            
    def download_aider_source(self):
        """下载aider源码"""
        self.log("下载aider源码...")
        
        # 如果当前目录就是aider项目，直接复制
        if (Path.cwd() / "pyproject.toml").exists() and "aider-chat" in open("pyproject.toml").read():
            self.log("检测到当前目录是aider项目，直接使用本地源码")
            self.source_dir = self.temp_dir / "aider_source"
            shutil.copytree(".", self.source_dir, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', 'dist', 'build'))
        else:
            # 从GitHub下载
            self.log("从GitHub下载aider源码...")
            zip_url = "https://github.com/Aider-AI/aider/archive/refs/heads/main.zip"
            zip_path = self.temp_dir / "aider.zip"
            
            urllib.request.urlretrieve(zip_url, zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
                
            self.source_dir = self.temp_dir / "aider-main"
            
    def install_dependencies(self):
        """安装所有依赖"""
        self.log("安装依赖包...")
        
        # 升级pip
        self.run_command([str(self.venv_pip), "install", "--upgrade", "pip"])
        
        # 安装PyInstaller
        self.run_command([str(self.venv_pip), "install", "pyinstaller"])
        
        # 安装aider及其依赖
        self.run_command([str(self.venv_pip), "install", "-e", "."], cwd=self.source_dir)
        
        # 安装额外依赖用于完整功能
        optional_deps = ["help", "browser"]
        for dep in optional_deps:
            try:
                self.run_command([str(self.venv_pip), "install", "-e", f".[{dep}]"], cwd=self.source_dir)
            except:
                self.log(f"可选依赖 {dep} 安装失败，跳过")
                
    def create_spec_file(self):
        """创建PyInstaller spec文件"""
        self.log("创建PyInstaller配置文件...")
        
        spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# 添加aider源码路径
aider_path = r"{source_dir}"
sys.path.insert(0, aider_path)

block_cipher = None

# 收集所有必要的数据文件
datas = [
    (r"{source_dir}\\aider\\resources", "aider\\resources"),
    (r"{source_dir}\\aider\\queries", "aider\\queries"),
]

# 隐藏导入
hiddenimports = [
    'aider',
    'aider.main',
    'aider.models',
    'aider.coders',
    'aider.llm',
    'litellm',
    'tiktoken',
    'tokenizers',
    'transformers',
    'torch',
    'numpy',
    'scipy',
    'networkx',
    'tree_sitter',
    'tree_sitter_languages',
    'PIL',
    'yaml',
    'json5',
    'rich',
    'prompt_toolkit',
    'gitpython',
    'beautifulsoup4',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    'colorama',
    'packaging',
    'setuptools',
]

a = Analysis(
    [r"{source_dir}\\aider\\main.py"],
    pathex=[aider_path],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='aider',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='aider',
)
'''.format(source_dir=str(self.source_dir).replace('\\', '\\\\'))

        spec_path = self.temp_dir / "aider.spec"
        with open(spec_path, 'w', encoding='utf-8') as f:
            f.write(spec_content)
            
        return spec_path
        
    def build_executable(self):
        """构建可执行文件"""
        self.log("构建Windows可执行文件...")
        
        spec_path = self.create_spec_file()
        
        # 使用PyInstaller构建
        self.run_command([
            str(self.venv_python), "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            str(spec_path)
        ], cwd=self.temp_dir)
        
        self.exe_dir = self.temp_dir / "dist" / "aider"
        
    def create_config_files(self):
        """创建配置文件和使用说明"""
        self.log("创建配置文件...")
        
        # 创建默认配置文件
        config_content = """# Aider 配置文件
# 适用于内网环境，通过 OpenAI Compatible API 连接大模型

# 基本设置
model: openai/your-model-name
api-base: http://your-internal-api-server:port/v1
api-key: your-api-key

# 可选设置
# max-tokens: 4096
# temperature: 0.1
# no-auto-commits: true
# dark-mode: true
"""
        
        with open(self.exe_dir / ".aider.conf.yml", 'w', encoding='utf-8') as f:
            f.write(config_content)
            
        # 创建模型设置文件
        model_settings = """# 模型设置文件
# 针对内网OpenAI Compatible API的优化配置

- name: openai/your-model-name
  edit_format: diff
  weak_model_name: null
  use_repo_map: true
  send_undo_reply: false
  lazy: false
  reminder: sys
  examples_as_sys_msg: true
  cache_control: false
  caches_by_default: false
  use_system_prompt: true
  use_temperature: true
  streaming: true
  editor_model_name: null
  editor_edit_format: null
  extra_params:
    max_tokens: 4096
"""
        
        with open(self.exe_dir / ".aider.model.settings.yml", 'w', encoding='utf-8') as f:
            f.write(model_settings)
            
    def create_batch_files(self):
        """创建启动批处理文件"""
        self.log("创建启动脚本...")
        
        # 主启动脚本
        start_bat = """@echo off
chcp 65001 > nul
title Aider - AI Pair Programming

echo ===============================================
echo           Aider - AI Pair Programming
echo ===============================================
echo.

REM 设置环境变量（根据您的内网API服务器配置）
REM set OPENAI_API_BASE=http://your-internal-api-server:port/v1
REM set OPENAI_API_KEY=your-api-key

echo 当前目录: %CD%
echo.
echo 使用方法:
echo   aider --model openai/your-model-name --api-base http://your-server:port/v1 --api-key your-key
echo.
echo 或者编辑 .aider.conf.yml 文件设置默认配置
echo.

cmd /k
"""
        
        with open(self.exe_dir / "start_aider.bat", 'w', encoding='utf-8') as f:
            f.write(start_bat)
            
        # 示例使用脚本
        example_bat = """@echo off
chcp 65001 > nul

REM 示例：连接到内网OpenAI Compatible API
REM 请根据您的实际环境修改以下参数

set API_BASE=http://your-internal-server:8000/v1
set API_KEY=your-api-key-here
set MODEL_NAME=your-model-name

echo 正在启动 Aider...
echo API Base: %API_BASE%
echo Model: %MODEL_NAME%
echo.

aider.exe --model openai/%MODEL_NAME% --api-base %API_BASE% --api-key %API_KEY%

pause
"""
        
        with open(self.exe_dir / "example_start.bat", 'w', encoding='utf-8') as f:
            f.write(example_bat)
            
    def create_documentation(self):
        """创建使用文档"""
        self.log("创建使用文档...")
        
        readme_content = """# Aider 离线Windows版使用说明

## 简介
这是Aider的完全离线Windows版本，可以在内网环境中使用，通过OpenAI Compatible API连接您的大模型服务。

## 系统要求
- Windows 10/11 (64位)
- 内网中的OpenAI Compatible API服务

## 快速开始

### 1. 解压文件
将整个文件夹解压到您想要的位置。

### 2. 配置API连接
编辑 `.aider.conf.yml` 文件，设置您的API参数：

```yaml
model: openai/your-model-name
api-base: http://your-internal-api-server:port/v1
api-key: your-api-key
```

### 3. 启动Aider
- 双击 `start_aider.bat` 打开命令行环境
- 或者直接运行 `example_start.bat`（需要先编辑其中的参数）

### 4. 使用Aider
```bash
# 进入您的项目目录
cd C:\\path\\to\\your\\project

# 启动aider（如果已配置.aider.conf.yml）
aider

# 或者直接指定参数
aider --model openai/your-model --api-base http://your-server:port/v1 --api-key your-key
```

## 常用命令

```bash
# 查看帮助
aider --help

# 列出可用模型
aider --list-models

# 使用特定模型
aider --model openai/gpt-4

# 设置上下文窗口
aider --model openai/your-model --max-tokens 8192

# 禁用自动提交
aider --no-auto-commits
```

## 配置文件

### .aider.conf.yml (主配置文件)
```yaml
model: openai/your-model-name
api-base: http://your-internal-api-server:port/v1
api-key: your-api-key
max-tokens: 4096
temperature: 0.1
dark-mode: true
```

### .aider.model.settings.yml (模型设置文件)
用于优化特定模型的行为，无需修改。

## 环境变量设置

您也可以通过环境变量设置API参数：

```bat
set OPENAI_API_BASE=http://your-internal-server:port/v1
set OPENAI_API_KEY=your-api-key
```

## 故障排除

### 连接问题
- 检查API服务器地址和端口是否正确
- 确认API密钥有效
- 测试网络连通性

### 模型问题
- 确认模型名称正确
- 检查模型是否支持chat completion
- 验证模型的上下文窗口大小

### 性能优化
- 使用diff格式进行代码编辑
- 适当设置max-tokens参数
- 根据需要调整temperature参数

## 技术支持

如有问题，请参考：
- Aider官方文档: https://aider.chat/docs/
- GitHub仓库: https://github.com/Aider-AI/aider

## 版本信息
- 构建时间: """ + f"{self.get_build_time()}" + """
- 包含组件: Aider + 所有Python依赖
- 支持功能: 代码编辑、Git集成、多语言支持

---
祝您使用愉快！
"""
        
        with open(self.exe_dir / "README.md", 'w', encoding='utf-8') as f:
            f.write(readme_content)
            
    def get_build_time(self):
        """获取构建时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def create_final_package(self):
        """创建最终的发布包"""
        self.log("创建最终发布包...")
        
        # 确保输出目录存在
        self.output_dir.mkdir(exist_ok=True)
        
        # 创建版本信息文件
        version_info = {
            "build_time": self.get_build_time(),
            "python_version": sys.version,
            "platform": "Windows",
            "components": ["aider", "python_dependencies"],
            "usage": "Internal network with OpenAI Compatible API"
        }
        
        with open(self.exe_dir / "version_info.json", 'w', encoding='utf-8') as f:
            json.dump(version_info, f, indent=2, ensure_ascii=False)
            
        # 复制到输出目录
        final_dir = self.output_dir / "aider_windows_offline"
        if final_dir.exists():
            shutil.rmtree(final_dir)
            
        shutil.copytree(self.exe_dir, final_dir)
        
        # 创建压缩包
        zip_path = self.output_dir / "aider_windows_offline.zip"
        if zip_path.exists():
            zip_path.unlink()
            
        shutil.make_archive(
            str(self.output_dir / "aider_windows_offline"),
            'zip',
            str(final_dir)
        )
        
        self.log(f"✅ 离线包创建完成!")
        self.log(f"📁 目录: {final_dir}")
        self.log(f"📦 压缩包: {zip_path}")
        
    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and self.temp_dir.exists():
            self.log("清理临时文件...")
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
    def build(self):
        """执行完整的构建流程"""
        try:
            self.log("🚀 开始构建 Aider Windows 离线包...")
            
            self.setup_temp_environment()
            self.download_aider_source()
            self.install_dependencies()
            self.build_executable()
            self.create_config_files()
            self.create_batch_files()
            self.create_documentation()
            self.create_final_package()
            
            self.log("🎉 构建完成!")
            
        except Exception as e:
            self.error(f"构建失败: {e}")
        finally:
            self.cleanup()

def main():
    parser = argparse.ArgumentParser(description="构建Aider离线Windows包")
    parser.add_argument("-o", "--output", default="dist", help="输出目录 (默认: dist)")
    
    args = parser.parse_args()
    
    builder = AiderOfflineBuilder(args.output)
    builder.build()

if __name__ == "__main__":
    main() 