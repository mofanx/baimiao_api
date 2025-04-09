#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
白描OCR截图工具 - 集成版
支持Linux、Windows和macOS系统
使用环境变量获取敏感信息
支持快捷键调用
"""

import os
import sys
import time
import base64
import platform
import tempfile
import shutil
import subprocess
import hashlib
import uuid
import json
import threading
import requests
from pathlib import Path

# 可选依赖，根据平台动态导入
try:
    import keyboard
except ImportError:
    keyboard = None
    print("警告：未安装keyboard模块，快捷键功能将不可用")
    print("安装方法：pip install keyboard")

try:
    import pyclip
except ImportError:
    pyclip = None
    print("警告：未安装pyclip模块，剪贴板功能可能受限")
    print("安装方法：pip install pyclip")


class BaimiaoOCR:
    """白描OCR API封装类"""
    
    def __init__(self):
        """初始化白描OCR
        
        从环境变量获取敏感信息，如果没有则使用默认值
        """
        # 从环境变量获取用户名和密码
        self.username = os.environ.get('BAIMIAO_USERNAME', '')
        self.password = os.environ.get('BAIMIAO_PASSWORD', '')
        self.uuid = os.environ.get('BAIMIAO_UUID', '')
        self.login_token = os.environ.get('BAIMIAO_TOKEN', '')
        
        # 如果环境变量中没有设置，尝试创建新的UUID
        if not self.uuid:
            self.uuid = str(uuid.uuid4())
            print(f"已生成新的UUID: {self.uuid}")
            print("建议将此UUID添加到环境变量中: BAIMIAO_UUID")
            
        # 设置API URL和请求头
        self.url = "https://web.baimiaoapp.com"
        self.headers = {
            "Host": "web.baimiaoapp.com",
            "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'X-AUTH-TOKEN': self.login_token,
            'X-AUTH-UUID': self.uuid,
            'Origin': 'https://web.baimiaoapp.com',
            'Referer': 'https://web.baimiaoapp.com/',
        }

    def login(self):
        """登录白描API"""
        if not self.username or not self.password:
            print("警告：未设置用户名或密码，将使用匿名登录")
            return self._anonymous_login()
            
        # 确保UUID已设置
        if not self.uuid:
            self.uuid = str(uuid.uuid4())
        self.headers["X-AUTH-UUID"] = self.uuid

        # 准备登录请求
        login_headers = self.headers.copy()
        login_headers['X-AUTH-TOKEN'] = ''
        login_headers['X-AUTH-UUID'] = self.uuid

        # 根据用户名格式确定登录类型
        login_type = "mobile" if self.username.isdigit() else "email"

        # 准备登录数据
        data = {
            'username': self.username,
            'password': self.password,
            'type': login_type
        }

        # 发送登录请求
        response = requests.post(f"{self.url}/api/user/login", headers=login_headers, json=data)
        if response.ok:
            result = response.json()
            if result.get('data', {}).get('token'):
                self.login_token = result['data']['token']
                self.headers["X-AUTH-TOKEN"] = self.login_token
                print("登录成功！")
                return True
            else:
                raise Exception(json.dumps(result, ensure_ascii=False))
        else:
            raise Exception(f"Http请求错误\nHttp状态码: {response.status_code}\n{response.text}")

    def _anonymous_login(self):
        """匿名登录白描API"""
        # 确保UUID已设置
        if not self.uuid:
            self.uuid = str(uuid.uuid4())
        self.headers["X-AUTH-UUID"] = self.uuid

        # 发送匿名登录请求
        response = requests.post(f"{self.url}/api/user/login/anonymous", headers=self.headers)
        if response.ok:
            result = response.json()
            if result.get('data', {}).get('token') is not None:
                self.login_token = result['data']['token']
                self.headers["X-AUTH-TOKEN"] = self.login_token
                print("匿名登录成功！")
                return True
            else:
                raise Exception(json.dumps(result, ensure_ascii=False))
        else:
            raise Exception(f"Http请求错误\nHttp状态码: {response.status_code}\n{response.text}")
            
    def recognize(self, base64_image):
        """识别图片中的文字
        
        Args:
            base64_image (str): 图片的base64编码字符串
            
        Returns:
            str: 识别出的文字
        """
        # 确保登录状态
        if not self.uuid or not self.login_token:
            self.login()

        self.headers['X-AUTH-UUID'] = self.uuid
        self.headers['X-AUTH-TOKEN'] = self.login_token

        # 匿名登录获取最新token
        response = requests.post(f"{self.url}/api/user/login/anonymous", headers=self.headers)
        if response.ok:
            result = response.json()
            if result.get('data', {}).get('token') is not None:
                self.login_token = result['data']['token']
                if not self.login_token:
                    self.login()
                self.headers["X-AUTH-TOKEN"] = self.login_token
            else:
                raise Exception(json.dumps(result, ensure_ascii=False))
        else:
            raise Exception(f"Http请求错误\nHttp状态码: {response.status_code}\n{response.text}")

        # 获取权限
        data = {'mode': 'single'}
        response = requests.post(f"{self.url}/api/perm/single", headers=self.headers, json=data)
        if response.ok:
            result = response.json()
            if result.get('data', {}).get('engine'):
                engine = result['data']['engine']
                token = result['data']['token']
            else:
                raise Exception("已经达到今日识别上限，请前往白描手机端开通会员或明天再试")
        else:
            raise Exception(f"Http请求错误\nHttp状态码: {response.status_code}\n{response.text}")

        # 计算哈希值
        image_data_url = f"data:image/png;base64,{base64_image}"
        hash_value = hashlib.sha1(image_data_url.encode('utf-8')).hexdigest()

        # 开始 OCR 识别过程
        data = {
            "batchId": "",
            "total": 1,
            "token": token,
            "hash": hash_value,
            "name": "screenshot.png",
            "size": 0,
            "dataUrl": image_data_url,
            "result": {},
            "status": "processing",
            "isSuccess": False
        }
        response = requests.post(f"{self.url}/api/ocr/image/{engine}", headers=self.headers, json=data)
        if response.ok:
            result = response.json()
            if result.get('data', {}).get('jobStatusId'):
                job_status_id = result['data']['jobStatusId']
            else:
                raise Exception(json.dumps(result, ensure_ascii=False))
        else:
            raise Exception(f"Http请求错误\nHttp状态码: {response.status_code}\n{response.text}")

        # 轮询结果
        while True:
            time.sleep(0.1)
            params = {'jobStatusId': job_status_id}
            response = requests.get(f"{self.url}/api/ocr/image/{engine}/status", headers=self.headers, params=params)
            if response.ok:
                result = response.json()
                if not result.get('data', {}).get('isEnded'):
                    continue
                else:
                    words_result = result['data']['ydResp']['words_result']
                    text = "\n".join([item['words'] for item in words_result])
                    return text
            else:
                raise Exception(f"Http请求错误\nHttp状态码: {response.status_code}\n{response.text}")


class ScreenshotTool:
    """多平台截图工具类"""
    
    def __init__(self, cache_dir_name='baimiao_ocr'):
        """初始化截图工具
        
        Args:
            cache_dir_name (str): 缓存目录名称
        """
        self.is_capturing = False
        self.system = platform.system()  # 获取操作系统类型
        
        # 获取用户缓存目录
        self.cache_dir = self._get_cache_dir(cache_dir_name)
        
        # 设置截图保存路径
        if self.cache_dir:
            self.temp_dir = self.cache_dir  # 不是临时创建的目录，所以不会在__del__中被删除
            self.screenshot_path = os.path.join(self.cache_dir, f'screenshot_{int(time.time())}.png')
        else:
            # 如果创建缓存目录失败，使用临时目录
            self.temp_dir = tempfile.mkdtemp()
            self.screenshot_path = os.path.join(self.temp_dir, 'screenshot.png')
            
    def _get_cache_dir(self, cache_dir_name):
        """根据不同操作系统获取缓存目录"""
        try:
            if self.system == 'Linux':
                # Linux系统
                if hasattr(os, 'geteuid') and os.geteuid() == 0:
                    # 如果是root用户运行，获取原始用户
                    username = os.environ.get('SUDO_USER', 'root')
                    user_home = f"/home/{username}"
                else:
                    # 非root用户
                    user_home = os.path.expanduser('~')
                cache_dir = os.path.join(user_home, '.cache', cache_dir_name)
                
                # 创建目录并设置权限
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir, exist_ok=True)
                    # 如果是root创建的目录，确保原始用户有权限
                    if hasattr(os, 'geteuid') and os.geteuid() == 0:
                        username = os.environ.get('SUDO_USER')
                        if username and username != 'root':
                            import pwd
                            uid = pwd.getpwnam(username).pw_uid
                            gid = pwd.getpwnam(username).pw_gid
                            os.chown(cache_dir, uid, gid)
                            
            elif self.system == 'Windows':
                # Windows系统
                appdata = os.environ.get('LOCALAPPDATA')
                if not appdata:
                    appdata = os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local')
                cache_dir = os.path.join(appdata, cache_dir_name)
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir, exist_ok=True)
                    
            elif self.system == 'Darwin':
                # macOS系统
                user_home = os.path.expanduser('~')
                cache_dir = os.path.join(user_home, 'Library', 'Caches', cache_dir_name)
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir, exist_ok=True)
            else:
                # 其他系统使用临时目录
                print(f"未知操作系统: {self.system}，使用临时目录")
                return None
                
            return cache_dir
        except Exception as e:
            print(f"创建缓存目录失败: {e}")
            return None
        
    def __del__(self):
        """清理临时文件"""
        # 清理临时文件
        if hasattr(self, 'temp_dir') and self.temp_dir and os.path.exists(self.temp_dir):
            if self.temp_dir.startswith(tempfile.gettempdir()):  # 只删除系统临时目录
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # 删除截图文件
        if hasattr(self, 'screenshot_path') and os.path.exists(self.screenshot_path):
            try:
                os.remove(self.screenshot_path)
            except Exception as e:
                print(f"删除截图文件失败: {e}")
        
    def capture_screenshot(self):
        """截取屏幕区域
        
        Returns:
            str: 截图文件路径，如果截图失败则返回None
        """
        print("正在启动截图工具...")
        try:
            if self._take_screenshot_with_system_tools():
                return self.screenshot_path
            else:
                print("截图失败，请确保安装了截图工具")
                return None
        except Exception as e:
            print(f"截图失败: {str(e)}")
            return None
    
    def _take_screenshot_with_system_tools(self):
        """使用系统工具进行截图"""
        try:
            print("正在进行区域截图...")
            
            if self.system == 'Linux':
                return self._take_screenshot_linux()
            elif self.system == 'Windows':
                return self._take_screenshot_windows()
            elif self.system == 'Darwin':
                return self._take_screenshot_macos()
            else:
                print(f"不支持的操作系统: {self.system}")
                return False
        except Exception as e:
            print(f"截图失败: {str(e)}")
            return False
            
    def _take_screenshot_linux(self):
        """Linux系统下的截图方法"""
        try:
            # 检查是否安装了gnome-screenshot
            if not shutil.which('gnome-screenshot'):
                print("错误：未安装gnome-screenshot工具")
                return False
                
            # 检查是否是root用户运行
            if hasattr(os, 'geteuid') and os.geteuid() == 0:
                # 获取当前用户的DISPLAY和XAUTHORITY环境变量
                current_user = os.environ.get('SUDO_USER')
                user_home = f"/home/{current_user}" if current_user else os.path.expanduser('~')
                display = os.environ.get('DISPLAY', ':0')
                xauthority = os.environ.get('XAUTHORITY', f"{user_home}/.Xauthority")
                
                # 使用su命令以原用户身份运行gnome-screenshot
                cmd = f"DISPLAY={display} XAUTHORITY={xauthority} gnome-screenshot -a -f {self.screenshot_path}"
                subprocess.run(['su', current_user, '-c', cmd], check=True)
            else:
                # 非root用户直接运行
                subprocess.run(['gnome-screenshot', '-a', '-f', self.screenshot_path], check=True)

            return self._wait_for_screenshot()
        except subprocess.CalledProcessError as e:
            print(f"gnome-screenshot截图失败: {e}")
            return False
        except Exception as e:
            print(f"Linux截图失败: {str(e)}")
            return False
            
    def _take_screenshot_windows(self):
        """Windows系统下的截图方法"""
        try:
            # 使用PIL和pyautogui进行截图
            try:
                from PIL import ImageGrab
                import pyautogui
            except ImportError:
                print("错误：未安装必要的库，请运行以下命令安装：")
                print("pip install pillow pyautogui")
                return False
                
            # 提示用户按下回车键开始截图
            print("请按下回车键开始截图，然后拖动鼠标选择区域...")
            input()
            
            # 记录鼠标初始位置
            start_x, start_y = pyautogui.position()
            print("请拖动鼠标并点击以选择区域...")
            
            # 等待鼠标点击
            pyautogui.mouseDown()
            while pyautogui.mouseIsDown():
                time.sleep(0.1)
                
            # 获取结束位置
            end_x, end_y = pyautogui.position()
            
            # 确保坐标正确（左上角到右下角）
            left = min(start_x, end_x)
            top = min(start_y, end_y)
            right = max(start_x, end_x)
            bottom = max(start_y, end_y)
            
            # 截取屏幕区域
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            screenshot.save(self.screenshot_path)
            
            return self._wait_for_screenshot()
        except Exception as e:
            print(f"Windows截图失败: {str(e)}")
            return False
            
    def _take_screenshot_macos(self):
        """macOS系统下的截图方法"""
        try:
            # 使用screencapture命令进行截图
            subprocess.run(['screencapture', '-i', '-s', self.screenshot_path], check=True)
            return self._wait_for_screenshot()
        except subprocess.CalledProcessError as e:
            print(f"screencapture截图失败: {e}")
            return False
        except Exception as e:
            print(f"macOS截图失败: {str(e)}")
            return False
            
    def _wait_for_screenshot(self):
        """等待截图文件生成"""
        # 等待截图文件生成
        max_wait = 5  # 最大等待时间（秒）
        wait_time = 0
        while wait_time < max_wait:
            if os.path.exists(self.screenshot_path) and os.path.getsize(self.screenshot_path) > 0:
                print(f"截图文件已生成: {self.screenshot_path}")
                return True
            time.sleep(0.5)
            wait_time += 0.5
            
        print("截图文件生成超时")
        return False

    def image_to_base64(self, image_path):
        """将图片文件转换为base64编码"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在：{image_path}")
        
        with open(image_path, 'rb') as image_file:
            base64_data = base64.b64encode(image_file.read()).decode('utf-8')
        return base64_data


class ScreenshotOCR:
    """结合截图和白描OCR的工具类"""
    
    def __init__(self, cache_dir_name='baimiao_ocr'):
        """初始化截图OCR工具"""
        self.screenshot_tool = ScreenshotTool(cache_dir_name)
        self.ocr = BaimiaoOCR()
        
    def capture_and_recognize(self):
        """截取屏幕并识别文字
        
        Returns:
            str: 识别出的文字，如果失败则返回None
        """
        try:
            # 截图
            screenshot_path = self.screenshot_tool.capture_screenshot()
            if not screenshot_path or not os.path.exists(screenshot_path):
                print("截图失败")
                self._send_notification("白描OCR", "截图失败", "error")
                return None
                
            # 转换为base64
            base64_data = self.screenshot_tool.image_to_base64(screenshot_path)
                
            # OCR识别
            print("正在进行OCR识别...")
            text = self.ocr.recognize(base64_data)
            
            # 复制到剪贴板
            if text:
                self._copy_to_clipboard(text)
                print("识别成功！文本已复制到剪贴板")
                self._send_notification("白描OCR", "识别成功！文本已复制到剪贴板", "normal")
            else:
                print("OCR识别失败或未识别出文本")
                self._send_notification("白描OCR", "OCR识别失败或未识别出文本", "error")
                
            return text
        except Exception as e:
            error_msg = f"截图识别失败: {str(e)}"
            print(error_msg)
            self._send_notification("白描OCR", error_msg, "error")
            return None
            
    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        try:
            # 优先使用pyclip库
            if pyclip:
                pyclip.copy(text)
                return True
                
            # 如果没有pyclip，根据操作系统选择备用方法
            system = platform.system()
            if system == 'Linux':
                # Linux使用xclip或xsel
                if shutil.which('xclip'):
                    subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)
                    return True
                elif shutil.which('xsel'):
                    subprocess.run(['xsel', '-b', '-i'], input=text.encode('utf-8'), check=True)
                    return True
                else:
                    print("警告：未安装xclip或xsel，无法复制到剪贴板")
                    print("安装方法：sudo apt-get install xclip 或 sudo apt-get install xsel")
                    return False
            elif system == 'Windows':
                # Windows使用pywin32
                try:
                    import win32clipboard
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                    return True
                except ImportError:
                    print("警告：未安装pywin32，无法复制到剪贴板")
                    print("安装方法：pip install pywin32")
                    return False
            elif system == 'Darwin':
                # macOS使用pbcopy
                subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
                return True
            else:
                print(f"不支持的操作系统: {system}")
                return False
        except Exception as e:
            print(f"复制到剪贴板失败: {str(e)}")
            return False
            
    def _send_notification(self, title, message, level='normal'):
        """发送系统通知
        
        Args:
            title (str): 通知标题
            message (str): 通知内容
            level (str): 通知级别，'normal'或'error'
        """
        try:
            system = platform.system()
            
            if system == 'Linux':
                # Linux使用notify-send
                icon = "dialog-error" if level == 'error' else "dialog-information"
                
                # 判断是否为root用户
                if hasattr(os, 'geteuid') and os.geteuid() == 0:
                    # root用户需要以原始用户身份运行
                    username = os.environ.get('SUDO_USER')
                    if username:
                        cmd = f"DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u {username})/bus notify-send -i {icon} \"{title}\" \"{message}\""
                        subprocess.run(['su', username, '-c', cmd], check=False)
                    else:
                        print("无法确定原始用户，不发送通知")
                else:
                    # 非root用户直接运行
                    subprocess.run(['notify-send', '-i', icon, title, message], check=False)
                    
            elif system == 'Windows':
                # Windows使用win10toast
                try:
                    from win10toast import ToastNotifier
                    toaster = ToastNotifier()
                    toaster.show_toast(title, message, duration=3, threaded=True)
                except ImportError:
                    print("警告：未安装win10toast，无法发送通知")
                    print("安装方法：pip install win10toast")
                    
            elif system == 'Darwin':
                # macOS使用osascript
                apple_script = f'display notification "{message}" with title "{title}"'
                subprocess.run(['osascript', '-e', apple_script], check=False)
                
        except Exception as e:
            print(f"发送通知失败: {str(e)}")


def register_hotkey(hotkey, callback):
    """注册快捷键
    
    Args:
        hotkey (str): 快捷键组合，如'f8+8'
        callback (callable): 回调函数
        
    Returns:
        bool: 注册成功返回True，失败返回False
    """
    if not keyboard:
        print("错误：未安装keyboard模块，无法注册快捷键")
        print("安装方法：pip install keyboard")
        return False
        
    try:
        keyboard.add_hotkey(hotkey, callback)
        print(f"已成功注册快捷键: {hotkey}")
        return True
    except Exception as e:
        print(f"注册快捷键失败: {str(e)}")
        return False


def main():
    """主函数"""
    try:
        # 初始化OCR工具
        ocr_tool = ScreenshotOCR()
        
        # 尝试登录
        try:
            ocr_tool.ocr.login()
        except Exception as e:
            print(f"登录失败: {str(e)}")
            print("将使用匿名登录")
            ocr_tool.ocr._anonymous_login()
        
        # 注册快捷键
        if keyboard:
            # 截图 OCR 快捷键
            register_hotkey('f8+8', ocr_tool.capture_and_recognize)
            
            print("白描OCR已启动！")
            print("使用 f8+8 进行截图 OCR")
            print("按 Ctrl+C 退出程序")
            
            # 阻塞主线程，等待快捷键触发
            keyboard.wait('ctrl+c')
        else:
            # 如果没有keyboard模块，直接执行一次OCR
            print("没有安装keyboard模块，将直接执行一次OCR")
            ocr_tool.capture_and_recognize()
    except KeyboardInterrupt:
        print("程序已被用户中断")
    except Exception as e:
        print(f"发生错误: {str(e)}")
    finally:
        print("程序已退出")


if __name__ == '__main__':
    main()
