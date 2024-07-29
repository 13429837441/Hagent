#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
import logging
from datetime import *


class Logger(object):
    """
    将日志存在指定文件下
    logname：文件名
    mess:日志内容
    """
    def __init__(self, path, logname="Record-Msg"):
        self.log_name = logname
        """获取当天日期"""
        log_date = str(date.today())
        project_name = os.path.join("log", str(log_date))
        """获取工程路径"""
        base_dir = path
        project_path = os.path.join(base_dir, project_name)
        """获取log日志路径"""
        log_path = os.path.join(project_path)
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        """创建一个logger"""
        self.logger = logging.getLogger('log')
        logger_level = logging.INFO
        self.logger.setLevel(logger_level)
        """创建一个handler，用于写入日志文件"""
        if len(self.logger.handlers) == 0:  # 避免重复创建handlers
            """定义handler的输出格式formatter"""
            log_format = '[%(asctime)s]-[%(funcName)s]-%(message)s'
            formatter = logging.Formatter(log_format)
            # 日志输出到文件
            filehand = logging.FileHandler(os.path.join(log_path, str(self.log_name)+'.log'), encoding="utf-8", mode="a")
            filehand.setFormatter(formatter)
            self.logger.addHandler(filehand)
            # 日志输出到控制台
            # cmdhand = logging.StreamHandler(sys.stdout)
            # cmdhand.setFormatter(formatter)
            # self.logger.addHandler(cmdhand)
    """
    向日志文件里写入日志内容
    """
    def log(self, mess):
        # return self.logger.info(mess.decode('utf8').encode('gbk'))           # 控制台输出使用
        return self.logger.info(mess)                                         # pycharm客户端输出使用
