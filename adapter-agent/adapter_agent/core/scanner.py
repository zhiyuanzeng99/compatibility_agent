"""
Scanner Module - 项目扫描分析器（完整版）

功能：
- 自动识别目标 AI 应用的技术栈和架构
- 支持多种框架检测
- 数据流分析
- 安全需求推断
"""

import os
import re
import ast
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum


class FrameworkType(Enum):
    """支持的框架类型"""
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"
    HAYSTACK = "haystack"
    AUTOGEN = "autogen"
    CREWAI = "crewai"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class LLMProvider(Enum):
    """LLM 提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    VERTEXAI = "vertexai"
    AZURE = "azure"
    BEDROCK = "bedrock"
    LOCAL = "local"
    UNKNOWN = "unknown"


class DeploymentType(Enum):
    """部署方式"""
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    SERVERLESS = "serverless"
    BARE_METAL = "bare_metal"
    UNKNOWN = "unknown"


class CloudProvider(Enum):
    """云服务商"""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ALIYUN = "aliyun"
    ON_PREMISE = "on_premise"
    UNKNOWN = "unknown"


class IntegrationType(Enum):
    """集成方式"""
    SDK = "sdk"           # 白盒集成
    PROXY = "proxy"       # 黑盒集成（代理网关）
    MIDDLEWARE = "middleware"  # 中间件


@dataclass
class EntryPoint:
    """API 入口点"""
    file_path: str
    function_name: str
    http_method: Optional[str] = None
    route: Optional[str] = None
    is_async: bool = False


@dataclass
class DataFlow:
    """数据流信息"""
    input_sources: list[str] = field(default_factory=list)
    output_destinations: list[str] = field(default_factory=list)
    intermediate_stores: list[str] = field(default_factory=list)
    external_apis: list[str] = field(default_factory=list)


@dataclass
class SecurityRequirement:
    """安全需求"""
    category: str  # content_safety, pii, prompt_injection, tool_security
    priority: str  # high, medium, low
    description: str
    recommended_tools: list[str] = field(default_factory=list)


@dataclass
class ProjectProfile:
    """项目扫描结果 - 完整版"""
    # 基础信息
    project_path: str
    project_name: str

    # 技术栈
    framework: FrameworkType = FrameworkType.UNKNOWN
    framework_version: Optional[str] = None
    llm_provider: LLMProvider = LLMProvider.UNKNOWN
    language: str = "python"
    python_version: Optional[str] = None

    # 部署信息
    deployment: DeploymentType = DeploymentType.UNKNOWN
    cloud_provider: CloudProvider = CloudProvider.UNKNOWN

    # 已有安全工具
    existing_guardrails: list[str] = field(default_factory=list)

    # 入口点和数据流
    entry_points: list[EntryPoint] = field(default_factory=list)
    data_flow: Optional[DataFlow] = None

    # 依赖
    dependencies: dict[str, str] = field(default_factory=dict)

    # 推断的安全需求
    security_requirements: list[SecurityRequirement] = field(default_factory=list)

    # 集成方式建议
    recommended_integration: IntegrationType = IntegrationType.SDK

    # 是否异步
    has_async: bool = False

    # 扫描元数据
    scan_errors: list[str] = field(default_factory=list)
    scan_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "project_path": self.project_path,
            "project_name": self.project_name,
            "framework": self.framework.value,
            "framework_version": self.framework_version,
            "llm_provider": self.llm_provider.value,
            "language": self.language,
            "python_version": self.python_version,
            "deployment": self.deployment.value,
            "cloud_provider": self.cloud_provider.value,
            "existing_guardrails": self.existing_guardrails,
            "entry_points": [
                {
                    "file": ep.file_path,
                    "function": ep.function_name,
                    "method": ep.http_method,
                    "route": ep.route,
                    "async": ep.is_async
                }
                for ep in self.entry_points
            ],
            "dependencies": self.dependencies,
            "security_requirements": [
                {
                    "category": sr.category,
                    "priority": sr.priority,
                    "description": sr.description,
                    "recommended_tools": sr.recommended_tools
                }
                for sr in self.security_requirements
            ],
            "recommended_integration": self.recommended_integration.value,
            "has_async": self.has_async,
        }


class ProjectScanner:
    """
    项目扫描器 - 完整版

    检测策略:
    1. package.json / requirements.txt 依赖分析
    2. import 语句静态分析
    3. 配置文件识别 (yaml/json/toml)
    4. Dockerfile / K8s manifest 分析
    5. API 端点扫描
    6. 环境变量检测
    """

    # 框架检测模式
    FRAMEWORK_PATTERNS = {
        FrameworkType.LANGCHAIN: [
            r'from\s+langchain',
            r'import\s+langchain',
            r'LLMChain',
            r'ChatOpenAI',
            r'AgentExecutor',
            r'ConversationChain',
        ],
        FrameworkType.LLAMAINDEX: [
            r'from\s+llama_index',
            r'import\s+llama_index',
            r'VectorStoreIndex',
            r'ServiceContext',
            r'QueryEngine',
        ],
        FrameworkType.HAYSTACK: [
            r'from\s+haystack',
            r'import\s+haystack',
            r'Pipeline',
            r'DocumentStore',
        ],
        FrameworkType.AUTOGEN: [
            r'from\s+autogen',
            r'import\s+autogen',
            r'AssistantAgent',
            r'UserProxyAgent',
        ],
        FrameworkType.CREWAI: [
            r'from\s+crewai',
            r'import\s+crewai',
            r'Agent',
            r'Crew',
            r'Task',
        ],
    }

    # LLM 提供商检测模式
    LLM_PATTERNS = {
        LLMProvider.OPENAI: [
            r'from\s+openai',
            r'import\s+openai',
            r'OPENAI_API_KEY',
            r'ChatOpenAI',
            r'OpenAI\(',
        ],
        LLMProvider.ANTHROPIC: [
            r'from\s+anthropic',
            r'import\s+anthropic',
            r'ANTHROPIC_API_KEY',
            r'ChatAnthropic',
            r'Claude',
        ],
        LLMProvider.VERTEXAI: [
            r'from\s+vertexai',
            r'import\s+vertexai',
            r'ChatVertexAI',
            r'GOOGLE_APPLICATION_CREDENTIALS',
        ],
        LLMProvider.AZURE: [
            r'AzureOpenAI',
            r'AZURE_OPENAI',
            r'azure\.ai',
        ],
        LLMProvider.BEDROCK: [
            r'bedrock',
            r'AWS_BEDROCK',
            r'BedrockChat',
        ],
    }

    # 安全工具检测模式
    GUARDRAIL_PATTERNS = {
        "openguardrails": [r'openguardrails', r'OpenGuardrails'],
        "nemo_guardrails": [r'nemoguardrails', r'NeMo.*Guardrails', r'LLMRails'],
        "llama_guard": [r'llama_guard', r'LlamaGuard'],
        "guardrails_ai": [r'guardrails', r'Guardrails\(', r'Guard\.from_rail'],
        "llama_firewall": [r'llama_firewall', r'LlamaFirewall'],
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        if not self.project_path.exists():
            raise ValueError(f"项目路径不存在: {project_path}")
        self.profile = ProjectProfile(
            project_path=str(self.project_path),
            project_name=self.project_path.name
        )

    def scan(self) -> ProjectProfile:
        """执行完整扫描"""
        # 1. 扫描依赖
        self._scan_dependencies()

        # 2. 识别框架
        self._detect_framework()

        # 3. 识别 LLM 提供商
        self._detect_llm_provider()

        # 4. 检测已有安全工具
        self._detect_existing_guardrails()

        # 5. 扫描部署配置
        self._detect_deployment()

        # 6. 查找 API 入口点
        self._find_entry_points()

        # 7. 分析数据流
        self._analyze_data_flow()

        # 8. 推断安全需求
        self._infer_security_requirements()

        # 9. 推荐集成方式
        self._recommend_integration_type()

        # 10. 检测异步模式
        self._detect_async_pattern()

        return self.profile

    def _scan_dependencies(self) -> None:
        """扫描项目依赖"""
        # requirements.txt
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            self._parse_requirements(req_file)

        # pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            self._parse_pyproject(pyproject)

        # setup.py
        setup_py = self.project_path / "setup.py"
        if setup_py.exists():
            self._parse_setup_py(setup_py)

        # package.json (Node.js)
        package_json = self.project_path / "package.json"
        if package_json.exists():
            self._parse_package_json(package_json)

    def _parse_requirements(self, file_path: Path) -> None:
        """解析 requirements.txt"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # 解析包名和版本
                        match = re.match(r'^([a-zA-Z0-9_-]+)([<>=!~]+.*)?$', line)
                        if match:
                            pkg_name = match.group(1)
                            version = match.group(2) or ""
                            self.profile.dependencies[pkg_name] = version
        except Exception as e:
            self.profile.scan_errors.append(f"解析 requirements.txt 失败: {e}")

    def _parse_pyproject(self, file_path: Path) -> None:
        """解析 pyproject.toml"""
        try:
            import tomllib
            with open(file_path, 'rb') as f:
                data = tomllib.load(f)

            # 获取依赖
            deps = data.get('project', {}).get('dependencies', [])
            for dep in deps:
                match = re.match(r'^([a-zA-Z0-9_-]+)([<>=!~\[]+.*)?$', dep)
                if match:
                    self.profile.dependencies[match.group(1)] = match.group(2) or ""

            # 获取 Python 版本
            py_version = data.get('project', {}).get('requires-python', '')
            if py_version:
                self.profile.python_version = py_version

        except ImportError:
            # Python < 3.11 没有 tomllib
            self.profile.scan_warnings.append("tomllib 不可用，跳过 pyproject.toml 解析")
        except Exception as e:
            self.profile.scan_errors.append(f"解析 pyproject.toml 失败: {e}")

    def _parse_setup_py(self, file_path: Path) -> None:
        """解析 setup.py"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 简单提取 install_requires
                deps = re.findall(r"['\"]([^'\"]+)['\"]", content)
                for dep in deps:
                    if any(c in dep for c in ['>=', '<=', '==', '~=']):
                        match = re.match(r'^([a-zA-Z0-9_-]+)', dep)
                        if match:
                            self.profile.dependencies[match.group(1)] = ""
        except Exception as e:
            self.profile.scan_errors.append(f"解析 setup.py 失败: {e}")

    def _parse_package_json(self, file_path: Path) -> None:
        """解析 package.json"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                deps = data.get('dependencies', {})
                deps.update(data.get('devDependencies', {}))
                for pkg, version in deps.items():
                    self.profile.dependencies[pkg] = version
                self.profile.language = "javascript"
        except Exception as e:
            self.profile.scan_errors.append(f"解析 package.json 失败: {e}")

    def _detect_framework(self) -> None:
        """检测使用的框架"""
        all_python_files = list(self.project_path.rglob("*.py"))
        scores = {ft: 0 for ft in FrameworkType if ft != FrameworkType.UNKNOWN}

        for py_file in all_python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for framework, patterns in self.FRAMEWORK_PATTERNS.items():
                        for pattern in patterns:
                            if re.search(pattern, content):
                                scores[framework] += 1
            except (UnicodeDecodeError, PermissionError):
                continue

        # 选择得分最高的
        if max(scores.values()) > 0:
            self.profile.framework = max(scores, key=scores.get)
        elif all_python_files:
            self.profile.framework = FrameworkType.CUSTOM

        # 尝试获取版本
        framework_pkg = {
            FrameworkType.LANGCHAIN: "langchain",
            FrameworkType.LLAMAINDEX: "llama-index",
            FrameworkType.HAYSTACK: "haystack-ai",
            FrameworkType.AUTOGEN: "pyautogen",
            FrameworkType.CREWAI: "crewai",
        }
        if self.profile.framework in framework_pkg:
            pkg = framework_pkg[self.profile.framework]
            if pkg in self.profile.dependencies:
                self.profile.framework_version = self.profile.dependencies[pkg]

    def _detect_llm_provider(self) -> None:
        """检测 LLM 提供商"""
        all_files = list(self.project_path.rglob("*.py"))
        all_files.extend(self.project_path.rglob("*.env*"))
        all_files.extend(self.project_path.rglob("*.yaml"))
        all_files.extend(self.project_path.rglob("*.yml"))

        scores = {llm: 0 for llm in LLMProvider if llm != LLMProvider.UNKNOWN}

        for file_path in all_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for provider, patterns in self.LLM_PATTERNS.items():
                        for pattern in patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                scores[provider] += 1
            except (UnicodeDecodeError, PermissionError):
                continue

        if max(scores.values()) > 0:
            self.profile.llm_provider = max(scores, key=scores.get)

    def _detect_existing_guardrails(self) -> None:
        """检测已有的安全工具"""
        all_python_files = list(self.project_path.rglob("*.py"))

        for py_file in all_python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for tool, patterns in self.GUARDRAIL_PATTERNS.items():
                        for pattern in patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                if tool not in self.profile.existing_guardrails:
                                    self.profile.existing_guardrails.append(tool)
                                break
            except (UnicodeDecodeError, PermissionError):
                continue

    def _detect_deployment(self) -> None:
        """检测部署方式"""
        # Dockerfile
        if (self.project_path / "Dockerfile").exists():
            self.profile.deployment = DeploymentType.DOCKER

        # docker-compose
        if (self.project_path / "docker-compose.yml").exists() or \
           (self.project_path / "docker-compose.yaml").exists():
            self.profile.deployment = DeploymentType.DOCKER

        # Kubernetes
        k8s_files = list(self.project_path.rglob("*deployment*.yaml"))
        k8s_files.extend(self.project_path.rglob("*deployment*.yml"))
        if k8s_files or (self.project_path / "k8s").exists():
            self.profile.deployment = DeploymentType.KUBERNETES

        # Serverless
        if (self.project_path / "serverless.yml").exists() or \
           (self.project_path / "serverless.yaml").exists() or \
           (self.project_path / "template.yaml").exists():  # SAM
            self.profile.deployment = DeploymentType.SERVERLESS

        # 检测云提供商
        self._detect_cloud_provider()

    def _detect_cloud_provider(self) -> None:
        """检测云服务商"""
        all_files = list(self.project_path.rglob("*.py"))
        all_files.extend(self.project_path.rglob("*.yaml"))
        all_files.extend(self.project_path.rglob("*.yml"))
        all_files.extend(self.project_path.rglob("*.json"))

        for file_path in all_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                    if 'aws' in content or 'boto3' in content or 's3://' in content:
                        self.profile.cloud_provider = CloudProvider.AWS
                        return
                    if 'azure' in content or 'azure.core' in content:
                        self.profile.cloud_provider = CloudProvider.AZURE
                        return
                    if 'google.cloud' in content or 'gcp' in content or 'gs://' in content:
                        self.profile.cloud_provider = CloudProvider.GCP
                        return
                    if 'aliyun' in content or 'alibabacloud' in content or 'oss://' in content:
                        self.profile.cloud_provider = CloudProvider.ALIYUN
                        return
            except (UnicodeDecodeError, PermissionError):
                continue

    def _find_entry_points(self) -> None:
        """查找 API 入口点"""
        all_python_files = list(self.project_path.rglob("*.py"))

        # FastAPI / Flask 路由模式
        route_patterns = [
            # FastAPI
            (r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', 'fastapi'),
            (r'@router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', 'fastapi'),
            # Flask
            (r'@app\.route\s*\(\s*["\']([^"\']+)["\']', 'flask'),
            (r'@blueprint\.route\s*\(\s*["\']([^"\']+)["\']', 'flask'),
        ]

        for py_file in all_python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                    for i, line in enumerate(lines):
                        for pattern, framework in route_patterns:
                            match = re.search(pattern, line)
                            if match:
                                # 查找下一个函数定义
                                for j in range(i + 1, min(i + 5, len(lines))):
                                    func_match = re.search(r'(async\s+)?def\s+(\w+)', lines[j])
                                    if func_match:
                                        is_async = func_match.group(1) is not None
                                        func_name = func_match.group(2)

                                        if framework == 'fastapi':
                                            http_method = match.group(1).upper()
                                            route = match.group(2)
                                        else:
                                            http_method = "GET"
                                            route = match.group(1)

                                        self.profile.entry_points.append(EntryPoint(
                                            file_path=str(py_file),
                                            function_name=func_name,
                                            http_method=http_method,
                                            route=route,
                                            is_async=is_async
                                        ))
                                        break
            except (UnicodeDecodeError, PermissionError):
                continue

    def _analyze_data_flow(self) -> None:
        """分析数据流"""
        data_flow = DataFlow()
        all_python_files = list(self.project_path.rglob("*.py"))

        for py_file in all_python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                    # 检测外部 API 调用
                    if re.search(r'requests\.(get|post|put|delete)', content):
                        data_flow.external_apis.append("HTTP requests")
                    if re.search(r'aiohttp|httpx', content):
                        data_flow.external_apis.append("Async HTTP")

                    # 检测数据存储
                    if re.search(r'sqlite|postgresql|mysql|mongodb', content, re.IGNORECASE):
                        data_flow.intermediate_stores.append("Database")
                    if re.search(r'redis', content, re.IGNORECASE):
                        data_flow.intermediate_stores.append("Redis")
                    if re.search(r'chromadb|pinecone|milvus|weaviate', content, re.IGNORECASE):
                        data_flow.intermediate_stores.append("Vector DB")

                    # 检测输入源
                    if re.search(r'stdin|input\(', content):
                        data_flow.input_sources.append("Console")
                    if re.search(r'request\.(json|form|body)', content):
                        data_flow.input_sources.append("HTTP Request")
                    if re.search(r'open\(|read_file|load', content):
                        data_flow.input_sources.append("File")

            except (UnicodeDecodeError, PermissionError):
                continue

        self.profile.data_flow = data_flow

    def _infer_security_requirements(self) -> None:
        """推断安全需求"""
        requirements = []

        # 基于框架推断
        if self.profile.framework in [FrameworkType.LANGCHAIN, FrameworkType.LLAMAINDEX]:
            requirements.append(SecurityRequirement(
                category="prompt_injection",
                priority="high",
                description="LLM 框架需要防护 Prompt Injection 攻击",
                recommended_tools=["openguardrails", "llama_firewall", "nemo_guardrails"]
            ))

        # 基于 LLM 提供商推断
        if self.profile.llm_provider != LLMProvider.UNKNOWN:
            requirements.append(SecurityRequirement(
                category="content_safety",
                priority="high",
                description="需要内容安全检测，防止有害输出",
                recommended_tools=["openguardrails", "llama_guard"]
            ))

        # 如果有外部 API 调用
        if self.profile.data_flow and self.profile.data_flow.external_apis:
            requirements.append(SecurityRequirement(
                category="tool_security",
                priority="high",
                description="存在外部 API 调用，需要工具调用安全检查",
                recommended_tools=["llama_firewall", "guardrails_ai"]
            ))

        # 如果有数据存储
        if self.profile.data_flow and self.profile.data_flow.intermediate_stores:
            requirements.append(SecurityRequirement(
                category="pii",
                priority="medium",
                description="存在数据存储，需要 PII 检测和脱敏",
                recommended_tools=["openguardrails", "nemo_guardrails"]
            ))

        # 默认添加基础安全需求
        if not requirements:
            requirements.append(SecurityRequirement(
                category="content_safety",
                priority="medium",
                description="基础内容安全防护",
                recommended_tools=["openguardrails"]
            ))

        self.profile.security_requirements = requirements

    def _recommend_integration_type(self) -> None:
        """推荐集成方式"""
        # 如果是已知框架，推荐 SDK 集成
        if self.profile.framework not in [FrameworkType.UNKNOWN, FrameworkType.CUSTOM]:
            self.profile.recommended_integration = IntegrationType.SDK

        # 如果有 API 入口点，可以用中间件
        elif self.profile.entry_points:
            self.profile.recommended_integration = IntegrationType.MIDDLEWARE

        # 否则建议代理方式
        else:
            self.profile.recommended_integration = IntegrationType.PROXY

    def _detect_async_pattern(self) -> None:
        """检测异步模式"""
        all_python_files = list(self.project_path.rglob("*.py"))

        for py_file in all_python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if re.search(r'async\s+def|await\s+|asyncio|aiohttp', content):
                        self.profile.has_async = True
                        return
            except (UnicodeDecodeError, PermissionError):
                continue


def scan_project(project_path: str) -> ProjectProfile:
    """便捷函数：扫描项目"""
    scanner = ProjectScanner(project_path)
    return scanner.scan()
