# 白描OCR API 使用说明


## 环境依赖安装
推荐使用 Mamba 管理 Python 环境：
```bash
mamba activate base
mamba install fastapi uvicorn httpx requests
```

若 Mamba 中缺少某些包，可再使用 pip：
```bash
pip install fastapi uvicorn httpx requests
```

## 配置文件
1. 复制 `config.ini.example` 为 `config.ini`
2. 填写白描账号信息与可选的 API Key：
```ini
[defaults]
username = 您的账号
password = 您的密码
login_token = 
uuid = 
api_key = 可选：若不使用环境变量，则在此处设置调用鉴权密钥
```

> `login_token`、`uuid` 会在首次成功登录后自动写回，可留空。

## 启动 API 服务
本项目提供 `api_server.py` 作为 FastAPI 接口层：

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

服务启动前需设置鉴权密钥（两种方式二选一）：

1. 环境变量：`export BAIMIAO_API_KEY=你的密钥`
2. 在 `config.ini` 的 `defaults.api_key` 中填写密钥

## API 使用示例

### 1. 通过图片 URL 识别
```bash
curl -X POST "http://localhost:8000/ocr" \
     -H "Authorization: Bearer ${BAIMIAO_API_KEY}" \
     -H "Content-Type: application/json" \
     -d '{"image_url": "https://example.com/sample.png"}'
```

### 2. 上传本地文件
```bash
curl -X POST "http://localhost:8000/ocr" \
     -H "Authorization: Bearer ${BAIMIAO_API_KEY}" \
     -F "file=@/path/to/image.png"
```

响应默认为纯文本，换行会原样保留。

## 使用 PM2 守护运行

项目提供 `ecosystem.config.js` 方便借助 PM2 进行守护与日志管理：

```bash
pm2 start ecosystem.config.js
pm2 status
pm2 logs baimiao-ocr-api
```

> 日志默认写入 `logs/baimiao-out.log` 与 `logs/baimiao-error.log`，启动前请确保目录存在：`mkdir -p logs`

若需开机自启，可执行：
```bash
pm2 startup
pm2 save
```

## 注意事项
1. 白描官方服务有调用频率限制，请合理使用，避免账号被封禁。
2. 若识别失败，请查看服务日志（FastAPI 控制台或 PM2 日志）排查。
3. `login_token` 有效期有限，过期后程序会自动重新登录并更新配置。
