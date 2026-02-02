"""
Deployer 模块测试
"""

import tempfile
import pytest
from pathlib import Path

from guard_adapter.scanner import ScanResult, ProjectType, IntegrationType
from guard_adapter.generator import GenerationResult, GeneratedFile
from guard_adapter.deployer import Deployer, DeploymentResult, quick_deploy


class TestDeployer:
    """部署器测试"""

    def create_mock_results(self, project_path: str):
        """创建模拟的扫描和生成结果"""
        scan_result = ScanResult(
            project_path=project_path,
            project_type=ProjectType.CLAUDEBOT,
            integration_type=IntegrationType.SDK,
        )

        gen_result = GenerationResult(
            files=[
                GeneratedFile(
                    file_path=str(Path(project_path) / "guard_wrapper.py"),
                    content="# Guard Wrapper\nclass GuardWrapper:\n    pass",
                    is_new=True,
                    description="测试文件"
                ),
            ]
        )

        return scan_result, gen_result

    def test_deploy_creates_files(self):
        """测试部署创建文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result, gen_result = self.create_mock_results(tmpdir)

            deployer = Deployer(scan_result, gen_result)
            result = deployer.deploy()

            assert result.success
            assert len(result.deployed_files) == 1

            # 验证文件已创建
            guard_file = Path(tmpdir) / "guard_wrapper.py"
            assert guard_file.exists()

    def test_deploy_dry_run(self):
        """测试模拟部署"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result, gen_result = self.create_mock_results(tmpdir)

            deployer = Deployer(scan_result, gen_result)
            result = deployer.deploy(dry_run=True)

            assert result.success
            assert "[DRY RUN]" in result.deployed_files[0]

            # 验证文件未实际创建
            guard_file = Path(tmpdir) / "guard_wrapper.py"
            assert not guard_file.exists()

    def test_deploy_creates_backup(self):
        """测试部署创建备份"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 先创建一个已存在的文件
            existing_file = Path(tmpdir) / "guard_wrapper.py"
            existing_file.write_text("# Old content")

            scan_result, gen_result = self.create_mock_results(tmpdir)

            deployer = Deployer(scan_result, gen_result)
            result = deployer.deploy(create_backup=True)

            assert result.success
            assert result.backup_dir is not None
            assert Path(result.backup_dir).exists()

    def test_deploy_no_backup(self):
        """测试不创建备份的部署"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result, gen_result = self.create_mock_results(tmpdir)

            deployer = Deployer(scan_result, gen_result)
            result = deployer.deploy(create_backup=False)

            assert result.success
            assert result.backup_dir is None

    def test_deploy_invalid_path(self):
        """测试部署到无效路径"""
        scan_result = ScanResult(
            project_path="/nonexistent/path/12345",
            project_type=ProjectType.CLAUDEBOT,
            integration_type=IntegrationType.SDK,
        )
        gen_result = GenerationResult(files=[
            GeneratedFile(
                file_path="/nonexistent/path/12345/test.py",
                content="test",
                is_new=True
            )
        ])

        deployer = Deployer(scan_result, gen_result)
        result = deployer.deploy()

        assert not result.success
        assert len(result.errors) > 0

    def test_deploy_empty_files(self):
        """测试没有文件要部署"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scan_result = ScanResult(
                project_path=tmpdir,
                project_type=ProjectType.CLAUDEBOT,
                integration_type=IntegrationType.SDK,
            )
            gen_result = GenerationResult(files=[])

            deployer = Deployer(scan_result, gen_result)
            result = deployer.deploy()

            assert not result.success
            assert "没有要部署的文件" in result.errors[0]

    def test_rollback(self):
        """测试回滚功能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建原始文件
            original_file = Path(tmpdir) / "guard_wrapper.py"
            original_content = "# Original content"
            original_file.write_text(original_content)

            scan_result, gen_result = self.create_mock_results(tmpdir)

            deployer = Deployer(scan_result, gen_result)
            result = deployer.deploy(create_backup=True)

            assert result.success

            # 验证文件已被修改
            assert original_file.read_text() != original_content

            # 执行回滚
            rollback_success = deployer.rollback(result.backup_dir)
            assert rollback_success

            # 验证文件已恢复
            assert original_file.read_text() == original_content

    def test_deployment_result_summary(self):
        """测试部署结果摘要"""
        result = DeploymentResult(
            success=True,
            deployed_files=["/test/guard_wrapper.py"],
            backup_dir="/test/backup",
        )

        summary = result.summary()
        assert "✅ 部署成功" in summary
        assert "guard_wrapper.py" in summary


class TestQuickDeploy:
    """快速部署测试"""

    def test_quick_deploy(self):
        """测试快速部署"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一个简单的 Python 文件
            main_file = Path(tmpdir) / "main.py"
            main_file.write_text("print('hello')")

            result = quick_deploy(tmpdir)

            assert isinstance(result, DeploymentResult)
            # 即使是未知项目类型，也应该生成基础文件
