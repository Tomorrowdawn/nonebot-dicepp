import os
import re
import random
import bot_utils
from bot_config import LOCAL_IMG_PATH
from logger import dice_log


class LocalizationText:
    def __init__(self, key: str, default_text: str = "", comment: str = ""):
        self.key = key
        self.loc_texts: list = [default_text] if default_text else []
        self.comment = comment

    def add(self, text: str) -> None:
        """
        增加一个可选择的本地化字符串, 调用get可以随机返回一个可选择的本地化字符串
        """
        self.loc_texts.append(text)

    def get(self) -> str:
        """
        返回一个可选择的本地化字符串, 若没有可用的本地化字符串, 返回空字符串
        """
        def replace_image_code(match):
            key = match.group(1)
            file_path = os.path.join(LOCAL_IMG_PATH, key)
            if os.path.exists(file_path):
                return bot_utils.cq_code.get_cq_image(file_path)
            else:
                dice_log(f"[LocalImage] 找不到图片 {file_path}")
                return match.group(0)

        loc_text = random.choice(self.loc_texts) if self.loc_texts else ""
        loc_text = re.sub(r"IMG\((.{1,50}?\.[A-Za-z]{1,10}?)\)", replace_image_code, loc_text)
        return loc_text
