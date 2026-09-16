# 简历展示版：DeepSeek + 零付费评测准备

用户批准实现，但不执行真实模型评测。本次运行不得调用收费 API。

## 交付范围

- 保留 baseline 默认及 OpenAI-compatible 自定义模型；提供显式 DeepSeek CLI preset、环境变量、非思考模式及单次输出上限。
- deterministic condenser 真正限制摘要长度；候选先脱敏再截断，运行时传入密钥脱敏配置。
- 提供只读评测计划入口，列出任务、消融、指标、预算及可信 oracle 要求，不创建客户端、不运行 agent、不报告虚构成功率。
- 标记 scripted 报告性质，补充中文评测流程、演示说明、简历措辞及离线 CI。
- 离线测试、类型和格式检查。真实模型效果、跨进程恢复、默认 full mode、LLM auxiliary 生产接线、语义证据校验不在本次交付范围；不得声称全部已完成。

## 验收

DeepSeek 配置通过 mock HTTP 检查，无真实 API 调用；计划命令无网络且真实指标为 null；新增风险回归和原有测试通过。预算是步骤/单次输出/累计已报告 token 控制，不声称为账单硬上限。
