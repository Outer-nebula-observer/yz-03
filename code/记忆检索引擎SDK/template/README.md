# 记忆引擎模板

复制本目录为你的引擎目录（目录名建议与 name 一致、小写下划线、不以下划线开头、不命中保留名），
在 engine.py 实现 MemoryEnginePlugin 契约，重启服务即自动注册。

详细契约见 docs/memory_engine_sdk.md。

注意：目录名以 _ 开头（如本 _template）会被 discover 跳过，不会注册。
