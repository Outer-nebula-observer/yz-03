# -*- coding: utf-8 -*-
"""long_short_term_memory 引擎包入口。

按照 SDK discover_plugins() 约定：模块级 engine_plugin 必须真实导出，
不能 try/except 吞成 None（返工清单 B2）。
"""

from .engine import LongShortTermMemoryEngine, engine_plugin

__all__ = ["LongShortTermMemoryEngine", "engine_plugin"]
