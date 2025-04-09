#!/usr/bin/env python

import os
import sys
import time
import keyboard
import pyclip
import base64
import subprocess
import tempfile
import shutil
import platform
from pathlib import Path

# 导入白描OCR模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import BaimiaoOCR, config


class ScreenshotOCR:
    def __init__(self):
        default_config = dict(config.items('defaults'))
        self.ocr = BaimiaoOCR(default_config)
        self.is_capturing = False
        self.system = platform.system()  # 获取操作系统类型
        
        # 获取用户缓存目录
        self.cache_dir = self._get_cache_dir()
        
        # 设置截图保存路径
        if self.cache_dir:
            self.temp_dir = self.cache_dir  # 不是临时创建的目录，所以不会在__del__中被删除
            self.screenshot_path = os.path.join(self.cache_dir, f'screenshot_{int(time.time())}.png')
        else:
            # 如果创建缓存目录失败，使用临时目录
            self.temp_dir = tempfile.mkdtemp()
            self.screenshot_path = os.path.join(self.temp_dir, 'screenshot.png')
            
    def _get_cache_dir(self):
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
                cache_dir = os.path.join(user_home, '.cache', 'baimiao_ocr')
                
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
                cache_dir = os.path.join(appdata, 'BaimiaoOCR')
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir, exist_ok=True)
                    
            elif self.system == 'Darwin':
                # macOS系统
                user_home = os.path.expanduser('~')
                cache_dir = os.path.join(user_home, 'Library', 'Caches', 'BaimiaoOCR')
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
        """截取屏幕区域并进行OCR识别"""
        print("正在启动截图工具...")
        try:
            if self._take_screenshot_with_system_tools():
                return self._process_screenshot_file()
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
        """等待截图文件生成"""
        timeout = 10  # 设置超时时间（秒）
        start_time = time.time()
        while not os.path.exists(self.screenshot_path) or os.path.getsize(self.screenshot_path) == 0:
            if time.time() - start_time > timeout:
                print("截图超时")
                return False
            time.sleep(0.5)
            
        print(f"截图文件已生成: {self.screenshot_path}")
        return True
    
    def _process_screenshot_file(self):
        """处理截图文件并进行OCR识别"""
        try:
            if not os.path.exists(self.screenshot_path) or os.path.getsize(self.screenshot_path) == 0:
                print("截图文件不存在或为空")
                return None
                
            with open(self.screenshot_path, 'rb') as f:
                img_base64 = base64.b64encode(f.read()).decode()
            
            try:
                text = self.ocr.recognize(img_base64)
                pyclip.copy(text)
                print("识别成功！文本已复制到剪贴板")
                return text
            except Exception as e:
                print(f"OCR识别失败: {str(e)}")
                return None
        except Exception as e:
            print(f"截图处理失败: {str(e)}")
            return None
        finally:
            if os.path.exists(self.screenshot_path):
                try:
                    os.remove(self.screenshot_path)
                except:
                    pass

    def start_listening(self):
        """开始监听快捷键"""
        print(f"当前操作系统: {self.system}")
        print("按下 F8+9 快捷键开始截图OCR，按ESC键退出")
        try:
            keyboard.add_hotkey('f8+9', self.capture_screenshot)
            keyboard.wait('esc')
        except Exception as e:
            print(f"设置快捷键失败: {e}")
            print("请手动按回车键进行截图OCR")
            while True:
                try:
                    input("按回车键开始截图OCR，按Ctrl+C退出: ")
                    self.capture_screenshot()
                except KeyboardInterrupt:
                    print("\n程序已退出")
                    break



def main():
    config_path = Path(__file__).parent / 'config.ini'
    if not config_path.exists():
        print("错误：找不到配置文件 config.ini")
        print("请根据 config.ini.example 创建配置文件")
        return
    
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
    
    screenshot_ocr = ScreenshotOCR()
    screenshot_ocr.start_listening()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"\n程序发生错误: {e}")
