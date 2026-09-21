# 火山商品清单

商品名 → 商品编码的映射，用于将用户表述定位到具体商品；同时作为「用户未明确商品」时商品清单的数据来源。商品名称与火山引擎官网产品页保持一致。

`ProductCode` 是流程内部字段，**不对客展示、也不在对客表述中提及**；面向用户一律只说商品名称。

## 商品清单

| 分类 | 商品 | ProductCode | 关键词（中英，大小写不敏感） | 说明 |
| --- | --- | --- | --- | --- |
| AI | 火山方舟 | `ark_bd` | 方舟, ark, 火山方舟, 豆包大模型, doubao, 大模型, 模型推理, 接入点, endpoint | 一站式大模型服务平台，提供模型精调、推理、评测等全方位功能与服务。 |
| AI | 开源LLM模型 | `ark_open_source_llm` | 开源模型, 开源大模型, deepseek, qwen, kimi, open source llm | 在火山方舟上调用 DeepSeek 等第三方开源大模型。 |
| AI | 火山方舟订阅套餐 | `ark_subscription` | 方舟套餐, 订阅套餐, 模型套餐, ark subscription | 火山方舟的预付费套餐包，按约定额度抵扣模型调用消耗。 |
| AI | Viking 知识库 | `VDB_KnowledgeBase` | viking 知识库, 知识库, rag, 检索增强, knowledge base | 检索增强生成（RAG）服务，智能解析结构化与非结构化文档，结合大模型推理提供问答。 |
| AI | VikingDB 向量数据库 | `VikingDB` | vikingdb, 向量数据库, 向量检索, 向量库, embedding | 大规模云原生向量数据库，高效存储和检索海量多模态向量数据。 |
| AI | Viking AI 搜索 | `REC-SaaS-LLM-SEARCH` | viking 搜索, ai 搜索, 智能搜索, 语义搜索 | 面向大模型时代的 AI 搜索推荐引擎。 |
| AI | 记忆库 Mem0 | `VikingDB_Memory` | 记忆库, mem0, 长期记忆, agent memory | 为智能体构建专属长效记忆系统，完成记忆的抽取、存储与精准调用。 |
| AI | TRAE CN | `Trae` | trae, ai ide, ai 编程, 智能编程, 编程助手, 代码助手, coding plan | 基于 AI 的智能开发环境，提供代码补全、智能问答与 coding agent 能力。 |
| AI | ArkClaw | `ArkClawX` | arkclaw, 编程智能体, coding agent | 7×24 在线的专属智能伙伴，承接研发任务的自主规划与执行。 |
| AI | 扣子 | `veCoze_Pro` | 扣子, coze, 智能体平台, agent 平台, bot 搭建 | 一站式 AI Agent 开发平台，提供多种开发模式与框架，覆盖开发到部署全流程。 |
| AI | 图像生成大模型 | `Doubao-Seedream` | seedream, 豆包图像, 文生图, 图生图, 图像生成, image generation | 提供文生图、图生图及图像特效三大核心能力。 |
| AI | 即梦AI-图片生成3.0系列 | `DreaminaAI_Seed_ImageG` | 即梦图片, 即梦文生图, dreamina 图片 | 即梦 AI 的图片生成能力，面向营销与创意场景的图像创作。 |
| AI | 即梦AI-视频生成 | `DreaminaAI_Seed_VideoG` | 即梦, dreamina, seedance, 视频生成, 文生视频, 图生视频 | 即梦 AI 的视频生成能力，支持文生视频、图生视频与镜头控制。 |
| AI | 豆包语音合成模型3.0 | `SeedTTS3.0` | 语音合成, tts, 文字转语音, 豆包语音合成, seedtts | 超自然的语音合成能力，善于表达多种情绪、演绎丰富情景。 |
| AI | 声音复刻 | `VoiceCloning` | 声音复刻, 音色复刻, 克隆音色, voice cloning | 最短 5 秒实现声音复刻，高度还原音色相似度与声音自然度。 |
| AI | 豆包流式语音识别模型2.0 | `Doubao_Seed_ASR_Streaming_2.0` | 流式语音识别, 实时语音识别, asr, 语音转文字 | 面向实时音频流的低延迟语音识别，支持多方言混合识别。 |
| AI | 豆包录音文件识别模型2.0 | `Doubao_Seed_ASR_AUC_2.0` | 录音文件识别, 音频转写, 离线语音识别, auc | 对已有音视频文件做批量转写。 |
| AI | 豆包语音场景大模型-豆包端到端实时语音大模型 | `Doubao_scene_SLM_Doubao_realtime_voice_model` | 实时语音大模型, 语音对话, 端到端语音, realtime voice | 深度融合语音与文本模态的端到端语音对话模型。 |
| AI | 豆包语音场景大模型-豆包同声传译大模型 | `Doubao_scene_SLM_Doubao_SI_model` | 同声传译, 同传, 实时翻译, simultaneous interpretation | 提供实时语音跨语种翻译。 |
| AI | 机器学习平台 | `ML` | 机器学习平台, mlp, vemlp, 模型训练, 训练任务, 推理服务 | 面向机器学习应用开发者的企业级云原生平台，提供建模调试工具与高性能推理服务。 |
| AI | AI 数据湖服务 | `LAS_SaaS_AI` | las, ai 数据湖, 数据湖, 多模态数据管理 | 构建 AI 数据湖，高效存储、管理和处理多模态数据，无缝对接火山方舟与机器学习平台。 |
| 计算 | 云服务器 | `ECS` | ecs, 云服务器, 服务器, 实例, cloud server | 提供稳定的弹性计算服务，通过实时增减计算资源适应业务变动。 |
| 计算 | GPU 云服务器 | `GPU_Server` | gpu, gpu 服务器, 显卡实例, 推理机器, 训练机器 | 提供 GPU 算力的弹性计算服务，适用于机器学习、视觉处理等场景。 |
| 计算 | 高性能计算GPU云服务器 | `HPC_GPU` | hpc gpu, 高性能 gpu, 大规模训练, 高性能计算 | 面向大规模并行训练的高性能 GPU 集群实例。 |
| 计算 | 弹性裸金属服务器 | `ECS_BareMetal` | 裸金属, 物理机, bare metal, ebm | 提供高性能算力服务与安全物理隔离能力。 |
| 计算 | 容器服务 | `VKE` | vke, 容器服务, kubernetes, k8s, 容器集群 | 以容器为核心的高性能 Kubernetes 容器集群管理服务。 |
| 计算 | 弹性容器 | `VCI` | vci, 弹性容器, 容器实例, serverless 容器 | Serverless 容器化计算服务，与容器服务 VKE 无缝集成，按实际运行时长计费。 |
| 计算 | 函数服务 | `veFaaS` | vefaas, 函数计算, 函数服务, serverless, faas, function | 事件驱动的无服务器函数托管计算平台，支持快速创建和部署函数。 |
| 计算 | 镜像仓库 | `cr` | cr, 镜像仓库, 容器镜像, registry, harbor | 安全高可用的容器镜像托管服务，支持镜像全生命周期管理。 |
| 计算 | 镜像服务 | `IMS` | ims, 镜像服务, 自定义镜像, image | 云服务器镜像的制作、导入、共享与跨地域复制。 |
| 计算 | 边缘计算节点 | `veEN` | 边缘计算, veen, 边缘节点, edge | 基于全域覆盖的边缘节点，提供弹性、可靠的异构算力与低时延网络资源。 |
| 计算 | 云手机 | `android_cloud` | 云手机, 云真机, android cloud, 云游戏手机 | 跨终端虚拟安卓云服务，提供稳定的安卓实例与低延迟串流技术。 |
| 存储 | 对象存储 | `TOS` | tos, 对象存储, object storage, bucket, 桶, 存储桶 | 海量、安全、低成本、高可靠的分布式云存储服务。 |
| 存储 | 弹性块存储 | `volume` | 云盘, 块存储, ebs, volume, 数据盘, 系统盘 | 为云服务器提供高可用、高可靠、高性能的块存储设备。 |
| 存储 | 弹性文件存储 | `FileNAS` | 弹性文件存储, efs, nas 极速型, filenas | 弹性伸缩、极致性能的 AI 云原生文件存储。 |
| 存储 | 文件存储 NAS 容量型 | `veFileNAS` | nas, 文件存储, nfs, 共享文件, vefilenas | 大容量共享文件存储，适合文件共享与内容管理场景。 |
| 存储 | 文件存储 vePFS | `vePFS` | vepfs, 并行文件系统, 高性能文件存储, pfs | 高吞吐、低延时、可扩展的并行文件存储服务。 |
| 存储 | 大数据文件存储 | `CloudFS` | cloudfs, 大数据文件存储, hdfs, 数据加速 | 支持 HDFS 语义的大数据文件存储，提供数据加速与多模式支持。 |
| 存储 | 云备份 | `CBR` | 云备份, 备份, cbr, 快照备份, 容灾备份 | 云上产品的统一灾备平台，集中管理数据备份与恢复。 |
| 数据库 | 云数据库 MySQL 版 | `RDS for MySQL` | rds mysql, mysql, 云数据库 mysql, 关系型数据库 | 即开即用、稳定可靠、灵活弹性的关系型数据库服务。 |
| 数据库 | 云数据库 PostgreSQL 版 | `RDS for PostgreSQL` | rds postgresql, postgresql, pg, 云数据库 pg | 完全兼容原生 PostgreSQL 的关系型数据库服务。 |
| 数据库 | 云数据库 SQL Server 版 | `RDS_for_SQL_Server` | sql server, rds sqlserver, mssql | 拥有正版授权、高度兼容微软生态的数据库服务。 |
| 数据库 | 云数据库 veDB MySQL 版 | `veDB for MySQL` | vedb, vedb mysql, 云原生数据库, 存算分离数据库 | 新一代分布式关系型数据库，完全兼容 MySQL。 |
| 数据库 | 缓存数据库 Redis 版 | `veDB_for_Redis` | redis, 缓存, 缓存数据库, kv 缓存 | 兼容 Redis 的缓存数据库，可用作缓存或数据持久化存储。 |
| 数据库 | 文档数据库 MongoDB 版 | `veDB for DocumentDB` | mongodb, 文档数据库, mongo | 开箱即用、完全兼容原生 MongoDB 的云数据库服务。 |
| 数据库 | 表格数据库 HBase 版 | `HBase` | hbase, 表格数据库, 宽表, 列式存储 | 基于 Apache HBase 的全托管数据库服务。 |
| 数据库 | 向量数据库 Milvus 版 | `Milvus_for_VectorDB` | milvus, milvus 向量库, 托管 milvus | 100% 兼容开源 Milvus 的云原生向量检索引擎。 |
| 数据库 | 云搜索服务 | `ESCloud` | 云搜索, elasticsearch, es, escloud, 全文检索 | 全托管一站式信息检索和分析平台，支持全文、向量、混合搜索。 |
| 数据库 | 数据库传输服务 | `DTS` | dts, 数据迁移, 数据同步, 数据订阅, 数据库迁移 | 一体化数据库数据传输管理服务，支持业务不停服迁移上云。 |
| 数据库 | 数据库工作台 | `DBW` | dbw, 数据库工作台, 数据库 gui, sql 窗口 | 面向多类型数据库生命周期管理的统一云管平台。 |
| 网络 | 公网 IP | `EIP` | eip, 弹性公网ip, 公网ip, 弹性ip | 可独立购买和持有的公网 IP 地址资源。 |
| 网络 | 共享带宽包 | `BandwidthPackage` | 共享带宽包, 带宽包, bandwidth package | 支持复用和共享带宽的云资源，提供多种计费方式。 |
| 网络 | 共享流量包 | `TrafficPackage` | 流量包, 共享流量包, traffic package | 预付费流量资源包，抵扣公网出流量费用。 |
| 网络 | NAT 网关 | `NAT_Gateway` | nat, nat 网关, snat, dnat | 为私有网络内的云服务器提供网络地址转换能力。 |
| 网络 | 负载均衡 | `CLB` | clb, 负载均衡, slb, 四层负载均衡 | 将访问流量按策略分发给多台后端服务器，提高系统整体可用性。 |
| 网络 | 应用型负载均衡 | `ALB` | alb, 应用型负载均衡, 七层负载均衡, http 负载均衡 | 面向 7 层互联网应用及云原生应用，基于内容精细化调度。 |
| 网络 | 网络型负载均衡 | `NLB` | nlb, 网络型负载均衡, 四层负载均衡, tcp 负载均衡 | 新一代四层负载均衡服务，支持更高性能的弹性转发能力。 |
| 网络 | 私网连接 | `PrivateLink_Endpoint` | 私网连接, privatelink, 终端节点, endpoint service | 通过终端节点建立私密的 VPC 间网络连接，避免公网访问风险。 |
| 网络 | 云企业网 | `CEN` | 云企业网, cen, 跨地域互通, 网络互通 | 通过自动路由分发学习，提供云上网络实例间高速稳定的互通能力。 |
| 网络 | 中转路由器 | `TransitRouter` | 中转路由器, transit router, tr, 路由中转 | 地域级路由器产品，支持灵活构建任意拓扑云上网络。 |
| 网络 | 专线连接 | `DirectConnect` | 专线, 物理专线, directconnect, 专线接入 | 连接本地数据中心与云上网络的高速、低时延专属通道。 |
| 网络 | VPN 连接 | `VPN` | vpn, ipsec, vpn 网关, 加密隧道 | 在 Internet 网络中建立临时、安全、可靠的通信隧道。 |
| 网络 | 全球加速 | `GA` | 全球加速, ga, 跨境加速, 网络加速 | 基于全球节点和骨干网，为游戏、协同办公等提供网络加速服务。 |
| 网络 | 云解析DNS | `DNS` | dns, 域名解析, 云解析, 解析记录 | 权威域名解析服务，支持智能线路与健康检查。 |
| 网络 | 私网解析PrivateZone | `PrivateZone` | privatezone, 私网解析, 内网域名, 内网 dns | VPC 内的私有域名解析服务。 |
| 网络 | API 网关 | `APIG` | api 网关, apig, 网关, api 管理 | 高扩展、高可用的云原生网关。 |
| 视频与分发 | 内容分发网络 | `CDN` | cdn, 内容分发, 加速, 静态加速 | 基于全球骨干网与海量加速节点，为多种类型内容提供高性能加速。 |
| 视频与分发 | 全站加速 | `dcdn` | 全站加速, dcdn, 动态加速, 动静态加速 | 为 API 和互联网应用提供安全、全链路的网络加速解决方案。 |
| 视频与分发 | 视频点播 | `vod` | 点播, vod, 视频点播, 转码, 媒资管理 | 包含媒资上传、管理、处理、音视频分发播放的全链路能力。 |
| 视频与分发 | 视频直播 | `LIVE` | 直播, live, 推流, 拉流, 直播转码 | 为企业和个人提供安全、稳定、专业的云端直播服务。 |
| 视频与分发 | 实时音视频 | `veRTC` | rtc, vertc, 实时音视频, 音视频通话, 连麦 | 提供全球范围内高质量、低延时的实时音视频通信能力。 |
| 视频与分发 | veImageX | `imagex` | imagex, veimagex, 图片处理, 图片加速, 图片存储 | 图像、文档等素材的上传、托管、智能处理和分发一站式解决方案。 |
| 大数据 | E-MapReduce | `E-MapReduce` | emr, e-mapreduce, hadoop, spark, 大数据集群 | 云原生开源大数据平台。 |
| 大数据 | 流式计算 Flink 版 | `realtime-compute-flink` | flink, 流式计算, 实时计算, 流处理 | 云原生全托管实时数据处理分析服务。 |
| 大数据 | ByteHouse | `bytehouse` | bytehouse, 云数仓, 数据仓库, clickhouse, olap | 极致性能、弹性伸缩的分析型数据库。 |
| 大数据 | 大数据研发治理套件 DataLeap | `DataLeap` | dataleap, 数据开发, 数据治理, 数据地图, 调度 | 一站式数据中台套件。 |
| 大数据 | 全域数据集成 DataSail | `DataSail` | datasail, 数据集成, 数据同步, etl | 高速稳定的批量和流式数据同步引擎。 |
| 大数据 | 增长分析 DataFinder | `finder` | 增长分析, datafinder, 用户行为分析, 埋点分析 | 一站式用户分析与运营平台。 |
| 中间件 | 消息队列 Kafka 版 | `Message_Queue_for_Kafka` | kafka, 消息队列 kafka, 消息中间件 | 基于 Apache Kafka 构建的高可用、高吞吐分布式消息队列服务。 |
| 中间件 | 消息队列 RocketMQ 版 | `Message_Queue_for_RocketMQ` | rocketmq, 消息队列 rocketmq, 事务消息 | 基于 Apache RocketMQ 构建的低延迟、高并发分布式消息中间件。 |
| 中间件 | 消息队列 RabbitMQ 版 | `Message_Queue_for_RabbitMQ` | rabbitmq, 消息队列 rabbitmq, amqp | 兼容开源 RabbitMQ 的高可用、低延迟消息服务。 |
| 中间件 | 云原生消息引擎 | `BMQ` | bmq, 云原生消息引擎, 存算分离消息 | 全托管、高吞吐、动态扩缩的分布式存算分离消息服务。 |
| 中间件 | 微服务引擎 | `MSE` | mse, 微服务引擎, 注册中心, 配置中心, nacos | 一键快速构建云原生微服务体系。 |
| 安全 | Web 应用防火墙 | `WAF` | waf, web 防火墙, 应用防火墙, 网站防护 | 防御恶意入侵和攻击，解决数据泄露、合规与隐私保护问题。 |
| 安全 | 云防火墙 | `CloudFirewall` | 云防火墙, cfw, 东西向防护, 访问控制 | SaaS 化防火墙，提供访问控制、流量可视化和日志审计。 |
| 安全 | 大模型应用防火墙 | `LLM_FW_Software` | 大模型防火墙, llm 防火墙, 提示词注入防护, ai 安全 | 防护提示词注入、敏感数据泄露及模型滥用等新型威胁。 |
| 安全 | DDoS高防 | `AntiDDoS_Pro` | ddos 高防, 高防 ip, 抗 d, ddos 防护 | 通过高防 IP 清洗大流量 DDoS 攻击。 |
| 安全 | DDoS原生防护 | `AntiDDoS-origin` | ddos 原生防护, 基础防护, origin | 直接为云上公网资产提供的 DDoS 防护能力。 |
| 安全 | 云安全中心 | `SecCenter` | 云安全中心, 主机安全, 安全中心, 漏洞检测 | 集资产管理、威胁检测、智能分析、协同响应于一体的云安全运营平台。 |
| 安全 | 云堡垒机 | `VBH` | 堡垒机, vbh, 运维审计, 特权访问 | 4A 统一的运维安全审计平台，保障企业安全合规。 |
| 安全 | 云加密机 | `CloudHSM` | 云加密机, hsm, cloudhsm, 密钥硬件 | 通过合规认证的硬件密码模块，保护密钥与加密运算。 |
| 安全 | 飞连 | `SealSuite` | 飞连, sealsuite, 零信任, 办公网络, 员工准入 | AI 时代的办公安全平台，帮助员工随时随地安全高效办公。 |
| 运维 | 日志服务 | `TLS` | tls, 日志服务, 日志项目, log service, volclog | 实时日志平台，提供日志采集、检索分析等功能。 |
| 运维 | 云监控 | `CloudMonitor` | 云监控, cloudmonitor, 监控告警, 监控大盘 | 监控云上资源健康状态，并及时对异常资源告警。 |
| 运维 | 托管 Prometheus | `VMP` | prometheus, vmp, 托管 prometheus, 指标监控 | 继承和对接 Prometheus 开源生态的免运维云原生监控引擎。 |
| 运维 | 应用性能监控全链路版 | `APMPlus` | apm, apmplus, 应用性能监控, 链路追踪, trace | 针对应用服务的品质、性能以及自定义埋点的 APM 服务。 |
| 通用 | 域名服务 | `Domain` | 域名, 域名注册, domain, 买域名 | 提供域名注册、转入、委托购买、管理等服务。 |
| 通用 | 证书中心 | `SSL` | ssl, ssl 证书, https 证书, 数字证书, 证书中心 | 数字证书全生命周期管理平台，提供 SSL 证书和私有 CA 服务。 |
| 通用 | 国内短信 | `sms` | 短信, sms, 验证码短信, 通知短信 | 面向国内的验证码、通知与营销短信发送。 |
| 通用 | 国际/港澳台短信 | `sms_intl` | 国际短信, 海外短信, sms intl, 港澳台短信 | 面向海外及港澳台地区的短信发送。 |

## 匹配方式

- 按表格顺序自上而下匹配，首个命中的行决定商品。
- 中文按包含关系匹配，不做分词；英文大小写不敏感。
- 一句话同时命中多个商品时，返回全部命中项，由调用方决定如何处理。
- 未命中时返回空，**不得猜测或拼写 `ProductCode`**——编码错误会让询价返回看似合理的错误价格，比明确告知未收录更有害。

## 分类

`分类` 列用于按品类筛选，取值：`AI`、`计算`、`存储`、`数据库`、`网络`、`视频与分发`、`大数据`、`中间件`、`安全`、`运维`、`通用`。用户按品类提问（如"有哪些 AI 商品"）时，只返回该分类下的商品。

## 未收录的商品

本清单只收录主流商品，不覆盖火山引擎全部售卖商品。用户所提商品不在表中时：

- 如实说明该商品未收录，引导用户前往火山引擎官网产品页确认；
- **可以**走 buy 动作（转交产品 skill 或引导控制台，均不需要商品编码）；
- **不能**通过 CLI 询价，price 动作需引导用户前往价格计算器；
- unsubscribe 动作请用户直接提供实例 ID，`Product` 从实例信息中读取。

## 新增商品

在表格中按分类归位追加一行，填齐五列。`商品` 须与官网产品页名称一致；`ProductCode` 必须取自官方文档或实际接口返回，无法核实时不要新增该行；`说明` 控制在一句话内，描述该商品解决什么问题。
