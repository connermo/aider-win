#!/usr/bin/env python3
"""
Aider Windows Offline Package Builder

This script builds a standalone Windows executable package for aider,
including all dependencies and configuration files.
"""

import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path
import zipfile
import json
import argparse
from typing import Optional

class AiderWindowsBuilder:
    def __init__(self, output_dir="dist"):
        self.output_dir = Path(output_dir)
        self.temp_dir: Optional[Path] = None
        self.venv_dir: Optional[Path] = None
        self.exe_dir: Optional[Path] = None
        self.source_dir: Optional[Path] = None
        self.venv_python: Optional[Path] = None
        self.venv_pip: Optional[Path] = None
        
    def log(self, message):
        """Print log message with timestamp"""
        print(f"[BUILD] {message}")
        
    def error(self, message):
        print(f"[ERROR] {message}")
        sys.exit(1)
        
    def run_command(self, cmd, cwd=None, check=True):
        """Execute command and handle errors"""
        self.log(f"Running: {' '.join(map(str, cmd))}")
        if cwd:
            self.log(f"In directory: {cwd}")
        
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd, 
                check=check, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                shell=True if isinstance(cmd, str) else False
            )
            if result.stdout:
                self.log(result.stdout)
            return result
        except subprocess.CalledProcessError as e:
            self.error(f"Command failed with return code {e.returncode}")
            self.error(f"STDOUT: {e.stdout}")
            self.error(f"STDERR: {e.stderr}")
            raise
            
    def setup_environment(self):
        """Setup build environment"""
        self.log("Setting up build environment...")
        
        # Create temp directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aider_build_"))
        self.log(f"Temp directory: {self.temp_dir}")
        
        # Copy source code
        if (Path.cwd() / "pyproject.toml").exists() and "aider-chat" in open("pyproject.toml").read():
            self.log("Detected aider project in current directory, using local source")
            self.source_dir = self.temp_dir / "aider_source"
            shutil.copytree(".", self.source_dir, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'dist', 'build'))
        else:
            self.log("Downloading aider source from GitHub...")
            # Download and extract aider source
            import urllib.request
            url = "https://github.com/paul-gauthier/aider/archive/main.zip"
            zip_path = self.temp_dir / "aider.zip"
            urllib.request.urlretrieve(url, zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
            
            self.source_dir = self.temp_dir / "aider-main"
            
    def create_virtual_environment(self):
        """Create Python virtual environment"""
        self.log("Creating virtual environment...")
        
        self.venv_dir = self.temp_dir / "venv"
        self.run_command([sys.executable, "-m", "venv", str(self.venv_dir)])
        
        # Set venv paths
        if os.name == 'nt':  # Windows
            self.venv_python = self.venv_dir / "Scripts" / "python.exe"
            self.venv_pip = self.venv_dir / "Scripts" / "pip.exe"
        else:
            self.venv_python = self.venv_dir / "bin" / "python"
            self.venv_pip = self.venv_dir / "bin" / "pip"
    
    def download_tiktoken_encodings(self):
        """Pre-download tiktoken encoding files"""
        self.log("Downloading tiktoken encoding files...")
        
        assert self.temp_dir is not None, "temp_dir must be set before calling this method"
        assert self.venv_python is not None, "venv_python must be set before calling this method"
        
        try:
            # First verify tiktoken is installed and importable
            test_script = '''
import sys
import os
try:
    import tiktoken
    print(f"✓ tiktoken version: {tiktoken.__version__}")
    print(f"✓ tiktoken path: {tiktoken.__file__}")
    
    # Test basic functionality
    from pathlib import Path
    tiktoken_path = Path(tiktoken.__file__).parent
    data_path = tiktoken_path / "data"
    print(f"✓ tiktoken data directory: {data_path}")
    print(f"✓ tiktoken data directory exists: {data_path.exists()}")
    
    if data_path.exists():
        tiktoken_files = list(data_path.glob("*.tiktoken"))
        print(f"✓ Found {len(tiktoken_files)} tiktoken files")
        for f in tiktoken_files:
            print(f"  - {f.name}")
    else:
        print("! tiktoken data directory not found - will download encodings")
    
    # Test if cl100k_base encoding works (this might download files)
    try:
        enc = tiktoken.get_encoding('cl100k_base')
        print(f"✓ cl100k_base encoding loaded successfully (vocab size: {enc.n_vocab})")
    except Exception as e:
        print(f"! cl100k_base encoding test failed: {e}")
    
    print("✓ tiktoken testing completed successfully")
        
except ImportError as e:
    print(f"✗ Failed to import tiktoken: {e}")
    sys.exit(1)
except Exception as e:
    print(f"! tiktoken test warning: {e}")
    print("✓ tiktoken is available but some tests failed - continuing build")
'''
            
            # Create and run test script
            test_script_path = self.temp_dir / "test_tiktoken.py"
            with open(test_script_path, 'w', encoding='utf-8') as f:
                f.write(test_script)
            
            self.log("Testing tiktoken installation...")
            try:
                self.run_command([str(self.venv_python), str(test_script_path)])
            except subprocess.CalledProcessError as e:
                self.log(f"Warning: tiktoken test failed with return code {e.returncode}")
                self.log("This might be due to network issues, but tiktoken should still work at runtime")
            
            # Attempt to pre-download common encodings, but don't fail if it doesn't work
            download_script = '''
import tiktoken
import os
import sys
from pathlib import Path

# Common encoding list - start with most important
encodings_to_download = [
    "cl100k_base",  # GPT-4, GPT-3.5-turbo (most important)
    "o200k_base",   # GPT-4o models
    "p50k_base",    # Codex models, text-davinci-002, text-davinci-003
    "r50k_base",    # GPT-3 models like davinci
]

print("Starting tiktoken encoding download...")
success_count = 0
total_count = len(encodings_to_download)

for encoding_name in encodings_to_download:
    try:
        print(f"Downloading {encoding_name}...")
        enc = tiktoken.get_encoding(encoding_name)
        print(f"✓ {encoding_name} downloaded successfully (vocab size: {enc.n_vocab})")
        success_count += 1
    except Exception as e:
        print(f"! Failed to download {encoding_name}: {e}")
        # Don't exit on failure, just continue with next encoding
        
print(f"\\nDownload completed: {success_count}/{total_count} encodings downloaded successfully")

# Verify the encoding files are available
try:
    tiktoken_path = Path(tiktoken.__file__).parent
    data_path = tiktoken_path / "data"
    if data_path.exists():
        tiktoken_files = list(data_path.glob("*.tiktoken"))
        print(f"Total tiktoken files available: {len(tiktoken_files)}")
        if tiktoken_files:
            print("Available encoding files:")
            for f in sorted(tiktoken_files):
                print(f"  - {f.name}")
    else:
        print("Note: tiktoken data directory not found - encodings will be downloaded at runtime")
except Exception as e:
    print(f"Note: Could not check tiktoken data files: {e}")

print("Tiktoken encoding preparation completed")
'''
            
            # Create and run download script
            download_script_path = self.temp_dir / "download_tiktoken.py"
            with open(download_script_path, 'w', encoding='utf-8') as f:
                f.write(download_script)
            
            self.log("Attempting to pre-download tiktoken encodings...")
            try:
                self.run_command([str(self.venv_python), str(download_script_path)])
            except subprocess.CalledProcessError as e:
                self.log(f"Warning: tiktoken encoding download failed with return code {e.returncode}")
                self.log("This is not critical - encodings will be downloaded when first needed at runtime")
            
            # Clean up temporary scripts
            test_script_path.unlink(missing_ok=True)
            download_script_path.unlink(missing_ok=True)
            
            self.log("✓ Tiktoken encoding setup completed")
            
        except Exception as e:
            self.log(f"Warning: Failed to setup tiktoken encodings: {e}")
            self.log("The build will continue - tiktoken encodings will be downloaded at runtime if needed")
            # Don't fail the build for this issue

    def install_dependencies(self):
        """Install all dependencies"""
        self.log("Installing dependency packages...")
        
        # Upgrade pip - use python -m pip instead of calling pip.exe directly
        self.run_command([str(self.venv_python), "-m", "pip", "install", "--upgrade", "pip"])
        
        # Install PyInstaller
        self.run_command([str(self.venv_pip), "install", "pyinstaller"])
        
        # Install aider and its dependencies
        self.run_command([str(self.venv_pip), "install", "-e", "."], cwd=self.source_dir)
        
        # Install optional dependencies for full functionality
        optional_deps = ["help", "browser"]
        for dep in optional_deps:
            try:
                self.run_command([str(self.venv_pip), "install", "-e", f".[{dep}]"], cwd=self.source_dir)
            except:
                self.log(f"Optional dependency {dep} installation failed, skipping")
        
        # Pre-download tiktoken encoding files
        # Temporarily disabled while debugging build issues
        # self.download_tiktoken_encodings()
        
    def create_launcher_file(self):
        """Create launcher file to avoid relative import issues"""
        launcher_content = '''#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Ensure aider module can be found
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import and run aider main program
from aider.main import main

if __name__ == "__main__":
    main()
'''
        launcher_path = self.source_dir / "aider_launcher.py"
        with open(launcher_path, 'w', encoding='utf-8') as f:
            f.write(launcher_content)
        return launcher_path

    def create_spec_file(self):
        """Create PyInstaller spec file"""
        self.log("Creating PyInstaller configuration file...")
        
        # Create launcher file
        launcher_path = self.create_launcher_file()
        
        # Use relative paths to avoid Windows path issues
        source_path = str(self.source_dir).replace('\\', '/')
        launcher_path_str = str(launcher_path).replace('\\', '/')
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

# Add aider source path
aider_path = r"{source_path}"
sys.path.insert(0, aider_path)

block_cipher = None

# Get tiktoken data file paths
tiktoken_datas = []
try:
    import tiktoken
    # Get tiktoken package location
    tiktoken_pkg_path = Path(tiktoken.__file__).parent
    tiktoken_data_path = tiktoken_pkg_path / "data"
    
    if tiktoken_data_path.exists():
        # Add all encoding files
        for encoding_file in tiktoken_data_path.glob("*.tiktoken"):
            tiktoken_datas.append((str(encoding_file), f"tiktoken/data/{{encoding_file.name}}"))
        
        # If no specific file is found, add the entire data directory
        if not tiktoken_datas:
            tiktoken_datas.append((str(tiktoken_data_path), "tiktoken/data"))
    
    print(f"Found tiktoken data at: {{tiktoken_data_path}}")
    print(f"Tiktoken data files: {{len(tiktoken_datas)}}")
    
except ImportError as e:
    print(f"Could not import tiktoken: {{e}}")
    tiktoken_datas = []

# Collect all necessary data files
datas = [
    (r"{source_path}/aider/resources", "aider/resources"),
    (r"{source_path}/aider/queries", "aider/queries"),
] + tiktoken_datas

# Hide imports
hiddenimports = [
    'aider',
    'aider.main',
    'aider.models',
    'aider.coders',
    'aider.llm',
    'litellm',
    'tiktoken',
    'tiktoken.registry',
    'tiktoken.core',
    'tiktoken.model',
    'tokenizers',
    'transformers',
    'torch',
    'numpy',
    'scipy',
    'networkx',
    'tree_sitter',
    'tree_sitter_languages',
    'tree_sitter_language_pack',
    'requests',
    'httpx',
    'openai',
    'anthropic',
    'google',
    'google.generativeai',
    'google.ai.generativelanguage_v1beta',
    'google.api_core',
    'grpc',
    'litellm.cost_calculator',
    'litellm.utils',
    'litellm.router',
    'litellm.proxy',
    'litellm.caching',
    'litellm.exceptions',
    'litellm.integrations',
    'litellm.types',
    'litellm.llms',
    'litellm.llms.openai',
    'litellm.llms.anthropic',
    'litellm.llms.azure',
    'litellm.llms.bedrock',
    'litellm.llms.vertex_ai',
    'litellm.llms.gemini',
    'litellm.llms.ollama',
    'litellm.llms.custom_httpx',
    'pkg_resources',
    'pkg_resources.py2_warn',
    'importlib_metadata',
    'importlib_resources',
    'configargparse',
    'shtab',
    'diff_match_patch',
    'flake8',
    'pycodestyle',
    'pyflakes',
    'mccabe',
    'prompt_toolkit',
    'rich',
    'markdown_it',
    'pygments',
    'yaml',
    'json5',
    'pathspec',
    'gitpython',
    'git',
    'watchfiles',
    'pexpect',
    'ptyprocess',
    'psutil',
    'sounddevice',
    'soundfile',
    'pydub',
    'pillow',
    'beautifulsoup4',
    'bs4',
    'soupsieve',
    'certifi',
    'urllib3',
    'charset_normalizer',
    'idna',
    'click',
    'colorama',
    'packaging',
    'typing_extensions',
    'six',
    'pytz',
    'python_dateutil',
    'dateutil',
]

a = Analysis(
    [r"{source_path}/aider_launcher.py"],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='aider',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''
        
        spec_path = self.temp_dir / "aider.spec"
        with open(spec_path, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        return spec_path
        
    def build_executable(self):
        """Build executable file"""
        self.log("Building Windows executable file...")
        
        spec_path = self.create_spec_file()
        
        # Use PyInstaller to build
        self.run_command([
            str(self.venv_python), "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            "--distpath", str(self.temp_dir / "dist"),
            "--workpath", str(self.temp_dir / "build"),
            str(spec_path)
        ], cwd=self.temp_dir)
        
        # onefile mode, exe file directly in dist directory
        self.exe_dir = self.temp_dir / "dist"
        
    def create_config_files(self):
        """Create configuration files and usage instructions"""
        self.log("Creating configuration files...")
        
        # Create default configuration file
        config_content = """# Aider Configuration File
# For internal network use, connecting to large model via OpenAI Compatible API

# Basic settings
model: openai/your-model-name
openai-api-base: http://your-internal-api-server:port/v1
openai-api-key: your-api-key

# Optional settings
# max-chat-history-tokens: 4096
# temperature: 0.1
# no-auto-commits: true
# dark-mode: true
"""
        
        with open(self.exe_dir / ".aider.conf.yml", 'w', encoding='utf-8') as f:
            f.write(config_content)
            
        # Create model settings file
        model_settings = """# Model Settings File
# Optimization configuration for specific models

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
        """Create batch files for starting"""
        self.log("Creating start script...")
        
        # Main start script
        start_bat = """@echo off
chcp 65001 > nul
title Aider - AI Pair Programming

echo ===============================================
echo           Aider - AI Pair Programming
echo ===============================================
echo.

REM Set environment variables (based on your internal API server configuration)
REM set OPENAI_API_BASE=http://your-internal-api-server:port/v1
REM set OPENAI_API_KEY=your-api-key

echo Current directory: %CD%
echo.
echo Usage:
echo   aider --model openai/your-model-name --openai-api-base http://your-server:port/v1 --openai-api-key your-key
echo.
echo Or edit .aider.conf.yml file to set default configuration
echo.

cmd /k
"""
        
        with open(self.exe_dir / "start_aider.bat", 'w', encoding='utf-8') as f:
            f.write(start_bat)
            
        # Example usage script
        example_bat = """@echo off
chcp 65001 > nul

REM Example: Connect to internal OpenAI Compatible API
REM Please modify the following parameters based on your actual environment

set API_BASE=http://your-internal-server:8000/v1
set API_KEY=your-api-key-here
set MODEL_NAME=your-model-name

echo Starting Aider...
echo API Base: %API_BASE%
echo Model: %MODEL_NAME%
echo.

aider.exe --model openai/%MODEL_NAME% --openai-api-base %API_BASE% --openai-api-key %API_KEY%

pause
"""
        
        with open(self.exe_dir / "example_start.bat", 'w', encoding='utf-8') as f:
            f.write(example_bat)
            
    def create_documentation(self):
        """Create usage documentation"""
        self.log("Creating usage documentation...")
        
        readme_content = """# Aider Offline Windows Version Usage Instructions

## Introduction
This is the complete offline Windows version of Aider, which can be used in internal network environments, connecting to your large model service via OpenAI Compatible API.

## System Requirements
- Windows 10/11 (64-bit)
- Internal network OpenAI Compatible API service

## Quick Start

### 1. Extract Files
Extract the entire folder to the location you want.

### 2. Configure API Connection
Edit `.aider.conf.yml` file to set your API parameters:

```yaml
model: openai/your-model-name
openai-api-base: http://your-internal-api-server:port/v1
openai-api-key: your-api-key
```

### 3. Start Aider
- Double-click `start_aider.bat` to open command line environment
- Or directly run `example_start.bat` (need to edit parameters first)

### 4. Use Aider
```bash
# Enter your project directory
cd C:\\path\\to\\your\\project

# Start aider (if .aider.conf.yml is configured)
aider

# Or specify parameters directly
aider --model openai/your-model --openai-api-base http://your-server:port/v1 --openai-api-key your-key
```

## Common Commands

```bash
# View help
aider --help

# List available models
aider --list-models

# Use specific model
aider --model openai/gpt-4

# Set context window
aider --model openai/your-model --max-chat-history-tokens 8192

# Disable auto commits
aider --no-auto-commits
```

## Configuration Files

### .aider.conf.yml (Main Configuration File)
```yaml
model: openai/your-model-name
openai-api-base: http://your-internal-api-server:port/v1
openai-api-key: your-api-key
max-chat-history-tokens: 4096
temperature: 0.1
dark-mode: true
```

### .aider.model.settings.yml (Model Settings File)
Used for optimizing behavior of specific models, no need to modify.

## Environment Variable Settings

You can also set API parameters via environment variables:

```bat
set AIDER_OPENAI_API_BASE=http://your-internal-server:port/v1
set AIDER_OPENAI_API_KEY=your-api-key
```

## Troubleshooting

### Connection Issues
- Check API server address and port
- Confirm API key is valid
- Test network connectivity

### Model Issues
- Confirm model name is correct
- Check if model supports chat completion
- Verify model context window size

### Performance Optimization
- Use diff format for code editing
- Appropriately set max-chat-history-tokens parameter
- Adjust temperature parameter based on needs

## Technical Support

For help, please refer to:
- Aider Official Documentation: https://aider.chat/docs/
- GitHub Repository: https://github.com/Aider-AI/aider

## Version Information
- Build Time: """ + f"{self.get_build_time()}" + """
- Included Components: Aider + All Python Dependencies
- Supported Features: Code Editing, Git Integration, Multi-Language Support

---
Have a great time using it!
"""
        
        with open(self.exe_dir / "README.md", 'w', encoding='utf-8') as f:
            f.write(readme_content)
            
    def get_build_time(self):
        """Get build time"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def create_final_package(self):
        """Create final release package"""
        self.log("Creating final release package...")
        
        # Ensure output directory exists
        self.output_dir.mkdir(exist_ok=True)
        
        # Create version information file
        version_info = {
            "build_time": self.get_build_time(),
            "python_version": sys.version,
            "platform": "Windows",
            "components": ["aider", "python_dependencies"],
            "usage": "Internal network with OpenAI Compatible API"
        }
        
        with open(self.exe_dir / "version_info.json", 'w', encoding='utf-8') as f:
            json.dump(version_info, f, indent=2, ensure_ascii=False)
            
        # Copy to output directory
        final_dir = self.output_dir / "aider_windows_offline"
        if final_dir.exists():
            shutil.rmtree(final_dir)
            
        shutil.copytree(self.exe_dir, final_dir)
        
        # Create zip package
        zip_path = self.output_dir / "aider_windows_offline.zip"
        if zip_path.exists():
            zip_path.unlink()
            
        shutil.make_archive(
            str(self.output_dir / "aider_windows_offline"),
            'zip',
            str(final_dir)
        )
        
        self.log(f"✅ Offline package created successfully!")
        self.log(f"📁 Directory: {final_dir}")
        self.log(f"�� Zip Package: {zip_path}")
        
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and self.temp_dir.exists():
            self.log("Cleaning up temporary files...")
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
    def build(self):
        """Execute complete build process"""
        try:
            self.log("🚀 Starting Aider Windows Offline Package Build...")
            
            self.setup_environment()
            self.create_virtual_environment()
            self.install_dependencies()
            self.build_executable()
            self.create_config_files()
            self.create_batch_files()
            self.create_documentation()
            self.create_final_package()
            
            self.log("🎉 Build completed!")
            
        except Exception as e:
            self.error(f"Build failed: {e}")
        finally:
            self.cleanup()

def main():
    parser = argparse.ArgumentParser(description="Build Aider Offline Windows Package")
    parser.add_argument("-o", "--output", default="dist", help="Output directory (default: dist)")
    
    args = parser.parse_args()
    
    builder = AiderWindowsBuilder(args.output)
    builder.build()

if __name__ == "__main__":
    main() 