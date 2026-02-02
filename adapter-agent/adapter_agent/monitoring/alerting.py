"""
Alerting - 智能告警系统

基于规则和阈值的告警管理
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from enum import Enum
import threading
import asyncio


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertState(Enum):
    """告警状态"""
    FIRING = "firing"       # 触发中
    RESOLVED = "resolved"   # 已解决
    SILENCED = "silenced"   # 已静默


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    condition: str                    # 告警条件表达式
    level: AlertLevel
    description: str
    threshold: float
    duration_seconds: int = 60        # 持续时间阈值
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "condition": self.condition,
            "level": self.level.value,
            "description": self.description,
            "threshold": self.threshold,
            "duration_seconds": self.duration_seconds,
            "labels": self.labels,
            "annotations": self.annotations
        }


@dataclass
class Alert:
    """告警实例"""
    id: str
    rule_name: str
    level: AlertLevel
    state: AlertState
    message: str
    value: float
    threshold: float
    started_at: datetime
    resolved_at: Optional[datetime] = None
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "level": self.level.value,
            "state": self.state.value,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "started_at": self.started_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "labels": self.labels,
            "annotations": self.annotations
        }

    @property
    def duration(self) -> timedelta:
        """告警持续时间"""
        end_time = self.resolved_at or datetime.now()
        return end_time - self.started_at


@dataclass
class SilenceRule:
    """静默规则"""
    id: str
    matchers: Dict[str, str]     # 匹配条件
    starts_at: datetime
    ends_at: datetime
    created_by: str
    comment: str


class AlertManager:
    """
    告警管理器

    管理告警规则、触发和通知
    """

    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._silences: Dict[str, SilenceRule] = {}
        self._handlers: List[Callable[[Alert], None]] = []
        self._pending_alerts: Dict[str, datetime] = {}  # 待确认的告警
        self._lock = threading.Lock()
        self._alert_counter = 0

        # 注册内置规则
        self._register_builtin_rules()

    def _register_builtin_rules(self):
        """注册内置告警规则"""
        # 安全检查失败率过高
        self.add_rule(AlertRule(
            name="high_safety_block_rate",
            condition="safety_check_blocked / safety_check_total > threshold",
            level=AlertLevel.WARNING,
            description="安全检查拦截率过高",
            threshold=0.1,
            duration_seconds=300
        ))

        # 安全检查延迟过高
        self.add_rule(AlertRule(
            name="high_safety_check_latency",
            condition="safety_check_latency_p99 > threshold",
            level=AlertLevel.WARNING,
            description="安全检查延迟过高（P99）",
            threshold=1.0,
            duration_seconds=60
        ))

        # 安全工具不可用
        self.add_rule(AlertRule(
            name="safety_tool_unavailable",
            condition="tool_health_status == 0",
            level=AlertLevel.CRITICAL,
            description="安全工具不可用",
            threshold=0,
            duration_seconds=30
        ))

    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则"""
        with self._lock:
            self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> None:
        """移除告警规则"""
        with self._lock:
            self._rules.pop(name, None)

    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """添加告警处理器"""
        self._handlers.append(handler)

    def check_and_fire(
        self,
        rule_name: str,
        current_value: float,
        labels: Dict[str, str] = None
    ) -> Optional[Alert]:
        """
        检查规则并触发告警

        Args:
            rule_name: 规则名称
            current_value: 当前值
            labels: 标签

        Returns:
            触发的告警（如果有）
        """
        with self._lock:
            rule = self._rules.get(rule_name)
            if not rule:
                return None

            labels = labels or {}
            alert_key = f"{rule_name}:{hash(frozenset(labels.items()))}"

            # 检查是否超过阈值
            is_firing = self._evaluate_condition(rule, current_value)

            if is_firing:
                # 检查持续时间
                if alert_key not in self._pending_alerts:
                    self._pending_alerts[alert_key] = datetime.now()
                    return None

                elapsed = (datetime.now() - self._pending_alerts[alert_key]).total_seconds()
                if elapsed < rule.duration_seconds:
                    return None

                # 检查是否已存在该告警
                if alert_key in self._alerts:
                    return self._alerts[alert_key]

                # 创建新告警
                alert = self._create_alert(rule, current_value, labels)

                # 检查静默
                if not self._is_silenced(alert):
                    self._alerts[alert_key] = alert
                    self._notify(alert)
                    return alert
                else:
                    alert.state = AlertState.SILENCED
                    self._alerts[alert_key] = alert
                    return alert

            else:
                # 清除待确认状态
                self._pending_alerts.pop(alert_key, None)

                # 如果存在告警，则解决
                if alert_key in self._alerts:
                    alert = self._alerts[alert_key]
                    if alert.state == AlertState.FIRING:
                        alert.state = AlertState.RESOLVED
                        alert.resolved_at = datetime.now()
                        self._notify(alert)

            return None

    def _evaluate_condition(self, rule: AlertRule, value: float) -> bool:
        """评估告警条件"""
        # 简化实现：直接比较阈值
        # 实际实现应支持更复杂的表达式
        return value > rule.threshold

    def _create_alert(
        self,
        rule: AlertRule,
        value: float,
        labels: Dict[str, str]
    ) -> Alert:
        """创建告警"""
        self._alert_counter += 1
        alert_id = f"alert_{self._alert_counter}"

        return Alert(
            id=alert_id,
            rule_name=rule.name,
            level=rule.level,
            state=AlertState.FIRING,
            message=rule.description,
            value=value,
            threshold=rule.threshold,
            started_at=datetime.now(),
            labels={**rule.labels, **labels},
            annotations=rule.annotations
        )

    def _is_silenced(self, alert: Alert) -> bool:
        """检查告警是否被静默"""
        now = datetime.now()

        for silence in self._silences.values():
            if silence.starts_at <= now <= silence.ends_at:
                # 检查匹配条件
                match = True
                for key, value in silence.matchers.items():
                    if alert.labels.get(key) != value:
                        match = False
                        break
                if match:
                    return True

        return False

    def _notify(self, alert: Alert) -> None:
        """通知告警处理器"""
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception:
                pass

    def add_silence(
        self,
        matchers: Dict[str, str],
        duration_hours: float,
        created_by: str,
        comment: str
    ) -> SilenceRule:
        """添加静默规则"""
        silence_id = f"silence_{len(self._silences) + 1}"
        now = datetime.now()

        silence = SilenceRule(
            id=silence_id,
            matchers=matchers,
            starts_at=now,
            ends_at=now + timedelta(hours=duration_hours),
            created_by=created_by,
            comment=comment
        )

        with self._lock:
            self._silences[silence_id] = silence

        return silence

    def remove_silence(self, silence_id: str) -> None:
        """移除静默规则"""
        with self._lock:
            self._silences.pop(silence_id, None)

    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return [
            alert for alert in self._alerts.values()
            if alert.state == AlertState.FIRING
        ]

    def get_all_alerts(
        self,
        level: Optional[AlertLevel] = None,
        state: Optional[AlertState] = None
    ) -> List[Alert]:
        """获取所有告警"""
        alerts = list(self._alerts.values())

        if level:
            alerts = [a for a in alerts if a.level == level]
        if state:
            alerts = [a for a in alerts if a.state == state]

        return alerts

    def get_alert_statistics(self) -> Dict[str, Any]:
        """获取告警统计"""
        alerts = list(self._alerts.values())

        return {
            "total": len(alerts),
            "firing": len([a for a in alerts if a.state == AlertState.FIRING]),
            "resolved": len([a for a in alerts if a.state == AlertState.RESOLVED]),
            "silenced": len([a for a in alerts if a.state == AlertState.SILENCED]),
            "by_level": {
                level.value: len([a for a in alerts if a.level == level])
                for level in AlertLevel
            }
        }

    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        with self._lock:
            for alert in self._alerts.values():
                if alert.id == alert_id:
                    alert.annotations["acknowledged"] = "true"
                    alert.annotations["acknowledged_at"] = datetime.now().isoformat()
                    return True
        return False


class WebhookNotifier:
    """Webhook 通知器"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def __call__(self, alert: Alert) -> None:
        """发送告警通知"""
        import json
        try:
            import urllib.request
            data = json.dumps(alert.to_dict()).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass


class EmailNotifier:
    """邮件通知器"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        recipients: List[str]
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipients = recipients

    def __call__(self, alert: Alert) -> None:
        """发送邮件通知"""
        # 实际实现应使用 smtplib 发送邮件
        pass
