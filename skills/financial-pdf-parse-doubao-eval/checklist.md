# financial-pdf-parse-doubao-eval 自检清单

- [ ] `SKILL.md` frontmatter 合法。
- [ ] 不包含真实密钥。
- [ ] 包含价格预估与用户确认。
- [ ] 包含短轮询，不死循环。
- [ ] 包含 PDF 专用结果模板。
- [ ] 包含金融财报后处理。
- [ ] 包含输出 schema。
- [ ] 包含错误码。
- [ ] 包含 fallback synthetic 不计入真实评测声明。
- [ ] 脚本支持 Windows / Linux。
- [ ] 结果文件路径规范。
- [ ] evals 覆盖正常、复杂、异常场景。
- [ ] `--output-profile minimal|standard|debug` 可用。
- [ ] `validate_outputs.py --output-profile` 可校验三种 profile。
- [ ] `quality_checks.json` 包含 data_authenticity、table_statistics、metric_statistics。
- [ ] 报告明确“输出完整性检查通过不等于解析准确率 100%”。
- [ ] Ground Truth 准确率以 `gt_eval_result.json` 为准。
