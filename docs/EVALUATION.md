# Coding Agent 评测流程（本版不执行真实测评）

## 当前结论

执行 runtime 现已为 LangGraph 状态图，live model 接入为 LangChain provider SDK；scripted fixtures 也走同一状态图。框架迁移不改变下文关于 hidden oracle、样本量和真实模型未测的边界。

本版交付评测协议与离线回归，不包含 DeepSeek 自主编码成功率。`baseline-scripted.json` 的 3/3 是预设正确编辑的运行时演示，token 字段是合成值，不能用于模型能力或费用宣传。现有 fixture 测试可见且可修改，不是可信 hidden-test benchmark。

```powershell
python -m coding_agent.evaluation.plan
python -m pytest -q
```

第一个命令只读取 manifest、输出 JSON 协议，不创建模型客户端、不运行 agent、不创建项目、不联网。真实指标均为 `null` / `not_run`。第二个命令进行本地工程回归，包括脚本驱动 E2E，不调用收费模型。

## 将来真实测评的六步流程

1. **冻结任务**：先用现有 3 个微任务试跑，再扩到约 12 个 Python 任务，覆盖 bug 修复、补测试、接口变更、多文件修改、命令失败恢复、长输出处理。记录任务版本、初始 commit、Python/依赖版本。先人工验证初始缺陷与 gold patch，gold 不提供给模型。
2. **建立可信判题**：visible tests 用于 agent 调试；hidden tests 保存在 evaluator 控制的外部目录，不进入工具可见仓库。agent 结束后，evaluator 在全新 fixture 上应用 patch，恢复可信测试，再执行 hidden oracle。禁止直接信任 agent 修改过的测试、finish 文案或它报告的 exit code。当前 runner 的 `run_oracle` 尚未实现这一隔离协议，必须补齐后再报告真实成功率。
3. **低预算试跑**：先只跑 baseline、单任务、一次；DeepSeek Flash 非思考模式，8 steps、单次输出最多 1024 tokens、累计已报告 token 停止阈值 12000、auxiliary calls=0。不自动扩任务或重跑失败任务。确认轨迹正常并获得付费批准后再扩到 3 个任务。
4. **同条件消融**：baseline 与 full 使用同任务、同模型、同初始 commit、同限制，各一次；每个任务从干净副本开始，项目记忆 DB 独立，禁止先跑 full 污染 baseline。需要定位增益时再单独加 processor/repo-map/project-memory。没有结果不把 full 设为默认。
5. **记忆专项**：同项目 Run A 形成记忆，Run B 测召回；不同项目 Run C 不得召回。分别测试有 remote、无 remote、linked worktree；测试过时/恶意/错误证据候选被拒、密钥不落库、DB 不可用的降级。A/B 可显式共享 DB，其余必须隔离。Run A/B 的真实回答质量本版未测。
6. **导出报告并复查失败**：保存 events、patch、summary、独立 oracle 输出、模型返回 usage 和任务配置。人工分类定位失败：探索不足、错误编辑、测试伪通过、上下文丢失、预算停止、工具失败。报告样本量和分母，不能只选成功任务。

## 指标与报告模板

| 指标 | 定义 | 本版真实模型结果 |
|---|---|---|
| Task success | 完成状态且可信 hidden oracle 通过 / 全部任务 | 未测 |
| Token | 模型报告的 main + auxiliary input/output | 未测 |
| Cost | 账单或注明日期/缓存命中价格的估算；未知不可记为 0 | 未测 |
| Latency / steps | 中位数及逐任务原始值，包括失败任务 | 未测 |
| Context / memory | 选择/省略量、候选拒绝量、跨 Run 召回证据 | 仅工程测试 |

报告每行建议字段：`task_id, commit, model, preset, repeat, status, oracle_exit_code, success, steps, input_tokens, output_tokens, auxiliary_tokens, elapsed_ms, cost_usd, failure_category, artifacts_path`。

模型 temperature 不保证完全确定性；3 个小任务、每次一遍只适合 smoke test，不足以说明一般编码能力。不要宣传 token 节省百分比、成功率提升或真实成本，直到同条件数据支持它们。

## 预算边界

本次 API 调用数为 0。将来 `--max-output-tokens` 限制每个请求的生成长度；`--max-steps` 限制 agent 步数；`--max-tokens` 在响应后按报告累计判断停止，输入开销和最后一个响应可使总量超过阈值。重试也可能产生请求，异常响应的 usage 目前不能完整结算。它们**不是账户账单硬上限**，真实费用需配合账户充值/消费限制和人工逐任务批准。

CLI 使用确定性 condenser/extractor，没有生产接线的 LLM auxiliary 客户端。辅助预算类是扩展边界，不应把非零辅助参数理解为启用 LLM；未来启用前必须补充单次输入/输出预留、失败调用计费与 hard-limit 测试。
