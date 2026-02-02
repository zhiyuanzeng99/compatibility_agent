"""
监控模块测试
"""

import pytest
import asyncio
from datetime import datetime

from adapter_agent.monitoring import (
    MetricsCollector,
    Metric,
    MetricType,
    AlertManager,
    Alert,
    AlertLevel,
    AlertRule,
    HealthChecker,
    HealthStatus,
    Dashboard,
    DashboardBuilder,
    ChartType
)


class TestMetricsCollector:
    """指标收集器测试"""

    def test_counter(self):
        """测试计数器"""
        collector = MetricsCollector()
        counter = collector.register_counter("test_counter", "测试计数器", ["label1"])

        counter.inc(label1="a")
        counter.inc(label1="a")
        counter.inc(label1="b")

        assert counter.get(label1="a") == 2
        assert counter.get(label1="b") == 1

    def test_gauge(self):
        """测试仪表盘"""
        collector = MetricsCollector()
        gauge = collector.register_gauge("test_gauge", "测试仪表盘")

        gauge.set(100)
        assert gauge.get() == 100

        gauge.inc(10)
        assert gauge.get() == 110

        gauge.dec(30)
        assert gauge.get() == 80

    def test_histogram(self):
        """测试直方图"""
        collector = MetricsCollector()
        histogram = collector.register_histogram(
            "test_histogram",
            "测试直方图",
            buckets=[0.1, 0.5, 1.0, 5.0]
        )

        histogram.observe(0.05)
        histogram.observe(0.3)
        histogram.observe(0.8)
        histogram.observe(2.0)

        # P50 应该在 0.5 左右
        p50 = histogram.get_percentile(0.5)
        assert p50 <= 1.0

    def test_summary(self):
        """测试摘要"""
        collector = MetricsCollector()
        summary = collector.register_summary("test_summary", "测试摘要")

        for i in range(100):
            summary.observe(i)

        stats = summary.get_stats()
        assert stats["count"] == 100
        assert stats["avg"] == 49.5
        assert stats["min"] == 0
        assert stats["max"] == 99

    def test_prometheus_export(self):
        """测试 Prometheus 导出"""
        collector = MetricsCollector()
        counter = collector.register_counter("http_requests", "HTTP请求数", ["method"])

        counter.inc(method="GET")
        counter.inc(method="POST")

        output = collector.export_prometheus()
        assert "http_requests" in output


class TestAlertManager:
    """告警管理器测试"""

    def test_add_rule(self):
        """测试添加规则"""
        manager = AlertManager()
        rule = AlertRule(
            name="test_rule",
            condition="value > threshold",
            level=AlertLevel.WARNING,
            description="测试规则",
            threshold=100
        )

        manager.add_rule(rule)
        # 规则已添加

    def test_fire_alert(self):
        """测试触发告警"""
        manager = AlertManager()
        rule = AlertRule(
            name="high_error_rate",
            condition="error_rate > threshold",
            level=AlertLevel.ERROR,
            description="错误率过高",
            threshold=0.1,
            duration_seconds=0  # 立即触发
        )
        manager.add_rule(rule)

        # 模拟高错误率
        alert = manager.check_and_fire("high_error_rate", 0.2)
        # 第一次不会立即触发（需要持续时间）

    def test_alert_statistics(self):
        """测试告警统计"""
        manager = AlertManager()
        stats = manager.get_alert_statistics()

        assert "total" in stats
        assert "firing" in stats
        assert "resolved" in stats
        assert "by_level" in stats

    def test_silence(self):
        """测试静默"""
        manager = AlertManager()
        silence = manager.add_silence(
            matchers={"service": "test"},
            duration_hours=1,
            created_by="admin",
            comment="维护期间静默"
        )

        assert silence.id is not None


class TestHealthChecker:
    """健康检查器测试"""

    @pytest.fixture
    def checker(self):
        return HealthChecker()

    @pytest.mark.asyncio
    async def test_register_and_check(self, checker):
        """测试注册和检查"""
        async def mock_check():
            from adapter_agent.monitoring.health import ComponentHealth
            return ComponentHealth(
                name="test_service",
                status=HealthStatus.HEALTHY
            )

        checker.register_check("test_service", mock_check)

        result = await checker.check("test_service")
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_all(self, checker):
        """测试检查所有"""
        async def healthy_check():
            from adapter_agent.monitoring.health import ComponentHealth
            return ComponentHealth(name="healthy", status=HealthStatus.HEALTHY)

        async def unhealthy_check():
            from adapter_agent.monitoring.health import ComponentHealth
            return ComponentHealth(name="unhealthy", status=HealthStatus.UNHEALTHY)

        checker.register_check("service1", healthy_check)
        checker.register_check("service2", unhealthy_check)

        report = await checker.check_all()

        assert report.overall_status == HealthStatus.UNHEALTHY  # 有不健康组件
        assert len(report.components) == 2


class TestDashboard:
    """仪表盘测试"""

    def test_dashboard_builder(self):
        """测试仪表盘构建器"""
        builder = DashboardBuilder("test_dashboard", "测试仪表盘")

        dashboard = (builder
            .set_description("这是一个测试仪表盘")
            .set_refresh_interval(30)
            .add_stat_panel("请求数", "request_total", width=3)
            .add_line_chart("请求趋势", ["request_total", "error_total"], width=6)
            .add_pie_chart("错误分布", "error_total", group_by="type", width=3)
            .build()
        )

        assert dashboard.name == "测试仪表盘"
        assert len(dashboard.panels) == 3
        assert dashboard.refresh_interval_seconds == 30

    def test_dashboard_to_dict(self):
        """测试仪表盘序列化"""
        dashboard = Dashboard(
            id="test",
            name="Test Dashboard",
            description="Test"
        )

        data = dashboard.to_dict()
        assert data["id"] == "test"
        assert data["name"] == "Test Dashboard"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
