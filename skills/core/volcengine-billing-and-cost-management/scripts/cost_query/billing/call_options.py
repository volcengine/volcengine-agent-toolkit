"""Action 的 CLI 调用选项；不放业务参数或认证信息。"""

from .cost_change import COST_CHANGE_ACTIONS


ACTION_CLI_OPTIONS = dict.fromkeys(COST_CHANGE_ACTIONS, (
    "--force", "--version", "2022-01-01", "--method", "POST",
    "--header", "Content-Type=application/json", "--output", "json",
))
