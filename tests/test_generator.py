"""
Generator 模块测试
"""

import tempfile
import pytest
from pathlib import Path

from guard_adapter.scanner import ScanResult, ProjectType, IntegrationType
from guard_adapter.generator import CodeGenerator, GenerationResult, generate_code


class TestCodeGenerator:
    """代码生成器测试"""

    def create_mock_scan_result(self, project_path: str, project_type: ProjectType) -> ScanResult:
        """创建模拟的扫描结果"""
        return ScanResult(
            project_path=project_path,
            project_type=project_type,
            integration_type=IntegrationType.SDK,
            has_async=True,
        )

    def test_generate_for_claudebot(self):
        """测试为 ClaudeBot 生成代码"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result = self.create_mock_scan_result(tmpdir, ProjectType.CLAUDEBOT)

            generator = CodeGenerator(scan_result)
            result = generator.generate()

            assert result.is_success
            assert len(result.files) >= 2  # guard_wrapper.py + safe_claudebot.py

            # 检查生成了核心包装器
            file_paths = [f.file_path for f in result.files]
            assert any("guard_wrapper.py" in p for p in file_paths)
            assert any("safe_claudebot.py" in p for p in file_paths)

    def test_generate_for_langchain(self):
        """测试为 LangChain 生成代码"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result = self.create_mock_scan_result(tmpdir, ProjectType.LANGCHAIN)

            generator = CodeGenerator(scan_result)
            result = generator.generate()

            assert result.is_success
            file_paths = [f.file_path for f in result.files]
            assert any("guard_langchain.py" in p for p in file_paths)

    def test_generate_for_generic(self):
        """测试为通用项目生成代码"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result = self.create_mock_scan_result(tmpdir, ProjectType.GENERIC_PYTHON)

            generator = CodeGenerator(scan_result)
            result = generator.generate()

            assert result.is_success
            # 至少应该生成基础包装器
            file_paths = [f.file_path for f in result.files]
            assert any("guard_wrapper.py" in p for p in file_paths)

    def test_generate_includes_instructions(self):
        """测试生成结果包含集成说明"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result = self.create_mock_scan_result(tmpdir, ProjectType.CLAUDEBOT)

            generator = CodeGenerator(scan_result)
            result = generator.generate()

            assert len(result.instructions) > 0

    def test_generated_code_contains_guard_class(self):
        """测试生成的代码包含 GuardWrapper 类"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result = self.create_mock_scan_result(tmpdir, ProjectType.CLAUDEBOT)

            generator = CodeGenerator(scan_result)
            result = generator.generate()

            guard_wrapper_file = next(
                (f for f in result.files if "guard_wrapper.py" in f.file_path),
                None
            )

            assert guard_wrapper_file is not None
            assert "class GuardWrapper" in guard_wrapper_file.content
            assert "check_input" in guard_wrapper_file.content
            assert "check_output" in guard_wrapper_file.content
            assert "check_tool_call" in guard_wrapper_file.content


class TestGenerateCode:
    """便捷函数测试"""

    def test_generate_code_function(self):
        """测试 generate_code 便捷函数"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result = ScanResult(
                project_path=tmpdir,
                project_type=ProjectType.CLAUDEBOT,
                integration_type=IntegrationType.SDK,
            )

            result = generate_code(scan_result)
            assert isinstance(result, GenerationResult)
            assert result.is_success
