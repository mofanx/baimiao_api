import os
import base64
from openai import OpenAI

def llm_ocr(image_path="image.png", api_key=None, base_url=None, model="grok-2-vision"):
    # 读取图片并转为base64
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    
    # 使用OpenAI客户端调用Grok API
    client = OpenAI(api_key=api_key or os.environ.get("NEW_API_KEY"), 
                   base_url=base_url or os.environ.get("NEW_API_URL"))
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "请识别图片中的文字，只返回文字内容，不要其他解释。"},
            {"role": "user", "content": [
                {"type": "text", "text": "这张图片中有什么文字？请直接提取出来。"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
            ]}
        ],
        max_tokens=1024
    )
    
    return response.choices[0].message.content

if __name__ == '__main__':
    print(llm_ocr('image.png', model="grok-2-vision"))