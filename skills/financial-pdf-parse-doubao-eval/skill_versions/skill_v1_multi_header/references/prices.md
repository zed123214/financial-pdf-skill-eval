# Pricing Reference

| parse_mode | unit_price_yuan_per_page | Usage |
|---|---:|---|
| `normal` | 0.02 | Fast parsing for digital PDFs. |
| `detail` | 0.04 | Deep parsing for scanned PDFs, dense financial tables, and formal evaluation. |

Formula:

```text
estimated_price_yuan = page_count * unit_price_yuan_per_page
```

All prices are estimates. Final fees are determined by the Volcengine bill.
