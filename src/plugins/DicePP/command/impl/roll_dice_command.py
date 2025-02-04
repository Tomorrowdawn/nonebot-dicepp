from typing import List, Tuple, Any

from bot_core import Bot, DC_USER_DATA, DC_GROUP_DATA
from command.command_config import *
from command.dicepp_command import UserCommandBase, custom_user_command, MessageMetaData
from command import BotCommandBase
from command.bot_command import PrivateMessagePort, GroupMessagePort, BotSendMsgCommand
from command.impl import try_use_point
import localization

from roll_dice import RollResult, RollExpression, preprocess_roll_exp, parse_roll_exp, RollDiceError

LOC_ROLL_RESULT = "roll_result"
LOC_ROLL_RESULT_REASON = "roll_result_reason"
LOC_ROLL_RESULT_HIDE = "roll_result_hide"
LOC_ROLL_RESULT_HIDE_REASON = "roll_result_hide_reason"
LOC_ROLL_RESULT_HIDE_GROUP = "roll_result_hide_group"
LOC_ROLL_RESULT_MULTI = "roll_result_multi"
LOC_ROLL_D20_BS = "roll_d20_success"
LOC_ROLL_D20_BF = "roll_d20_failure"
LOC_ROLL_D20_MULTI = "roll_d20_multiple"
LOC_ROLL_D20_BS_SHORT = "roll_d20_success_short"
LOC_ROLL_D20_BF_SHORT = "roll_d20_failure_short"
LOC_ROLL_D20_2 = "roll_d20_2"
LOC_ROLL_D20_3_5 = "roll_d20_3_5"
LOC_ROLL_D20_6_10 = "roll_d20_6_10"
LOC_ROLL_D20_11_15 = "roll_d20_11_15"
LOC_ROLL_D20_16_18 = "roll_d20_16_18"
LOC_ROLL_D20_19 = "roll_d20_19"
LOC_ROLL_EXP = "roll_exp"

CFG_ROLL_ENABLE = "roll_enable"
CFG_ROLL_HIDE_ENABLE = "roll_hide_enable"
CFG_ROLL_EXP_COST = "roll_exp_cost"

MULTI_ROLL_LIMIT = 10  # 多轮掷骰上限次数

DCP_USER_DATA_ROLL_A_UID = ["roll"]  # 所有用户掷骰相关信息存储路径, 跟在user_id后面
DCP_GROUP_DATA_ROLL_A_GID = ["roll"]  # 所有群掷骰相关信息存储路径, 跟在group_id后面, 私聊时group_id为private

DCP_ROLL_TIME_A_ID_ROLL = ["time"]  # 掷骰次数信息的相对路径
DCP_ROLL_D20_A_ID_ROLL = ["d20"]  # D20信息的相关路径

DCK_ROLL_TODAY = "today"  # 获取每日信息的key, 适用范围包括 DCP_ROLL_TIME_A_ID_ROLL 和 DCP_ROLL_D20_A_ID_ROLL
DCK_ROLL_TOTAL = "total"  # 获取所有历史信息的key, 适用范围包括 DCP_ROLL_TIME_A_ID_ROLL 和 DCP_ROLL_D20_A_ID_ROLL


@custom_user_command(readable_name="掷骰指令",
                     priority=0,
                     group_only=False,
                     flag=DPP_COMMAND_FLAG_DEFAULT,
                     cluster=DPP_COMMAND_CLUSTER_DEFAULT)
class RollDiceCommand(UserCommandBase):
    """
    掷骰相关的指令, 以.r开头
    """

    def __init__(self, bot: Bot):
        super().__init__(bot)
        bot.loc_helper.register_loc_text(LOC_ROLL_RESULT,
                                         "{nickname}'s roll result is {roll_result_final} {d20_state}",
                                         ".r不带原因时返回的语句 {nickname}:昵称; {roll_result_final}:最终掷骰结果"
                                         " {d20_state}: 如果骰子中包含唯一d20时返回的语句, 具体内容见下文")
        bot.loc_helper.register_loc_text(LOC_ROLL_RESULT_REASON,
                                         "{nickname}'s roll result for {roll_reason} " +
                                         "is {roll_result_final} {d20_state}",
                                         ".r带原因时返回的语句 {roll_reason}:原因; 其他关键字见上文同名关键字")
        bot.loc_helper.register_loc_text(LOC_ROLL_RESULT_HIDE,
                                         "{nickname}'s hidden roll result is {roll_result_final} {d20_state}",
                                         ".rh不带原因时返回的语句 关键字见上文同名关键字")
        bot.loc_helper.register_loc_text(LOC_ROLL_RESULT_HIDE_REASON,
                                         "{nickname}'s hidden roll result for {roll_reason}" +
                                         " is {roll_result_final} {d20_state}",
                                         ".rh带原因时返回的语句 关键字见上文同名关键字")
        bot.loc_helper.register_loc_text(LOC_ROLL_RESULT_HIDE_GROUP,
                                         "{nickname} process a hidden rolling",
                                         "执行.rh时在群里的回复")
        bot.loc_helper.register_loc_text(LOC_ROLL_RESULT_MULTI,
                                         "{time}times {roll_exp}: [{roll_result}]",
                                         "当掷骰表达式中含有#来多次掷骰时, 用这个格式组成上文的{roll_result_final}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_BS, "Great, success!", "唯一d20投出大成功的反馈, 替换{d20_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_BF, "Wow, failure!", "唯一d20投出大失败的反馈, 替换{d20_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_MULTI, "{time}times {short_state}",
                                         "多次掷骰时唯一d20投出大成功或大失败的反馈 " +
                                         "{time}:大成功或大失败的次数; {short_state}:大成功或大失败的简短描述")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_BS_SHORT, "Success", "多次掷骰出现大成功时替换上文中的{short_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_BF_SHORT, "Failure", "多次掷骰出现大失败时替换上文中的{short_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_2, "", "唯一d20的骰值等于2的反馈, 替换{d20_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_3_5, "", "唯一d20的骰值在3到5之间的反馈, 替换{d20_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_6_10, "", "唯一d20的骰值在6到10之间的反馈, 替换{d20_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_11_15, "", "唯一d20的骰值在11到15之间的反馈, 替换{d20_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_16_18, "", "唯一d20的骰值在16到18之间的反馈, 替换{d20_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_D20_19, "", "唯一d20的骰值等于19的反馈, 替换{d20_state}")
        bot.loc_helper.register_loc_text(LOC_ROLL_EXP, "Expectation of {expression} is:\n{expectation}", "计算掷骰表达式期望时的回复")

        bot.cfg_helper.register_config(CFG_ROLL_ENABLE, "1", "掷骰指令开关")
        bot.cfg_helper.register_config(CFG_ROLL_HIDE_ENABLE, "1", "暗骰指令开关(暗骰会发送私聊信息, 可能增加风控风险)")
        bot.cfg_helper.register_config(CFG_ROLL_EXP_COST, "10", "计算掷骰表达式期望(.rexp)所花费的点数")

    def can_process_msg(self, msg_str: str, meta: MessageMetaData) -> Tuple[bool, bool, Any]:
        should_proc: bool = msg_str.startswith(".r")
        should_pass: bool = False
        return should_proc, should_pass, None

    def process_msg(self, msg_str: str, meta: MessageMetaData, hint: Any) -> List[BotCommandBase]:
        # 判断功能开关
        try:
            assert (int(self.bot.cfg_helper.get_config(CFG_ROLL_ENABLE)[0]) != 0)
        except AssertionError:
            feedback = self.bot.loc_helper.format_loc_text(localization.LOC_FUNC_DISABLE, func=self.readable_name)
            port = GroupMessagePort(meta.group_id) if meta.group_id else PrivateMessagePort(meta.user_id)
            return [BotSendMsgCommand(self.bot.account, feedback, [port])]
        # 解析掷骰语句
        msg_str = msg_str[2:].strip()
        is_hidden = False
        is_show_info = True
        compute_exp = False
        while msg_str and msg_str[0] in ["h", "s"]:
            if msg_str[0] == "h":  # 暗骰
                is_hidden = True
            if msg_str[0] == "s":  # 缩略中间结果
                is_show_info = False
            msg_str = msg_str[1:]
        if msg_str[:3] == "exp":
            msg_str = msg_str[3:]
            compute_exp = True
        msg_str = msg_str.strip()
        if not msg_str:
            msg_str = 'd'
        # 判断暗骰开关
        try:
            assert (not is_hidden or int(self.bot.cfg_helper.get_config(CFG_ROLL_HIDE_ENABLE)[0]) != 0)
        except AssertionError:
            feedback = self.bot.loc_helper.format_loc_text(localization.LOC_FUNC_DISABLE, func="暗骰指令")
            port = GroupMessagePort(meta.group_id) if meta.group_id else PrivateMessagePort(meta.user_id)
            return [BotSendMsgCommand(self.bot.account, feedback, [port])]

        exp_str: str
        reason_str: str
        # 分割掷骰原因与掷骰表达式
        if " " in msg_str and not compute_exp:
            exp_str, reason_str = msg_str.split(" ", 1)
            reason_str = reason_str.strip()
        else:
            exp_str, reason_str = msg_str, ""
        times = 1  # 掷骰次数
        if "#" in exp_str:
            time_str, exp_str = exp_str.split("#", 1)
            try:
                times = int(time_str)
                assert 0 < times <= MULTI_ROLL_LIMIT
            except (ValueError, AssertionError):
                times = 1

        # 解析表达式并生成结果
        try:
            exp_str = preprocess_roll_exp(exp_str)
            exp: RollExpression = parse_roll_exp(exp_str)
            res_list: List[RollResult] = [exp.get_result() for _ in range(times)]
        except RollDiceError as e:
            feedback = e.info
            # 生成机器人回复端口
            port = GroupMessagePort(meta.group_id) if meta.group_id else PrivateMessagePort(meta.user_id)
            return [BotSendMsgCommand(self.bot.account, feedback, [port])]

        # 回复端口
        port = GroupMessagePort(meta.group_id) if not is_hidden and meta.group_id else PrivateMessagePort(meta.user_id)

        if compute_exp:  # 计算期望走单独的流程
            # 尝试扣除点数
            cost_point = int(self.bot.cfg_helper.get_config(CFG_ROLL_EXP_COST)[0])
            res = try_use_point(self.bot, meta.user_id, cost_point)
            # 点数不足
            if res:
                return [BotSendMsgCommand(self.bot.account, res, [port])]
            else:
                exp_result = get_roll_exp_result(exp)
                feedback = self.format_loc(LOC_ROLL_EXP, expression=exp.get_result().get_exp(), expectation=exp_result)
                return [BotSendMsgCommand(self.bot.account, feedback, [port])]

        # 得到结果字符串
        if len(res_list) > 1:
            roll_exp = res_list[0].get_exp()
            roll_result = "\n" + (",\n".join([res.get_result() if is_show_info else res.get_val() for res in res_list]))

            roll_result_final = self.format_loc(LOC_ROLL_RESULT_MULTI,
                                                time=times, roll_exp=roll_exp, roll_result=roll_result)
        else:
            if is_show_info:
                roll_result_final = res_list[0].get_complete_result()
            else:
                roll_result_final = res_list[0].get_exp_val()

        # 获取其他信息
        nickname = self.bot.get_nickname(meta.user_id, meta.group_id)
        # 大成功和大失败次数
        d20_state = get_d20_state_loc_text(self.bot, res_list)

        loc_args = {"nickname": nickname, "roll_reason": reason_str,
                    "roll_result_final": roll_result_final, "d20_state": d20_state}

        # 生成最终回复字符串
        feedback: str = ""
        commands: List[BotCommandBase] = []
        if is_hidden:
            if reason_str:
                feedback = self.format_loc(LOC_ROLL_RESULT_HIDE_REASON, **loc_args)
            elif not reason_str:
                feedback = self.format_loc(LOC_ROLL_RESULT_HIDE, **loc_args)
            if meta.group_id:
                group_feedback: str = self.format_loc(LOC_ROLL_RESULT_HIDE_GROUP, nickname=nickname)
                commands.append(BotSendMsgCommand(self.bot.account, group_feedback, [GroupMessagePort(meta.group_id)]))
        elif not is_hidden:
            if reason_str:
                feedback = self.format_loc(LOC_ROLL_RESULT_REASON, **loc_args)
            elif not reason_str:
                feedback = self.format_loc(LOC_ROLL_RESULT, **loc_args)

        # 记录掷骰结果
        record_roll_data(self.bot, meta, res_list)
        commands.append(BotSendMsgCommand(self.bot.account, feedback, [port]))
        return commands

    def get_help(self, keyword: str, meta: MessageMetaData) -> str:
        if keyword == "r":
            help_str = "掷骰：.r[掷骰表达式]([掷骰原因])\n" \
                       "[掷骰表达式]：([轮数]#)[个数]d面数(优/劣势)(k[取点数最大的骰子数])不带面数时视为掷一个默认的20面骰\n" \
                       "r后加h即为暗骰\n" \
                       "示例:\n" \
                       ".rd20+1d4+4\n" \
                       ".r4#d    //投4次d20\n" \
                       ".rd20劣势+4 //带劣势攻击\n" \
                       ".r2#d优势+4 攻击被束缚的地精 //两次有加值的优势攻击\n" \
                       ".r1d12+2d8+5抗性 //得到减半向下取整的投骰总值"
            return help_str
        return ""

    def get_description(self) -> str:
        return ".r 掷骰"


def get_roll_exp_result(expression: RollExpression) -> str:
    repeat_times = 10000
    stat_range = [1, 5, 25, 45, 55, 75, 95, 99]  # 统计区间, 大于0, 小于100
    res_list: List[int] = list(sorted((expression.get_result().get_val() for _ in range(repeat_times))))
    mean = sum(res_list)/repeat_times
    info = []
    stat_range_num: List[int] = [0] + [repeat_times*r//100 for r in stat_range] + [-1]
    for num in stat_range_num:
        info.append(res_list[num])
    feedback = ""
    left_range = 0
    for index, right_range in enumerate(stat_range):
        feedback += f"{left_range}%~{right_range}% -> [{info[index]}~{info[index + 1]}]\n"
        left_range = right_range
    feedback += f"{stat_range[-1]}%~100% -> [{info[-2]}~{info[-1]}]\n"
    feedback += f"均值: {mean}"
    return feedback


def get_d20_state_loc_text(bot: Bot, res_list: List[RollResult]):
    d20_state: str = ""
    success_time = sum([res.d20_num == 1 and res.d20_state == 20 for res in res_list])
    failure_time = sum([res.d20_num == 1 and res.d20_state == 1 for res in res_list])
    if len(res_list) == 1 and (success_time + failure_time) != 0:  # 掷骰轮数等于1且存在大成功或大失败
        if success_time:
            d20_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_BS)
        elif failure_time:
            d20_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_BF)
    elif len(res_list) > 1:  # 掷骰轮数大于1且存在大成功或大失败
        success_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_BS_SHORT)
        failure_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_BF_SHORT)
        success_info, failure_info = "", ""
        if success_time:
            success_info = bot.loc_helper.format_loc_text(LOC_ROLL_D20_MULTI,
                                                          time=success_time, short_state=success_state)
        if failure_time:
            failure_info = bot.loc_helper.format_loc_text(LOC_ROLL_D20_MULTI,
                                                          time=failure_time, short_state=failure_state)
        d20_state = " ".join([info for info in [success_info, failure_info] if info])
    elif len(res_list) == 1 and res_list[0].d20_num == 1:  # 掷骰轮数等于1且不存在大成功或大失败且有唯一D20
        d20_result = res_list[0].d20_state
        if d20_result == 2:
            d20_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_2)
        elif 3 <= d20_result <= 5:
            d20_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_3_5)
        elif 6 <= d20_result <= 10:
            d20_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_6_10)
        elif 11 <= d20_result <= 15:
            d20_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_11_15)
        elif 16 <= d20_result <= 18:
            d20_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_16_18)
        elif d20_result == 19:
            d20_state = bot.loc_helper.format_loc_text(LOC_ROLL_D20_19)

    return d20_state


def record_roll_data(bot: Bot, meta: MessageMetaData, res_list: List[RollResult]):
    """统计掷骰数据"""
    roll_times = len(res_list)
    cur_roll_result: List[int] = [sum([res.d20_num != 1 for res in res_list])]  # 第0个元素为非D20数量
    for i in range(1, 21):
        cur_roll_result.append(sum([res.d20_num == 1 and res.d20_state == i for res in res_list]))
    # 更新用户数据
    dcp_user_prefix = [meta.user_id] + DCP_USER_DATA_ROLL_A_UID
    bot.data_manager.get_data(DC_USER_DATA, dcp_user_prefix, default_val={})
    # 掷骰次数
    user_time_data = bot.data_manager.get_data(DC_USER_DATA,
                                               dcp_user_prefix + DCP_ROLL_TIME_A_ID_ROLL,
                                               default_val={DCK_ROLL_TODAY: 0, DCK_ROLL_TOTAL: 0})
    user_time_data[DCK_ROLL_TODAY] += roll_times
    user_time_data[DCK_ROLL_TOTAL] += roll_times
    bot.data_manager.set_data(DC_USER_DATA, dcp_user_prefix + DCP_ROLL_TIME_A_ID_ROLL, user_time_data)
    # D20信息
    user_d20_data = bot.data_manager.get_data(DC_USER_DATA,
                                              dcp_user_prefix + DCP_ROLL_D20_A_ID_ROLL,
                                              default_val={DCK_ROLL_TODAY: [0]*21, DCK_ROLL_TOTAL: [0]*21})
    for i in range(1, 21):
        user_d20_data[DCK_ROLL_TODAY][i] += cur_roll_result[i]
        user_d20_data[DCK_ROLL_TOTAL][i] += cur_roll_result[i]
    bot.data_manager.set_data(DC_USER_DATA, dcp_user_prefix + DCP_ROLL_D20_A_ID_ROLL, user_d20_data)
    # 更新群数据
    group_id = meta.group_id if meta.group_id else "private"
    dcp_group_prefix = [group_id] + DCP_USER_DATA_ROLL_A_UID
    bot.data_manager.get_data(DC_GROUP_DATA, dcp_group_prefix, default_val={})
    # 掷骰次数
    group_time_data = bot.data_manager.get_data(DC_GROUP_DATA,
                                                dcp_user_prefix + DCP_ROLL_TIME_A_ID_ROLL,
                                                default_val={DCK_ROLL_TODAY: 0, DCK_ROLL_TOTAL: 0})
    group_time_data[DCK_ROLL_TODAY] += roll_times
    group_time_data[DCK_ROLL_TOTAL] += roll_times
    bot.data_manager.set_data(DC_GROUP_DATA, dcp_user_prefix + DCP_ROLL_TIME_A_ID_ROLL, group_time_data)
    # D20信息
    group_d20_data = bot.data_manager.get_data(DC_GROUP_DATA,
                                               dcp_group_prefix + DCP_ROLL_D20_A_ID_ROLL,
                                               default_val={DCK_ROLL_TODAY: [0] * 21, DCK_ROLL_TOTAL: [0] * 21})
    for i in range(1, 21):
        group_d20_data[DCK_ROLL_TODAY][i] += cur_roll_result[i]
        group_d20_data[DCK_ROLL_TOTAL][i] += cur_roll_result[i]
    bot.data_manager.set_data(DC_GROUP_DATA, dcp_group_prefix + DCP_ROLL_D20_A_ID_ROLL, group_d20_data)
    return
