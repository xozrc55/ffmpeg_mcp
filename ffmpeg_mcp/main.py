#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FFmpeg MCP 服务 - 主入口文件

这个文件是FFmpeg MCP服务的主入口点，负责启动MCP服务器并提供FFmpeg相关工具函数。
"""

from fastmcp import FastMCP
import subprocess
import os
import json
import uuid
import functools
import base64
from typing import Dict, Any, List, Optional, Annotated, Tuple, Callable
import typer
from starlette.requests import Request
from starlette.responses import JSONResponse

from ffmpeg_mcp.utils.utils import (
    get_temp_directory,
    get_resources_directory,
    copy_to_resources,
    ensure_directory_exists,
    is_url,
    download_video,
    check_file_exists,
    run_ffmpeg_command,
    get_video_duration,
    format_time,
)



# 创建MCP服务器实例
mcp = FastMCP("ffmpeg_mcp")

# API Key 中间件 - 用于 SSE 传输模式
from starlette.middleware.base import BaseHTTPMiddleware

# 使用 BaseHTTPMiddleware 类实现 API Key 验证
class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key=None):
        super().__init__(app)
        # 如果提供了 API Key，则使用提供的，否则使用默认的
        self.api_key = api_key
    
    async def dispatch(self, request: Request, call_next):
        # 从请求头中获取 API Key
        request_api_key = request.headers.get("X-API-Key")
        
        # 使用实例变量中的 API Key
        valid_key = self.api_key
        
        
        # 验证 API Key
        if not request_api_key or request_api_key != valid_key:
            return JSONResponse(
                status_code=401,
                content={"error": "无效的 API Key", "status": "unauthorized"}
            )
            
        # API Key 有效，继续处理请求
        return await call_next(request)

def require_api_key(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        api_key = kwargs.pop("api_key", None)
        # 如果没有提供 API Key，则假设中间件已经验证过了
        if api_key is None:
            return func(*args, **kwargs)
        # 如果提供了 API Key，则验证是否与全局 API_KEY 相等
        if api_key != API_KEY:
            return {"error": "无效的 API Key", "status": "unauthorized"}
        return func(*args, **kwargs)
    return wrapper

# FFmpeg 相关工具
@mcp.tool
def ffmpeg_version() -> dict:
    """获取 FFmpeg 的版本信息
    
    Returns:
        包含 FFmpeg 版本信息的字典
    """
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True)
        return {"version": result.stdout.split('\n')[0]}
    except subprocess.CalledProcessError as e:
        return {"error": f"FFmpeg 调用错误: {str(e)}"}
    except FileNotFoundError:
        return {"error": "FFmpeg 未安装或未在 PATH 中"}

@mcp.tool
def ffmpeg_get_video_info(video_path: str) -> dict:
    """获取视频文件的详细信息
    
    Args:
        video_path: 视频文件路径
    
    Returns:
        包含视频信息的字典，包括时长、分辨率、编码格式等
    """
    try:
        if not check_file_exists(video_path):
            return {"error": f"视频文件不存在: {video_path}"}
        
        # 构建 FFmpeg 命令获取视频信息
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path]
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            info = json.loads(result.stdout)
            
            # 提取关键信息
            video_info = {
                "filename": os.path.basename(video_path),
                "format": info.get("format", {}).get("format_name", "未知"),
                "duration": float(info.get("format", {}).get("duration", 0)),
                "size": int(info.get("format", {}).get("size", 0)),
                "bit_rate": int(info.get("format", {}).get("bit_rate", 0)),
                "streams": []
            }
            
            # 提取流信息
            for stream in info.get("streams", []):
                stream_type = stream.get("codec_type", "未知")
                stream_info = {
                    "type": stream_type,
                    "codec": stream.get("codec_name", "未知"),
                    "codec_long_name": stream.get("codec_long_name", "未知")
                }
                
                # 视频流特有信息
                if stream_type == "video":
                    stream_info.update({
                        "width": stream.get("width", 0),
                        "height": stream.get("height", 0),
                        "fps": eval(stream.get("r_frame_rate", "0/1")) if "/" in stream.get("r_frame_rate", "0/1") else 0,
                        "bit_depth": stream.get("bits_per_raw_sample", "未知"),
                        "pix_fmt": stream.get("pix_fmt", "未知")
                    })
                
                # 音频流特有信息
                elif stream_type == "audio":
                    stream_info.update({
                        "sample_rate": stream.get("sample_rate", "未知"),
                        "channels": stream.get("channels", 0),
                        "channel_layout": stream.get("channel_layout", "未知")
                    })
                
                video_info["streams"].append(stream_info)
            
            return {
                "success": True,
                "info": video_info
            }
        else:
            return {
                "success": False,
                "error": f"获取视频信息失败: {result.stderr}"
            }
    except Exception as e:
        return {"error": f"处理过程中出现异常: {str(e)}"}

@mcp.tool
def ffmpeg_extract_audio(video_path: str, audio_format: str = "mp3") -> dict:
    """从视频中提取音频并保存到默认资源目录
    
    Args:
        video_path: 视频文件路径或 URL
        audio_format: 音频格式，默认为 mp3
    
    Returns:
        包含提取结果的字典
    """
    try:
        local_video_path = video_path

        # 若为网络地址则先下载到本地
        if is_url(video_path):
            try:
                local_video_path = download_video(video_path)
                print(f"已下载网络视频到临时文件: {local_video_path}")
            except Exception as e:
                return {"error": f"下载视频失败: {str(e)}"}
        elif not check_file_exists(video_path):
            return {"error": f"视频文件不存在: {video_path}"}

        # 生成输出路径：资源目录 + 唯一文件名
        resources_dir = get_resources_directory()
        original_name = os.path.basename(local_video_path)
        name_root, _ = os.path.splitext(original_name)
        output_filename = f"{name_root}_audio_{uuid.uuid4().hex[:8]}.{audio_format}"
        output_path = os.path.join(resources_dir, output_filename)

        # 确保输出目录存在
        ensure_directory_exists(output_path)

        # 选择编码器
        acodec = "copy" if audio_format == "aac" else "libmp3lame"

        # 构建 FFmpeg 命令
        cmd = [
            "ffmpeg", "-i", local_video_path, "-vn", "-acodec", acodec,
            "-y", output_path
        ]

        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            return {
                "success": True,
                "message": f"音频提取成功: {output_path}",
                "output_path": output_path,
                "source": "网络视频" if is_url(video_path) else "本地视频"
            }
        else:
            return {
                "success": False,
                "error": f"FFmpeg 提取音频错误: {result.stderr}"
            }
    except Exception as e:
        return {"error": f"提取过程中出现异常: {str(e)}"}

@mcp.tool
def ffmpeg_create_thumbnail(video_path: str, time_position: str = "00:00:05") -> dict:
    """从视频中提取特定时间点的缩略图并保存到默认资源目录
    
    Args:
        video_path: 视频文件路径或 URL
        time_position: 时间点，格式为 HH:MM:SS，默认为 5 秒
    
    Returns:
        包含提取结果的字典
    """
    try:
        if not check_file_exists(video_path):
            return {"error": f"视频文件不存在: {video_path}"}

        # 生成输出路径：资源目录 + 唯一文件名
        resources_dir = get_resources_directory()
        original_name = os.path.basename(video_path)
        name_root, ext = os.path.splitext(original_name)
        output_filename = f"{name_root}_thumbnail_{uuid.uuid4().hex[:8]}.jpg"
        thumbnail_path = os.path.join(resources_dir, output_filename)

        # 确保输出目录存在
        ensure_directory_exists(thumbnail_path)
        
        # 构建 FFmpeg 命令
        cmd = [
            "ffmpeg", "-i", video_path, "-ss", time_position, "-vframes", "1",
            "-y", thumbnail_path
        ]
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"缩略图提取成功: {thumbnail_path}",
                "output_path": thumbnail_path
            }
        else:
            return {
                "success": False,
                "error": f"FFmpeg 提取缩略图错误: {result.stderr}"
            }
    except Exception as e:
        return {"error": f"提取过程中出现异常: {str(e)}"}

# 去水印工具：始终将结果保存到资源目录，不再暴露 output_path 参数
@mcp.tool
def ffmpeg_remove_watermark(video_path: str, x: int = 590, y: int = 1200, width: int = 100, height: int = 40, output_dir: Optional[str] = None) -> dict:
    """去除视频中的水印
    
    Args:
        video_path: 输入视频文件路径
        x: 水印左上角的x坐标
        y: 水印左上角的y坐标
        width: 水印宽度
        height: 水印高度
        output_dir: 输出目录路径，如果不指定则使用资源目录
    
    Returns:
        包含处理结果的字典
    """
    try:
        # 处理网络视频
        local_video_path = video_path
        # 若为网络地址则先下载
        if is_url(video_path):
            try:
                local_video_path = download_video(video_path)
            except Exception as e:
                return {"error": f"下载视频失败: {str(e)}"}
        elif not check_file_exists(video_path):
            return {"error": f"视频文件不存在: {video_path}"}
        
        # 准备输出文件名
        original_name = os.path.basename(local_video_path)
        name_root, ext = os.path.splitext(original_name)
        output_filename = f"nowatermark_{name_root}_{uuid.uuid4().hex[:8]}{ext}"
        
        # 决定输出目录
        if output_dir is None:
            # 如果未指定输出目录，使用默认的资源目录
            output_dir = get_resources_directory()
        else:
            # 如果路径不是绝对路径，则转换为绝对路径
            if not os.path.isabs(output_dir):
                output_dir = os.path.abspath(output_dir)
        
        # 生成完整输出路径
        output_path = os.path.join(output_dir, output_filename)
        
        # 确保输出目录存在
        ensure_directory_exists(output_dir)
        
        # 构建 FFmpeg 命令，使用 delogo 滤镜去除水印
        cmd = [
            "ffmpeg", "-i", local_video_path,
            "-vf", f"delogo=x={x}:y={y}:w={width}:h={height}:show=0",
            "-c:a", "copy", "-y", output_path
        ]
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"水印去除成功: {output_path}",
                "output_path": output_path,
            }
        else:
            return {
                "success": False,
                "error": f"FFmpeg 去除水印错误: {result.stderr}"
            }
    except Exception as e:
        return {"error": f"处理过程中出现异常: {str(e)}"}



# 资源目录映射：使用 FastMCP 的资源机制自动处理文件列举与下载
@mcp.resource('resource://{param}')
def resources_dir(param: str) -> dict:
    """根据参数路径读取视频并返回Base64编码的blob数据及其MIME类型
    
    Args:
        param: 指定要获取的视频文件名，如果为空则返回目录路径
        
    Returns:
        如果指定了有效的视频文件名，返回包含视频的Base64编码数据和MIME类型的字典；
        否则返回目录路径或错误信息
    """
    # 获取资源目录路径
    resources_path = get_resources_directory()
    
    # 如果param为空，返回目录路径
    if not param:
        return {
            "type": "directory",
            "path": resources_path
        }
    
    # 构造完整的文件路径
    file_path = os.path.join(resources_path, param)
    
    # 检查文件是否存在
    if not os.path.isfile(file_path):
        # 如果文件不存在，返回错误信息
        return {
            "type": "error",
            "message": f"文件不存在: {param}"
        }
    
    # 检查是否为视频文件并确定MIME类型
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    # 根据文件扩展名确定MIME类型
    mime_types = {
        '.mp4': "video/mp4",
        '.avi': "video/x-msvideo",
        '.mov': "video/quicktime",
        '.mkv': "video/x-matroska",
        '.webm': "video/webm",
        '.flv': "video/x-flv"
    }
    
    # 如果不是支持的视频格式，返回错误
    if ext not in mime_types:
        return {
            "type": "error",
            "message": f"不支持的文件类型: {ext}"
        }
    
    # 获取对应的MIME类型
    mime_type = mime_types[ext]
    
    # 读取文件内容并进行Base64编码
    try:
        with open(file_path, 'rb') as f:
            # 读取文件内容
            file_content = f.read()
            # Base64编码
            encoded_content = base64.b64encode(file_content).decode('utf-8')
            
            # 返回包含Base64编码数据和MIME类型的字典
            return {
                "type": "blob",
                "mime_type": mime_type,
                "content": encoded_content,
                "filename": param
            }
    except Exception as e:
        return {
            "type": "error",
            "message": f"读取文件失败: {str(e)}"
        }

app = typer.Typer(help="FFmpeg MCP 服务命令行接口. 通过 MCP 服务器提供 FFmpeg 工具.")

@app.command(name="local", help="以本地 stdio 模式启动 FFmpeg MCP 服务.")
def serve_local():
    """
    启动 FFmpeg MCP 服务器，通过 stdio 进行通信。
    """
    typer.echo(f"启动FFmpeg MCP服务 (模式: local, 传输: stdio)...")
    mcp.run(transport="stdio")

@app.command(name="host", help="以网络主机模式启动 FFmpeg MCP 服务.")
def serve_host(
    host_address: Annotated[str, typer.Option(help="服务器监听的主机地址.")] = "0.0.0.0",
    port: Annotated[int, typer.Option(help="服务器运行的端口号.")] = 9000,
    api_key: Annotated[str, typer.Option(help="设置自定义API Key")] = ""
):
    """
    启动 FFmpeg MCP 服务器，监听网络接口。
    """
    transport = "sse"

    # 如果提供了自定义API密钥，则设置全局API密钥
    if api_key :
        # 设置全局API密钥
        api_key.strip()

    typer.echo(f"启动FFmpeg MCP服务 (模式: host, 地址: {host_address}, 端口: {port}, 传输: {transport})...")
    typer.echo(f"服务将在 http://{host_address}:{port}/{transport} 上运行")
    
    
    # 添加 API Key 中间件，使用 Starlette 的 Middleware 类正确包装 APIKeyMiddleware
    from starlette.middleware import Middleware
    if api_key is None or api_key == "":
        mcp.run(transport=transport, host=host_address, port=port)
    else:
        typer.echo("API Key 认证已启用，请在请求头中添加 X-API-Key")
        mcp.run(transport=transport, host=host_address, port=port, middleware=[Middleware(APIKeyMiddleware, api_key=api_key)])

  

if __name__ == "__main__":
    app()
