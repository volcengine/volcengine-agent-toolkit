# 检索模板管理

查找、使用或管理检索模板时读本文。执行模板中的查询时，再读 [高级检索](advanced-query.md)；需要导出时读 [查询结果导出](result-export.md)。账号、授权和结果说明遵循 [账号与操作规则](rules.md)。

只管理模板时，不需要检查历史日志是否齐全。系统模板通过 CloudTrail 查询，命令中传入已核实的 `--expected-account-id`；自定义模板通过 TLS 工具操作，单独核实其调用身份。

## 系统模板

列出系统模板（默认 `--source system`）：

```bash
python3 scripts/cloud_trail.py --expected-account-id <account-id> advanced templates list --source system --max-results 10
python3 scripts/cloud_trail.py --expected-account-id <account-id> advanced templates list --source system --max-results 10 --next-token '<next-token>'
```

每次返回一页模板，包括 `TemplateList` 中的名称、分类和查询语句，以及 `NextToken`、`HasMore`、调用身份和原始响应元数据。有更多结果时，按需用返回的 `NextToken` 继续查询，不把当前页当成全部模板。

查询系统模板不需要加载 `volcengine-tls`，也不需要 TLS 日志主题或历史日志检查，但 `ve` 必须支持 `ListSearchTemplates`。接口调用失败时说明错误，不能说模板列表为空。

查看详情时，脚本会读取全部列表页，按名称精确匹配。同名模板可以用分类区分，不直接选择第一条：

```bash
python3 scripts/cloud_trail.py --expected-account-id <account-id> advanced templates describe --source system --template-name '<name>' --category '<category>'
```

## 自定义模板

先按 `volcengine-tls` 查看当前支持的保存查询功能及接口说明，核实调用身份、地域和日志主题。只管理模板时，检查模板的权限和内容即可；要执行模板中的查询时，再检查日志是否包含所需时段和事件，以及索引是否支持查询。

- 查看：列出指定主题中的保存查询，查看模板名称和查询语句。
- 使用：补齐本次查询的时间范围和条件，按高级检索流程执行。临时调整查询时，不修改原模板。
- 保存或复制：用用户指定的名称保存查询语句，再读取模板，核对主题、名称和内容。
- 修改：优先使用服务已有的更新功能。如果需要另建模板替换，先保存并验证新模板，保留原模板，由用户决定是否删除。
- 删除：确认要删除哪个模板后执行，再查询确认是否已删除。删除模板不删除日志。

写操作遵循 rules.md 的授权要求。返回结果不明确时先查询状态，不重复写入。缺少功能、凭证或权限时，说明具体问题和继续操作需要的条件。
