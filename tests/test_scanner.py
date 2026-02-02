"""
Scanner 模块测试
"""

import os
import tempfile
import pytest
from pathlib import Path

from guard_adapter.scanner import (
    ProjectScanner,
    ScanResult,
    ProjectType,
    IntegrationType,
    scan_project,
)


class TestProjectScanner:
    """项目扫描器测试"""

    def test_scan_empty_directory(self):
        """测试扫描空目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = ProjectScanner(tmpdir)
            result = scanner.scan()

            assert result.project_type == ProjectType.UNKNOWN
            assert len(result.integration_points) == 0

    def test_scan_claudebot_project(self):
        """测试扫描 ClaudeBot 项目"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建模拟的 ClaudeBot 文件
            bot_file = Path(tmpdir) / "bot.py"
            bot_file.write_text("""
import anthropic

class ClaudeBot:
    def __init__(self):
        self.client = anthropic.Anthropic()

    async def chat(self, user_input: str) -> str:
        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            messages=[{"role": "user", "content": user_input}]
        )
        return response.content[0].text
""")

            scanner = ProjectScanner(tmpdir)
            result = scanner.scan()

            assert result.project_type == ProjectType.CLAUDEBOT
            assert result.has_async is True
            assert len(result.integration_points) > 0

    def test_scan_langchain_project(self):
        """测试扫描 LangChain 项目"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建模拟的 LangChain 文件
            app_file = Path(tmpdir) / "app.py"
            app_file.write_text("""
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain

llm = ChatOpenAI()
chain = LLMChain(llm=llm)
""")

            scanner = ProjectScanner(tmpdir)
            result = scanner.scan()

            assert result.project_type == ProjectType.LANGCHAIN

    def test_scan_with_requirements(self):
        """测试扫描带 requirements.txt 的项目"""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("""
anthropic>=0.18.0
pydantic>=2.0.0
aiohttp>=3.8.0
""")

            scanner = ProjectScanner(tmpdir)
            result = scanner.scan()

            assert "anthropic>=0.18.0" in result.dependencies
            assert "pydantic>=2.0.0" in result.dependencies

    def test_scan_nonexistent_path(self):
        """测试扫描不存在的路径"""
        with pytest.raises(ValueError, match="项目路径不存在"):
            ProjectScanner("/nonexistent/path/12345")

    def test_find_main_entry(self):
        """测试查找主入口文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            main_file = Path(tmpdir) / "main.py"
            main_file.write_text("# Main entry")

            scanner = ProjectScanner(tmpdir)
            result = scanner.scan()

            assert result.main_entry == str(main_file)

    def test_detect_async_pattern(self):
        """测试检测异步模式"""
        with tempfile.TemporaryDirectory() as tmpdir:
            async_file = Path(tmpdir) / "async_app.py"
            async_file.write_text("""
import asyncio

async def main():
    await asyncio.sleep(1)
""")

            scanner = ProjectScanner(tmpdir)
            result = scanner.scan()

            assert result.has_async is True


class TestScanProject:
    """便捷函数测试"""

    def test_scan_project_function(self):
        """测试 scan_project 便捷函数"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_project(tmpdir)
            assert isinstance(result, ScanResult)
            assert result.project_path == str(Path(tmpdir).resolve())
