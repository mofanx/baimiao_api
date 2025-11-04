# -*- coding: utf-8 -*-
import base64
import binascii
import json
import os
import secrets
from typing import Optional, Tuple

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from starlette.datastructures import UploadFile

from main import BaimiaoOCR, config

API_KEY_ENV_VAR = "BAIMIAO_API_KEY"

app = FastAPI(title="Baimiao OCR Service", version="1.0.0")


def get_api_key() -> Optional[str]:
    env_value = os.getenv(API_KEY_ENV_VAR)
    if env_value:
        return env_value.strip()
    if config.has_option('defaults', 'api_key'):
        return config.get('defaults', 'api_key').strip()
    return None


def init_ocr_client() -> BaimiaoOCR:
    defaults = dict(config.items('defaults'))
    return BaimiaoOCR(defaults)


ocr_client = init_ocr_client()


async def ensure_authorized(authorization: Optional[str] = Header(None)) -> None:
    expected_key = get_api_key()
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务未配置 API Key，请设置环境变量 {API_KEY_ENV_VAR} 或在 config.ini 的 defaults.api_key 中配置。"
        )
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization 头"
        )
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not secrets.compare_digest(token, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Authorization"
        )


def normalize_base64(data: str) -> str:
    if not isinstance(data, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_base64 必须是字符串")
    stripped = data.strip()
    marker = "base64,"
    if marker in stripped:
        stripped = stripped.split(marker, 1)[1]
    if not stripped:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_base64 不能为空")
    try:
        base64.b64decode(stripped, validate=True)
    except binascii.Error as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_base64 非有效的 Base64 编码") from exc
    return stripped


async def fetch_url_as_base64(image_url: str) -> str:
    if not isinstance(image_url, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_url 必须是字符串")
    url = image_url.strip()
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_url 不能为空")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"下载图片失败: {exc}") from exc
    if not response.content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="下载到的图片内容为空")
    return base64.b64encode(response.content).decode("utf-8")


async def extract_image_payload(request: Request) -> Tuple[str, str]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type.lower():
        form = await request.form()
        upload = form.get("file")
        if isinstance(upload, UploadFile):
            data = await upload.read()
            if not data:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件内容为空")
            return base64.b64encode(data).decode("utf-8"), "upload"
        image_base64 = form.get("image_base64")
        if image_base64:
            return normalize_base64(image_base64), "form_base64"
        image_url = form.get("image_url")
        if image_url:
            return await fetch_url_as_base64(image_url), "form_url"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="multipart/form-data 请求需包含 file、image_base64 或 image_url 字段")

    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON 请求体格式错误") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON 请求体必须为对象")

    image_base64 = payload.get("image_base64")
    if image_base64:
        return normalize_base64(image_base64), "json_base64"
    image_url = payload.get("image_url")
    if image_url:
        return await fetch_url_as_base64(image_url), "json_url"

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供 image_base64 或 image_url")


@app.post("/ocr")
async def ocr_endpoint(request: Request, _: None = Depends(ensure_authorized)):
    base64_data, source = await extract_image_payload(request)
    try:
        text = await run_in_threadpool(ocr_client.recognize, base64_data)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OCR 识别失败: {exc}") from exc
    return PlainTextResponse(text)
