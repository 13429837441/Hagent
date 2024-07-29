# -*- coding: utf-8 -*-
import base64
import math
import struct
import json
import os
import sys
import socket
import signal
import platform
import threading
import subprocess
from Htool import MyEncoder
from Hagent import Ui_MainWindow
from PyQt5 import QtWidgets, QtCore, uic
from Hlogger import Logger
from mitmproxy import flowfilter
from qt_material import apply_stylesheet
from PyQt5.QtGui import QIcon, QPainter, QBrush, QColor, QFont, QRegExpValidator, QPalette
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QFrame, QLabel, QTreeWidgetItem, QMessageBox, QWidget
from PyQt5.QtCore import QThread, pyqtSignal, QDateTime, QObject, QRegExp, Qt
request_list = []


def obj_is_json(data):
    """判断对象是否是JSON字符串"""
    try:
        int(data)  # 即先判断该字符串是否为int
        return False, None
    except ValueError:
        pass

    try:
        json_obj = json.loads(data)
    except ValueError:
        return False, None

    return True, json_obj


def add_dict_to_tree(parent_item, data):
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                child_item = QTreeWidgetItem(parent_item)
                child_item.setText(0, key)
                add_dict_to_tree(child_item, value)
            else:
                item = QTreeWidgetItem(parent_item)
                item.setText(0, key)
                item.setText(1, str(value))
    else:
        item = QTreeWidgetItem(parent_item)
        item.setText(0, 0)
        item.setText(1, str(data))


class Server(QObject):
    message_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.console = Logger(os.path.split(os.path.realpath(__file__))[0])
        # 创建服务器套接字并绑定地址
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("localhost", 9999))
        self.server_socket.listen(5)
        self.clients = []  # 存储连接到服务器的客户端套接字

    def get_connect_count(self):
        return len(self.clients)

    def start_server(self):
        # 循环接受客户端连接
        try:
            while True:
                client_socket, addr = self.server_socket.accept()
                self.clients.append(client_socket)
                # 启动一个新线程来处理每个客户端的消息接收
                threading.Thread(target=self.receive_messages, args=(client_socket,)).start()
        except:
            self.console.log("TCP服务端关闭")

    def receive_messages(self, client_socket):
        # 循环接收客户端发送的消息
        global request_list
        while True:
            try:
                # 接收报文头的长度
                first_byte = client_socket.recv(4)
                header_size = struct.unpack('i', first_byte)[0]
                # 接收报头报文
                header_bytes = client_socket.recv(header_size)
                # 解析报头
                header_json = header_bytes.decode('utf-8')
                header_dic = json.loads(header_json)
                # 获取真实数据的长度
                body_len = header_dic['total_len']
                # 获取数据
                recv_size = 0
                data = b''
                while recv_size < body_len:
                    if body_len - recv_size < 1024:
                        recv_date = client_socket.recv(body_len - recv_size)
                    else:
                        recv_date = client_socket.recv(1024)
                    data += recv_date
                    recv_size += len(recv_date)

                if not data:
                    break
                message = data.decode("utf-8")
                message = json.loads(message)
                # self.console.log(f"客户端发来的消息是：{message}")
                # 发射消息接收信号
                request_list.append(message[-1])
                self.message_received.emit(json.dumps(message[:-1]))
            except Exception as e:
                self.console.log(f"Error service receiving message: {e}")
                # client_socket.close()
                break

    def send_message(self, message):
        # 制作报头
        header_dic = {'total_len': len(message)}
        header_json = json.dumps(header_dic)
        header_bytes = header_json.encode('utf-8')
        # 报头的长度
        header_size = len(header_bytes)
        # 广播消息给所有连接的客户端
        for client in self.clients:
            try:
                # 发送报头长度
                client.send(struct.pack('i', header_size))
                # 发送报头
                client.send(header_bytes)
                # 发送消息
                client.send(message)
            except Exception as e:
                self.console.log(f"Error sending message: {e}")


class HAgentMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(HAgentMainWindow, self).__init__(parent)
        self.pid = 0
        self.message_obj = dict()
        self._running = False
        self.signal_led = QLabel()
        self.pt = platform.system()
        self.path = os.path.split(os.path.realpath(__file__))[0]
        # 建立通信
        self.console = Logger(self.path)
        # 创建服务器对象
        self.server = Server()
        # 将消息接收信号连接到处理消息的槽函数
        self.server.message_received.connect(self.handle_message)
        self.setupUi(self)
        # 数据表格
        self.tableWidget.itemClicked.connect(self.on_item_click)
        # 应用按钮
        self.pushButton_2.clicked.connect(self.click_pushbutton_2)
        # 开始按钮
        self.pushButton_3.clicked.connect(self.click_pushbutton_3)
        # 停止按钮
        self.pushButton.clicked.connect(self.click_pushbutton)
        # 启用按钮
        self.pushButton_4.clicked.connect(self.click_pushbutton_4)
        # 停用按钮
        self.pushButton_5.clicked.connect(self.click_pushbutton_5)
        # 帮助按钮
        self.commandLinkButton.clicked.connect(self.click_command_button_1)
        # 复选框组件
        self.checkBox.clicked.connect(self.on_checkbox_1_click)
        self.checkBox_2.clicked.connect(self.on_checkbox_2_click)
        self.checkBox_3.clicked.connect(self.on_checkbox_3_click)
        self.checkBox_4.clicked.connect(self.on_checkbox_4_click)
        # 启动服务器
        threading.Thread(target=self.server.start_server).start()
        # 启动UI校验
        self.settings()

    def settings(self):
        """创建一个QLabel作为信号灯"""
        self.signal_led.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.signal_led.setAutoFillBackground(True)
        pal = self.signal_led.palette()
        pal.setColor(QPalette.Background, Qt.red)  # 默认设置为红色表示关闭
        self.signal_led.setPalette(pal)
        # 在状态栏添加信号灯
        self.statusbar.addWidget(self.signal_led)

        """设置输入框校验器"""
        reg = QRegExp('[0-9]+$')
        validator = QRegExpValidator()
        validator.setRegExp(reg)
        reg_1 = QRegExp('[1-9][0-9]|100$')
        validator_1 = QRegExpValidator()
        validator_1.setRegExp(reg_1)
        # 设置状态码输入框只能输入数字
        self.lineEdit_3.setValidator(validator)
        self.lineEdit_5.setValidator(validator)
        self.lineEdit_6.setValidator(validator_1)

    def run_record(self):
        record_path = os.path.join(self.path, "Hrecord.py")
        if self.pt == "Linux":
            self.process = subprocess.Popen(
                ['mitmdump', '-s', record_path, self.lineEdit.text(), self.comboBox.currentText()],
                stdout=subprocess.PIPE, preexec_fn=os.setsid)
        else:
            self.process = subprocess.Popen(
                ['mitmdump', '-s', record_path, self.lineEdit.text(), self.comboBox.currentText()],
                stdout=subprocess.PIPE)
        while self._running:
            self.process.stdout.readline().rstrip().decode('utf-8')
        # 杀掉进程
        if self.pt == "Linux":
            os.killpg(int(self.process.pid), signal.SIGKILL)
        else:
            os.system('taskkill /t /f /pid {}'.format(self.process.pid))

    def handle_message(self, message):
        row_count = self.tableWidget.rowCount()  # 返回当前行数(尾部)
        self.tableWidget.insertRow(row_count)  # 尾部插入一行
        for index, val in enumerate(json.loads(message)):
            self.tableWidget.setItem(row_count, index, QtWidgets.QTableWidgetItem(str(val)))
            if index == 1:
                if val == 200:
                    self.tableWidget.item(row_count, index).setForeground(QColor("lightgreen"))
                else:
                    self.tableWidget.item(row_count, index).setForeground(QColor("red"))

    def on_item_click(self, item):
        """点击表格事件"""
        row = item.row()
        pack_obj = json.loads(base64.b64decode(request_list[row]).decode("utf-8"))
        request_header = pack_obj[0]
        request_body = json.dumps(pack_obj[1], indent=4, ensure_ascii=False, cls=MyEncoder)
        response_header = pack_obj[2]
        response_body = json.dumps(pack_obj[3], indent=4, ensure_ascii=False, cls=MyEncoder)
        self.treeWidget.clear()
        add_dict_to_tree(self.treeWidget, request_header)
        self.treeWidget_2.clear()
        add_dict_to_tree(self.treeWidget_2, response_header)
        self.textEdit.clear()
        self.textEdit.setPlainText(request_body)
        self.textEdit_2.clear()
        self.textEdit_2.setPlainText(response_body)

    def click_pushbutton(self):
        """停止按钮事件"""
        if self._running:
            self._running = False
            self.server.send_message("STOP".encode("utf-8"))
            self.statusbar.showMessage('停止监听程序', 1000)
            self.set_signal_led(False)
        else:
            if self.server.get_connect_count() > 0:
                self.server.send_message("STOP".encode("utf-8"))
                self.set_signal_led(False)
            QMessageBox.about(self, "提示", "未发现运行中的监听程序！")

    def click_pushbutton_2(self):
        """应用按钮事件【改包】"""
        self.message_obj = {}
        url = self.lineEdit_2.text()
        type_post = self.radioButton.isChecked()
        type_get = self.radioButton_2.isChecked()
        status_code = self.lineEdit_3.text()
        r_h = self.checkBox.checkState()
        r_b = self.checkBox_2.checkState()
        s_h = self.checkBox_3.checkState()
        s_b = self.checkBox_4.checkState()
        if url != "":  # 请求地址不为空
            is_json = True
            self.message_obj["method"] = "Repackage"
            self.message_obj["url"] = url
            self.message_obj["code"] = int(status_code) if status_code != "" else -999
            self.message_obj["operator"] = [r_h, r_b, s_h, s_b]
            if r_h == 2:  # 请求头选中
                r_h_t = self.textEdit_6.toPlainText()
                is_json, json_data = obj_is_json(r_h_t)
                if is_json:
                    self.message_obj["r_h"] = json.dumps(json_data)
                else:
                    QMessageBox.about(self, "提示", "请求头内容必须是JSON字符串格式！")
            if r_b == 2:  # 请求体选中
                r_b_t = self.textEdit_5.toPlainText()
                is_json, json_data = obj_is_json(r_b_t)
                if is_json:
                    self.message_obj["r_b"] = json.dumps(json_data)
                else:
                    QMessageBox.about(self, "提示", "请求体内容必须是JSON字符串格式！")
            if s_h == 2:  # 响应头选中
                s_h_t = self.textEdit_4.toPlainText()
                is_json, json_data = obj_is_json(s_h_t)
                if is_json:
                    self.message_obj["s_h"] = json.dumps(json_data)
                else:
                    QMessageBox.about(self, "提示", "响应头内容必须是JSON字符串格式！")
            if s_b == 2:  # 响应体选中
                s_b_t = self.textEdit_3.toPlainText()
                is_json, json_data = obj_is_json(s_b_t)
                if is_json:
                    self.message_obj["s_b"] = json.dumps(json_data)
                else:
                    QMessageBox.about(self, "提示", "响应体内容必须是JSON字符串格式！")
            if type_post:
                self.message_obj["type"] = "POST"
            else:
                self.message_obj["type"] = "GET"
            if is_json:     # 发送改包指令
                send_order = json.dumps(self.message_obj, ensure_ascii=False, cls=MyEncoder).encode("utf-8")
                self.server.send_message(send_order)
                QMessageBox.about(self, "提示", "改包数据指令发送成功！")
        else:
            QMessageBox.about(self, "提示", "请先输入接口URL！")

    def click_pushbutton_3(self):
        """开始按钮事件"""
        global request_list
        request_list = []
        if not self._running:
            self._running = True
            self.statusbar.showMessage('启动监听程序', 1000)
            self.set_signal_led(True)
            t = threading.Thread(target=self.run_record, args=())
            t.start()
        else:
            QMessageBox.about(self, "提示", "监听程序正在运行！")

    def click_command_button_1(self):
        """命令按钮事件"""
        help_text = "<p>过滤条件规则如下:</p>" \
                    "<p>    rex  示例：默认正则匹配请求url</p>" \
                    "<p>    ~q  Request   示例：匹配请求内容</p>" \
                    "<p>    ~s  Response  示例：匹配响应内容</p>" \
                    "<p>    ~a  text/javascript  示例：匹配content-type</p>" \
                    "<p>    ~h  rex  示例：正则匹配请求header或者响应header</p>" \
                    "<p>    ~hq rex  示例：正则匹配请求header</p>" \
                    "<p>    ~hs rex  示例：正则匹配响应header</p>" \
                    "<p>    ~b rex   示例：正则匹配请求body或者响应body</p>"\
                    "<p>    ~bq rex  示例：正则匹配请求body</p>" \
                    "<p>    ~bs rex  示例：正则匹配响应body</p>"\
                    "<p>    ~t rex   示例：正则匹配请求header的content-type</p>" \
                    "<p>    ~d rex   示例：正则匹配请求domain</p>"\
                    "<p>    ~m rex   示例：正则匹配请求method</p>" \
                    "<p>    ~u rex   示例：正则匹配请求url</p>" \
                    "<p>    ~c code  示例：匹配响应code</p>" \
                    "<p>*具体使用方法参考：mitmproxy.flowfilter*</p>"
        QMessageBox.question(self, "帮助", help_text, QMessageBox.Yes)

    def click_pushbutton_4(self):
        """启用弱网工具"""
        self.message_obj = {}
        # mock_path = os.path.join(self.path, "test.py")
        # subprocess.call(["runas", "/user:Administrator", "python", mock_path])
        filter_option = self.lineEdit_4.text()
        lag = self.checkBox_5.checkState()
        lag_in = self.checkBox_7.checkState()
        lag_out = self.checkBox_8.checkState()
        drop = self.checkBox_6.checkState()
        drop_in = self.checkBox_9.checkState()
        drop_out = self.checkBox_10.checkState()
        lag_v = self.lineEdit_5.text()
        drop_v = self.lineEdit_6.text()
        self.message_obj["method"] = "MockNetwork"
        self.message_obj["operator"] = [lag, drop]
        self.message_obj["filter"] = filter_option
        if lag == 2:    # 模拟延迟操作
            if lag_v == "": lag_v = 0
            self.message_obj["lag"] = {"in": lag_in, "out": lag_out, "value": int(lag_v)/1000}
        if drop == 2:   # 模拟丢包操作
            if drop_v == "": drop_v = 0
            self.message_obj["drop"] = {"in": drop_in, "out": drop_out, "value": int(drop_v)/100}
        send_order = json.dumps(self.message_obj, ensure_ascii=False, cls=MyEncoder).encode("utf-8")
        if self._running:
            if lag == 0 and drop == 0:
                QMessageBox.about(self, "提示", "请先选择需要模拟的场景！")
            else:
                try:
                    flowfilter.parse(filter_option)
                    self.server.send_message(send_order)
                    QMessageBox.about(self, "提示", "模拟弱网指令发送成功！")
                except ValueError:
                    QMessageBox.about(self, "提示", "过滤表达式不对，请检查！")
        else:
            QMessageBox.about(self, "提示", "请先<开始>抓包程序，然后再<启用>！")

    def click_pushbutton_5(self):
        """停用弱网工具"""
        self.message_obj = {}
        self.message_obj["method"] = "UnMockNetwork"
        send_order = json.dumps(self.message_obj, ensure_ascii=False, cls=MyEncoder).encode("utf-8")
        self.server.send_message(send_order)
        QMessageBox.about(self, "提示", "停用模拟弱网指令发送成功！")

    def on_checkbox_4_click(self):
        """选择复选框后tab联动事件"""
        self.tabWidget_4.setCurrentIndex(0)

    def on_checkbox_3_click(self):
        """选择复选框后tab联动事件"""
        self.tabWidget_4.setCurrentIndex(1)

    def on_checkbox_2_click(self):
        """选择复选框后tab联动事件"""
        self.tabWidget_4.setCurrentIndex(2)

    def on_checkbox_1_click(self):
        """选择复选框后tab联动事件"""
        self.tabWidget_4.setCurrentIndex(3)

    def set_signal_led(self, state):
        """改变信号灯的状态"""
        pal = self.signal_led.palette()
        if state:
            pal.setColor(QPalette.Background, Qt.green)  # 绿色表示开启
        else:
            pal.setColor(QPalette.Background, Qt.red)  # 红色表示关闭
        self.signal_led.setPalette(pal)

    # 窗口关闭事件
    def closeEvent(self, evt):
        result = QMessageBox.question(self, '关闭应用', '确定关闭应用?',
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if result == QMessageBox.Yes:
            evt.accept()
            self.server.server_socket.close()
            QWidget.closeEvent(self, evt)
        else:
            evt.ignore()
            self.statusbar.showMessage('取消关闭', 1000)


if __name__ == '__main__':
    # 创建应用程序和主窗口
    app = QApplication(sys.argv)
    win = HAgentMainWindow()
    # 设置样式表
    apply_stylesheet(app, theme='dark_teal.xml')
    # 运行
    win.show()
    sys.exit(app.exec_())
