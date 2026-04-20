Lorenz single debug archive

This archive contains the Lorenz single-parameter tuning and exploratory outputs
that were generated during the eval_reservoir debugging process.

Best result kept outside the archive:

- `outputs_abfull/eval_layer_n1000_ridge7e5_round19/ridge7e-5_ratio0375_predict400_n1000`

Why this result is kept:

- It is the best validated Lorenz single result at full `n=1000` scale.
- Summary metrics from `eval_summary.json`:
  - `found = 715 / 1000`
  - `miss_rate = 0.285`
  - `mean = 24.038802637124732`
  - `median = 24.276025517582895`
  - `std = 0.7324634912722936`
  - `requested_base_param_value = 30.0`
  - `base_param_value = 29.936708450317383`
  - `mapping_used.source = paper_reference`

What was archived here:

- Early Lorenz single baseline/quick runs from `outputs/lorenz_single`
- Alternate base-mapping runs from `outputs_ab/lorenz_single_eval_*`
- All Lorenz single eval-layer sweep rounds except the best full-scale Round19
- Temporary Lorenz single full run directories under `outputs_abfull/lorenz_single_*`

Purpose:

- Keep the repository surface focused on the single best Lorenz single result.
- Preserve the full tuning trail for later inspection without leaving many
  competing result directories at the top level.
