| Agent | Model | Metric (test) | Model | Best baseline | Baseline score | Δ | Δ 95% CI | Promoted |
|---|---|---|---|---|---|---|---|---|
| scout | `ari-scout-vulnclass@1.0.0` | macro_f1 | 0.298 | static_analyze_patterns | 0.090 | +0.208 | [+0.188, +0.227] (significant) | yes |
| probe | `ari-probe-strategy@1.0.0` | accuracy | 0.631 | cwe_lookup | 0.606 | +0.025 | [+0.004, +0.048] (significant) | yes |
| trace | `ari-trace-tactics@1.0.0` | f1_at_k | 0.457 | prior_top3 | 0.438 | +0.019 | [-0.095, +0.126] | no |
| diagnose | `ari-diagnose-rootcause@1.0.0` | macro_f1 | 0.525 | cwe_lookup | 0.525 | +0.000 | [+0.000, +0.000] | no |
| patch | `ari-patch-strategy@1.0.0` | macro_f1 | 0.734 | cwe_lookup | 0.750 | -0.016 | [-0.027, -0.008] (significant) | no |
| fortify | `ari-fortify-d3fend@1.0.0` | f1_at_k | 0.286 | knn_name | 0.263 | +0.024 | [-0.101, +0.152] | no |
| verify | `ari-verify-evidence@1.0.0` | macro_f1 | 0.976 | diff_rules | 0.859 | +0.118 | [+0.102, +0.134] (significant) | yes |
