"""
Dashboard - 可视化仪表盘

提供监控数据的可视化展示
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum


class ChartType(Enum):
    """图表类型"""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    GAUGE = "gauge"
    TABLE = "table"
    STAT = "stat"
    HEATMAP = "heatmap"


@dataclass
class TimeRange:
    """时间范围"""
    start: datetime
    end: datetime

    @classmethod
    def last_minutes(cls, minutes: int) -> "TimeRange":
        end = datetime.now()
        start = end - timedelta(minutes=minutes)
        return cls(start=start, end=end)

    @classmethod
    def last_hours(cls, hours: int) -> "TimeRange":
        end = datetime.now()
        start = end - timedelta(hours=hours)
        return cls(start=start, end=end)

    @classmethod
    def last_days(cls, days: int) -> "TimeRange":
        end = datetime.now()
        start = end - timedelta(days=days)
        return cls(start=start, end=end)


@dataclass
class DataQuery:
    """数据查询"""
    metric_name: str
    aggregation: str = "avg"     # avg, sum, min, max, count
    group_by: List[str] = field(default_factory=list)
    filters: Dict[str, str] = field(default_factory=dict)


@dataclass
class DashboardPanel:
    """仪表盘面板"""
    id: str
    title: str
    chart_type: ChartType
    queries: List[DataQuery]
    width: int = 6              # 1-12 栅格宽度
    height: int = 4             # 高度单位
    position: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "chart_type": self.chart_type.value,
            "queries": [
                {
                    "metric_name": q.metric_name,
                    "aggregation": q.aggregation,
                    "group_by": q.group_by,
                    "filters": q.filters
                }
                for q in self.queries
            ],
            "width": self.width,
            "height": self.height,
            "position": self.position,
            "options": self.options
        }


@dataclass
class Dashboard:
    """仪表盘"""
    id: str
    name: str
    description: str = ""
    panels: List[DashboardPanel] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    refresh_interval_seconds: int = 30
    time_range: TimeRange = field(default_factory=lambda: TimeRange.last_hours(1))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "panels": [p.to_dict() for p in self.panels],
            "variables": self.variables,
            "refresh_interval_seconds": self.refresh_interval_seconds,
            "time_range": {
                "start": self.time_range.start.isoformat(),
                "end": self.time_range.end.isoformat()
            }
        }

    def add_panel(self, panel: DashboardPanel) -> None:
        """添加面板"""
        self.panels.append(panel)

    def remove_panel(self, panel_id: str) -> None:
        """移除面板"""
        self.panels = [p for p in self.panels if p.id != panel_id]


class DashboardBuilder:
    """仪表盘构建器"""

    def __init__(self, dashboard_id: str, name: str):
        self._dashboard = Dashboard(id=dashboard_id, name=name)
        self._panel_counter = 0
        self._current_row = 0
        self._current_col = 0

    def set_description(self, description: str) -> "DashboardBuilder":
        """设置描述"""
        self._dashboard.description = description
        return self

    def set_refresh_interval(self, seconds: int) -> "DashboardBuilder":
        """设置刷新间隔"""
        self._dashboard.refresh_interval_seconds = seconds
        return self

    def set_time_range(self, time_range: TimeRange) -> "DashboardBuilder":
        """设置时间范围"""
        self._dashboard.time_range = time_range
        return self

    def add_variable(self, name: str, value: Any) -> "DashboardBuilder":
        """添加变量"""
        self._dashboard.variables[name] = value
        return self

    def add_stat_panel(
        self,
        title: str,
        metric_name: str,
        aggregation: str = "avg",
        width: int = 3,
        **options
    ) -> "DashboardBuilder":
        """添加统计面板"""
        panel = self._create_panel(
            title=title,
            chart_type=ChartType.STAT,
            queries=[DataQuery(metric_name=metric_name, aggregation=aggregation)],
            width=width,
            height=2,
            options=options
        )
        self._dashboard.add_panel(panel)
        return self

    def add_line_chart(
        self,
        title: str,
        metrics: List[str],
        aggregation: str = "avg",
        group_by: List[str] = None,
        width: int = 6,
        height: int = 4,
        **options
    ) -> "DashboardBuilder":
        """添加折线图"""
        queries = [
            DataQuery(
                metric_name=m,
                aggregation=aggregation,
                group_by=group_by or []
            )
            for m in metrics
        ]
        panel = self._create_panel(
            title=title,
            chart_type=ChartType.LINE,
            queries=queries,
            width=width,
            height=height,
            options=options
        )
        self._dashboard.add_panel(panel)
        return self

    def add_bar_chart(
        self,
        title: str,
        metric_name: str,
        group_by: List[str],
        aggregation: str = "sum",
        width: int = 6,
        height: int = 4,
        **options
    ) -> "DashboardBuilder":
        """添加柱状图"""
        panel = self._create_panel(
            title=title,
            chart_type=ChartType.BAR,
            queries=[DataQuery(
                metric_name=metric_name,
                aggregation=aggregation,
                group_by=group_by
            )],
            width=width,
            height=height,
            options=options
        )
        self._dashboard.add_panel(panel)
        return self

    def add_pie_chart(
        self,
        title: str,
        metric_name: str,
        group_by: str,
        width: int = 4,
        height: int = 4,
        **options
    ) -> "DashboardBuilder":
        """添加饼图"""
        panel = self._create_panel(
            title=title,
            chart_type=ChartType.PIE,
            queries=[DataQuery(
                metric_name=metric_name,
                aggregation="sum",
                group_by=[group_by]
            )],
            width=width,
            height=height,
            options=options
        )
        self._dashboard.add_panel(panel)
        return self

    def add_gauge_panel(
        self,
        title: str,
        metric_name: str,
        min_value: float = 0,
        max_value: float = 100,
        thresholds: List[Dict] = None,
        width: int = 3,
        **options
    ) -> "DashboardBuilder":
        """添加仪表盘面板"""
        options.update({
            "min": min_value,
            "max": max_value,
            "thresholds": thresholds or []
        })
        panel = self._create_panel(
            title=title,
            chart_type=ChartType.GAUGE,
            queries=[DataQuery(metric_name=metric_name, aggregation="last")],
            width=width,
            height=3,
            options=options
        )
        self._dashboard.add_panel(panel)
        return self

    def add_table(
        self,
        title: str,
        metrics: List[str],
        group_by: List[str] = None,
        width: int = 12,
        height: int = 4,
        **options
    ) -> "DashboardBuilder":
        """添加表格"""
        queries = [
            DataQuery(metric_name=m, aggregation="last", group_by=group_by or [])
            for m in metrics
        ]
        panel = self._create_panel(
            title=title,
            chart_type=ChartType.TABLE,
            queries=queries,
            width=width,
            height=height,
            options=options
        )
        self._dashboard.add_panel(panel)
        return self

    def new_row(self) -> "DashboardBuilder":
        """开始新行"""
        self._current_row += 1
        self._current_col = 0
        return self

    def _create_panel(
        self,
        title: str,
        chart_type: ChartType,
        queries: List[DataQuery],
        width: int,
        height: int,
        options: Dict
    ) -> DashboardPanel:
        """创建面板"""
        self._panel_counter += 1

        # 自动布局
        if self._current_col + width > 12:
            self._current_row += 1
            self._current_col = 0

        panel = DashboardPanel(
            id=f"panel_{self._panel_counter}",
            title=title,
            chart_type=chart_type,
            queries=queries,
            width=width,
            height=height,
            position={"x": self._current_col, "y": self._current_row * 4},
            options=options
        )

        self._current_col += width
        return panel

    def build(self) -> Dashboard:
        """构建仪表盘"""
        return self._dashboard


def create_safety_monitoring_dashboard() -> Dashboard:
    """创建安全监控仪表盘"""
    builder = DashboardBuilder("safety_monitoring", "安全监控仪表盘")

    return (builder
        .set_description("AI 安全工具运行状态监控")
        .set_refresh_interval(30)

        # 第一行：关键指标
        .add_stat_panel("安全检查总数", "safety_check_total", "sum", width=3)
        .add_stat_panel("拦截数", "safety_check_blocked", "sum", width=3)
        .add_stat_panel("平均延迟", "safety_check_latency_seconds", "avg", width=3)
        .add_gauge_panel(
            "服务健康度",
            "tool_health_status",
            max_value=1,
            thresholds=[
                {"value": 0.5, "color": "red"},
                {"value": 0.8, "color": "yellow"},
                {"value": 1, "color": "green"}
            ],
            width=3
        )

        .new_row()

        # 第二行：趋势图
        .add_line_chart(
            "安全检查趋势",
            ["safety_check_total", "safety_check_blocked"],
            group_by=["tool"],
            width=8
        )
        .add_pie_chart(
            "拦截原因分布",
            "safety_check_blocked",
            group_by="reason",
            width=4
        )

        .new_row()

        # 第三行：延迟分布
        .add_line_chart(
            "延迟分布（P50/P90/P99）",
            ["safety_check_latency_p50", "safety_check_latency_p90", "safety_check_latency_p99"],
            width=6
        )
        .add_bar_chart(
            "各工具检查量",
            "safety_check_total",
            group_by=["tool"],
            width=6
        )

        .build()
    )


def create_system_overview_dashboard() -> Dashboard:
    """创建系统概览仪表盘"""
    builder = DashboardBuilder("system_overview", "系统概览")

    return (builder
        .set_description("GuardAdapter 系统整体运行状态")
        .set_refresh_interval(60)

        # 系统状态
        .add_stat_panel("活跃连接数", "active_connections", "sum", width=3)
        .add_stat_panel("QPS", "request_rate", "avg", width=3)
        .add_stat_panel("错误率", "error_rate", "avg", width=3)
        .add_stat_panel("CPU 使用率", "cpu_usage", "avg", width=3)

        .new_row()

        # 请求趋势
        .add_line_chart(
            "请求趋势",
            ["request_total", "request_success", "request_failed"],
            width=12
        )

        .new_row()

        # 各服务状态
        .add_table(
            "服务状态",
            ["service_health", "service_latency", "service_error_rate"],
            group_by=["service_name"],
            width=12
        )

        .build()
    )
