import random
from typing import List, Tuple, Any

from bot_core.dicebot import Bot
from command.command_config import *
from command.dicepp_command import UserCommandBase, custom_user_command, MessageMetaData
from command.bot_command import BotCommandBase, PrivateMessagePort, GroupMessagePort, BotSendMsgCommand
from bot_utils import time

LOC_JRRP = "jrrp"


@custom_user_command(readable_name="今日人品", priority=DPP_COMMAND_PRIORITY_DEFAULT)
class JrrpCommand(UserCommandBase):

    def __init__(self, bot: Bot):
        super().__init__(bot)
        bot.loc_helper.register_loc_text(LOC_JRRP, "{name}'s daily lucky points are:{jrrp}", ".jrrp返回的内容,{name}:用户名,{jrrp}:今日人品值.")

    def can_process_msg(self, msg_str: str, meta: MessageMetaData) -> Tuple[bool, bool, Any]:
        should_proc: bool = msg_str.startswith(".jrrp")
        should_pass: bool = False
        return should_proc, should_pass, msg_str[5:].strip()

    def process_msg(self, msg_str: str, meta: MessageMetaData, hint: Any) -> List[BotCommandBase]:
        port = GroupMessagePort(meta.group_id) if meta.group_id else PrivateMessagePort(meta.user_id)
        # 解析语句
        date_str: str = time.datetime_to_str_day(time.get_current_date_raw())
        seed_str: str = date_str + meta.user_id  # 拼接形成一个固定的seed

        random.seed(seed_str)
        jrrp: str = str(random.randint(1, 100))  # 根据上面的seed获取确定值

        user_name: str = self.bot.get_nickname(meta.user_id, meta.group_id)
        feedback: str = self.format_loc(LOC_JRRP, name=user_name, jrrp=jrrp)

        return [BotSendMsgCommand(self.bot.account, feedback, [port])]

    def get_help(self, keyword: str, meta: MessageMetaData) -> str:
        if keyword == "jrrp":  # help后的接着的内容
            feedback: str = ".jrrp 获取今日人品，每日0点刷新"
            return feedback
        return ""

    def get_description(self) -> str:
        return ".jrrp 获取今日人品"  # help指令中返回的内容
