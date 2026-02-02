"""
Plugin Base - 插件基类

定义插件的通用接口和管理机制
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Type
from datetime import datetime
from enum import Enum


class PluginStatus(Enum):
    """插件状态"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginConfig:
    """插件配置"""
    name: str
    version: str
    enabled: bool = True
    priority: int = 100
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "priority": self.priority,
            "settings": self.settings
        }


@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    version: str
    description: str
    author: str
    plugin_type: str
    status: PluginStatus
    loaded_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "plugin_type": self.plugin_type,
            "status": self.status.value,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "error": self.error
        }


class BasePlugin(ABC):
    """
    插件基类

    所有插件必须继承此类
    """

    # 插件元信息（子类必须覆盖）
    NAME: str = "base_plugin"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Base plugin"
    AUTHOR: str = "GuardAdapter"
    PLUGIN_TYPE: str = "base"

    def __init__(self, config: Optional[PluginConfig] = None):
        self.config = config or PluginConfig(
            name=self.NAME,
            version=self.VERSION
        )
        self._status = PluginStatus.UNLOADED
        self._loaded_at: Optional[datetime] = None
        self._error: Optional[str] = None

    @property
    def status(self) -> PluginStatus:
        return self._status

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name=self.NAME,
            version=self.VERSION,
            description=self.DESCRIPTION,
            author=self.AUTHOR,
            plugin_type=self.PLUGIN_TYPE,
            status=self._status,
            loaded_at=self._loaded_at,
            error=self._error
        )

    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化插件

        Returns:
            是否初始化成功
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """关闭插件"""
        pass

    async def load(self) -> bool:
        """加载插件"""
        self._status = PluginStatus.LOADING
        try:
            success = await self.initialize()
            if success:
                self._status = PluginStatus.LOADED
                self._loaded_at = datetime.now()
                if self.config.enabled:
                    self._status = PluginStatus.ENABLED
            else:
                self._status = PluginStatus.ERROR
            return success
        except Exception as e:
            self._status = PluginStatus.ERROR
            self._error = str(e)
            return False

    async def unload(self) -> None:
        """卸载插件"""
        try:
            await self.shutdown()
        finally:
            self._status = PluginStatus.UNLOADED
            self._loaded_at = None

    def enable(self) -> None:
        """启用插件"""
        if self._status == PluginStatus.LOADED or self._status == PluginStatus.DISABLED:
            self._status = PluginStatus.ENABLED
            self.config.enabled = True

    def disable(self) -> None:
        """禁用插件"""
        if self._status == PluginStatus.ENABLED:
            self._status = PluginStatus.DISABLED
            self.config.enabled = False


class PluginManager:
    """
    插件管理器

    统一管理所有插件的加载、卸载和配置
    """

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_classes: Dict[str, Type[BasePlugin]] = {}

    def register_plugin_class(self, plugin_class: Type[BasePlugin]) -> None:
        """注册插件类"""
        self._plugin_classes[plugin_class.NAME] = plugin_class

    def get_registered_plugins(self) -> List[str]:
        """获取所有已注册的插件类名称"""
        return list(self._plugin_classes.keys())

    async def load_plugin(
        self,
        name: str,
        config: Optional[PluginConfig] = None
    ) -> bool:
        """
        加载插件

        Args:
            name: 插件名称
            config: 插件配置

        Returns:
            是否加载成功
        """
        if name in self._plugins:
            return True  # 已加载

        plugin_class = self._plugin_classes.get(name)
        if not plugin_class:
            return False

        plugin = plugin_class(config)
        success = await plugin.load()

        if success:
            self._plugins[name] = plugin

        return success

    async def unload_plugin(self, name: str) -> bool:
        """
        卸载插件

        Args:
            name: 插件名称

        Returns:
            是否卸载成功
        """
        plugin = self._plugins.get(name)
        if not plugin:
            return False

        await plugin.unload()
        del self._plugins[name]
        return True

    async def reload_plugin(self, name: str) -> bool:
        """
        重新加载插件

        Args:
            name: 插件名称

        Returns:
            是否重新加载成功
        """
        plugin = self._plugins.get(name)
        if plugin:
            config = plugin.config
            await self.unload_plugin(name)
            return await self.load_plugin(name, config)
        return False

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """获取插件实例"""
        return self._plugins.get(name)

    def get_all_plugins(self) -> Dict[str, BasePlugin]:
        """获取所有已加载的插件"""
        return self._plugins.copy()

    def get_enabled_plugins(self) -> List[BasePlugin]:
        """获取所有启用的插件"""
        return [
            p for p in self._plugins.values()
            if p.status == PluginStatus.ENABLED
        ]

    def get_plugins_by_type(self, plugin_type: str) -> List[BasePlugin]:
        """按类型获取插件"""
        return [
            p for p in self._plugins.values()
            if p.PLUGIN_TYPE == plugin_type
        ]

    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        plugin = self._plugins.get(name)
        return plugin.info if plugin else None

    def get_all_plugin_info(self) -> List[PluginInfo]:
        """获取所有插件信息"""
        return [p.info for p in self._plugins.values()]

    async def load_all(self) -> Dict[str, bool]:
        """加载所有注册的插件"""
        results = {}
        for name in self._plugin_classes:
            results[name] = await self.load_plugin(name)
        return results

    async def unload_all(self) -> None:
        """卸载所有插件"""
        for name in list(self._plugins.keys()):
            await self.unload_plugin(name)
