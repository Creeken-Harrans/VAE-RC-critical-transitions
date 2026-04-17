# 基于论文的临界转变复现项目

本仓库用于复现论文 **Unsupervised learning for anticipating critical transitions** 的核心实验流程：

- 第一阶段：`VAE` 从不同参数下的时间序列中无监督提取 latent parameter
- 第二阶段：`parameter-driven reservoir computing` 使用提取出的 latent parameter 进行外推与临界转变预测

这不是机械逐字复刻作者私有代码，而是：

1. 以论文内容作为最高约束
2. 用作者最接近的公开代码补齐论文未写明的实现细节
3. 在当前仓库基础上做最小增量修补，而不是无脑推倒重写

## 1. 当前仓库定位

本项目已经过一轮“先审计、再补全”的整理：

- 保留了现有的 `configs/`、`src/data/`、`src/models/`、`src/train/`、`scripts/`、`tests/` 结构
- 修补了与论文复现直接相关的缺口
- 没有为了“目录好看”而强行大重构

## 2. 哪些部分来自论文硬约束

以下内容直接按论文实现：

- 两阶段框架：`VAE + parameter-driven reservoir`
- Lorenz 单参数、Lorenz 双参数、Lorenz 部分观测、KS、food-chain 五类实验
- latent channel 选择准则：
  - `var(mu_z)` 高
  - `mean(sigma_z^2)` 低
- Table I 中的 VAE 与 reservoir 超参数
- Appendix D/E/F 中的线性或仿射映射
- Appendix B 的标准 KL 数值形式
- Appendix G 的 `ReLU + Adam`

## 3. 哪些部分来自作者公开代码补齐

以下内容属于 `repo-informed completion`：

- VAE encoder 使用 4 层 dilated `Conv1d`
- `hidden_channels=32`
- `param_size=5`
- `prop_layers=1`
- inverse-variance weighted latent aggregation
- hypernetwork 风格 decoder
- Euler-like residual one-step predictor
- parameter-channel reservoir update

参考仓库：

- `lw-kong/VAE-CNN-RNN-extracting-parameter`
- `lw-kong/Reservoir_with_a_Parameter_Channel_PRR2021`

## 4. 哪些部分属于保守补全

论文没有完全写明、因此在不违背论文逻辑下做了保守补全：

- Lorenz / food-chain 使用 `solve_ivp`
- KS 使用 Fourier pseudo-spectral + ETDRK4
- Lorenz 部分观测默认 `delay=8`
- reservoir 的 `ridge_reg` 暴露为配置项
- 双参数测试集使用 latent 平面扫描，再映射回物理参数平面做真值对照
- Lorenz 单参数的 reservoir critical-point evaluation 默认使用**当前 run 实际拟合得到的** `physical = a * z + b`
- Lorenz 单参数的 latent scan direction 默认根据当前 run 的拟合斜率自动推断
- 单参数 critical transition 搜索中，若未找到转变点，则记为 miss，不再把扫描边界伪装成临界点

其中需要特别说明：

- 论文里写 “number of hidden layers fixed at 32”
- 这里不把它解释成 32 层 CNN
- 默认按作者公开代码最保守地解释为 `hidden_channels=32`

## 5. 环境安装

默认你已经进入 `pytorch` conda 环境，例如：

```bash
conda activate pytorch
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 6. 目录说明

主要目录如下：

- `configs/`：实验配置
- `src/data/`：数据生成与样本构造
- `src/models/vae/`：VAE 主体
- `src/models/reservoir/`：parameter-driven reservoir
- `src/train/`：训练、评估、总入口
- `scripts/`：便捷脚本
- `tests/`：最基础的 shape / smoke tests
- `outputs/`：运行时自动生成

## 7. 快速运行

如果你已经在 `(pytorch)` 环境里，直接用 `python` 即可。

### 7.1 最快跑通 Lorenz 单参数 quick 模式

```bash
python scripts/generate_all_data.py --config configs/lorenz_single.yaml --quick
python -m src.train.train_vae --config configs/lorenz_single.yaml --quick
python -m src.train.eval_vae --config configs/lorenz_single.yaml --quick
python -m src.train.train_reservoir --config configs/lorenz_single.yaml --quick
python -m src.train.eval_reservoir --config configs/lorenz_single.yaml --quick
```

或者直接一条龙：

```bash
python -m src.train.reproduce --config configs/lorenz_single.yaml --quick
```

### 7.2 shell 脚本方式

```bash
bash scripts/run_lorenz_single.sh --quick
bash scripts/run_lorenz_two_param.sh --quick
bash scripts/run_lorenz_partial.sh --quick
bash scripts/run_ks.sh --quick
bash scripts/run_food_chain.sh --quick
```

## 8. 全实验入口

### Lorenz 单参数

```bash
python -m src.train.reproduce --config configs/lorenz_single.yaml --quick
python -m src.train.reproduce --config configs/lorenz_single.yaml --full
```

### Lorenz 双参数

```bash
python -m src.train.reproduce --config configs/lorenz_two_param.yaml --quick
python -m src.train.reproduce --config configs/lorenz_two_param.yaml --full
```

### Lorenz 部分观测

```bash
python -m src.train.reproduce --config configs/lorenz_partial_obs.yaml --quick
python -m src.train.reproduce --config configs/lorenz_partial_obs.yaml --full
```

### KS

```bash
python -m src.train.reproduce --config configs/ks.yaml --quick
python -m src.train.reproduce --config configs/ks.yaml --full
```

### Food-chain

```bash
python -m src.train.reproduce --config configs/food_chain.yaml --quick
python -m src.train.reproduce --config configs/food_chain.yaml --full
```

## 9. 分步骤运行

### 9.1 只生成数据

```bash
python scripts/generate_all_data.py --config configs/lorenz_single.yaml --quick
```

### 9.2 只训练 VAE

```bash
python -m src.train.train_vae --config configs/lorenz_single.yaml --quick
```

### 9.3 只评估 VAE 并画图

```bash
python -m src.train.eval_vae --config configs/lorenz_single.yaml --quick
```

### 9.4 只训练 reservoir

```bash
python -m src.train.train_reservoir --config configs/lorenz_single.yaml --quick
```

### 9.5 只评估 reservoir / 临界点搜索 / 画图

```bash
python -m src.train.eval_reservoir --config configs/lorenz_single.yaml --quick
```

对于 Lorenz 单参数，如果你只改了 reservoir 评估逻辑，不需要重跑前面的训练，直接重新运行这一步即可：

```bash
python -m src.train.eval_reservoir --config configs/lorenz_single.yaml --full
```

## 10. 输出结果

运行后会在：

```bash
outputs/<experiment_name>/<mode>/
```

下生成：

- `data/trajectories.npz`
- `vae/best.tar`
- `vae/latent_stats.npz`
- `vae/latent_summary.json`
- `reservoir/reservoir.pkl`
- `reservoir/eval_summary.json`
- `figures/*.png`

其中 `vae/latent_summary.json` 现在会额外保存：

- `physical_from_latent.coef`
- `physical_from_latent.intercept`
- `physical_from_latent.r2`
- `active_channel`

`reservoir/eval_summary.json` 在 Lorenz 单参数修复后会额外保存：

- `mapping_used`
- `latent_scan_direction`
- `target_physical_direction`
- `num_realizations`
- `num_found`
- `num_miss`
- `miss_rate`
- `base_param_value`
- `base_latent_value`
- `base_index`
- `found_only_predicted_critical_point`

也就是说，critical histogram 现在只使用真正找到转变点的 realization，不再把 miss 的扫描边界值混进去。

## 11. 生成的图

至少支持以下论文对应类型：

### Lorenz 单参数

- `fig_lorenz_single_channel_stats.png`
- `fig_lorenz_single_latent_vs_rho.png`
- `fig_lorenz_single_critical_hist.png`

注意：

- `fig_lorenz_single_critical_hist.png` 现在默认基于当前 run 的拟合映射绘制
- 配置中的论文映射只作为参考展示值保留，不再默认直接用于当前 run 的真实回映射

### KS

- `fig_ks_channel_stats.png`
- `fig_ks_latent_vs_phi.png`
- `fig_ks_critical_hist.png`

### Lorenz 双参数

- `fig_lorenz_two_param_channel_stats.png`
- `fig_lorenz_two_param_latent_planes.png`
- `fig_lorenz_two_param_classification.png`

### Lorenz 部分观测

- `fig_lorenz_partial_channel_stats.png`
- `fig_lorenz_partial_latent_vs_rho.png`
- `fig_lorenz_partial_critical_hist.png`

### Food-chain

- `fig_food_chain_channel_stats.png`
- `fig_food_chain_latent_vs_kappa.png`
- `fig_food_chain_critical_hist.png`

## 12. quick demo 与 full reproduction 的区别

### quick

- 参数点更少
- 轨迹更短
- epoch 更少
- reservoir realization 更少
- 适合先验证工程是否跑通

### full

- 尽量贴近论文参数规模
- 运行更慢
- 更适合做正式复现统计

## 13. 测试

当前提供最基本的 shape / smoke test。

如果你装了 `pytest`：

```bash
pytest -q
```

如果没有装 `pytest`，也可以直接执行最小测试逻辑。

## 14. 当前实现的工程说明

- VAE 完全使用 PyTorch
- 线性/仿射拟合也统一到了 PyTorch `lstsq`
- reservoir 主体当前保留为 `numpy` 实现

保留 `numpy` reservoir 的原因是：

- 它已经能稳定表达论文需要的 parameter-channel 状态更新
- 与当前工程接口兼容
- 相比重写成 torch，局部保留更符合“最小增量补全”原则

## 15. 当前仓库中哪些文件被修补

本轮主要修补了：

- `scripts/generate_all_data.py`
- `scripts/run_*.sh`
- `README.md`
- `src/utils/linear_map.py`
- `src/train/train_vae.py`
- `src/train/eval_vae.py`
- `src/train/eval_reservoir.py`
- `configs/lorenz_two_param.yaml`
- `tests/test_shapes.py`

## 16. 注意事项

- 请先激活 `(pytorch)` 环境，再运行 `python ...`
- `scripts/generate_all_data.py` 现在已经修复了 `ModuleNotFoundError: No module named 'src'`
- 如果论文级 full 模式过慢，请先用 `--quick` 验证链路
