# 白描OCR API 使用说明


## 安装依赖
```bash
pip install requests
```

## 配置说明
1. 复制 `config.ini.example` 为 `config.ini`
2. 编辑 `config.ini` 填写您的账号信息:
```ini
[default]
username = 您的账号
password = 您的密码
login_token = 
uuid = 
```



## 注意事项
1. 请勿频繁调用API，避免账号被封禁
2. 首次使用会自动生成uuid并保存到config.ini
3. 登录token有效期为7天，过期后需要重新登录


