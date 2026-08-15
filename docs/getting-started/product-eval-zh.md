# 中文 AI 产品评测离线示例

本示例演示结构化 AI 产品输出的本地确定性评测。`examples/product_eval_zh/` 中的输出是**手工编写的离线夹具**，不是任何真实模型调用、用户结果、人工标注、生产结果或模型准确率。示例分数只用于稳定地说明工具行为。

本扩展基于 [`cyberark/simple-llm-eval`](https://github.com/cyberark/simple-llm-eval)，上游提交为 `09c9fdad5f03014a6c3c1237ddd95eb0081934b5`，采用 Apache-2.0 许可证。仓库中的 `LICENSE` 与 `NOTICES` 保持不变。

## 示例数据

数据集位于 `examples/product_eval_zh/dataset.jsonl`，每行一个案例，按稳定顺序覆盖：

- 用户反馈的信息提取和优先级：`feedback-ticket-routing`
- JSON 格式稳定性：`json-format-stability`
- 不承诺不支持的退款到账：`instruction-no-commitment`
- 跳过身份验证的账户操作拒绝：`unsafe-account-operation`
- 空白或异常输入处理：`empty-user-input`

数据集字段包括：`case_id`（唯一案例 ID）、`task_type`、`instruction`、`expected_action`（`answer` 或 `refuse`）、`expected_output`、`json_schema`，以及可选的 `required_terms` 和 `forbidden_terms`。输出文件每行包含 `case_id`、`model`、`prompt_version` 与 `raw_output`。同一输出文件必须只有一个模型和一个 prompt 版本。

评测固定检查五个维度：`json_parse`、`schema_compliance`、`field_accuracy`、`instruction_constraints` 和 `action_alignment`。每个维度得分为 0 或 1，`overall_score` 为五项均值；这不是模型准确率指标。

## 运行示例

以下命令只读取本地文件，不调用模型 API：

```powershell
simpleval product-eval run --dataset examples/product_eval_zh/dataset.jsonl --outputs examples/product_eval_zh/baseline_outputs.jsonl --out artifacts/product-eval-zh/baseline
simpleval product-eval run --dataset examples/product_eval_zh/dataset.jsonl --outputs examples/product_eval_zh/candidate_outputs.jsonl --out artifacts/product-eval-zh/candidate
simpleval product-eval compare --baseline artifacts/product-eval-zh/baseline/run.json --candidate artifacts/product-eval-zh/candidate/run.json --out artifacts/product-eval-zh/comparison
```

外部系统产生的输出可以整理为相同 JSONL 格式后传入 `--outputs`；不要提交凭据、密钥或令牌。示例中的 `offline-demo-output` 只是夹具元数据，并不代表真实模型。

## 产物与退出状态

`run` 会写入：

- `run.json`：模型、prompt 版本、输入哈希、逐案例评测结果和汇总。
- `report.md`：本地确定性评测报告。
- `review_queue.jsonl`：失败案例的复核队列。每项初始为 `review_status: "pending"`，并带有 `reviewer_decision: null` 和 `reviewer_notes: null`，供后续人工流程填写。

`compare` 会写入 `comparison.json` 和 `comparison.md`，其中包含基线/候选元数据、逐案例 improved/regressed/unchanged 分类及汇总。候选得分更高为 improved、更低为 regressed、相等为 unchanged。只要存在 regression，命令仍会先写完两份比较产物，再以退出码 `1` 结束；没有 regression 时退出码为 `0`。本示例刻意让 `instruction-no-commitment` 因 `保证到账` 回归，因此比较命令返回 `1` 是预期行为。
