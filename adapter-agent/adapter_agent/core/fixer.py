"""
Fixer Module - 自动修复器（完整版）

功能：
- 自动诊断集成问题
- 提供修复建议
- 自动执行修复
- 支持多种问题类型
"""

import re
import ast
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

from .scanner import ProjectProfile
from .validator import ValidationReport, ValidationStatus, ValidationCheck


class IssueType(Enum):
    """问题类型"""
    MISSING_FILE = "missing_file"
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    MISSING_COMPONENT = "missing_component"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_ERROR = "dependency_error"
    PERMISSION_ERROR = "permission_error"
    PERFORMANCE_ISSUE = "performance_issue"


class FixStatus(Enum):
    """修复状态"""
    PENDING = "pending"
    FIXED = "fixed"
    PARTIALLY_FIXED = "partially_fixed"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"


@dataclass
class Issue:
    """检测到的问题"""
    type: IssueType
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    severity: str = "medium"  # low, medium, high, critical
    auto_fixable: bool = False
    fix_suggestion: str = ""


@dataclass
class FixAction:
    """修复操作"""
    description: str
    action_type: str  # file_write, file_patch, command, manual
    target: Optional[str] = None
    content: Optional[str] = None
    command: Optional[str] = None


@dataclass
class FixResult:
    """修复结果"""
    success: bool
    status: FixStatus
    issues_found: List[Issue] = field(default_factory=list)
    actions_taken: List[FixAction] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status": self.status.value,
            "issues_found": [
                {
                    "type": i.type.value,
                    "description": i.description,
                    "severity": i.severity,
                    "auto_fixable": i.auto_fixable
                }
                for i in self.issues_found
            ],
            "actions_taken": [
                {"description": a.description, "type": a.action_type}
                for a in self.actions_taken
            ],
            "errors": self.errors,
            "recommendations": self.recommendations
        }


class Fixer:
    """
    自动修复器 - 完整版

    诊断和修复安全防护集成中的问题
    """

    def __init__(
        self,
        profile: ProjectProfile,
        validation_report: Optional[ValidationReport] = None
    ):
        self.profile = profile
        self.validation_report = validation_report
        self.project_path = Path(profile.project_path)

    def diagnose(self) -> List[Issue]:
        """
        诊断问题

        Returns:
            发现的问题列表
        """
        issues = []

        # 1. 检查文件问题
        self._diagnose_file_issues(issues)

        # 2. 检查语法问题
        self._diagnose_syntax_issues(issues)

        # 3. 检查导入问题
        self._diagnose_import_issues(issues)

        # 4. 检查配置问题
        self._diagnose_config_issues(issues)

        # 5. 检查依赖问题
        self._diagnose_dependency_issues(issues)

        # 6. 从验证报告中提取问题
        if self.validation_report:
            self._extract_validation_issues(issues)

        return issues

    def fix(self, auto_fix: bool = True) -> FixResult:
        """
        执行修复

        Args:
            auto_fix: 是否自动修复可修复的问题

        Returns:
            修复结果
        """
        result = FixResult(
            success=True,
            status=FixStatus.PENDING
        )

        # 诊断问题
        issues = self.diagnose()
        result.issues_found = issues

        if not issues:
            result.status = FixStatus.FIXED
            return result

        # 尝试修复
        fixed_count = 0
        failed_count = 0

        for issue in issues:
            if issue.auto_fixable and auto_fix:
                try:
                    action = self._fix_issue(issue)
                    if action:
                        result.actions_taken.append(action)
                        fixed_count += 1
                except Exception as e:
                    result.errors.append(f"修复失败 ({issue.type.value}): {str(e)}")
                    failed_count += 1
            else:
                result.recommendations.append(
                    f"[{issue.severity.upper()}] {issue.description}: {issue.fix_suggestion}"
                )

        # 确定最终状态
        if failed_count > 0:
            result.success = False
            result.status = FixStatus.PARTIALLY_FIXED if fixed_count > 0 else FixStatus.FAILED
        elif fixed_count > 0:
            result.status = FixStatus.FIXED
        else:
            result.status = FixStatus.MANUAL_REQUIRED

        return result

    def _diagnose_file_issues(self, issues: List[Issue]) -> None:
        """诊断文件问题"""
        required_files = [
            ("safety_wrapper.py", "核心安全包装器"),
        ]

        for filename, desc in required_files:
            file_path = self.project_path / filename
            if not file_path.exists():
                issues.append(Issue(
                    type=IssueType.MISSING_FILE,
                    description=f"缺少 {desc} 文件: {filename}",
                    file_path=str(file_path),
                    severity="high",
                    auto_fixable=True,
                    fix_suggestion=f"重新生成 {filename} 文件"
                ))

    def _diagnose_syntax_issues(self, issues: List[Issue]) -> None:
        """诊断语法问题"""
        python_files = [
            self.project_path / "safety_wrapper.py",
            self.project_path / "safety_config.yaml",
        ]

        for file_path in python_files:
            if file_path.exists() and file_path.suffix == '.py':
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    ast.parse(content)
                except SyntaxError as e:
                    issues.append(Issue(
                        type=IssueType.SYNTAX_ERROR,
                        description=f"语法错误: {e.msg}",
                        file_path=str(file_path),
                        line_number=e.lineno,
                        severity="critical",
                        auto_fixable=False,
                        fix_suggestion=f"修复第 {e.lineno} 行的语法错误"
                    ))

    def _diagnose_import_issues(self, issues: List[Issue]) -> None:
        """诊断导入问题"""
        wrapper_path = self.project_path / "safety_wrapper.py"

        if not wrapper_path.exists():
            return

        try:
            with open(wrapper_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查常见的导入问题
            imports = re.findall(r'^(?:from|import)\s+(\w+)', content, re.MULTILINE)

            external_deps = {
                'nemoguardrails': 'nemoguardrails',
                'openguardrails': 'openguardrails',
                'guardrails': 'guardrails-ai',
                'llama_firewall': 'llama-firewall',
                'transformers': 'transformers',
            }

            for imp in imports:
                if imp in external_deps:
                    # 检查依赖是否安装
                    try:
                        __import__(imp)
                    except ImportError:
                        issues.append(Issue(
                            type=IssueType.DEPENDENCY_ERROR,
                            description=f"缺少依赖: {imp}",
                            severity="high",
                            auto_fixable=True,
                            fix_suggestion=f"pip install {external_deps[imp]}"
                        ))

        except Exception:
            pass

    def _diagnose_config_issues(self, issues: List[Issue]) -> None:
        """诊断配置问题"""
        config_path = self.project_path / "safety_config.yaml"

        if config_path.exists():
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)

                # 检查必要的配置项
                if not config:
                    issues.append(Issue(
                        type=IssueType.CONFIG_ERROR,
                        description="配置文件为空",
                        file_path=str(config_path),
                        severity="medium",
                        auto_fixable=True,
                        fix_suggestion="重新生成配置文件"
                    ))

            except yaml.YAMLError as e:
                issues.append(Issue(
                    type=IssueType.CONFIG_ERROR,
                    description=f"YAML 解析错误: {e}",
                    file_path=str(config_path),
                    severity="high",
                    auto_fixable=False,
                    fix_suggestion="修复 YAML 语法错误"
                ))
            except ImportError:
                pass

    def _diagnose_dependency_issues(self, issues: List[Issue]) -> None:
        """诊断依赖问题"""
        req_file = self.project_path / "requirements.txt"

        if not req_file.exists():
            return

        # 检查是否缺少安全相关依赖
        with open(req_file, 'r', encoding='utf-8') as f:
            content = f.read().lower()

        # 根据项目配置检查依赖
        # 这里简化处理，实际应该根据使用的安全工具来检查

    def _extract_validation_issues(self, issues: List[Issue]) -> None:
        """从验证报告中提取问题"""
        if not self.validation_report:
            return

        for check in self.validation_report.checks:
            if check.status == ValidationStatus.FAILED:
                issue_type = self._map_check_to_issue_type(check.name)
                issues.append(Issue(
                    type=issue_type,
                    description=check.message,
                    severity="high",
                    auto_fixable=self._is_auto_fixable(check.name),
                    fix_suggestion=self._get_fix_suggestion(check.name)
                ))

    def _map_check_to_issue_type(self, check_name: str) -> IssueType:
        """将检查名称映射到问题类型"""
        mapping = {
            "file_exists": IssueType.MISSING_FILE,
            "syntax_check": IssueType.SYNTAX_ERROR,
            "module_import": IssueType.IMPORT_ERROR,
            "required_components": IssueType.MISSING_COMPONENT,
            "performance": IssueType.PERFORMANCE_ISSUE,
        }

        for key, value in mapping.items():
            if key in check_name:
                return value

        return IssueType.CONFIG_ERROR

    def _is_auto_fixable(self, check_name: str) -> bool:
        """判断问题是否可自动修复"""
        auto_fixable = [
            "file_exists",
            "missing_component",
        ]
        return any(af in check_name for af in auto_fixable)

    def _get_fix_suggestion(self, check_name: str) -> str:
        """获取修复建议"""
        suggestions = {
            "file_exists": "重新运行代码生成",
            "syntax_check": "检查并修复语法错误",
            "module_import": "检查依赖安装",
            "required_components": "重新生成包装器代码",
            "performance": "优化检查逻辑或使用缓存",
        }

        for key, value in suggestions.items():
            if key in check_name:
                return value

        return "请参考文档手动修复"

    def _fix_issue(self, issue: Issue) -> Optional[FixAction]:
        """修复单个问题"""
        fix_handlers = {
            IssueType.MISSING_FILE: self._fix_missing_file,
            IssueType.DEPENDENCY_ERROR: self._fix_dependency,
            IssueType.CONFIG_ERROR: self._fix_config,
        }

        handler = fix_handlers.get(issue.type)
        if handler:
            return handler(issue)

        return None

    def _fix_missing_file(self, issue: Issue) -> FixAction:
        """修复缺失文件问题"""
        # 生成默认的安全包装器
        if "safety_wrapper" in str(issue.file_path):
            default_content = self._get_default_wrapper()

            with open(issue.file_path, 'w', encoding='utf-8') as f:
                f.write(default_content)

            return FixAction(
                description="生成默认安全包装器",
                action_type="file_write",
                target=issue.file_path,
                content=default_content[:100] + "..."
            )

        return None

    def _fix_dependency(self, issue: Issue) -> FixAction:
        """修复依赖问题"""
        import subprocess

        # 从描述中提取依赖名
        match = re.search(r'缺少依赖:\s*(\w+)', issue.description)
        if match:
            dep = match.group(1)
            try:
                subprocess.run(
                    ['pip', 'install', dep],
                    capture_output=True,
                    check=True
                )
                return FixAction(
                    description=f"安装依赖 {dep}",
                    action_type="command",
                    command=f"pip install {dep}"
                )
            except subprocess.CalledProcessError:
                raise RuntimeError(f"安装 {dep} 失败")

        return None

    def _fix_config(self, issue: Issue) -> FixAction:
        """修复配置问题"""
        if "配置文件为空" in issue.description:
            default_config = """# Safety Configuration
safety:
  strict_mode: true
  enable_logging: true
"""
            with open(issue.file_path, 'w', encoding='utf-8') as f:
                f.write(default_config)

            return FixAction(
                description="生成默认配置",
                action_type="file_write",
                target=issue.file_path
            )

        return None

    def _get_default_wrapper(self) -> str:
        """获取默认包装器代码"""
        return '''"""
安全包装器 - 由 Fixer 自动生成
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SafetyCheckResult:
    is_safe: bool
    reason: str = ""
    risk_level: str = "low"
    sanitized_content: Optional[str] = None


class SafetyWrapper:
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def check_input(self, user_input: str) -> SafetyCheckResult:
        # 基础 Prompt Injection 检测
        patterns = [
            r'ignore\\s+previous\\s+instructions?',
            r'jailbreak',
        ]
        for pattern in patterns:
            if re.search(pattern, user_input.lower()):
                return SafetyCheckResult(
                    is_safe=False,
                    reason="检测到潜在的 Prompt Injection",
                    risk_level="critical"
                )
        return SafetyCheckResult(is_safe=True)

    def check_output(self, response: str) -> SafetyCheckResult:
        return SafetyCheckResult(is_safe=True)

    def check_tool_call(self, tool_name: str, tool_args: dict) -> SafetyCheckResult:
        dangerous = ['delete', 'drop', 'rm']
        if any(d in tool_name.lower() for d in dangerous):
            return SafetyCheckResult(
                is_safe=False,
                reason="危险工具调用",
                risk_level="high"
            )
        return SafetyCheckResult(is_safe=True)


safety = SafetyWrapper()
'''


def fix(
    profile: ProjectProfile,
    validation_report: Optional[ValidationReport] = None,
    auto_fix: bool = True
) -> FixResult:
    """便捷函数：执行修复"""
    fixer = Fixer(profile, validation_report)
    return fixer.fix(auto_fix)
