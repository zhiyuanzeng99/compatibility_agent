"""
Metrics - 监控指标收集

收集和管理系统运行指标
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum
import time
import threading
from collections import defaultdict


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"          # 计数器（只增不减）
    GAUGE = "gauge"              # 仪表盘（可增可减）
    HISTOGRAM = "histogram"      # 直方图（分布统计）
    SUMMARY = "summary"          # 摘要（百分位统计）


@dataclass
class MetricLabel:
    """指标标签"""
    name: str
    value: str


@dataclass
class Metric:
    """指标定义"""
    name: str
    type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    unit: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "labels": self.labels,
            "unit": self.unit
        }


@dataclass
class MetricValue:
    """指标值"""
    metric_name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels
        }


class Counter:
    """计数器"""

    def __init__(self, name: str, description: str, labels: List[str] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, value: float = 1, **labels) -> None:
        """增加计数"""
        with self._lock:
            key = tuple(sorted(labels.items()))
            self._values[key] += value

    def get(self, **labels) -> float:
        """获取当前值"""
        key = tuple(sorted(labels.items()))
        return self._values.get(key, 0)

    def get_all(self) -> List[MetricValue]:
        """获取所有值"""
        result = []
        for key, value in self._values.items():
            labels = dict(key)
            result.append(MetricValue(
                metric_name=self.name,
                value=value,
                timestamp=datetime.now(),
                labels=labels
            ))
        return result


class Gauge:
    """仪表盘"""

    def __init__(self, name: str, description: str, labels: List[str] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def set(self, value: float, **labels) -> None:
        """设置值"""
        with self._lock:
            key = tuple(sorted(labels.items()))
            self._values[key] = value

    def inc(self, value: float = 1, **labels) -> None:
        """增加"""
        with self._lock:
            key = tuple(sorted(labels.items()))
            self._values[key] += value

    def dec(self, value: float = 1, **labels) -> None:
        """减少"""
        with self._lock:
            key = tuple(sorted(labels.items()))
            self._values[key] -= value

    def get(self, **labels) -> float:
        """获取当前值"""
        key = tuple(sorted(labels.items()))
        return self._values.get(key, 0)

    def get_all(self) -> List[MetricValue]:
        """获取所有值"""
        result = []
        for key, value in self._values.items():
            labels = dict(key)
            result.append(MetricValue(
                metric_name=self.name,
                value=value,
                timestamp=datetime.now(),
                labels=labels
            ))
        return result


class Histogram:
    """直方图"""

    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

    def __init__(
        self,
        name: str,
        description: str,
        labels: List[str] = None,
        buckets: List[float] = None
    ):
        self.name = name
        self.description = description
        self.labels = labels or []
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._counts: Dict[tuple, Dict[float, int]] = defaultdict(lambda: defaultdict(int))
        self._sums: Dict[tuple, float] = defaultdict(float)
        self._totals: Dict[tuple, int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float, **labels) -> None:
        """记录观测值"""
        with self._lock:
            key = tuple(sorted(labels.items()))
            self._sums[key] += value
            self._totals[key] += 1

            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1

    def get_percentile(self, percentile: float, **labels) -> float:
        """获取百分位值"""
        key = tuple(sorted(labels.items()))
        total = self._totals.get(key, 0)
        if total == 0:
            return 0

        target = total * percentile
        cumulative = 0

        for bucket in self.buckets:
            cumulative += self._counts[key].get(bucket, 0)
            if cumulative >= target:
                return bucket

        return self.buckets[-1]


class Summary:
    """摘要统计"""

    def __init__(
        self,
        name: str,
        description: str,
        labels: List[str] = None,
        max_samples: int = 1000
    ):
        self.name = name
        self.description = description
        self.labels = labels or []
        self.max_samples = max_samples
        self._samples: Dict[tuple, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def observe(self, value: float, **labels) -> None:
        """记录观测值"""
        with self._lock:
            key = tuple(sorted(labels.items()))
            samples = self._samples[key]
            samples.append(value)

            # 保持最大样本数
            if len(samples) > self.max_samples:
                self._samples[key] = samples[-self.max_samples:]

    def get_quantile(self, quantile: float, **labels) -> float:
        """获取分位数"""
        key = tuple(sorted(labels.items()))
        samples = sorted(self._samples.get(key, []))

        if not samples:
            return 0

        idx = int(len(samples) * quantile)
        return samples[min(idx, len(samples) - 1)]

    def get_stats(self, **labels) -> Dict[str, float]:
        """获取统计信息"""
        key = tuple(sorted(labels.items()))
        samples = self._samples.get(key, [])

        if not samples:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}

        return {
            "count": len(samples),
            "sum": sum(samples),
            "avg": sum(samples) / len(samples),
            "min": min(samples),
            "max": max(samples),
            "p50": self.get_quantile(0.5, **labels),
            "p90": self.get_quantile(0.9, **labels),
            "p99": self.get_quantile(0.99, **labels),
        }


class MetricsCollector:
    """
    指标收集器

    统一管理所有监控指标
    """

    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._summaries: Dict[str, Summary] = {}
        self._lock = threading.Lock()

        # 注册内置指标
        self._register_builtin_metrics()

    def _register_builtin_metrics(self):
        """注册内置指标"""
        # 请求相关
        self.register_counter(
            "safety_check_total",
            "安全检查总数",
            ["tool", "result"]
        )
        self.register_counter(
            "safety_check_blocked",
            "安全检查拦截数",
            ["tool", "reason"]
        )

        # 延迟相关
        self.register_histogram(
            "safety_check_latency_seconds",
            "安全检查延迟（秒）",
            ["tool"]
        )

        # 系统状态
        self.register_gauge(
            "active_connections",
            "活跃连接数",
            ["service"]
        )
        self.register_gauge(
            "tool_health_status",
            "工具健康状态",
            ["tool"]
        )

    def register_counter(
        self,
        name: str,
        description: str,
        labels: List[str] = None
    ) -> Counter:
        """注册计数器"""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, description, labels)
            return self._counters[name]

    def register_gauge(
        self,
        name: str,
        description: str,
        labels: List[str] = None
    ) -> Gauge:
        """注册仪表盘"""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, description, labels)
            return self._gauges[name]

    def register_histogram(
        self,
        name: str,
        description: str,
        labels: List[str] = None,
        buckets: List[float] = None
    ) -> Histogram:
        """注册直方图"""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, description, labels, buckets)
            return self._histograms[name]

    def register_summary(
        self,
        name: str,
        description: str,
        labels: List[str] = None
    ) -> Summary:
        """注册摘要"""
        with self._lock:
            if name not in self._summaries:
                self._summaries[name] = Summary(name, description, labels)
            return self._summaries[name]

    def counter(self, name: str) -> Optional[Counter]:
        """获取计数器"""
        return self._counters.get(name)

    def gauge(self, name: str) -> Optional[Gauge]:
        """获取仪表盘"""
        return self._gauges.get(name)

    def histogram(self, name: str) -> Optional[Histogram]:
        """获取直方图"""
        return self._histograms.get(name)

    def summary(self, name: str) -> Optional[Summary]:
        """获取摘要"""
        return self._summaries.get(name)

    def collect_all(self) -> Dict[str, Any]:
        """收集所有指标"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "counters": {},
            "gauges": {},
            "histograms": {},
            "summaries": {}
        }

        for name, counter in self._counters.items():
            result["counters"][name] = [v.to_dict() for v in counter.get_all()]

        for name, gauge in self._gauges.items():
            result["gauges"][name] = [v.to_dict() for v in gauge.get_all()]

        return result

    def export_prometheus(self) -> str:
        """导出 Prometheus 格式"""
        lines = []

        # 导出计数器
        for name, counter in self._counters.items():
            lines.append(f"# HELP {name} {counter.description}")
            lines.append(f"# TYPE {name} counter")
            for value in counter.get_all():
                labels_str = ",".join(f'{k}="{v}"' for k, v in value.labels.items())
                if labels_str:
                    lines.append(f"{name}{{{labels_str}}} {value.value}")
                else:
                    lines.append(f"{name} {value.value}")

        # 导出仪表盘
        for name, gauge in self._gauges.items():
            lines.append(f"# HELP {name} {gauge.description}")
            lines.append(f"# TYPE {name} gauge")
            for value in gauge.get_all():
                labels_str = ",".join(f'{k}="{v}"' for k, v in value.labels.items())
                if labels_str:
                    lines.append(f"{name}{{{labels_str}}} {value.value}")
                else:
                    lines.append(f"{name} {value.value}")

        return "\n".join(lines)


class Timer:
    """计时器上下文管理器"""

    def __init__(self, histogram: Histogram, **labels):
        self.histogram = histogram
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self.start_time
        self.histogram.observe(elapsed, **self.labels)


# 全局指标收集器实例
_default_collector = MetricsCollector()


def get_default_collector() -> MetricsCollector:
    """获取默认指标收集器"""
    return _default_collector
