"""
部署模块 - 将生成的代码部署到目标项目
"""

import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .scanner import ScanResult
from .generator import GenerationResult, GeneratedFile


@dataclass
class DeploymentResult:
    """部署结果"""
    success: bool
    deployed_files: list[str] = field(default_factory=list)
    backup_dir: Optional[str] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """生成部署摘要"""
        lines = []
        if self.success:
            lines.append("✅ 部署成功!")
            lines.append(f"   已部署 {len(self.deployed_files)} 个文件")
            if self.backup_dir:
                lines.append(f"   备份目录: {self.backup_dir}")
        else:
            lines.append("❌ 部署失败")
            for error in self.errors:
                lines.append(f"   错误: {error}")

        if self.warnings:
            lines.append("\n⚠️  警告:")
            for warning in self.warnings:
                lines.append(f"   {warning}")

        lines.append("\n📁 已部署文件:")
        for file in self.deployed_files:
            lines.append(f"   - {file}")

        return '\n'.join(lines)


class Deployer:
    """部署器 - 将生成的代码部署到目标项目"""

    def __init__(self, scan_result: ScanResult, generation_result: GenerationResult):
        self.scan_result = scan_result
        self.generation_result = generation_result
        self.project_path = Path(scan_result.project_path)

    def deploy(self, dry_run: bool = False, create_backup: bool = True) -> DeploymentResult:
        """
        执行部署

        Args:
            dry_run: 如果为 True，只显示会做什么但不实际执行
            create_backup: 是否创建备份

        Returns:
            部署结果
        """
        result = DeploymentResult(success=True)

        # 1. 验证前置条件
        if not self._validate_prerequisites(result):
            result.success = False
            return result

        # 2. 创建备份
        if create_backup and not dry_run:
            result.backup_dir = self._create_backup(result)

        # 3. 部署文件
        for gen_file in self.generation_result.files:
            if dry_run:
                result.deployed_files.append(f"[DRY RUN] {gen_file.file_path}")
            else:
                success = self._deploy_file(gen_file, result)
                if success:
                    result.deployed_files.append(gen_file.file_path)
                else:
                    result.success = False

        # 4. 验证部署
        if not dry_run:
            self._verify_deployment(result)

        return result

    def _validate_prerequisites(self, result: DeploymentResult) -> bool:
        """验证部署前置条件"""
        # 检查项目目录是否存在
        if not self.project_path.exists():
            result.errors.append(f"项目目录不存在: {self.project_path}")
            return False

        # 检查是否有要部署的文件
        if not self.generation_result.files:
            result.errors.append("没有要部署的文件")
            return False

        # 检查目录写入权限
        if not os.access(self.project_path, os.W_OK):
            result.errors.append(f"没有目录写入权限: {self.project_path}")
            return False

        return True

    def _create_backup(self, result: DeploymentResult) -> Optional[str]:
        """创建备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.project_path / f".guard_adapter_backup_{timestamp}"

        try:
            backup_dir.mkdir(exist_ok=True)

            # 备份可能被覆盖的文件
            for gen_file in self.generation_result.files:
                target_path = Path(gen_file.file_path)
                if target_path.exists():
                    relative_path = target_path.relative_to(self.project_path)
                    backup_path = backup_dir / relative_path
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target_path, backup_path)

            return str(backup_dir)

        except Exception as e:
            result.warnings.append(f"备份创建失败: {e}")
            return None

    def _deploy_file(self, gen_file: GeneratedFile, result: DeploymentResult) -> bool:
        """部署单个文件"""
        target_path = Path(gen_file.file_path)

        try:
            # 确保目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 检查文件是否已存在
            if target_path.exists() and gen_file.is_new:
                result.warnings.append(f"文件已存在，将被覆盖: {target_path}")

            # 写入文件
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(gen_file.content)

            return True

        except Exception as e:
            result.errors.append(f"部署文件失败 {target_path}: {e}")
            return False

    def _verify_deployment(self, result: DeploymentResult) -> None:
        """验证部署结果"""
        for file_path in result.deployed_files:
            if "[DRY RUN]" in file_path:
                continue

            path = Path(file_path)
            if not path.exists():
                result.errors.append(f"部署验证失败: 文件不存在 {file_path}")
                result.success = False
            elif path.stat().st_size == 0:
                result.warnings.append(f"文件为空: {file_path}")

    def rollback(self, backup_dir: str) -> bool:
        """
        回滚部署

        Args:
            backup_dir: 备份目录路径

        Returns:
            是否回滚成功
        """
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            return False

        try:
            # 恢复备份的文件
            for backup_file in backup_path.rglob("*"):
                if backup_file.is_file():
                    relative_path = backup_file.relative_to(backup_path)
                    target_path = self.project_path / relative_path
                    shutil.copy2(backup_file, target_path)

            # 删除新部署的文件（不在备份中的）
            for gen_file in self.generation_result.files:
                target_path = Path(gen_file.file_path)
                backup_file = backup_path / target_path.relative_to(self.project_path)
                if not backup_file.exists() and target_path.exists():
                    target_path.unlink()

            return True

        except Exception:
            return False


class QuickDeployer:
    """
    快速部署器 - 一键完成扫描、生成、部署全流程
    """

    def __init__(self, project_path: str):
        self.project_path = project_path

    def deploy(self, dry_run: bool = False) -> tuple[ScanResult, GenerationResult, DeploymentResult]:
        """
        一键部署

        Returns:
            (扫描结果, 生成结果, 部署结果)
        """
        from .scanner import ProjectScanner
        from .generator import CodeGenerator

        # Step 1: 扫描
        scanner = ProjectScanner(self.project_path)
        scan_result = scanner.scan()

        # Step 2: 生成
        generator = CodeGenerator(scan_result)
        gen_result = generator.generate()

        # Step 3: 部署
        deployer = Deployer(scan_result, gen_result)
        deploy_result = deployer.deploy(dry_run=dry_run)

        return scan_result, gen_result, deploy_result


def quick_deploy(project_path: str, dry_run: bool = False) -> DeploymentResult:
    """
    便捷函数：一键部署

    Usage:
        result = quick_deploy("/path/to/your/project")
        print(result.summary())
    """
    deployer = QuickDeployer(project_path)
    _, _, deploy_result = deployer.deploy(dry_run=dry_run)
    return deploy_result
