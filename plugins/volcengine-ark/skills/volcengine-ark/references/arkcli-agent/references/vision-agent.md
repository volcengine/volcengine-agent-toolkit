# Vision / Ultra Agent（火山）

## 先确定创建类型

- 用户只说“创建一个会生图的 Agent”：这描述的是工具能力，不自动指定 Vision。可按 [普通 Agent 的工具模型绑定](agent.md#工具绑定模型仅部分工具支持)配置；普通 Agent 使用多模态工具同样可能受服务端开白约束。
- 用户明确要求 Vision / Ultra / 视觉创作类型：使用 `BaseAgent: ultra_vision_agent_preview`。旧值 `multimodal_agent_preview` 仍可读取、复制，不主动迁移已有资源。普通类型是 `ark_agent_preview`，省略类型由后端按普通 Agent 处理。
- 召回文档中的 Vision 示例不能覆盖用户意图。类型选择会影响结果且上下文无法确定时，先澄清一次。
- 本页只针对火山；不据此宣称其他产品支持 Vision。

## 主模型、工具模型与权限

`Model.Id` 是 Agent 主模型；`Tools[].Configs[].Models[].ID` 是生图/视频工具模型，不能混用。

Vision 主模型用 `arkcli agent model list --usage vision --format json` 查询，与火山前端读取同一份视觉创作配置；`--env stg` 读取 stg 配置，不回退线上。返回 `items[].model` 是完整模型 ID，`default` 是配置原始标记，`default_model` 是按前端规则选出的默认 ID（第一个标记项，否则第一项）。配置顺序和版本白名单保持不变，缺少名称或版本的项会被跳过，完整 ID 忽略大小写去重。

可用 `--name` 按完整 ID 或展示名筛选；`default_model` 始终指向原目录的默认项，筛选后可能不在 items 中。Vision 查询每次读取当前配置，不使用 ArkModels 缓存；`--refresh-cache` 不改变这一行为。不支持 `--query`、`--primary-only`、`--include-all`，这些 ArkModels 选项不能用于扩大或缩小视觉版本白名单。查询失败不能当作无候选，也不回退普通模型列表；空目录应说明当前环境未配置候选。

目录候选不等于账号已开白或模型已开通。用户提供明确主模型 ID 时保留并交由服务端校验，不增加创建前的强制白名单拦截；没有 ID 时从查询结果选择，不硬编码示例模型，不反复查源码寻找候选。BytePlus 不支持此查询。

### 模型开白引导

`--usage vision` 对筛选后每个候选额外查询当前账号可见的基础模型及精确版本，返回 `items[].model_access`，不隐藏候选、不改 `default_model`。判断与前端一致：`ListFoundationModels` 精确 Names 命中，再查 `ListFoundationModelVersions` 精确 ModelVersions 命中；不根据 `Owned`、计费项或 MA 功能权限判断模型开白。

- `status=visible`：账号能看到模型和版本；仍不保证计费开通、Vision 功能授权或实际推理成功。
- `status=requires_whitelist`：模型或版本未出现在当前账号查询结果中。展示该项 `application_url` 和模型 ID，引导用户申请，等待开白后重查；不要自动提交申请、换模型，或建议 `agent activate` / `models activate` 代替开白。
- `status=unknown`：查询失败或响应缺失，不能当作未开白。按 `reason` 区分模型或版本查询阶段，检查登录、网络及接口状态后重查。

申请入口使用当前查询返回的 `application_url`，与前端一致，不自行拼接地址。本能力只查询和提供引导，不新增创建前本地硬拦截，也不自动发起申请。开白查询不复用 ArkModels 的 5 分钟缓存，每次重查当前账号状态；可以用 `--name` 缩小查询范围。`--format json` 的退出码 0 表示目录查询完成，不能替代逐项检查 `model_access.status`。旧版没有此字段时，不能把字段缺失解释成已开白。

仅需要自行选择工具模型时查询 `agent model list --usage tool --format json`，按生图/视频模态选择真实返回的 `items[].model`。已有明确 ID 时不增加资格前置拦截。工具模型对象支持 `ID`、`Name`、`Version`、`Default`；`ID` 是实际绑定，Name/Version 由后端解析回显。

新建时优先为启用的生成工具显式绑定已确认模型。省略 Models 依赖服务端默认配置，不保证可用；若返回 `default model endpoint for tool "image_generate" is not configured`，说明缺少工具默认模型，不是主模型错误或 MA 未开通。查询工具候选、确认具体版本的输出模态后补齐该工具的 Models，保留其他工具配置；不要重复发送相同请求、替换主模型或开通服务来试错。创建后仍须回读绑定，配置成功不代表生成成功。

MA 服务开通、Vision 账号/项目开白、模型可用性是不同检查。`agent activate` 不授予 Vision 开白。遇到 `FunctionNotAllowed` 应报告权限问题和服务端 RequestId，不自动换账号、改成普通类型或绕过确认调用 raw API。

## 请求参数与模板

当前服务端要求：

- `Model.ReasoningEffort: high`；前端默认 `ServiceTier: default`。
- 基础工具集 `agent_toolset_20260916`（服务端兼容 20260701）与多模态工具集 `agent_toolset_multimodal_20260825` 同时存在。
- 多模态工具启用 `image_generate`、`visual_search`、`compose_video`、`general_search`、`todo_write`；`video_generate` 按用户需求启用。虽然前端只在启用视频时强制视频合成，CLI 模板按当前后端约束保留 compose_video/general_search。
- 前端 Vision 关闭基础 `web_search`；不是关闭多模态 `general_search`。
- `--tool` 是整个 Tools 数组替换；只传 image_generate 会丢掉必要工具集。CLI 不会因 `--base-agent` 自动补齐 Vision 工具或改模型参数。

下面是请求结构模板，不是已验证可执行的模型配置。将占位 ID 换成本次确认的真实 ID 后保存为 `vision-agent.json`；不用视频时不附带视频模型绑定。

```json
{
  "Name": "arkcli-vision-agent",
  "BaseAgent": "ultra_vision_agent_preview",
  "Model": {"Id": "<confirmed-vision-main-model-id>", "ReasoningEffort": "high", "ServiceTier": "default"},
  "System": "根据用户需求生成创作成果，使用可用工具并说明输出文件。",
  "Tools": [
    {
      "Type": "agent_toolset_20260916",
      "DefaultConfig": {"Enabled": true, "PermissionPolicy": {"Type": "always_allow"}},
      "Configs": [{"Name": "web_search", "Enabled": false}]
    },
    {
      "Type": "agent_toolset_multimodal_20260825",
      "DefaultConfig": {"Enabled": false, "PermissionPolicy": {"Type": "always_allow"}},
      "Configs": [
        {"Name": "image_generate", "Enabled": true, "Models": [{"ID": "<confirmed-image-model-id>", "Default": true}]},
        {"Name": "visual_search", "Enabled": true},
        {"Name": "compose_video", "Enabled": true},
        {"Name": "general_search", "Enabled": true},
        {"Name": "todo_write", "Enabled": true},
        {"Name": "video_generate", "Enabled": false}
      ]
    }
  ]
}
```

权限策略应与用户要求一致；模板的 always_allow 不是额外授权。按实际需求设置 system、Skills、MCP，不因创建 Vision 自动添加无关资源。

```bash
arkcli agent agent create \
  --file ./vision-agent.json \
  --dry-run --format json
```

Preview 零网络，只检查输入与请求形态，不证明权限、模型和后端约束通过。复述配置、未决项和费用影响，按所属 Skill 的宿主授权契约取得本轮授权后，移除 `--dry-run` 执行一次，再 `agent agent get <returned-agent-id> --format json`。宿主使用 permission Widget 时，不在聊天中重复确认或自行补开通授权参数。

## 回读、复制与失败处理

- 核对 `BaseAgent`、`Model.Id/ReasoningEffort`、完整 Tools、`Configs[].Models[].ID`；table 只展示摘要，核对绑定用 JSON/YAML。
- `+new-agent --fork <id>` 保留基座类型和工具模型。修改工具仍须提交完整数组；不自动升级工具集、不迁移旧类型。该命令不支持 `--dry-run`；先用 `agent agent get <id>` 核对源配置，复述复制与覆盖内容并取得本轮授权，再执行 fork。不能为了预览改用另一条创建流程，也不能将源配置读取当作复制已完成。
- update / `+iterate` 可修改模型参数和工具，但不支持改变 BaseAgent。Session override 也不能切换基座类型，只继承源类型并按服务端约束校验覆盖后的配置。
- 返回字段缺失时记录实际 CLI 版本、原始请求和输出，不声称已落库；检查版本兼容性，不用重复 create 试探。创建超时先只读核对是否已经创建，避免重复资源。
- 工具模型透传、创建成功、实际生成图片是三个不同验收层次。仅完成预览/创建不得声称生图端到端成功；运行 Session 可能产生沙箱与模型费用。
