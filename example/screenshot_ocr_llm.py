#!/usr/bin/env python

"""
多平台截图OCR工具 - 使用大语言模型进行OCR识别
支持Linux、Windows和macOS系统
模块化设计，方便其他脚本调用
"""

import os
import sys
import time
import base64
import platform
import tempfile
import shutil
import subprocess
from pathlib import Path

# 可选依赖，根据平台动态导入
try:
    import keyboard
except ImportError:
    keyboard = None

try:
    import pyclip
except ImportError:
    pyclip = None


class ScreenshotTool:
    """多平台截图工具类"""
    
    def __init__(self, cache_dir_name='llm_ocr'):
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
        """根据不同操作系统获取缓存目录
        
        Args:
            cache_dir_name (str): 缓存目录名称
            
        Returns:
            str: 缓存目录路径，如果创建失败则返回None
        """
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
        """使用系统工具进行截图
        
        Returns:
            bool: 截图是否成功
        """
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
        """Linux系统下的截图方法
        
        Returns:
            bool: 截图是否成功
        """
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
        """Windows系统下的截图方法
        
        Returns:
            bool: 截图是否成功
        """
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
        """macOS系统下的截图方法
        
        Returns:
            bool: 截图是否成功
        """
        try:
            # 使用macOS自带的screencapture工具
            subprocess.run(['screencapture', '-i', self.screenshot_path], check=True)
            return self._wait_for_screenshot()
        except subprocess.CalledProcessError as e:
            print(f"macOS截图失败: {e}")
            return False
        except Exception as e:
            print(f"macOS截图失败: {str(e)}")
            return False
            
    def _wait_for_screenshot(self):
        """等待截图文件生成
        
        Returns:
            bool: 截图文件是否生成成功
        """
        timeout = 10  # 设置超时时间（秒）
        start_time = time.time()
        while not os.path.exists(self.screenshot_path) or os.path.getsize(self.screenshot_path) == 0:
            if time.time() - start_time > timeout:
                print("截图超时")
                return False
            time.sleep(0.5)
            
        print(f"截图文件已生成: {self.screenshot_path}")
        return True


class LLMOCR:
    """使用大语言模型进行OCR识别的类"""
    
    def __init__(self, api_key=None, api_base=None, model=None):
        """初始化LLM OCR工具
        
        Args:
            api_key (str, optional): API密钥，如果为None则使用环境变量中的密钥
            api_base (str, optional): API基础URL，如果为None则使用环境变量中的URL
            model (str, optional): 使用的模型名称，默认为"grok-2-vision"
        """
        # 优先使用传入的参数，然后是环境变量
        self.api_key = api_key or os.environ.get('GROK_API_KEY') or os.environ.get('NEW_API_KEY')
        self.api_base = api_base or os.environ.get('GROK_API_BASE') or os.environ.get('NEW_API_URL')
        self.model = model or "grok-2-vision"
        
        if not self.api_key or not self.api_base:
            print("警告: 未设置API密钥或API URL，请设置环境变量或传入参数")
    
    def recognize(self, image_path):
        """使用大语言模型识别图片中的文本
        
        Args:
            image_path (str): 图片路径
            
        Returns:
            str: 识别出的文本，如果识别失败则返回空字符串
        """
        try:
            if not self.api_key or not self.api_base:
                raise ValueError("未设置API密钥或API URL")
                
            # 动态导入OpenAI库
            try:
                import openai
            except ImportError:
                print("错误：未安装openai库，请运行以下命令安装：")
                print("pip install openai")
                return ""
            
            # 读取图片并转换为base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 初始化OpenAI客户端
            client = openai.OpenAI(api_key=self.api_key, base_url=self.api_base)
            
            # 发送请求
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请识别图片中的所有文本，并保持原始格式输出。仅输出文本内容，不要添加任何解释或其他内容。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )
            
            # 提取文本
            text = response.choices[0].message.content.strip()
            return text
            
        except Exception as e:
            print(f"OCR识别失败: {str(e)}")
            return ""


class ScreenshotOCRLLM:
    """结合截图和大语言模型OCR的工具类"""
    
    def __init__(self, api_key=None, api_base=None, model=None, cache_dir_name='llm_ocr'):
        """初始化截图OCR工具
        
        Args:
            api_key (str, optional): API密钥
            api_base (str, optional): API基础URL
            model (str, optional): 模型名称
            cache_dir_name (str, optional): 缓存目录名称
        """
        self.screenshot_tool = ScreenshotTool(cache_dir_name)
        self.ocr = LLMOCR(api_key, api_base, model)
        
    # 定义通知函数
    def send_system_notification_linux(self, title="LLM", message="OCR识别完成"):
        """
        发送系统通知，自动处理root和非root用户的情况
        
        参数:
            title (str): 通知标题
            message (str): 通知内容
        """
        
        # 检查是否是root用户运行
        if os.geteuid() == 0:  # 如果是root用户(sudo)运行LLM
            # 获取实际用户信息
            current_user = os.environ.get('SUDO_USER')
            if current_user:
                # 设置显示相关环境变量
                user_home = f"/home/{current_user}"
                display = os.environ.get('DISPLAY', ':0')
                xauthority = os.environ.get('XAUTHORITY', f"{user_home}/.Xauthority")
                
                # 构建命令
                cmd = f"DISPLAY={display} XAUTHORITY={xauthority} notify-send '{title}' '{message}'"
                print(f"以用户 {current_user} 身份运行通知命令: {cmd}")
                
                # 使用su命令以原用户身份运行notify-send
                subprocess.run(['su', current_user, '-c', cmd], check=True)
            else:
                print("无法确定实际用户，通知可能无法显示")
        else:
            # 非root用户直接运行
            print("以普通用户身份运行通知命令")
            subprocess.run(['notify-send', title, message], check=True)
    
    def capture_and_recognize(self):
        """截取屏幕并识别文本
        
        Returns:
            str: 识别出的文本，如果失败则返回None
        """
        try:
            # 截图
            screenshot_path = self.screenshot_tool.capture_screenshot()
            if not screenshot_path or not os.path.exists(screenshot_path):
                print("截图失败")
                return None
                
            # OCR识别
            print("正在进行OCR识别...")
            text = self.ocr.recognize(screenshot_path)
            
            # 复制到剪贴板
            if text:
                self._copy_to_clipboard(text)
                print("识别成功！文本已复制到剪贴板")

            else:
                print("OCR识别失败或未识别出文本")
                
            return text
        except Exception as e:
            print(f"截图识别失败: {str(e)}")
            return None

    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板
        
        Args:
            text (str): 要复制的文本
        """
        try:
            # 尝试使用pyclip
            if pyclip:
                pyclip.copy(text)

                self.send_system_notification_linux(title=self.ocr.model, message="OCR识别完成")

                return
                
            # 如果没有pyclip，根据系统使用不同的方法
            if self.screenshot_tool.system == 'Linux':
                # Linux使用xclip或xsel
                if shutil.which('xclip'):
                    p = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
                    p.communicate(input=text.encode('utf-8'))
                elif shutil.which('xsel'):
                    p = subprocess.Popen(['xsel', '-ib'], stdin=subprocess.PIPE)
                    p.communicate(input=text.encode('utf-8'))
                else:
                    print("警告: 无法复制到剪贴板，请安装xclip或xsel")
                    
            elif self.screenshot_tool.system == 'Darwin':
                # macOS使用pbcopy
                p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                p.communicate(input=text.encode('utf-8'))
                
            elif self.screenshot_tool.system == 'Windows':
                # Windows使用clip
                p = subprocess.Popen(['clip'], stdin=subprocess.PIPE)
                p.communicate(input=text.encode('utf-8'))
                
        except Exception as e:
            print(f"复制到剪贴板失败: {str(e)}")
            
    def start_listening(self):
        """开始监听快捷键"""
        print(f"当前操作系统: {self.screenshot_tool.system}")
        
        if not keyboard:
            print("错误：未安装keyboard库，无法使用快捷键")
            print("请运行以下命令安装: pip install keyboard")
            print("将使用手动模式...")
            self._manual_mode()
            return
            
        print("按下 F8+9 快捷键开始截图OCR，按ESC键退出")
        try:
            keyboard.add_hotkey('f8+9', self.capture_and_recognize)
            keyboard.wait('esc')
        except Exception as e:
            print(f"设置快捷键失败: {e}")
            print("将使用手动模式...")
            self._manual_mode()
            
    def _manual_mode(self):
        """手动模式，通过回车键触发截图"""
        print("手动模式: 按回车键开始截图OCR，按Ctrl+C退出")
        while True:
            try:
                input("按回车键开始截图OCR，按Ctrl+C退出: ")
                self.capture_and_recognize()
            except KeyboardInterrupt:
                print("\n程序已退出")
                break


def main():
    """主函数"""
    # 检查系统依赖
    system = platform.system()
    if system == 'Linux' and not shutil.which('gnome-screenshot'):
        print("错误：未找到gnome-screenshot截图工具")
        print("请安装gnome-screenshot: sudo apt-get install gnome-screenshot")
        return
    elif system == 'Windows':
        try:
            import PIL
            import pyautogui
        except ImportError:
            print("错误：未安装必要的库")
            print("请运行以下命令安装：pip install pillow pyautogui")
            return
    
    # 创建并启动截图OCR工具
    screenshot_ocr = ScreenshotOCRLLM()
    screenshot_ocr.start_listening()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"\n程序发生错误: {e}")