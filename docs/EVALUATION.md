# Coding Agent 可信评测流程

## 当前状态

仓库已经完成一次冻结的 `resume-v1` 真实模型微任务评测。它固定使用 DeepSeek Flash 非思考模式、`baseline` preset 和 12 个 Python 微任务；每个任务只运行一次，没有挑选成功样本或自动重跑失败任务。

早期的 `benchmarks/baseline-scripted.json` 仍只是 3/3 脚本驱动工程演示：编辑动作和 token 值是预设的，不能用于宣传自主编码能力、真实费用或 token 节省。

## 2026-09-16 真实运行结果

脱敏原始报告见 [`benchmarks/deepseek-live-resume-v1.json`](../benchmarks/deepseek-live-resume-v1.json)。运行对应 Git commit `701a6401572a886f765c59ddc4d526355c6c51f1`，UTC 时间为 05:57:50–05:59:23。

| 指标 | 观测值 |
|---|---:|
| 完整任务成功（finish + patch apply + hidden oracle） | 0/12 |
| 补丁通过 hidden oracle | 6/12 |
| 尝试任务 | 12/12，未提前停止 |
| Agent 状态 | 8 step limit；4 token budget limit |
| 失败类别 | 6 agent protocol failed；6 hidden oracle failed |
| Reported tokens | 74,506（input 72,938；output 1,568；auxiliary 0） |
| 中位 steps / Agent elapsed | 8 / 6,254.5 ms |
| 可信费用 | 未知，报告为 `null` |

0/12 不是隐藏判题器全部失败：`off-by-one`、`change-contract`、`add-regression-test`、`empty-mean`、`optional-display-name` 和 `stable-priority` 的补丁都通过了 fresh-copy hidden oracle，但模型没有发出合法 finish，因此按预先冻结的成功定义仍判失败。12 个 Run 共记录 30 次合法模型动作和 55 次 `format_error`；没有一个 Run 执行 visible pytest。该结果暴露的首要问题是 DeepSeek/tool-call 格式与终止协议兼容性，而不是可以对外宣传的编码成功率。

运行后验证了任务顺序、全部 patch hash、events/summary/patch/judge 产物完整性；精确密钥扫描为 `SECRET_LEAK_FOUND=false`。本次结果不会自动重跑。任何修复后的第二轮都需要新的明确付费批准，并作为独立报告保留，不能覆盖本报告。

## 运行后的离线协议改进

本次真实评测结束后，离线修正了三个协议层问题：模型格式异常会以固定的安全原因码记录（缺少/多个/无效工具调用、参数无效或 SDK 解析失败等），并在下一步提供不包含原始模型响应的纠错提示；已经通过结构化工具绑定提供的 schema 不再重复复制到 system prompt；合法 `finish` 即使使当次已报告 token 达到预算，也会记为完成，而不是被事后预算检查覆盖。非 `finish` 动作达到预算时仍停止执行；格式错误仍占用决策步数。以上改动仅经过离线测试，**没有对 DeepSeek 发起新的付费调用**，也不能倒推旧报告中 55 次格式错误的精确子类。历史 0/12 结果保持不变。

## 一次性付费命令

在仓库根目录的忽略文件 `.env` 中配置：

```dotenv
DEEPSEEK_API_KEY=your-key
```

然后执行：

```powershell
$env:PYTHONPATH = 'src'
& '.venv/Scripts/python.exe' -m coding_agent.evaluation.live `
  --project-root . `
  --suite resume-v1 `
  --confirm-paid-run
```

没有 `--confirm-paid-run` 时，程序会在读取密钥和构造模型前退出。`.env` 被 Git 忽略，密钥不会写入配置、事件、artifact 或汇总报告。默认原始轨迹写入忽略目录 `runs/live-deepseek-resume-v1/`，脱敏报告写入 `benchmarks/deepseek-live-resume-v1.json`。

## 固定条件与预算语义

- 模型：`deepseek-flash`，thinking disabled；
- 记忆模式：`baseline`；
- 每个 Run 最多 8 次模型决策、每次最多 512 output tokens；
- 每个 Run 按模型已报告 usage 在响应后执行 8000 total-token 停止判断；
- auxiliary calls/tokens 均为 0；
- 12 个任务各一次，完整 Run 不重试；底层 SDK 的 `max_retries=1` 会单独写入报告；
- 用户授权上限为约 CNY 15，但它是人工授权，不是程序或供应商账单的硬上限。

最后一次响应可能让已报告 token 超过 8000；失败响应、SDK 重试和供应商侧计费也不一定完整反映在本地 usage 中。因此账户余额或供应商消费限制才是硬边界，`cost_usd` 在没有可信账单数据时保持 `null`。

## 为什么判分可信

12 个任务的顺序、prompt、初始文件、gold patch 和 oracle 都在付费运行前冻结。gold 只用于离线验证，不进入 Agent 工作区或 prompt。每个任务按以下顺序处理：

1. Agent 在只包含初始文件和 visible tests 的独立 Git 仓库中运行；
2. 导出统一 diff，计算 SHA-256；
3. evaluator 创建第二个全新仓库并应用 diff；
4. evaluator 只向第二个仓库注入外部 hidden tests；
5. 普通任务运行 hidden pytest；“补回归测试”任务要求新增测试先通过正确实现、再杀死 evaluator 注入的 mutation。

离线门禁逐个证明了全部 12 个初始版本不能通过、全部 12 个 gold patch 可以通过。Agent 删除或放宽 visible tests 不能删除 hidden tests。oracle 子进程会移除 `DEEPSEEK_API_KEY` 和 `OPENAI_API_KEY`。

报告分别记录：

- `protocol_completed`：Agent 是否正常发出 finish；
- `patch_applied`：补丁是否能应用到干净副本；
- `trusted_oracle_passed`：外部可信判题是否通过；
- `task_success`：以上三项全部为真；
- visible test 结果、状态、终止原因、steps、工具调用、延迟和 input/output/auxiliary tokens。

## Canary 与失败处理

第一个 `off-by-one` 任务同时作为连通性 canary。认证、网络传输、补丁/判分基础设施故障会停止整个 suite，避免继续付费；普通模型失败、step/token limit、错误补丁、未通过 hidden oracle 都保留在分母中并继续后续任务。任何失败任务都不会被替换，也不会为了改善结果而重跑。

最终结果只能表述为“12-task Python microtask evaluation，single run per task”。它不是 SWE-bench，也不能外推为通用 Coding Agent 成功率。真实报告发布后，应同时给出准确的通过数/12、总 reported tokens、中位 steps/latency 和失败类别。

## 离线复核

付费前后均运行：

```powershell
$env:PYTHONPATH = 'src'
& '.venv/Scripts/python.exe' -m pytest -q
& '.venv/Scripts/ruff.exe' check .
& '.venv/Scripts/ruff.exe' format --check .
& '.venv/Scripts/mypy.exe' src
openspec.cmd validate --all --strict
git diff --check
```

完整报告还会固化 evaluator 版本、冻结 manifest hash、项目 Git commit、Python/关键包版本、模型、限制和 UTC 起止时间，便于把简历数字追溯到确切代码。
