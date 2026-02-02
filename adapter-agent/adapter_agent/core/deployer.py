"""
Deployer Module - 部署器（完整版）

功能：
- 将生成的代码部署到目标项目
- 支持多种部署模式
- 自动备份和回滚
- 依赖安装
"""

import os
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

from .scanner import ProjectProfile
from .generator import GeneratedCode, GeneratedFile


class DeploymentMode(Enum):
    """部署模式"""
    DIRECT = "direct"           # 直接部署到项目
    STAGED = "staged"           # 分阶段部署
    CONTAINER = "container"     # 容器化部署
    DRY_RUN = "dry_run"        # 模拟部署


class DeploymentStatus(Enum):
    """部署状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentStep:
    """部署步骤"""
    name: str
    description: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class DeploymentResult:
    """部署结果"""
    success: bool
    status: DeploymentStatus
    deployed_files: List[str] = field(default_factory=list)
    backup_path: Optional[str] = None
    steps: List[DeploymentStep] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rollback_available: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status": self.status.value,
            "deployed_files": self.deployed_files,
            "backup_path": self.backup_path,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "error": s.error
                }
                for s in self.steps
            ],
            "errors": self.errors,
            "warnings": self.warnings,
            "rollback_available": self.rollback_available,
            "duration_seconds": self.duration_seconds,
        }


class Deployer:
    """
    部署器 - 完整版

    支持功能：
    - 文件部署
    - 自动备份
    - 依赖安装
    - 回滚支持
    - Docker 部署
    """

    def __init__(
        self,
        profile: ProjectProfile,
        generated_code: GeneratedCode,
        mode: DeploymentMode = DeploymentMode.DIRECT
    ):
        self.profile = profile
        self.generated_code = generated_code
        self.mode = mode
        self.project_path = Path(profile.project_path)
        self._backup_path: Optional[Path] = None

    def deploy(
        self,
        install_deps: bool = True,
        create_backup: bool = True,
        force: bool = False
    ) -> DeploymentResult:
        """
        执行部署

        Args:
            install_deps: 是否安装依赖
            create_backup: 是否创建备份
            force: 是否强制覆盖

        Returns:
            部署结果
        """
        result = DeploymentResult(
            success=True,
            status=DeploymentStatus.IN_PROGRESS,
            start_time=datetime.now()
        )

        try:
            # Step 1: 验证前置条件
            self._execute_step(
                result,
                "validate",
                "验证部署前置条件",
                lambda: self._validate_prerequisites(result, force)
            )

            if not result.success:
                return self._finalize_result(result)

            # Step 2: 创建备份
            if create_backup and self.mode != DeploymentMode.DRY_RUN:
                self._execute_step(
                    result,
                    "backup",
                    "创建项目备份",
                    lambda: self._create_backup(result)
                )

            # Step 3: 部署文件
            self._execute_step(
                result,
                "deploy_files",
                "部署生成的文件",
                lambda: self._deploy_files(result)
            )

            if not result.success:
                return self._finalize_result(result)

            # Step 4: 安装依赖
            if install_deps and self.mode != DeploymentMode.DRY_RUN:
                self._execute_step(
                    result,
                    "install_deps",
                    "安装项目依赖",
                    lambda: self._install_dependencies(result)
                )

            # Step 5: 验证部署
            self._execute_step(
                result,
                "verify",
                "验证部署结果",
                lambda: self._verify_deployment(result)
            )

            result.status = DeploymentStatus.COMPLETED

        except Exception as e:
            result.success = False
            result.status = DeploymentStatus.FAILED
            result.errors.append(f"部署异常: {str(e)}")

        return self._finalize_result(result)

    def _execute_step(
        self,
        result: DeploymentResult,
        name: str,
        description: str,
        action: callable
    ) -> None:
        """执行部署步骤"""
        step = DeploymentStep(name=name, description=description)
        step.status = DeploymentStatus.IN_PROGRESS
        result.steps.append(step)

        start_time = datetime.now()

        try:
            action()
            step.status = DeploymentStatus.COMPLETED
        except Exception as e:
            step.status = DeploymentStatus.FAILED
            step.error = str(e)
            result.success = False
            result.errors.append(f"步骤 '{name}' 失败: {str(e)}")

        step.duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    def _validate_prerequisites(self, result: DeploymentResult, force: bool) -> None:
        """验证部署前置条件"""
        # 检查项目目录
        if not self.project_path.exists():
            raise ValueError(f"项目目录不存在: {self.project_path}")

        # 检查写入权限
        if not os.access(self.project_path, os.W_OK):
            raise PermissionError(f"没有目录写入权限: {self.project_path}")

        # 检查是否有文件要部署
        if not self.generated_code.files:
            raise ValueError("没有要部署的文件")

        # 检查文件冲突
        if not force:
            for gen_file in self.generated_code.files:
                target_path = Path(gen_file.path)
                if target_path.exists() and gen_file.is_new:
                    result.warnings.append(f"文件已存在，将被覆盖: {target_path}")

    def _create_backup(self, result: DeploymentResult) -> None:
        """创建备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.project_path / f".adapter_backup_{timestamp}"

        backup_dir.mkdir(exist_ok=True)
        self._backup_path = backup_dir

        # 备份可能被修改的文件
        for gen_file in self.generated_code.files:
            target_path = Path(gen_file.path)
            if target_path.exists():
                try:
                    relative_path = target_path.relative_to(self.project_path)
                    backup_file = backup_dir / relative_path
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target_path, backup_file)
                except ValueError:
                    # 文件不在项目目录内
                    pass

        result.backup_path = str(backup_dir)
        result.rollback_available = True

    def _deploy_files(self, result: DeploymentResult) -> None:
        """部署文件"""
        for gen_file in self.generated_code.files:
            target_path = Path(gen_file.path)

            if self.mode == DeploymentMode.DRY_RUN:
                result.deployed_files.append(f"[DRY RUN] {target_path}")
                continue

            try:
                # 确保目录存在
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # 写入文件
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(gen_file.content)

                result.deployed_files.append(str(target_path))

            except Exception as e:
                raise IOError(f"写入文件失败 {target_path}: {str(e)}")

    def _install_dependencies(self, result: DeploymentResult) -> None:
        """安装依赖"""
        if not self.generated_code.dependencies:
            return

        # 更新 requirements.txt
        req_file = self.project_path / "requirements.txt"

        if req_file.exists():
            existing_deps = req_file.read_text().strip().split('\n')
        else:
            existing_deps = []

        # 添加新依赖
        new_deps = []
        for dep in self.generated_code.dependencies:
            dep_name = dep.split('>=')[0].split('==')[0].split('<')[0]
            if not any(dep_name in d for d in existing_deps):
                new_deps.append(dep)

        if new_deps:
            with open(req_file, 'a', encoding='utf-8') as f:
                f.write('\n# Added by Adapter Agent\n')
                for dep in new_deps:
                    f.write(f'{dep}\n')

            # 安装依赖
            try:
                subprocess.run(
                    ['pip', 'install'] + new_deps,
                    capture_output=True,
                    check=True,
                    cwd=str(self.project_path)
                )
            except subprocess.CalledProcessError as e:
                result.warnings.append(
                    f"依赖安装失败，请手动安装: pip install {' '.join(new_deps)}"
                )

    def _verify_deployment(self, result: DeploymentResult) -> None:
        """验证部署"""
        for file_path in result.deployed_files:
            if "[DRY RUN]" in file_path:
                continue

            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"部署验证失败: 文件不存在 {file_path}")

            if path.stat().st_size == 0:
                result.warnings.append(f"警告: 文件为空 {file_path}")

    def _finalize_result(self, result: DeploymentResult) -> DeploymentResult:
        """完成结果"""
        result.end_time = datetime.now()
        if not result.success and result.status == DeploymentStatus.IN_PROGRESS:
            result.status = DeploymentStatus.FAILED
        return result

    def rollback(self) -> bool:
        """回滚部署"""
        if not self._backup_path or not self._backup_path.exists():
            return False

        try:
            # 恢复备份的文件
            for backup_file in self._backup_path.rglob("*"):
                if backup_file.is_file():
                    relative_path = backup_file.relative_to(self._backup_path)
                    target_path = self.project_path / relative_path
                    shutil.copy2(backup_file, target_path)

            # 删除新部署的文件（不在备份中的）
            for gen_file in self.generated_code.files:
                target_path = Path(gen_file.path)
                try:
                    relative_path = target_path.relative_to(self.project_path)
                    backup_file = self._backup_path / relative_path
                    if not backup_file.exists() and target_path.exists():
                        target_path.unlink()
                except ValueError:
                    pass

            return True

        except Exception:
            return False


class ContainerDeployer:
    """
    容器化部署器

    支持 Docker 部署
    """

    def __init__(
        self,
        profile: ProjectProfile,
        generated_code: GeneratedCode
    ):
        self.profile = profile
        self.generated_code = generated_code
        self.project_path = Path(profile.project_path)

    def generate_dockerfile(self) -> str:
        """生成 Dockerfile"""
        deps = ' '.join(self.generated_code.dependencies)

        return f'''# Generated by Adapter Agent
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir {deps}

# Copy application
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "from safety_wrapper import safety; print('OK')" || exit 1

# Run application
CMD ["python", "main.py"]
'''

    def generate_docker_compose(self) -> str:
        """生成 docker-compose.yml"""
        return '''# Generated by Adapter Agent
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SAFETY_STRICT_MODE=true
      - SAFETY_LOGGING=true
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "from safety_wrapper import safety; print('OK')"]
      interval: 30s
      timeout: 10s
      retries: 3
'''

    def deploy(self, build: bool = True) -> DeploymentResult:
        """执行容器化部署"""
        result = DeploymentResult(
            success=True,
            status=DeploymentStatus.IN_PROGRESS,
            start_time=datetime.now()
        )

        try:
            # 生成 Dockerfile
            dockerfile_path = self.project_path / "Dockerfile.safety"
            dockerfile_path.write_text(self.generate_dockerfile())
            result.deployed_files.append(str(dockerfile_path))

            # 生成 docker-compose
            compose_path = self.project_path / "docker-compose.safety.yml"
            compose_path.write_text(self.generate_docker_compose())
            result.deployed_files.append(str(compose_path))

            # 构建镜像
            if build:
                subprocess.run(
                    ['docker', 'build', '-f', 'Dockerfile.safety', '-t', 'app-with-safety', '.'],
                    cwd=str(self.project_path),
                    check=True,
                    capture_output=True
                )

            result.status = DeploymentStatus.COMPLETED

        except subprocess.CalledProcessError as e:
            result.success = False
            result.status = DeploymentStatus.FAILED
            result.errors.append(f"Docker 构建失败: {e.stderr.decode() if e.stderr else str(e)}")

        except Exception as e:
            result.success = False
            result.status = DeploymentStatus.FAILED
            result.errors.append(f"容器化部署失败: {str(e)}")

        result.end_time = datetime.now()
        return result


def deploy(
    profile: ProjectProfile,
    generated_code: GeneratedCode,
    mode: DeploymentMode = DeploymentMode.DIRECT,
    **kwargs
) -> DeploymentResult:
    """便捷函数：执行部署"""
    if mode == DeploymentMode.CONTAINER:
        deployer = ContainerDeployer(profile, generated_code)
        return deployer.deploy(**kwargs)
    else:
        deployer = Deployer(profile, generated_code, mode)
        return deployer.deploy(**kwargs)
