# arkcli models performance (Volc only)

This capability compares public aggregated model performance. It is not an SLA
and does not diagnose a user's Endpoint.

```bash
# Independent TTFT and TPOT rankings; defaults: 10k input, past 6h, top 10.
arkcli models performance rank --metric all --format json

# Time series for one or more exact model selectors.
arkcli models performance trend \
  --model doubao-seed-2-0-mini@260428:fast \
  --model <another-name>@<version>:<deployment>

# Compare the same models at four input lengths by default.
arkcli models performance input-length \
  --model doubao-seed-2-0-mini@260428:fast \
  --metric all --time-window 7d
```

- `--metric`: `ttft`, `tpot`, or `all`. Lower values are better; do not create a combined score.
- `trend` uses the same defaults as `rank` for unspecified performance
  parameters: `--metric all`, `--thinking false`, `--input-length 10k`, and
  `--time-window 6h`. Only pass a flag when the user explicitly requests a
  different value.
- `--model`: required for `trend` and `input-length`; exact format
  `name@version:deployment`, where deployment is `default` or `fast`. Repeat
  `--model` to view multiple models in one trend request. At most 50 unique selectors.
- `rank` supports `--keyword`, `--deployment`, `--top 1..50`,
  `--order asc|desc`, and `--compare default-deployment|none`.
- Read `metadata`, `warnings`, and `disclaimer` in JSON output. A positive
  `data_delay_minutes` means the data is not real time.
