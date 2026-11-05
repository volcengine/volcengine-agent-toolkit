# 检索模板管理

仅查找、使用或管理检索模板时读取。执行保存的查询再按 advanced-query.md 进入查询；导出读 result-export.md。身份、确认和用户沟通见 rules.md；仅管理模板不检查日志历史覆盖。系统模板路径携带已核实的 expected-account-id；自定义模板由 TLS 工具核实身份。

系统模板列表调用示例（默认 `--source system`）：

```bash
python3 scripts/cloud_trail.py --expected-account-id <account-id> advanced templates list --source system --max-results 10
python3 scripts/cloud_trail.py --expected-account-id <account-id> advanced templates list --source system --max-results 10 --next-token '<next-token>'
```

每次读取一页，返回 `TemplateList`（名称、分类及查询语句）、`NextToken`、`HasMore`、调用身份及原始响应元数据。
有更多结果时按需使用返回的 `NextToken` 继续读取，不能把当前页视为全部模板。该入口无需加载 `volcengine-tls`，
也无需 TLS 主题或数据覆盖检查；需要 `ve` 支持 `ListSearchTemplates`，调用失败不能当作模板列表为空。
系统模板详情通过列表全页读取并按名称精确匹配；同名时可指定分类，不任意选第一条：

```bash
python3 scripts/cloud_trail.py --expected-account-id <account-id> advanced templates describe --source system --template-name '<name>' --category '<category>'
```

## 自定义模板

通过 `volcengine-tls` 查看当前支持的保存查询功能及接口说明，核实 TLS 身份、地域和主题后执行。仅管理模板时检查模板自身的权限与内容；执行保存的查询时再核对日志覆盖和索引。

- 查看：按主题列出保存查询，读取选定模板的名称和语句。
- 使用：补齐本次查询范围与条件，转入高级检索；临时调整保留在本次查询中。
- 保存或复制：按用户指定名称保存查询语句，回读核对主题、名称及内容。
- 修改：优先使用当前服务支持的更新能力；需要替换时，先另存并验证新模板，保留原模板供用户决定是否清理。
- 删除：确认具体模板后执行，回读核实结果，保留日志数据。

写操作按 rules.md 核对授权和影响，结果不明时先读取状态。工具能力或鉴权尚待确认时，说明具体缺项及继续所需条件。
