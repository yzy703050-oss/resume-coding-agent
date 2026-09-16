# 简历与面试展示

## 可直接使用的项目描述

**框架化 Coding Agent｜Python、LangChain、LangGraph、Pydantic、SQLite、pytest**

- 使用 LangGraph 状态图编排单智能体 ReAct 编码闭环，划分预算检查、上下文准备、模型决策、工具执行与结果观察节点，通过条件路由支持任务结束、失败恢复及预算停止。
- 设计分层上下文与项目记忆：Working/Episodic Memory、确定性有界历史摘要、Python AST Repo Map 和 SQLite 项目隔离存储；候选经过脱敏、策略、来源引用及去重校验后入库。
- 使用 LangChain 接入 DeepSeek 模型与自定义兼容接口，绑定由 Pydantic 定义的工具 schema，配置非思考模式与单次输出上限；输出可审计事件、Git Patch 和结构化报告，保留 baseline/full 消融入口。

不要写“真实成功率 100%”“节省 40% token”“完成 SWE-bench 测评”。本版仅工程回归与脚本驱动演示，DeepSeek 请求格式通过真实 LangChain SDK + mock HTTP 验证，端到端真实模型兼容性及效果尚未验证。框架依赖和默认运行路径已实际接线，不是仅添加依赖。

## 与旅行助手一起展示

旅行助手强调业务侧的规划执行、外部信息获取和偏好记忆；Coding Agent 强调代码侧的工具边界、失败恢复、上下文取舍与工程可观测性。两个项目形成“业务应用 + Agent runtime 工程”的互补，不必再复制旅行项目的多 Agent、向量库或 Web UI。

## 重点理解顺序

1. `agent/graph.py` 和 `agent/runner.py`：为什么每步只有一个 action，条件边如何控制循环，agent step 与 graph step 有何区别，谁拥有 terminal event。
2. `events/recorder.py` 与 projections：一次生成事件事实，分别投影到 richer history 与 audit，correlation_id 保留因果关联。
3. `context/manager.py` 与 selector：上下文来源如何组合，为什么不是把所有历史塞给模型；字符预算与 token 预算的区别。
4. `memory/candidates.py`、promotion、persistent：extractor 只提议、不直接写库；project_id 的 remote/common-dir 规则；来源引用验证不等于事实真实性验证。
5. `evaluation/plan.py` 和本目录评测文档：为什么 scripted 正确不能证明模型正确，如何用外部 hidden oracle 做可信判题。
6. `models/langchain_client.py` 与 `tool_binding.py`：LangChain 如何绑定原有工具契约，如何把 AIMessage 解码成单动作并映射 usage；为何不用框架默认 shell/tool memory 替代工程边界。

## 尚未完成，不应包装成现成功能

最终格式化 header/omission 字符精确计入上下文预算、最新事件的显式优先级及严格 section 配额、Repo Map symlink/ignored-file 防护、候选内容与 canonical evidence 的语义匹配、数据库失败诊断/生命周期、LLM auxiliary 失败计费和生产接线仍需后续 hardening。跨进程恢复和 full 默认化仍不在范围内。
