"""模板引擎包 —— discover_plugins 会扫描 engine_plugin 属性并自动注册。"""

from .engine import InvertedIndexEngine, engine_plugin

__all__ = ["InvertedIndexEngine", "engine_plugin"]
