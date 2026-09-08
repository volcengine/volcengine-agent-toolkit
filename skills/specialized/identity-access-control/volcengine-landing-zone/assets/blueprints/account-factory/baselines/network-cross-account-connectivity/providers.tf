provider "volcenginecc" {
  alias  = "member"
  region = var.region

  endpoints = {
    sts = "sts.volcengineapi.com"
  }

  # 底座凭证（用于发起 AssumeRole 的身份）不在此声明：
  # 由运行时环境变量 VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY /
  # 可选的 VOLCENGINE_SESSION_TOKEN / VOLCENGINE_REGION 提供。
  # 本 provider 仅负责"切到哪个成员账号"——由 account_id 决定。
  # account_id 注错时，AssumeRole 在 plan/apply 阶段即失败，绝不会在错误账号静默创建资源。
  assume_role = {
    assume_role_trn              = "trn:iam::${var.account_id}:role/OrganizationAccessControlRole"
    assume_role_session_name     = "af-network-baseline"
    assume_role_duration_seconds = 3600
  }
}
