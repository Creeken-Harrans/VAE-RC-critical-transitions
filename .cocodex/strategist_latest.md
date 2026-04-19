# Strategist Response

## Control Fields
- allow_implementation_phase: yes
- strategist_finish_vote: no
- finish_gate_status: open
- last_strategist_decision: 接受实现者的有效异议的一半：`src/data/lorenz.py` 中保留 `uniform_random` 能力是合理的，但当前不应把 `configs/lorenz_single.yaml` 默认值锁定到该策略。下一阶段先做受控 A/B：优先诊断 `configs/lorenz_single.yaml` 与 `src/train/eval_reservoir.py` 的映射/基点/健康过滤影响，同时把 `data.param_sampling_strategy` 作为并列对照变量而不是默认定案。

## Task Goal
- primary_goal: 让新生成的 `fig_lorenz_single_critical_hist.png` 在峰位、峰宽、左尾范围、与真值线 `23.99` 的相对位置上接近 `2501.01579v1.pdf` Fig.3(d)。
- non_goals: 不做仅视觉修饰；不扩大修改到无关系统；不把旧失效输出当完成证据。

## Hard Constraints
- constraint_1: 运行与验证必须使用 `/home/Creeken/miniconda3/envs/pytorch/bin/python`。
- constraint_2: 只能基于新生成的 `outputs/lorenz_single/...`、尤其 `reservoir/eval_summary.json` 和 `fig_lorenz_single_critical_hist.png` 收尾。
- constraint_3: 不回滚无关工作树改动；仅围绕 `lorenz_single` 链路推进。

## Repo Facts
- relevant_paths: `configs/lorenz_single.yaml`, `src/train/eval_reservoir.py`, `src/data/lorenz.py`, `src/models/reservoir/transition_search.py`, `README.md`, `2501.01579v1.pdf`
- confirmed_facts:
  - `.cocodex/session.json` 当前处于 `dispute`，但实现阶段允许继续。
  - `configs/lorenz_single.yaml` 当前为 `param_sampling_strategy: uniform_random`、`base_param_strategy: target_value`、`base_param_value: 30.0`、`use_paper_reference_mapping: false`、`require_healthy_base: true`。
  - `src/train/eval_reservoir.py` 会把 `mapping_used.source`、`status_counts`、`base_param_value`、`base_param_strategy` 写入 `reservoir/eval_summary.json`。
  - `src/data/lorenz.py` 已新增 `sample_single_params()`，支持 `linspace|uniform_random`。
  - 已知旧 full 结果存在 `run_fitted` 映射和明显左尾，尚无新的受控 A/B 证据。

## Recommended Architecture
- file_layout: 主改 `configs/lorenz_single.yaml`、必要时小改 `src/train/eval_reservoir.py`；`src/data/lorenz.py` 先保留能力，不继续深改；`src/models/reservoir/transition_search.py` 仅在扫描逻辑被证伪时再动。
- ownership_boundaries: 配置负责实验矩阵；评估脚本负责记录可解释诊断字段；数据脚本当前只提供采样开关，不承担默认策略结论。
- implementation_notes: 先把“评估映射/基点”与“训练采样策略”拆开，避免把两个变量同时默认化导致无法归因。

## Ordered Execution Plan
1. step: 撤回未经证实的默认采样结论，保留能力
   - input: `configs/lorenz_single.yaml`, `src/data/lorenz.py`
   - output: `src/data/lorenz.py` 继续支持 `uniform_random`，但配置默认恢复为论文复现前更可对照的基线；若需 A/B，用显式切换而不是默认锁死
2. step: 先跑评估侧 A/B
   - input: `use_paper_reference_mapping=false/true`, `base_param_value=30.0`，必要时再比较更健康的 base 值
   - output: 每组都有 `reservoir/eval_summary.json`，重点读取 `mapping_used.source`、`status_counts`、`miss_rate`、`base_param_value`
3. step: 再跑采样侧 A/B
   - input: `param_sampling_strategy=linspace/uniform_random`，其余保持第 2 步中更优评估设置不变
   - output: 判断左尾改善主要来自映射/基点还是采样分布
4. step: 仅在仍不符论文时下钻扫描逻辑
   - input: `src/models/reservoir/transition_search.py`, `require_healthy_base`, `auto_infer_scan_direction`
   - output: 明确是否存在方向推断、base 健康门槛或 coarse/binary 搜索导致的系统性偏移
5. step: 固化最优组合并重生最终图
   - input: 已验证最优配置
   - output: 新的 `fig_lorenz_single_critical_hist.png` 与自洽摘要

## Critique Of Implementer Status
- strengths:
  - 指出论文训练采样分布与原始 `linspace` 不一致，这个异议成立。
  - 已把采样策略改成可配置开关，而不是把代码写死，方向正确。
- weaknesses:
  - 过早把 `uniform_random` 设为配置默认，破坏了因果归因。
  - 还没有提交新的 `eval_summary.json` 证据来回答映射/base 是否是主导偏差源。
- required_corrections:
  - 不再把 `uniform_random` 当既定答案；改为受控变量。
  - 下一轮必须附带 A/B 结果摘要，而不是只给理论理由。

## Risks
- risk_1: `run_fitted` 映射若本身斜率/截距异常，任何数据采样修正都可能被后处理重新拉出长左尾。
- risk_2: `base_param_value=30.0` 配合 `require_healthy_base=true` 可能造成大量 `unhealthy_at_base` 或偏置样本筛除，直方图会被结构性扭曲。

## Verification Requirements
- automated:
  - 用指定 Python 跑至少一组可复现实验，并保存 `fig_lorenz_single_critical_hist.png`
  - 对每个 A/B 组检查 `reservoir/eval_summary.json` 的 `mapping_used.source`、`status_counts`、`miss_rate`、`base_param_value`
- manual:
  - 对照论文 Fig.3(d)：主峰应集中在 `23-24` 附近，左尾不能再长到 `~12-24`，真值线 `23.99` 相对位置应合理
  - 若改了采样策略，还要看分布改善是峰位、峰宽还是左尾截断

## Open Questions For Implementer
- q1: 在仅切换 `use_paper_reference_mapping=true`、其余不变时，`eval_summary.json` 的 `mapping_used`、`status_counts`、`miss_rate` 如何变化，左尾是否明显收缩？
- q2: 在固定更优评估设置后，`linspace` vs `uniform_random` 的差异主要体现为峰宽变化，还是峰位/左尾也显著变化？

## Next Step
- immediate_action: 先把 `configs/lorenz_single.yaml` 的 `param_sampling_strategy` 从默认 `uniform_random` 撤回为对照基线，并执行“评估侧 A/B 优先、采样侧 A/B 次之”的实验矩阵。
- stop_conditions:
  - 只有当新图与论文在峰位/峰宽/左尾上基本对齐，且 `eval_summary.json` 能解释为何对齐，才可申请 finish。
  - 若评估侧与采样侧 A/B 都不能解释偏差，再升级到 `transition_search` 逻辑审查。