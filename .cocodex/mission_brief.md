# Mission Brief

## Session
- session_id: use current .cocodex/session.json
- created_at: see session state
- updated_at: bootstrap round

## Objective
- user_request: 在 /home/Creeken/Paper/数院大创赛/Code 工作目录中持续修改代码，直到 lorenz_single 的 critical histogram 与论文 2501.01579v1 Fig.3(d) 相同或足够一致。
- success_definition: 重新生成的 `fig_lorenz_single_critical_hist.png` 在分布中心、离散度、左尾范围和真值线相对位置上与论文 Fig.3(d) 对齐；必要时调整 Lorenz 数据生成与评估链路，而不是只美化画图。

## Current Repo Facts
- root: /home/Creeken/Paper/数院大创赛/Code
- relevant_paths: `src/data/lorenz.py`, `src/train/eval_reservoir.py`, `src/utils/plotting.py`, `src/models/reservoir/transition_search.py`, `configs/lorenz_single.yaml`, `outputs/lorenz_single/full/...`, `2501.01579v1.pdf`
- existing_constraints:
  - 用户要求使用 conda 环境 `pytorch`，解释器为 `/home/Creeken/miniconda3/envs/pytorch/bin/python`
  - 当前用户指出目标文件是 `src/data/lorenz.py`，但现有偏差可能不止来自该文件
  - 必须按 cocodex 双角色流程推进，并保持 `.cocodex/session.json` 最新

## Rolling Context
- prior_decisions:
  - 尚未实施代码修改
  - 论文 Fig.3(d) 已定位到 PDF 第 3 页
- known_failures:
  - 当前生成图出现明显长左尾，样本大量落到 rho≈12-24，和论文图不符
  - 仓库 README 说明现版本默认使用 run-fitted mapping 而不是论文参考映射，这可能改变直方图回映射范围
- known_risks:
  - 偏差可能来自 Lorenz 数据生成、VAE latent->physical 映射、reservoir base 点选择、transition scan 逻辑、miss 样本处理中的任一环节
  - 如果只改 `lorenz.py` 可能无法修正论文图

## Expected Boundaries
- files_to_read_first: `configs/lorenz_single.yaml`, `src/data/lorenz.py`, `src/train/eval_reservoir.py`, `src/models/reservoir/transition_search.py`, `README.md` 中 Lorenz 单参数段落
- likely_files_to_modify: 首先怀疑 `src/data/lorenz.py`；其次可能是 `configs/lorenz_single.yaml`、`src/train/eval_reservoir.py` 或 `src/models/reservoir/transition_search.py`
- files_to_avoid: 与 Lorenz 单参数无关的系统实现

## Validation Targets
- tests_to_run:
  - 定向运行 Lorenz 相关单测
  - 使用 full 或针对性复现实验重新生成 `fig_lorenz_single_critical_hist.png`
  - 对比 `reservoir/eval_summary.json` 中 found/miss/mapping/base 参数摘要
- manual_checks:
  - 与论文 Fig.3(d) 视觉对比：峰值是否在 rho_c≈24 左侧、分布是否主要集中在 23-24 附近、是否不存在异常长左尾

## Open Questions For Strategist
- q1: 首轮实现应优先验证 `lorenz.py` 数据生成假设，还是先否定/确认 `eval_reservoir.py` 中 run-fitted mapping 与扫描基点造成的系统性偏差？
- q2: 在“与论文结果相同”的目标下，允许修改 config 中 `use_paper_reference_mapping` 或 base 参数策略吗，还是应坚持通过模型与数据本身得到论文形状？

## Compression Notes
- include only changed facts and durable context
- prefer paths, symbols, and deltas over long transcripts
