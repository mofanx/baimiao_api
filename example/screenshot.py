import os
import time
import shutil
import subprocess

def process_event():
    try:
        # 检查是否安装了gnome-screenshot
        if not shutil.which('gnome-screenshot'):
            print("错误：未安装gnome-screenshot工具")
            print("请使用 'sudo apt-get install gnome-screenshot' 安装")
            return
            
        # 使用gnome-screenshot进行区域截图
        screenshot_path = 'image2.png'
        print("使用gnome-screenshot进行区域截图...")
        
        # 检查是否是root用户运行
        if os.geteuid() == 0:
            # 获取当前用户的DISPLAY和XAUTHORITY环境变量
            current_user = os.environ.get('SUDO_USER')
            user_home = f"/home/{current_user}" if current_user else os.path.expanduser('~')
            display = os.environ.get('DISPLAY', ':0')
            xauthority = os.environ.get('XAUTHORITY', f"{user_home}/.Xauthority")
            
            # 使用su命令以原用户身份运行gnome-screenshot
            cmd = f"DISPLAY={display} XAUTHORITY={xauthority} gnome-screenshot -a -f {screenshot_path}"
            
            print(f"使用su命令以原用户身份运行gnome-screenshot: {cmd}")
            subprocess.run(['su', current_user, '-c', cmd], check=True)
        else:
            # 非root用户直接运行
            subprocess.run(['gnome-screenshot', '-a', '-f', screenshot_path], check=True)

        print(f"截图中...")
        
        # 等待截图完成
        timeout = 10  # 设置超时时间（秒）
        start_time = time.time()
        while not os.path.exists(screenshot_path) or os.path.getsize(screenshot_path) == 0:
            if time.time() - start_time > timeout:
                print("截图超时")
                return False
            time.sleep(0.5)
            
        print(f"截图已保存到: {screenshot_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"gnome-screenshot截图失败: {e}")
        return False
    except Exception as e:
        print(f"截图过程发生错误: {e}")
        return False

if __name__ == '__main__':

    process_event()