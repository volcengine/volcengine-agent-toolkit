#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""火山引擎合规最佳实践助手。

提供两个核心能力：
- recommend : 合规推荐（只读）。根据用户诉求（合规标准 / 关键词 / 关注风险等级），
              从火山引擎官方内置的合规包模板里推荐该开启哪些，并标出哪些已经开过，
              避免重复部署。
- overview  : 合规总览（只读）。汇总账号当前的合规态势——把全部已生效规则/合规包
              （官方内置 + 用户自定义都算）的评估结果，按类别（法规 / 最佳实践 /
              自定义）与严重度聚合成一份总览报告（md / csv / json）。

可选的写能力：
- apply     : 部署合规包（**写操作，需 --confirm**）。把 recommend 选中的官方内置
              模板真正部署为合规包；必要时先启用配置记录器。不加 --confirm 只 dry-run。

写操作边界：apply / enable-recorder 会改变账号状态，必须显式 --confirm 才执行；
recommend / overview 永远只读。合规「报告」与「资源修复」严格分离——本工具不修改
任何具体资源配置。

鉴权见 references/auth.md；本工具仅通过 `ve config <Action>` 调用，依赖调用方已完成
`ve` 鉴权。stdout 只承载结构化结果 / 产物路径，进度与诊断走 stderr。
"""

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

MAX_RESULTS = 100
BATCH = 100
RETRY = 2

# 内置合规包模板标签 -> 合规类别（用于报告分组与推荐过滤）。
LABEL_TO_CATEGORY = {"Law": "法规合规", "BestPractice": "最佳实践"}
CUSTOM_CATEGORY = "自定义"

# 规则风险等级 -> 报告严重度（四档）。
RISK_TO_SEVERITY = {"High": "Critical", "Medium": "High", "Low": "Medium"}
SEVERITY_ORDER = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "Unknown": 0}


def _eprint(*args):
    """进度/诊断打到 stderr，保持 stdout 只承载结构化结果。"""
    print(*args, file=sys.stderr, flush=True)


def ve_config(action, body):
    """调用 `ve config <action> --body <json>` 并解析 JSON 响应。

    步骤：
    1. 组装命令，body 以 JSON 传入（火山 CLI 统一 --body）。
    2. 失败按 RETRY 重试，覆盖后端偶发抖动。
    3. 解析 stdout；顶层 ResponseMetadata.Error 非空则抛出带 Action 的异常。
    """
    payload = json.dumps(body, ensure_ascii=False)
    last_err = None
    for attempt in range(RETRY + 1):
        proc = subprocess.run(
            ["ve", "config", action, "--body", payload],
            capture_output=True,
            text=True,
        )
        out = proc.stdout.strip()
        if proc.returncode == 0 and out:
            try:
                data = json.loads(out)
            except json.JSONDecodeError:
                last_err = f"[{action}] 响应不是合法 JSON：{out[:500]}"
            else:
                err = data.get("ResponseMetadata", {}).get("Error")
                if err:
                    raise RuntimeError(
                        f"[{action}] 接口错误 Code={err.get('Code')} "
                        f"Message={err.get('Message')}"
                    )
                return data.get("Result", {}) or {}
        else:
            last_err = f"[{action}] 退出码={proc.returncode} stderr={proc.stderr.strip()[:500]}"
        if attempt < RETRY:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{last_err}（已重试 {RETRY} 次）")


# ------------------------- 分页通用 -------------------------


def _paginate(action, body, item_key):
    """通用分页：反复调用 action 直到 NextToken 为空，聚合 item_key 列表。"""
    items = []
    next_token = ""
    while True:
        req = dict(body)
        req["MaxResults"] = MAX_RESULTS
        if next_token:
            req["NextToken"] = next_token
        result = ve_config(action, req)
        items.extend(result.get(item_key, []) or [])
        next_token = result.get("NextToken") or ""
        if not next_token:
            break
    return items


# ------------------------- 合规知识：内置模板 -------------------------


def list_builtin_templates(risk_levels=None):
    """列出官方内置合规包模板（带 Law / BestPractice 标签的即官方基线）。

    步骤：
    1. 分页拉取 ListConformancePackTemplates（服务端只返回 Released 模板）。
    2. 可选按 RiskLevel 过滤。
    3. 只保留带 Law / BestPractice 标签的官方模板；标签映射为合规类别。
    """
    body = {}
    if risk_levels:
        body["RiskLevel"] = risk_levels
    templates = []
    for t in _paginate("ListConformancePackTemplates", body, "ConformancePackTemplates"):
        labels = t.get("Labels", []) or []
        categories = [LABEL_TO_CATEGORY[l] for l in labels if l in LABEL_TO_CATEGORY]
        if not categories:
            continue
        templates.append(
            {
                "ConformancePackTemplateId": t.get("ConformancePackTemplateId"),
                "Name": t.get("Name", ""),
                "RiskLevel": t.get("RiskLevel", ""),
                "Description": t.get("Description", ""),
                "Labels": labels,
                "Categories": categories,
                "RuleTemplateCount": len(t.get("RuleTemplates", []) or []),
            }
        )
    return templates


def deployed_template_ids():
    """返回账号里已部署合规包所引用的模板 ID 集合（用于「已开启」标注）。"""
    ids = set()
    for p in _paginate("ListConformancePacks", {}, "ConformancePacks"):
        tid = p.get("ConformancePackTemplateId")
        if tid:
            ids.add(tid)
    return ids


# ------------------------- 合规推荐 -------------------------


def recommend(standard=None, keyword=None, risk_levels=None):
    """根据用户诉求推荐该开启的官方内置合规基线（只读）。

    步骤：
    1. 拉取官方内置模板目录（可选按风险等级过滤）。
    2. 按合规标准（Law / BestPractice 类别）与关键词过滤出候选。
    3. 对比账号已部署模板，给每条候选标注是否已开启。
    4. 已开启的排后、未开启的排前，便于优先推荐新增覆盖。
    """
    templates = list_builtin_templates(risk_levels)
    deployed = deployed_template_ids()
    kw = (keyword or "").strip().lower()
    want_category = LABEL_TO_CATEGORY.get(standard) if standard else None

    recs = []
    for t in templates:
        if want_category and want_category not in t["Categories"]:
            continue
        if kw and kw not in (t["Name"] + t["Description"]).lower():
            continue
        t = dict(t)
        t["AlreadyEnabled"] = t["ConformancePackTemplateId"] in deployed
        recs.append(t)

    recs.sort(key=lambda r: (r["AlreadyEnabled"], r["Name"]))
    return recs


# ------------------------- 部署预案与执行 -------------------------


def describe_rule_templates(template_ids):
    """批量拉取规则模板详情，返回 TemplateId -> 详情（含 Source / Parameters / AllowedEffects）。"""
    details = {}
    for i in range(0, len(template_ids), BATCH):
        batch = template_ids[i : i + BATCH]
        result = ve_config("DescribeRuleTemplates", {"TemplateIds": batch})
        for t in result.get("Templates", []) or []:
            details[t.get("TemplateId")] = t
    return details


def build_plan(template_id, name):
    """针对一个内置模板，生成 CreateConformancePack 的完整请求预案（只读）。

    步骤：
    1. 拉取合规包模板详情，拿到其包含的规则模板 ID 列表。
    2. 批量拉规则模板详情，为每个规则模板生成一条 RuleOverrides：
       - Name / RiskLevel 继承模板；
       - Effect 优先取 Audit（纯审计，避免自动修正误改用户资源）；
       - InputParameters 用必填参数的 DefaultValue 预填（缺省登记为待补）。
    3. 组装 CreateConformancePack body，返回预案 + 缺参提示。
    """
    detail = ve_config(
        "DescribeConformancePackTemplates",
        {"ConformancePackTemplateIds": [template_id]},
    )
    tpls = detail.get("ConformancePackTemplates", []) or []
    if not tpls:
        raise RuntimeError(f"未找到合规包模板 {template_id}（可能不可见或非 Released）")
    pack_tpl = tpls[0]
    rule_tpl_ids = pack_tpl.get("RuleTemplates", []) or []
    rule_details = describe_rule_templates(rule_tpl_ids) if rule_tpl_ids else {}

    overrides = []
    missing_params = []
    for rid in rule_tpl_ids:
        rt = rule_details.get(rid, {})
        allowed = rt.get("AllowedEffects", []) or []
        effect = "Audit" if "Audit" in allowed else (allowed[0] if allowed else "")
        input_params = {}
        for p in rt.get("Parameters", []) or []:
            if not p.get("IsCompulsory"):
                continue
            if p.get("DefaultValue") is not None:
                input_params[p["Name"]] = p["DefaultValue"]
            else:
                missing_params.append({"RuleTemplateId": rid, "Parameter": p.get("Name")})
        overrides.append(
            {
                "RuleTemplateId": rid,
                "Effect": effect,
                "Name": (rt.get("TemplateName") or f"rule-{rid[:8]}")[:100],
                "Description": rt.get("Description", "")[:100],
                "RiskLevel": rt.get("RiskLevel") or pack_tpl.get("RiskLevel") or "Medium",
                "InputParameters": input_params,
            }
        )

    body = {
        "Name": name,
        "Description": (pack_tpl.get("Description") or name)[:100],
        "RiskLevel": pack_tpl.get("RiskLevel") or "Medium",
        "ConformancePackTemplateId": template_id,
        "RuleOverrides": overrides,
    }
    return {
        "CreateConformancePackBody": body,
        "BaselineName": pack_tpl.get("Name", ""),
        "RuleTemplateCount": len(rule_tpl_ids),
        "MissingCompulsoryParameters": missing_params,
    }


def recorder_status():
    """查询配置记录器状态，返回记录器列表（空表示未启用）。"""
    result = ve_config("DescribeConfigurationRecorders", {"MaxResults": MAX_RESULTS})
    return result.get("ConfigurationRecorders", result.get("Recorders", [])) or []


def enable_recorder(confirm):
    """开启配置记录器（写操作，需 confirm）。

    步骤：
    1. PutConfigurationRecorder 全量资源类型（IncludeAllResourceTypes=true）。
    2. StartConfigurationRecorder 启动记录。
    未 confirm 时只返回将要执行的动作说明。
    """
    actions = [
        ("PutConfigurationRecorder", {"IncludeAllResourceTypes": True}),
        ("StartConfigurationRecorder", {}),
    ]
    if not confirm:
        return {"DryRun": True, "WouldRun": [a for a, _ in actions]}
    for action, body in actions:
        ve_config(action, body)
    return {"DryRun": False, "Ran": [a for a, _ in actions]}


def apply_pack(plan, confirm):
    """按预案部署合规包（写操作，需 confirm）。

    步骤：
    1. 若有缺失必填参数，拒绝执行并提示补齐。
    2. 未 confirm 时只回显将要创建的合规包摘要（dry-run）。
    3. confirm 时调用 CreateConformancePack，返回新合规包 ID。
    """
    if plan.get("MissingCompulsoryParameters"):
        raise RuntimeError(
            "存在缺省的必填参数，请补齐 InputParameters 后再部署："
            + json.dumps(plan["MissingCompulsoryParameters"], ensure_ascii=False)
        )
    body = plan["CreateConformancePackBody"]
    if not confirm:
        return {
            "DryRun": True,
            "WouldCreate": {
                "Name": body["Name"],
                "TemplateId": body["ConformancePackTemplateId"],
                "Rules": len(body.get("RuleOverrides", [])),
            },
        }
    result = ve_config("CreateConformancePack", body)
    return {"DryRun": False, "ConformancePackId": result.get("ConformancePackId")}


# ------------------------- 合规总览：来源/类别归类 -------------------------


def load_rules(conformance_pack_id=None):
    """加载账号内已生效规则，返回 RuleId -> 规则元信息（含所属合规包/模板）。"""
    body = {"RuleStatus": ["Enabled"]}
    if conformance_pack_id:
        body["ConformancePackId"] = conformance_pack_id
    rules = {}
    for r in _paginate("ListRules", body, "Rules"):
        rid = r.get("RuleId")
        if rid:
            rules[rid] = {
                "RuleId": rid,
                "RuleName": r.get("RuleName", ""),
                "RiskLevel": r.get("RiskLevel", ""),
                "ConformancePackId": r.get("ConformancePackId", ""),
                "RuleTemplateId": r.get("RuleTemplateId", ""),
                "Effect": r.get("Effect", ""),
            }
    return rules


def build_category_index():
    """建立「合规包 ID -> 合规类别」映射，用于给规则归类（法规 / 最佳实践 / 自定义）。

    步骤：
    1. 拉取账号已部署合规包，得到 合规包 ID -> 模板 ID。
    2. 拉取官方内置模板目录，得到 模板 ID -> 类别（Law/BestPractice）。
    3. 合成 合规包 ID -> 类别；命中官方模板的归对应类别，其余归自定义。
    """
    pack_to_template = {}
    for p in _paginate("ListConformancePacks", {}, "ConformancePacks"):
        pack_to_template[p.get("ConformancePackId")] = p.get("ConformancePackTemplateId")
    template_categories = {
        t["ConformancePackTemplateId"]: t["Categories"] for t in list_builtin_templates()
    }
    pack_category = {}
    for pack_id, tid in pack_to_template.items():
        cats = template_categories.get(tid)
        pack_category[pack_id] = cats[0] if cats else CUSTOM_CATEGORY
    return pack_category


def classify_rule(rule, pack_category):
    """给规则判定合规类别与来源。

    规则：
    1. 规则所属合规包命中官方内置模板 -> 对应类别（法规 / 最佳实践），来源 BuiltIn。
    2. 否则归自定义类别，来源 Custom。
    """
    category = pack_category.get(rule["ConformancePackId"], CUSTOM_CATEGORY)
    source = "BuiltIn" if category in LABEL_TO_CATEGORY.values() else "Custom"
    return category, source


# ------------------------- 评估结果读取 -------------------------


def compliance_by_rules(rule_ids):
    """批量查询按规则聚合的合规统计，返回 RuleId -> {状态: 数量}。"""
    stats = {}
    for i in range(0, len(rule_ids), BATCH):
        batch = rule_ids[i : i + BATCH]
        result = ve_config("DescribeComplianceByRules", {"RuleIds": batch})
        for item in result.get("ComplianceByRules", []) or []:
            rid = item.get("RuleId")
            counts = {}
            for s in item.get("Compliance", {}).get("ComplianceStatistics", []) or []:
                ctype = s.get("ComplianceType")
                if ctype:
                    counts[ctype] = counts.get(ctype, 0) + int(s.get("Count", 0))
            if rid:
                stats[rid] = counts
    return stats


def noncompliant_resources(rule_id, limit):
    """分页拉取某规则下不合规资源明细（ComplianceTypes=NonCompliant，天然排除豁免）。"""
    resources = []
    next_token = ""
    while True:
        body = {
            "RuleId": rule_id,
            "ComplianceTypes": ["NonCompliant"],
            "MaxResults": MAX_RESULTS,
        }
        if next_token:
            body["NextToken"] = next_token
        result = ve_config("ListEvaluationResults", body)
        for e in result.get("EvaluationResults", []) or []:
            resources.append(
                {
                    "AccountId": e.get("AccountId", ""),
                    "ResourceId": e.get("ResourceId", ""),
                    "ResourceType": e.get("ResourceType", ""),
                    "Region": e.get("Region", ""),
                    "Annotation": e.get("Annotation", ""),
                }
            )
        next_token = result.get("NextToken") or ""
        if not next_token or (limit and len(resources) >= limit):
            break
    return resources[:limit] if limit else resources


def build_findings(rules, stats, pack_category, max_resources, no_detail):
    """把规则 + 合规统计聚合成 findings，并标注类别与来源（只保留有不合规资源的规则）。"""
    findings = []
    for rid, rule in rules.items():
        counts = stats.get(rid, {})
        non_compliant = counts.get("NonCompliant", 0)
        if non_compliant <= 0:
            continue
        category, source = classify_rule(rule, pack_category)
        findings.append(
            {
                "RuleId": rid,
                "RuleName": rule["RuleName"],
                "RiskLevel": rule["RiskLevel"] or "Unknown",
                "Severity": RISK_TO_SEVERITY.get(rule["RiskLevel"], "Unknown"),
                "Category": category,
                "Source": source,
                "ConformancePackId": rule["ConformancePackId"],
                "NonCompliantCount": non_compliant,
                "CompliantCount": counts.get("Compliant", 0),
                "Resources": [] if no_detail else noncompliant_resources(rid, max_resources),
            }
        )
    findings.sort(
        key=lambda f: (SEVERITY_ORDER.get(f["Severity"], 0), f["NonCompliantCount"]),
        reverse=True,
    )
    return findings


def summarize(findings, rules):
    """生成总览摘要（评估规则数、不合规规则数、严重度分布、类别分布、不合规资源总数）。"""
    by_sev, by_cat = {}, {}
    total = 0
    for f in findings:
        by_sev[f["Severity"]] = by_sev.get(f["Severity"], 0) + 1
        by_cat[f["Category"]] = by_cat.get(f["Category"], 0) + 1
        total += f["NonCompliantCount"]
    return {
        "EvaluatedRules": len(rules),
        "NonCompliantRules": len(findings),
        "NonCompliantResources": total,
        "BySeverity": by_sev,
        "ByCategory": by_cat,
        "GeneratedAt": datetime.now(timezone.utc).astimezone().isoformat(),
    }


# ------------------------- 报告渲染 -------------------------


def render_markdown(summary, findings, scope_label):
    """把摘要 + findings 渲染成 markdown 总览报告（按合规类别分节）。"""
    buf = io.StringIO()
    buf.write("# 火山引擎合规总览报告\n\n")
    buf.write(f"- 评估范围：{scope_label}\n")
    buf.write(f"- 生成时间：{summary['GeneratedAt']}\n")
    buf.write(f"- 评估规则数：{summary['EvaluatedRules']}\n")
    buf.write(f"- 不合规规则数：{summary['NonCompliantRules']}\n")
    buf.write(f"- 不合规资源总数：{summary['NonCompliantResources']}\n\n")

    buf.write("## 严重度分布\n\n| 严重度 | 不合规规则数 |\n| --- | --- |\n")
    for sev in ["Critical", "High", "Medium", "Low", "Unknown"]:
        if summary["BySeverity"].get(sev):
            buf.write(f"| {sev} | {summary['BySeverity'][sev]} |\n")

    buf.write("\n## 类别分布\n\n| 合规类别 | 不合规规则数 |\n| --- | --- |\n")
    for cat, cnt in summary["ByCategory"].items():
        buf.write(f"| {cat} | {cnt} |\n")

    buf.write("\n## 不合规明细\n\n")
    if not findings:
        buf.write("未发现不合规规则。\n")
        return buf.getvalue()

    # 按合规类别分节，节内已按严重度降序。
    categories = [CUSTOM_CATEGORY if c not in LABEL_TO_CATEGORY.values() else c
                  for c in dict.fromkeys(f["Category"] for f in findings)]
    for cat in dict.fromkeys(categories):
        group = [f for f in findings if f["Category"] == cat]
        if not group:
            continue
        buf.write(f"### 合规类别：{cat}\n\n")
        for f in group:
            buf.write(f"#### [{f['Severity']}] {f['RuleName'] or f['RuleId']} (`{f['RuleId']}`)\n\n")
            buf.write(f"- 风险等级：{f['RiskLevel']}　来源：{f['Source']}　"
                      f"所属合规包：{f['ConformancePackId'] or '-'}\n")
            buf.write(f"- 不合规资源：{f['NonCompliantCount']}　合规资源：{f['CompliantCount']}\n")
            if f["Resources"]:
                buf.write("\n| 账号 | 资源 ID | 资源类型 | 地域 | 说明 |\n"
                          "| --- | --- | --- | --- | --- |\n")
                for r in f["Resources"]:
                    anno = (r["Annotation"] or "").replace("\n", " ").replace("|", "\\|")
                    buf.write(
                        f"| {r['AccountId']} | {r['ResourceId']} | {r['ResourceType']} "
                        f"| {r['Region']} | {anno} |\n"
                    )
            buf.write("\n")
    return buf.getvalue()


def render_csv(findings):
    """把不合规资源逐行展开成 CSV。"""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Severity", "RiskLevel", "Category", "Source", "RuleId", "RuleName",
                "ConformancePackId", "AccountId", "ResourceId", "ResourceType",
                "Region", "Annotation"])
    for f in findings:
        rows = f["Resources"] or [None]
        for r in rows:
            w.writerow([
                f["Severity"], f["RiskLevel"], f["Category"], f["Source"],
                f["RuleId"], f["RuleName"], f["ConformancePackId"],
                r["AccountId"] if r else "",
                r["ResourceId"] if r else f"({f['NonCompliantCount']} non-compliant)",
                r["ResourceType"] if r else "",
                r["Region"] if r else "",
                (r["Annotation"] or "").replace("\n", " ") if r else "",
            ])
    return buf.getvalue()


def write_artifacts(summary, findings, scope_label, out_dir):
    """把 md / csv / json 三份产物落盘并返回路径。"""
    out_dir = out_dir or tempfile.mkdtemp(prefix="volc-compliance-")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    paths = {}
    md = os.path.join(out_dir, f"compliance-overview-{ts}.md")
    with open(md, "w", encoding="utf-8") as fp:
        fp.write(render_markdown(summary, findings, scope_label))
    paths["md"] = md
    csvp = os.path.join(out_dir, f"compliance-findings-{ts}.csv")
    with open(csvp, "w", encoding="utf-8", newline="") as fp:
        fp.write(render_csv(findings))
    paths["csv"] = csvp
    jsonp = os.path.join(out_dir, f"compliance-overview-{ts}.json")
    with open(jsonp, "w", encoding="utf-8") as fp:
        json.dump({"Summary": summary, "Findings": findings}, fp, ensure_ascii=False, indent=2)
    paths["json"] = jsonp
    return paths


# ------------------------- 子命令入口 -------------------------


def cmd_recommend(args):
    """recommend：根据诉求推荐该开启的官方内置合规基线（只读）。"""
    risk = args.risk_level.split(",") if args.risk_level else None
    recs = recommend(standard=args.standard or None, keyword=args.keyword or None, risk_levels=risk)
    print(json.dumps({"Recommendations": recs}, ensure_ascii=False, indent=2))
    enabled = sum(1 for r in recs if r["AlreadyEnabled"])
    _eprint(f"匹配 {len(recs)} 个官方内置基线，其中 {enabled} 个已开启、{len(recs) - enabled} 个待开启。")
    if len(recs) - enabled:
        _eprint("未开启的可用 apply 部署（写操作，需 --confirm）。")


def cmd_overview(args):
    """overview：汇总账号当前合规态势，按类别与严重度出总览报告（只读）。"""
    rules = load_rules(args.conformance_pack_id or None)
    scope_label = (f"合规包 `{args.conformance_pack_id}`"
                   if args.conformance_pack_id else "single-account 全量已生效规则")
    if not rules:
        _eprint("范围内没有已生效规则。可先用 recommend 看该开启哪些官方基线，再 apply 部署。")
        print(json.dumps({"Summary": {"EvaluatedRules": 0}, "Findings": []}, ensure_ascii=False))
        return
    pack_category = build_category_index()
    stats = compliance_by_rules(list(rules.keys()))
    findings = build_findings(rules, stats, pack_category, args.max_resources, args.no_detail)
    summary = summarize(findings, rules)
    paths = write_artifacts(summary, findings, scope_label, args.out_dir)
    _eprint("=== 合规总览完成 ===")
    _eprint(f"摘要：{json.dumps(summary, ensure_ascii=False)}")
    for k in ("md", "csv", "json"):
        _eprint(f"{k} 产物：{paths[k]}")
    print(json.dumps({"Summary": summary, "Artifacts": paths}, ensure_ascii=False))


def cmd_apply(args):
    """apply：把推荐的内置模板部署为合规包（写操作，需 --confirm）。"""
    plan = build_plan(args.template_id, args.name)
    result = {"Plan": {"Name": args.name, "Rules": plan["RuleTemplateCount"]}}
    if args.enable_recorder and not recorder_status():
        result["Recorder"] = enable_recorder(args.confirm)
    result["Pack"] = apply_pack(plan, args.confirm)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if plan["MissingCompulsoryParameters"]:
        _eprint("⚠️ 存在缺省必填参数，需补齐 InputParameters 后再部署。")
    if not args.confirm:
        _eprint("这是 dry-run。确认无误后加 --confirm 真正部署（写操作）。")
    else:
        _eprint("已部署。资源评估异步进行，稍后用 overview 读结果。")


def main():
    parser = argparse.ArgumentParser(description="火山引擎合规最佳实践助手")
    sub = parser.add_subparsers(dest="command", required=True)

    p_rec = sub.add_parser("recommend", help="按诉求推荐该开启的官方内置合规基线（只读）")
    p_rec.add_argument("--standard", default="", choices=["", "Law", "BestPractice"],
                       help="按合规标准过滤：Law（法规，如等保）/ BestPractice（最佳实践）")
    p_rec.add_argument("--keyword", default="", help="按名称/描述关键词过滤（如 等保、对象存储）")
    p_rec.add_argument("--risk-level", default="", help="按风险等级过滤，逗号分隔（Low,Medium,High）")
    p_rec.set_defaults(func=cmd_recommend)

    p_ov = sub.add_parser("overview", help="汇总账号当前合规态势出总览报告（只读）")
    p_ov.add_argument("--conformance-pack-id", default="", help="只看指定合规包（可选，默认全量）")
    p_ov.add_argument("--no-detail", action="store_true", help="只做规则级统计，不拉资源明细")
    p_ov.add_argument("--max-resources", type=int, default=200, help="每规则最多拉取明细数，0 不限（默认 200）")
    p_ov.add_argument("--out-dir", default="", help="产物输出目录，默认临时目录")
    p_ov.set_defaults(func=cmd_overview)

    p_ap = sub.add_parser("apply", help="把内置模板部署为合规包（写操作，需 --confirm）")
    p_ap.add_argument("--template-id", required=True, help="合规包模板 ID（来自 recommend）")
    p_ap.add_argument("--name", required=True, help="将要创建的合规包名称")
    p_ap.add_argument("--enable-recorder", action="store_true", help="recorder 未启用时一并启用")
    p_ap.add_argument("--confirm", action="store_true", help="真正执行写操作；不加则 dry-run")
    p_ap.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        _eprint(f"执行失败：{exc}")
        sys.exit(1)
