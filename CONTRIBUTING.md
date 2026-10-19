# Contributing to volcengine-agent-toolkit

感谢你对 volcengine-agent-toolkit 的关注。本文档说明如何参与本项目。

---

## 项目维护模式

**本项目由 Volcengine 团队内部维护，目前不接受外部 Pull Request。**

我们选择这种模式的原因：

- 本仓库的 skill 需要与火山引擎内部产品迭代保持同步
- skill 质量需要通过内部 CI / e2e 测试验证
- 避免外部贡献者在 CLA、合规审批上花费不必要的时间

如果你提交 PR，我们会礼貌地关闭并请你转为 issue 反馈想法。这不是对你贡献的否定——只是当前阶段的协作方式。

> **未来计划**：当项目成熟、外部生态形成后，我们会重新评估是否开放外部贡献。届时本文档会更新。

---

## 你可以怎样帮助本项目

### 🐛 报告 Bug

最有价值的反馈方式。请在 [Issues](https://github.com/volcengine/volcengine-agent-toolkit/issues) 中提交，建议包含：

- **复现步骤**：从零到出现问题的完整命令序列
- **期望行为** vs **实际行为**
- **环境信息**：
  - Agent host（Claude Code / Codex / Gemini CLI）+ 版本
  - 操作系统
  - `ve` CLI 版本（如适用）
  - 涉及的 skill 名称

### 💡 提出 Feature Request

在 [Issues](https://github.com/volcengine/volcengine-agent-toolkit/issues) 中描述：

- **场景**：你希望在什么情况下用到这个能力
- **当前痛点**：现在你是怎么解决的，为什么不够好
- **期望形态**：希望的 skill 名称、触发条件、典型对话样例

我们会把合理的需求纳入内部 roadmap。

### 📖 改进文档

如果你发现：

- README / docs 里的内容**错误**（命令跑不通、链接 404、术语不准）
- 描述**有歧义**（多种理解都说得通）
- 缺少关键的**前置条件说明**

请在 Issue 中指出具体位置（文件 + 行号）和建议。

### 🔒 报告安全漏洞

**请勿在公开 Issue 中报告安全漏洞。** 参见 [SECURITY.md](./SECURITY.md)。

---

## 行为准则

参与本项目（包括提 Issue、评论、Discussion）即表示你同意遵守 [Code of Conduct](./CODE_OF_CONDUCT.md)。

---

## 内部贡献者

> 以下章节仅对 Volcengine 团队的内部维护者适用。

如果你是 Volcengine 团队成员，需要新增或修改 skill，请通过内部代码仓库（Bits-Code）的 MR 流程提交变更，由 reviewer 通过后同步到 GitHub。

---

## 许可证

本仓库采用 [MIT License](./LICENSE)。
