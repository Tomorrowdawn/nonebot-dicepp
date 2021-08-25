"""
一些通用指令, 比如.welcome
"""

from typing import List, Tuple, Any, Literal, Optional

from bot_core import Bot
from bot_config import CFG_MASTER
from data_manager import custom_data_chunk, DataChunkBase
from command.command_config import *
from command.dicepp_command import UserCommandBase, custom_user_command, MessageMetaData
from command.bot_command import BotCommandBase, PrivateMessagePort, GroupMessagePort, BotSendMsgCommand

LOC_WELCOME_DEFAULT = "welcome_default"
LOC_WELCOME_SET = "welcome_set"
LOC_WELCOME_RESET = "welcome_reset"
LOC_WELCOME_ILLEGAL = "welcome_illegal"

DC_WELCOME = "welcome"

WELCOME_MAX_LENGTH = 100


# 存放welcome数据
@custom_data_chunk(identifier=DC_WELCOME)
class _(DataChunkBase):
    def __init__(self):
        super().__init__()


@custom_user_command(readable_name="欢迎词指令", priority=DPP_COMMAND_PRIORITY_DEFAULT, group_only=True)
class WelcomeCommand(UserCommandBase):
    """
    .welcome 欢迎词指令
    """

    def __init__(self, bot: Bot):
        super().__init__(bot)
        bot.loc_helper.register_loc_text(LOC_WELCOME_DEFAULT, "Welcome!", "默认入群欢迎词")
        bot.loc_helper.register_loc_text(LOC_WELCOME_SET, "Welcoming word is \"{word}\" now", "设定入群欢迎词, word为当前设定的入群欢迎词")
        bot.loc_helper.register_loc_text(LOC_WELCOME_RESET, "Welcoming word has been reset", "重置入群欢迎词为空")
        bot.loc_helper.register_loc_text(LOC_WELCOME_ILLEGAL, "Welcoming word is illegal: {reason}", "非法的入群欢迎词, reason为原因")

    def can_process_msg(self, msg_str: str, meta: MessageMetaData) -> Tuple[bool, bool, Any]:
        should_proc: bool = msg_str.startswith(".welcome")
        should_pass: bool = False
        return should_proc, should_pass, meta.raw_msg[8:].strip()

    def process_msg(self, msg_str: str, meta: MessageMetaData, hint: Any) -> List[BotCommandBase]:
        port = GroupMessagePort(meta.group_id) if meta.group_id else PrivateMessagePort(meta.user_id)
        # 解析语句
        arg_str = hint
        feedback: str

        if not arg_str:
            self.bot.data_manager.set_data(DC_WELCOME, [meta.group_id], "")
            feedback = self.format_loc(LOC_WELCOME_RESET)
        else:
            if len(arg_str) > WELCOME_MAX_LENGTH:
                feedback = self.format_loc(LOC_WELCOME_ILLEGAL, reason=f"欢迎词长度大于{WELCOME_MAX_LENGTH}")
            elif arg_str == "default":
                self.bot.data_manager.delete_data(DC_WELCOME, [meta.group_id])
                feedback = self.format_loc(LOC_WELCOME_SET, word=self.format_loc(LOC_WELCOME_DEFAULT))
            else:
                self.bot.data_manager.set_data(DC_WELCOME, [meta.group_id], arg_str)
                feedback = self.format_loc(LOC_WELCOME_SET, word=arg_str)

        return [BotSendMsgCommand(self.bot.account, feedback, [port])]

    def get_help(self, keyword: str, meta: MessageMetaData) -> str:
        if keyword == "welcome":  # help后的接着的内容
            feedback: str = ".welcome [入群欢迎词]" \
                            "welcome后接想要设置的入群欢迎词, 不输入欢迎词则不开启入群欢迎" \
                            ".welcome default 使用默认入群欢迎词"
            return feedback
        return ""

    def get_description(self) -> str:
        return ".welcome 设置入群欢迎词"  # help指令中返回的内容


LOC_POINT_SHOW = "point_show"
LOC_POINT_CHECK = "point_check"
LOC_POINT_EDIT = "point_edit"
LOC_POINT_EDIT_ERROR = "point_edit_error"

CFG_POINT_INIT = "point_init"
CFG_POINT_ADD = "point_add"
CFG_POINT_MAX = "point_max"
CFG_POINT_LIMIT = "point_limit"

DC_POINT = "point"
DCK_POINT_CUR = "current"
DCK_POINT_TODAY = "today"


# 存放点数数据
@custom_data_chunk(identifier=DC_POINT)
class _(DataChunkBase):
    def __init__(self):
        super().__init__()


@custom_user_command(readable_name="点数指令", priority=DPP_COMMAND_PRIORITY_DEFAULT)
class PointCommand(UserCommandBase):
    """
    .point 和.m point指令
    """

    def __init__(self, bot: Bot):
        super().__init__(bot)
        bot.loc_helper.register_loc_text(LOC_POINT_SHOW, "Point of {name}: {point}", "用户查看点数的回复")
        bot.loc_helper.register_loc_text(LOC_POINT_CHECK, "Point of {id}: {result}", "Master查看某人的点数")
        bot.loc_helper.register_loc_text(LOC_POINT_EDIT, "Point: {result}", "Master调整某人的点数")
        bot.loc_helper.register_loc_text(LOC_POINT_EDIT_ERROR, "Error when editing points: {error}", "Master调整某人的点数时出现错误")

        bot.cfg_helper.register_config(CFG_POINT_INIT, "100", "新用户初始拥有的点数")
        bot.cfg_helper.register_config(CFG_POINT_ADD, "100", "每天给活跃用户增加的点数")
        bot.cfg_helper.register_config(CFG_POINT_MAX, "500", "用户能持有的点数上限")
        bot.cfg_helper.register_config(CFG_POINT_LIMIT, "300", "每天使用点数的上限")

    def tick_daily(self) -> List[BotCommandBase]:
        # 根据用户当日是否掷骰决定是否增加点数(暂定)
        from bot_core import DC_USER_DATA
        from command.impl import DCP_USER_DATA_ROLL_A_UID, DCP_ROLL_TIME_A_ID_ROLL, DCK_ROLL_TODAY
        from data_manager import DataManagerError
        point_init = int(self.bot.cfg_helper.get_config(CFG_POINT_INIT))
        point_add = int(self.bot.cfg_helper.get_config(CFG_POINT_ADD))
        point_max = int(self.bot.cfg_helper.get_config(CFG_POINT_MAX))
        user_ids = self.bot.data_manager.get_keys(DC_USER_DATA, [])
        dcp_roll_total_a_uid = DCP_USER_DATA_ROLL_A_UID + DCP_ROLL_TIME_A_ID_ROLL + [DCK_ROLL_TODAY]
        for user_id in user_ids:
            try:
                roll_time = self.bot.data_manager.get_data(DC_USER_DATA, [user_id] + dcp_roll_total_a_uid)
                assert roll_time > 0
            except (DataManagerError, AssertionError):
                continue
            prev_point = self.bot.data_manager.get_data(DC_POINT, [user_id, DCK_POINT_CUR], default_val=point_init)
            # 若已经超过上限, 说明是Master手动调整的, 不进行修改, 否则增加point_add
            cur_point = prev_point if prev_point > point_max else min(point_max, prev_point+point_add)
            self.bot.data_manager.set_data(DC_POINT, [user_id, DCK_POINT_CUR], cur_point)
            self.bot.data_manager.set_data(DC_POINT, [user_id, DCK_POINT_TODAY], 0)
        return []

    def can_process_msg(self, msg_str: str, meta: MessageMetaData) -> Tuple[bool, bool, Any]:
        should_proc: bool = False
        should_pass: bool = False
        if msg_str.startswith(".point"):
            return True, should_pass, ("show", None)
        elif msg_str.startswith(".m"):
            msg_str = msg_str[2:].lstrip()
            master_list = self.bot.cfg_helper.get_config(CFG_MASTER)
            if msg_str.startswith("point") and meta.user_id in master_list:
                return True, should_pass, ("mod", msg_str[5:].strip())
        return should_proc, should_pass, None

    def process_msg(self, msg_str: str, meta: MessageMetaData, hint: Any) -> List[BotCommandBase]:
        port = GroupMessagePort(meta.group_id) if meta.group_id else PrivateMessagePort(meta.user_id)
        # 解析语句
        cmd_type: Literal["show", "mod"] = hint[0]
        msg_str: Optional[str] = hint[1]
        feedback: str = ""
        point_init = int(self.bot.cfg_helper.get_config(CFG_POINT_INIT)[0])
        if cmd_type == "show":
            cur_point = self.bot.data_manager.get_data(DC_POINT, [meta.user_id, DCK_POINT_CUR], default_val=point_init)
            max_point = int(self.bot.cfg_helper.get_config(CFG_POINT_MAX)[0])
            nickname = self.bot.get_nickname(meta.user_id, meta.group_id)
            feedback = self.format_loc(LOC_POINT_SHOW, name=nickname, point=f"{cur_point}/{max_point}")
        elif cmd_type == "mod":
            if "=" in msg_str:
                target_id, target_point = msg_str.split("=", 1)
                try:
                    target_point = int(target_point)
                    nickname = self.bot.get_nickname(meta.user_id, target_id)
                    prev_point = self.bot.data_manager.get_data(DC_POINT, [target_id, DCK_POINT_CUR], default_val=point_init)
                    self.bot.data_manager.set_data(DC_POINT, [target_id, DCK_POINT_CUR], target_point)
                    feedback = self.format_loc(LOC_POINT_EDIT, result=f"{target_id}({nickname}) {prev_point}->{target_point}")
                except ValueError:
                    feedback = self.format_loc(LOC_POINT_EDIT_ERROR, error=str(ValueError))
            else:
                target_id = msg_str
                nickname = self.bot.get_nickname(meta.user_id, target_id)
                prev_point = self.bot.data_manager.get_data(DC_POINT, [target_id, DCK_POINT_CUR], default_val=point_init)
                feedback = self.format_loc(LOC_POINT_EDIT, result=f"{target_id}({nickname}): {prev_point}")

        return [BotSendMsgCommand(self.bot.account, feedback, [port])]

    def get_help(self, keyword: str, meta: MessageMetaData) -> str:
        if keyword == "point":  # help后的接着的内容
            feedback: str = "输入.point查看当前点数, 点数在使用消耗较大的指令时消耗"
            master_list = self.bot.cfg_helper.get_config(CFG_MASTER)
            if meta.user_id in master_list:
                feedback += "\n.m point [目标账号] 查看对方点数" \
                            "\n.m point [目标账号]=[目标数值] 将目标账号的点数设为指定数值"
            return feedback
        return ""

    def get_description(self) -> str:
        return ".point 查看当前点数"  # help指令中返回的内容
