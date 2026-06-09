# Evaluation Metrics

Required checks:

1. 表格数量检查。
2. 关键财务表识别检查。
3. 资产负债表勾稽：`资产总计 == 负债和所有者权益总计`，`负债合计 + 所有者权益合计 ~= 负债和所有者权益总计`。
4. 括号负数检查。
5. 小数点保留检查。
6. 期间列识别检查。
7. 噪声识别：`CONFIDENTIAL`、签名、盖章、临时图片 URL。
8. `pages_detail.json` schema 检查。
9. `parsed.md` 是否为空检查。
10. `result.json` business_code 检查。

`quality_checks.json`:

```json
{
  "checks": [
    {
      "name": "balance_equation_check",
      "statement": "合并资产负债表",
      "passed": true,
      "message": "资产总计等于负债和所有者权益总计"
    }
  ],
  "scores": {
    "table_count": 6,
    "financial_metric_count": 45,
    "balance_check_pass_rate": 1.0,
    "negative_number_detected": true,
    "noise_blocks_detected": true
  }
}
```
