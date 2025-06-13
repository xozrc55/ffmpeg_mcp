
"""ffmpeg_mcp 工具函数模块

此模块包含所有与文件系统、URL 处理、FFmpeg 命令执行等相关的通用辅助函数，
以便在 `main.py` 及其他子模块中复用，保持 `main.py` 的简洁。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from typing import Any, Dict, List, Optional

import requests

__all__ = [
    "get_temp_directory",
    "get_resources_directory",
    "copy_to_resources",
    "ensure_directory_exists",
    "is_url",
    "download_video",
    "check_file_exists",
    "run_ffmpeg_command",
    "get_video_duration",
    "format_time",
]


# --------------------------- 基础目录相关 ---------------------------

def get_temp_directory() -> str:
    """返回临时下载目录路径。

    统一使用 *当前工作目录* 下的 ``temp`` 文件夹，若不存在则自动创建。"""
    temp_dir = os.path.join(os.getcwd(), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def get_resources_directory() -> str:
    """返回资源目录路径。

    所有处理后可供用户下载的文件都会保存到 *当前工作目录* 下的 ``public`` 目录。
    若目录不存在则自动创建。"""
    resources_dir = os.path.join(os.getcwd(), "public")
    os.makedirs(resources_dir, exist_ok=True)
    return resources_dir


def copy_to_resources(file_path: str) -> str:
    """复制 ``file_path`` 到资源目录并生成唯一文件名，返回复制后的路径。"""
    resources_dir = get_resources_directory()
    original_name = os.path.basename(file_path)
    name_root, ext = os.path.splitext(original_name)
    new_filename = f"{name_root}_{uuid.uuid4().hex[:8]}{ext}"
    new_path = os.path.join(resources_dir, new_filename)
    shutil.copy2(file_path, new_path)
    return new_path


def ensure_directory_exists(path: str) -> None:
    """确保 ``path`` 所在目录存在（针对文件路径）或目录本身存在。"""
    directory = os.path.dirname(path) if os.path.splitext(path)[1] else path
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


# --------------------------- URL 与文件检查 ---------------------------

def is_url(path: str) -> bool:
    """判断 ``path`` 是否为 HTTP/HTTPS URL。"""
    return bool(re.match(r"^https?://", path))


def download_video(url: str) -> str:
    """下载网络视频到临时目录，返回本地文件路径。"""
    temp_dir = get_temp_directory()
    temp_filename = f"video_{uuid.uuid4().hex}.mp4"
    temp_filepath = os.path.join(temp_dir, temp_filename)

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(temp_filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return temp_filepath
    except Exception as e:
        # 若下载失败则删除空文件（如有）
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except OSError:
                pass
        raise RuntimeError(f"下载视频失败: {e}") from e


def check_file_exists(file_path: str) -> bool:
    """简单检查本地文件是否存在（URL 返回 False）。"""
    if is_url(file_path):
        return False
    return os.path.isfile(file_path)


# --------------------------- FFmpeg 相关 ---------------------------

def run_ffmpeg_command(cmd: List[str]) -> Dict[str, Any]:
    """执行 FFmpeg 命令并返回执行结果信息字典。"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "stdout": result.stdout, "stderr": result.stderr}
        return {
            "success": False,
            "error": f"FFmpeg 命令执行错误: {result.stderr}",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as exc:
        return {"success": False, "error": f"执行 FFmpeg 命令时出现异常: {exc}"}


def get_video_duration(video_path: str) -> Optional[float]:
    """通过 ``ffprobe`` 获取视频时长（秒）。失败时返回 ``None``。"""
    if not check_file_exists(video_path):
        return None

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            info = json.loads(result.stdout)
            return float(info.get("format", {}).get("duration", 0))
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def format_time(seconds: float) -> str:
    """将秒数转换为 ``HH:MM:SS.mmm`` 字符串。"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds_val = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds_val:06.3f}"
