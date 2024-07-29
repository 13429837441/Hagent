# -*- coding: utf-8 -*-
import json
import numpy as np


class MyEncoder(json.JSONEncoder):
    """
    重写JSONEncoder，兼容异常数据无法转换的情况
    :return:
    """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, bytes):
            return str(obj, encoding='utf-8')
        elif obj.__class__.__name__ == "PrettyOrderedSet":
            list(obj)
        else:
            return super(MyEncoder, self).default(obj)
