# -*- coding: utf-8 -*-
import os
import sys
import json
import struct
import base64
import socket
import threading
import mitmproxy.http
from Htool import MyEncoder
from Hlogger import Logger
from urllib.parse import urlencode
try:
    filtration_url = sys.argv[3]
    filtration_type = sys.argv[4]
except:
    filtration_url = ""
    filtration_type = "ALL"


def create_headers(headers):
    """
    组装请求头
    :param headers:
    :return:
    """
    headers_info = {}
    for k, v in headers.items():
        headers_info[k] = v
    return headers_info


def clear_url(url):
    """
    清理请求链接地址中带参数的情况
    :param url:
    :return:
    """
    return str(url).split("?")[0]


def creat_query(query):
    """
    组装请求链接地址中的参数
    :param query:
    :return:
    """
    new_list = urlencode(query)
    if new_list != "":
        new_query = f'?{new_list}'
    else:
        new_query = ''
    return new_query


class HAgent:
    def __init__(self):
        # 配置项
        self.config = {}
        # 创建socket对象
        self.socket_client = socket.socket()
        self.console = Logger(os.path.split(os.path.realpath(__file__))[0])
        # 连接到服务器
        self.socket_client.connect(("localhost", 9999))
        # 启动一个新线程来处理服务端的消息接收
        threading.Thread(target=self.receive_messages, args=()).start()

    def receive_messages(self):
        while True:
            # 接收报文头的长度
            header_size = struct.unpack('i', self.socket_client.recv(4))[0]
            # 接收报头报文
            header_bytes = self.socket_client.recv(header_size)
            # 解析报头
            header_json = header_bytes.decode('utf-8')
            header_dic = json.loads(header_json)
            # 获取真实数据的长度
            body_len = header_dic['total_len']
            # 获取数据
            recv_size = 0
            data = b''
            while recv_size < body_len:
                recv_date = self.socket_client.recv(1024)
                data += recv_date
                recv_size += len(recv_date)

            data_from_server = data.decode("utf-8")
            # print(f"客户端接收到服务端的消息：{data_from_server}")
            if data_from_server == "STOP":
                self.socket_client.close()
                break
            else:
                try:
                    data_json = json.loads(data_from_server)
                    if "method" in data_json and data_json["method"] == "Repackage":
                        self.config[data_json["url"]] = data_json
                except Exception as e:
                    self.console.log(f"Error client receiving message: {e}")

    def is_connect(self):
        try:
            self.socket_client.getpeername()
            return True
        except socket.error:
            return False

    def request(self, flow: mitmproxy.http.HTTPFlow):
        # 篡改请求数据
        current_url = clear_url(str(flow.request.pretty_url))
        if current_url in self.config.keys():
            interface_type = self.config[current_url]["type"]
            interface_operator = self.config[current_url]["operator"]
            if interface_operator[0] == 2:  # 修改请求头
                r_h_dict = json.loads(self.config[current_url]["r_h"])
                for header_key, header_value in r_h_dict.items():
                    flow.request.headers[header_key] = str(header_value)
            if interface_operator[1] == 2:  # 修改请求体
                if interface_type == "POST":
                    flow.request.content = bytes(self.config[current_url]["r_b"], "utf-8")
                else:
                    for query_key, query_value in self.config[current_url]["r_b"]:
                        flow.request.query[query_key] = query_value

    def response(self, flow: mitmproxy.http.HTTPFlow):
        filtration = [url for url in filtration_url.split(",") if url in str(flow.request.pretty_url)]
        if len(filtration) > 0:
            if filtration_type in str(flow.request.method) or filtration_type == "ALL":
                current_url = clear_url(str(flow.request.pretty_url))
                # 篡改响应数据
                if current_url in self.config.keys():
                    status_code = self.config[current_url]["code"]
                    interface_operator = self.config[current_url]["operator"]
                    interface_type = self.config[current_url]["type"]
                    if interface_operator[2] == 2:  # 修改响应头
                        s_h_dict = json.loads(self.config[current_url]["s_h"])
                        for header_key, header_value in s_h_dict.items():
                            flow.response.headers[header_key] = str(header_value)
                    if interface_operator[3] == 2:  # 修改响应体
                        flow.response.content = bytes(self.config[current_url]["s_b"], "utf-8")
                    if status_code != -999:     # 修改状态码
                        flow.response.status_code = status_code
                    # 删除改包配置, 确认接口请求方式一致才删除
                    if flow.request.method == interface_type:
                        self.config.pop(current_url)
                # 推送响应数据
                request_info = {'request_url': current_url,
                                'request_headers': create_headers(flow.request.headers)}
                if flow.request.method == "GET":
                    request_info['request_body'] = creat_query(flow.request.query)
                elif flow.request.method == "POST":
                    request_info['request_body'] = flow.request.get_text()
                else:
                    request_info['request_body'] = ""   # 暂时未处理
                request_info['request_method'] = flow.request.method
                request_info['status_code'] = flow.response.status_code
                try:
                    request_info['response_data'] = json.loads(flow.response.content)
                except:
                    request_info['response_data'] = flow.response.content.decode('utf8', 'ignore')
                request_info['response_headers'] = create_headers(flow.response.headers)
                request_info['request_time_start'] = flow.request.timestamp_start
                request_info['response_time_end'] = flow.response.timestamp_end
                request_info['response_time'] = round(request_info['response_time_end'] - request_info['request_time_start'], 5)
                if self.is_connect():
                    # base64加密其他参数
                    pack_info = base64.b64encode(json.dumps(
                        [
                            request_info['request_headers'],
                            request_info['request_body'],
                            request_info['response_headers'],
                            request_info['response_data']
                         ], indent=4, ensure_ascii=False, cls=MyEncoder).encode("utf-8")
                    )
                    # 发送消息
                    request_list = [
                        request_info['request_url'],
                        request_info['status_code'],
                        request_info['request_method'],
                        request_info['response_time'],
                        pack_info
                    ]
                    send_message = json.dumps(request_list, ensure_ascii=False, cls=MyEncoder).encode("utf-8")
                    # 制作报头
                    header_dic = {'total_len': len(send_message)}
                    header_json = json.dumps(header_dic)
                    header_bytes = header_json.encode('utf-8')
                    # 先发送报头的长度
                    header_size = len(header_bytes)
                    self.socket_client.send(struct.pack('i', header_size))
                    # 发送报头
                    self.socket_client.send(header_bytes)
                    # 发送真实的数据
                    self.socket_client.send(send_message)


addons = [
    HAgent()
]