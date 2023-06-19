# klippy status push to wechat
#
# Copyright (C) 2022 Xiaokui Zhao <xiaok@zxkxz.cn>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations
import logging
import requests
import base64
import os
import socket
import re
from PIL import Image, ImageFont, ImageDraw

# Annotation imports
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Dict,
    List,
)

if TYPE_CHECKING:
    from confighelper import ConfigHelper
    from .klippy_apis import KlippyAPI
    DBComp = database.MoonrakerDatabase


class PushWechat:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.last_print_stats: Dict[str, Any] = {}

        self.msgtype: str = config.get('msg_type')

        if self.msgtype == "wechat":
            self.corpsecret: str = config.get('corp_secret')
            self.corpsecret = self.corpsecret.replace(" ", "")

            self.agentid: str = config.get('agent_id')
            self.agentid = self.agentid.replace(" ", "")

            self.corpid: str = config.get('corp_id')
            self.corpid = self.corpid.replace(" ", "")

            self.touser: str = config.get('to_user')
            self.touser = self.touser.replace(" ", "")
        elif self.msgtype == "mail":
            self.mail_host: str = config.get('mail_host')
            self.mail_host = self.mail_host.replace(" ", "")

            self.mail_user: str = config.get('mail_user')
            self.mail_user = self.mail_user.replace(" ", "")

            self.mail_pass: str = config.get('mail_pass')
            self.mail_pass = self.mail_pass.replace(" ", "")

            self.touser: str = config.get('to_user')
            self.touser = self.touser.replace(" ", "")

            self.mail_port: int = config.get('mail_port', 25)
        else:
            self.server.add_warning(
                f"[Push_Wechat] Unsupported message types {self.msgtype}"
                "\n\nIf you want to get rid of this warning, please restart MoonRaker.")
            logging.error("Unsupported message types")
            return

        db: DBComp = self.server.load_component(config, "database")
        db_path = db.get_database_path()
        self.gc_path: str = db.get_item(
            "moonraker", "file_manager.gcode_path", "").result()
        self.print_name: str = db.get_item(
            "fluidd", "uiSettings.general.instanceName", "").result()
        if self.print_name is None:
            self.print_name = db.get_item(
                "mainsail", "uiSettings.general.instanceName", "").result()
        if self.print_name is None:
            self.print_name = self.server.get_host_info()['hostname']

        self.last_print_stats: Dict[str, Any] = {}
        self.server.register_event_handler(
            "server:klippy_started", self._handle_started)
        self.server.register_event_handler(
            "server:klippy_shutdown", self._handle_shutdown)
        self.server.register_event_handler(
            "server:status_update", self._status_update)

    async def _handle_started(self, state: str) -> None:
        if state != "ready":
            return
        kapis: KlippyAPI = self.server.lookup_component('klippy_apis')
        sub: Dict[str, Optional[List[str]]] = {"print_stats": None}
        try:
            result = await kapis.subscribe_objects(sub)
        except self.server.error as e:
            logging.info(f"Error subscribing to print_stats")
        self.last_print_stats = result.get("print_stats", {})
        if "state" in self.last_print_stats:
            state = self.last_print_stats["state"]
            logging.info(f"Job state initialized: {state}")

    async def _handle_shutdown(self, state: str) -> None:
        logging.info(f"Shutdown: {state}")

    async def _status_update(self, data: Dict[str, Any]) -> None:
        # print(data)
        if "webhooks" in data:
            webhooks = data['webhooks']
            state = webhooks['state']
            state_message = webhooks['state_message']
            logging.info(f"Status: {state}")
            logging.info(f"Info: {state_message}")
            if state == "shutdown":
                # 报错停机
                self._pushState(state=state, text=state_message)
        elif "print_stats" in data:
            print_stats = data['print_stats']

            if "state" in print_stats:
                new_ps = dict(self.last_print_stats)
                new_ps.update(print_stats)
                state = print_stats['state']
                filename = new_ps['filename']
                if state == "printing":
                    # 开始打印
                    self._pushState(state=state, filename=filename)
                elif state == "complete":
                    # 打印完成
                    self._pushState(state=state, filename=filename)
                elif state == "error":
                    # 错误
                    self._pushState(state=state, text=new_ps['message'])
                elif state == "paused":
                    # 暂停
                    self._pushState(state=state, filename=filename)
                elif state == "standby":
                    # 取消
                    self._pushState(state=state, filename=filename)
                else:
                    logging.info(f"状态：{state}")
                    print(data)
            self.last_print_stats.update(print_stats)

    def _getAsToken(self):
        dic = {'corpid': self.corpid, 'corpsecret': self.corpsecret}
        r = requests.post(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken", json=dic)
        data = r.json()
        errcode = data["errcode"]
        if errcode != 0:
            self.server.add_warning(
                f"[Push_Wechat] Failed to get access_token. ErrCode:{errcode},ErrMsg:{data['errmsg']}"
                "\n\nIf you want to get rid of this warning, please restart MoonRaker.")
            logging.error(
                f"Failed to get access_token. ErrCode:{errcode},ErrMsg:{data['errmsg']}")
            return None
        return data['access_token']

    def _uploadImage(self, path):
        # 判断图片是否存在
        if not os.path.exists(path):
            logging.error("image does not exist")
            return

        # 获取Access token
        AsToken: str = self._getAsToken()
        if AsToken is None:
            return False

        file = {'attachment_file': (path, open(path, 'rb'), 'image/png', {})}

        # 上传图片到企业微信素材库
        r = requests.post(
            f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={AsToken}&type=image", files=file)

        # 判断是否上传成功
        if r.json()['errcode'] != 0:
            logging.error(
                f"Media file upload failed. ErrCode:{r.json()['errcode']},ErrMsg:{r.json()['errmsg']}")
            return

        # 获取并返回素材ID
        media_id = r.json()['media_id']
        return media_id

    def _pushState(self, state: str, text: str = None, filename: str = None):
        dic = {}
        AsToken: str = self._getAsToken()
        if AsToken is None:
            return False

        state_title = ""
        info = ""
        media_id = ""
        digest = ""
        color = ""
        # 判断打印机状态
        if state == "shutdown":
            state_title = "停机"
            color = "red"
            info = text
            if "\n" in text:
                digest = text.split("\n")[0]
            else:
                digest = text

            # 创建图片
            im = Image.new("RGB", (300, 100), (64, 44, 46))
            dr = ImageDraw.Draw(im)
            font = ImageFont.truetype(os.path.join(
                "fonts", "/tmp/FreeMono.ttf"), 12)
            dr.text((35, 5), info, font=font, fill="#FF5252")
            # im.show()
            im.save(r"/tmp/mwx_media.png")

            # 上传临时图片
            media_id = self._uploadImage("/tmp/mwx_media.png")
        elif state == "printing":
            state_title = "开始打印"
            color = "green"
            info = f"Printstart: \n{filename}"
            digest = info

            files = os.listdir(self.gc_path + "/.thumbs/")
            img = ".png"
            for file in files:
                print(file)
                match = re.search(filename.replace(
                    ".gcode", "-") + "(.*?)x(.*?).png", file)

                if match:
                    if "32x32" not in file:
                        img = file
                        break

            media_path = self.gc_path + "/.thumbs/" + img
            if not os.path.exists(media_path):
                # 创建图片
                im = Image.new("RGB", (300, 80), (255, 255, 255))
                dr = ImageDraw.Draw(im)
                font = ImageFont.truetype(os.path.join(
                    "fonts", "/tmp/FreeMono.ttf"), 12)
                dr.text((35, 5), info, font=font, fill="#00FF7F")
                # im.show()
                im.save(r"/tmp/mwx_media.png")
                media_path = "/tmp/mwx_media.png"
            media_id = self._uploadImage(media_path)

        elif state == "complete":
            state_title = "打印结束"
            color = "blue"
            info = f"Printed: \n{filename} \n"
            digest = info

            files = os.listdir(self.gc_path + "/.thumbs/")
            img = ".png"
            for file in files:
                print(file)
                match = re.search(filename.replace(
                    ".gcode", "-") + "(.*?)x(.*?).png", file)

                if match:
                    if "32x32" not in file:
                        img = file
                        break

            media_path = self.gc_path + "/.thumbs/" + img
            if not os.path.exists(media_path):
                # 创建图片
                im = Image.new("RGB", (300, 80), (255, 255, 255))
                dr = ImageDraw.Draw(im)
                font = ImageFont.truetype(os.path.join(
                    "fonts", "/tmp/FreeMono.ttf"), 12)
                dr.text((35, 5), info, font=font, fill="#00BFFF")
                # im.show()
                im.save(r"/tmp/mwx_media.png")
                media_path = "/tmp/mwx_media.png"
            media_id = self._uploadImage(media_path)
        elif state == "error":
            state_title = "错误"
            color = "red"
            info = text
            digest = text

            # 创建图片
            im = Image.new("RGB", (300, 100), (64, 44, 46))
            dr = ImageDraw.Draw(im)
            font = ImageFont.truetype(os.path.join(
                "fonts", "/tmp/FreeMono.ttf"), 12)
            dr.text((35, 5), info, font=font, fill="#FF5252")
            # im.show()
            im.save(r"/tmp/mwx_media.png")

            # 上传临时图片
            media_id = self._uploadImage("/tmp/mwx_media.png")
        elif state == "paused":
            # 暂停
            state_title = "打印暂停"
            color = "yellow"
            info = f"Printing: \n{filename} \n"
            digest = info

            files = os.listdir(self.gc_path + "/.thumbs/")
            img = ".png"
            for file in files:
                print(file)
                match = re.search(filename.replace(
                    ".gcode", "-") + "(.*?)x(.*?).png", file)

                if match:
                    if "32x32" not in file:
                        img = file
                        break

            media_path = self.gc_path + "/.thumbs/" + img
            if not os.path.exists(media_path):
                # 创建图片
                im = Image.new("RGB", (300, 80), (255, 255, 255))
                dr = ImageDraw.Draw(im)
                font = ImageFont.truetype(os.path.join(
                    "fonts", "/tmp/FreeMono.ttf"), 12)
                dr.text((35, 5), info, font=font, fill="#00BFFF")
                # im.show()
                im.save(r"/tmp/mwx_media.png")
                media_path = "/tmp/mwx_media.png"
            media_id = self._uploadImage(media_path)
        elif state == "standby":
            # 取消
            state_title = "取消打印"
            color = "red"
            info = f"Printed: \n{filename} \n"
            digest = info

            files = os.listdir(self.gc_path + "/.thumbs/")
            img = ".png"
            for file in files:
                print(file)
                match = re.search(filename.replace(
                    ".gcode", "-") + "(.*?)x(.*?).png", file)

                if match:
                    if "32x32" not in file:
                        img = file
                        break

            media_path = self.gc_path + "/.thumbs/" + img
            if not os.path.exists(media_path):
                # 创建图片
                im = Image.new("RGB", (300, 80), (255, 255, 255))
                dr = ImageDraw.Draw(im)
                font = ImageFont.truetype(os.path.join(
                    "fonts", "/tmp/FreeMono.ttf"), 12)
                dr.text((35, 5), info, font=font, fill="#00BFFF")
                # im.show()
                im.save(r"/tmp/mwx_media.png")
                media_path = "/tmp/mwx_media.png"
            media_id = self._uploadImage(media_path)
        else:
            logging.error("unknown state")
            return

        f = open('/tmp/mwx_media.png', 'rb')
        imagebytes = base64.b64encode(f.read())
        f.close()
        imagestr = str(imagebytes)
        realimagestr = imagestr[2:len(imagestr)-1]

        hostname = self.server.get_host_info()['hostname']
        ip = self._extract_ip()
        info = info.replace("\n", "</br>")
        html = f"""
                </br>
                <img src="data:image/png;base64,{realimagestr}"></img>
                </br>
                <font size="5">状态：</font> <font color="{color}" size="5">{state}</font>
                </br>
                <font size="5">详情：</font> <font color="{color}" size="5">{info}</font>
                </br>
                <font size="5">域地址：</font> <a href="http://{hostname}/"> <font color="blue" size="5">{hostname}</font> </a>
                </br>
                <font size="5">IP地址: </font>  <a href="http://{ip}/"> <font color="blue" size="5">{ip}</font> </a>
                </br>
                </br>
                </br>
                <font color="green" size="4">点击“阅读原文”前往控制端</font>
                """

        if self.msgtype == "wechat":
            logging.info("wechat")
            article = {
                'title': f"[{self.print_name}] 状态更新：{state_title}",
                'thumb_media_id': media_id,
                'author': self.print_name,
                'content_source_url': f"http://{ip}/",
                'content': html,
                'digest': digest
            }
            dic = {'touser': self.touser, 'msgtype': "mpnews", 'agentid': self.agentid, 'mpnews': {
                'articles': [article]}, 'enable_duplicate_check': 0, 'duplicate_check_interval': 1800}

            r = requests.post(
                "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=" + AsToken, json=dic)
            if r.json()['errcode'] == 0:
                logging.info(f"Message push successfully: {r.json()['msgid']}")
                return
            else:
                self.server.add_warning(
                    f"[Push_Wechat] Failed to push message. ErrCode:{r.json()['errcode']},ErrMsg:{r.json()['errmsg']}"
                    "\n\nIf you want to get rid of this warning, please restart MoonRaker.")
                logging.error(
                    f"Failed to push message. ErrCode:{r.json()['errcode']},ErrMsg:{r.json()['errmsg']}")
                return
        elif self.msgtype == "mail":
            logging.info("mail")

    def _extract_ip(self):
        st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            st.connect(('10.255.255.255', 1))
            IP = st.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            st.close()
        return IP


def load_component(config: ConfigHelper) -> PushWechat:
    return PushWechat(config)
