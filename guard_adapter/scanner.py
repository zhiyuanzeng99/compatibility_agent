"""
项目扫描模块 - 扫描目标AI应用，识别项目类型和集成点
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ProjectType(Enum):
    """支持的项目类型"""
    CLAUDEBOT = "claudebot"
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"
    FASTAPI = "fastapi"
    FLASK = "flask"
    GENERIC_PYTHON = "generic_python"
    UNKNOWN = "unknown"


class IntegrationType(Enum):
    """集成方式"""
    SDK = "sdk"           # 白盒集成：直接修改代码
    PROXY = "proxy"       # 黑盒集成：代理网关模式


@dataclass
class IntegrationPoint:
    """集成点信息"""
    file_path: str
    line_number: int
    point_type: str  # pre_prompt, post_task_split, pre_tool_call, post_result
    code_snippet: str
    confidence: float = 1.0


@dataclass
class ScanResult:
    """扫描结果"""
    project_path: str
    project_type: ProjectType
    integration_type: IntegrationType
    python_version: Optional[str] = None
    main_entry: Optional[str] = None
    integration_points: list[IntegrationPoint] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    has_async: bool = False
    framework_version: Optional[str] = None
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.project_type != ProjectType.UNKNOWN and len(self.errors) == 0


class ProjectScanner:
    """项目扫描器 - 分析目标AI应用的结构"""

    # ClaudeBot 特征模式
    CLAUDEBOT_PATTERNS = [
        r'class\s+\w*[Cc]laude\w*[Bb]ot',
        r'from\s+anthropic\s+import',
        r'import\s+anthropic',
        r'Claude\s*\(',
        r'client\.messages\.create',
        r'anthropic\.Anthropic',
    ]

    # LangChain 特征模式
    LANGCHAIN_PATTERNS = [
        r'from\s+langchain',
        r'import\s+langchain',
        r'LLMChain',
        r'ChatOpenAI',
        r'AgentExecutor',
    ]

    # LlamaIndex 特征模式
    LLAMAINDEX_PATTERNS = [
        r'from\s+llama_index',
        r'import\s+llama_index',
        r'VectorStoreIndex',
        r'ServiceContext',
    ]

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        if not self.project_path.exists():
            raise ValueError(f"项目路径不存在: {project_path}")

    def scan(self) -> ScanResult:
        """执行项目扫描"""
        result = ScanResult(
            project_path=str(self.project_path),
            project_type=ProjectType.UNKNOWN,
            integration_type=IntegrationType.SDK,
        )

        # 1. 扫描依赖文件
        self._scan_dependencies(result)

        # 2. 识别项目类型
        self._detect_project_type(result)

        # 3. 查找主入口文件
        self._find_main_entry(result)

        # 4. 分析集成点
        self._find_integration_points(result)

        # 5. 检测异步模式
        self._detect_async_pattern(result)

        return result

    def _scan_dependencies(self, result: ScanResult) -> None:
        """扫描项目依赖"""
        # 检查 requirements.txt
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            with open(req_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        result.dependencies.append(line)

        # 检查 pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, 'r', encoding='utf-8') as f:
                content = f.read()
                # 简单提取依赖（MVP版本简化处理）
                deps_match = re.findall(r'"([^"]+)"', content)
                for dep in deps_match:
                    if any(c in dep for c in ['>=', '<=', '==', '~=']):
                        result.dependencies.append(dep)

        # 检查 setup.py
        setup_py = self.project_path / "setup.py"
        if setup_py.exists():
            with open(setup_py, 'r', encoding='utf-8') as f:
                content = f.read()
                deps = re.findall(r"['\"]([^'\"]+)['\"]", content)
                for dep in deps:
                    if any(c in dep for c in ['>=', '<=', '==', '~=']):
                        result.dependencies.append(dep)

    def _detect_project_type(self, result: ScanResult) -> None:
        """识别项目类型"""
        all_python_files = list(self.project_path.rglob("*.py"))

        scores = {
            ProjectType.CLAUDEBOT: 0,
            ProjectType.LANGCHAIN: 0,
            ProjectType.LLAMAINDEX: 0,
            ProjectType.FASTAPI: 0,
            ProjectType.FLASK: 0,
        }

        for py_file in all_python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                    # ClaudeBot 检测
                    for pattern in self.CLAUDEBOT_PATTERNS:
                        if re.search(pattern, content):
                            scores[ProjectType.CLAUDEBOT] += 1

                    # LangChain 检测
                    for pattern in self.LANGCHAIN_PATTERNS:
                        if re.search(pattern, content):
                            scores[ProjectType.LANGCHAIN] += 1

                    # LlamaIndex 检测
                    for pattern in self.LLAMAINDEX_PATTERNS:
                        if re.search(pattern, content):
                            scores[ProjectType.LLAMAINDEX] += 1

                    # FastAPI 检测
                    if re.search(r'from\s+fastapi|import\s+fastapi|FastAPI\s*\(', content):
                        scores[ProjectType.FASTAPI] += 1

                    # Flask 检测
                    if re.search(r'from\s+flask|import\s+flask|Flask\s*\(', content):
                        scores[ProjectType.FLASK] += 1

            except (UnicodeDecodeError, PermissionError):
                continue

        # 选择得分最高的类型
        if max(scores.values()) > 0:
            result.project_type = max(scores, key=scores.get)
        elif all_python_files:
            result.project_type = ProjectType.GENERIC_PYTHON

    def _find_main_entry(self, result: ScanResult) -> None:
        """查找主入口文件"""
        # 常见的入口文件名
        entry_candidates = [
            "main.py", "app.py", "bot.py", "claude_bot.py", "claudebot.py",
            "server.py", "run.py", "__main__.py", "cli.py"
        ]

        for candidate in entry_candidates:
            entry_file = self.project_path / candidate
            if entry_file.exists():
                result.main_entry = str(entry_file)
                return

        # 检查 src 目录
        src_dir = self.project_path / "src"
        if src_dir.exists():
            for candidate in entry_candidates:
                entry_file = src_dir / candidate
                if entry_file.exists():
                    result.main_entry = str(entry_file)
                    return

    def _find_integration_points(self, result: ScanResult) -> None:
        """查找集成点 - 确定在哪里插入安全检查"""
        all_python_files = list(self.project_path.rglob("*.py"))

        # 根据项目类型选择不同的模式
        if result.project_type == ProjectType.CLAUDEBOT:
            self._find_claudebot_integration_points(result, all_python_files)
        elif result.project_type == ProjectType.LANGCHAIN:
            self._find_langchain_integration_points(result, all_python_files)
        else:
            self._find_generic_integration_points(result, all_python_files)

    def _find_claudebot_integration_points(self, result: ScanResult, files: list) -> None:
        """查找 ClaudeBot 的集成点"""
        patterns = {
            'pre_prompt': [
                (r'def\s+(chat|send_message|process_input|handle_message)\s*\(', 'method_start'),
                (r'user_input\s*=|message\s*=|prompt\s*=', 'input_assignment'),
            ],
            'pre_tool_call': [
                (r'client\.messages\.create', 'api_call'),
                (r'tools?\s*=\s*\[', 'tool_definition'),
                (r'def\s+(execute_tool|run_tool|call_tool)\s*\(', 'tool_execution'),
            ],
            'post_result': [
                (r'return\s+.*response', 'return_response'),
                (r'\.content\[0\]\.text', 'extract_content'),
            ],
        }

        self._search_patterns(result, files, patterns)

    def _find_langchain_integration_points(self, result: ScanResult, files: list) -> None:
        """查找 LangChain 的集成点"""
        patterns = {
            'pre_prompt': [
                (r'def\s+(run|invoke|call)\s*\(', 'chain_invoke'),
                (r'chain\.run|chain\.invoke', 'chain_call'),
            ],
            'pre_tool_call': [
                (r'AgentExecutor', 'agent_executor'),
                (r'Tool\s*\(', 'tool_definition'),
            ],
            'post_result': [
                (r'return\s+.*result', 'return_result'),
            ],
        }

        self._search_patterns(result, files, patterns)

    def _find_generic_integration_points(self, result: ScanResult, files: list) -> None:
        """查找通用Python项目的集成点"""
        patterns = {
            'pre_prompt': [
                (r'def\s+(process|handle|chat|send)\s*\(', 'handler_method'),
                (r'input\s*\(|stdin', 'user_input'),
            ],
            'post_result': [
                (r'return\s+', 'return_statement'),
                (r'print\s*\(', 'print_output'),
            ],
        }

        self._search_patterns(result, files, patterns)

    def _search_patterns(self, result: ScanResult, files: list, patterns: dict) -> None:
        """在文件中搜索模式"""
        for py_file in files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    content = ''.join(lines)

                    for point_type, pattern_list in patterns.items():
                        for pattern, desc in pattern_list:
                            for match in re.finditer(pattern, content):
                                # 计算行号
                                line_num = content[:match.start()].count('\n') + 1
                                # 提取代码片段
                                snippet_start = max(0, line_num - 2)
                                snippet_end = min(len(lines), line_num + 2)
                                snippet = ''.join(lines[snippet_start:snippet_end])

                                result.integration_points.append(IntegrationPoint(
                                    file_path=str(py_file),
                                    line_number=line_num,
                                    point_type=point_type,
                                    code_snippet=snippet.strip(),
                                    confidence=0.8 if 'generic' not in desc else 0.5
                                ))
            except (UnicodeDecodeError, PermissionError):
                continue

    def _detect_async_pattern(self, result: ScanResult) -> None:
        """检测项目是否使用异步模式"""
        all_python_files = list(self.project_path.rglob("*.py"))

        for py_file in all_python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if re.search(r'async\s+def|await\s+|asyncio|aiohttp', content):
                        result.has_async = True
                        return
            except (UnicodeDecodeError, PermissionError):
                continue


def scan_project(project_path: str) -> ScanResult:
    """便捷函数：扫描项目"""
    scanner = ProjectScanner(project_path)
    return scanner.scan()
