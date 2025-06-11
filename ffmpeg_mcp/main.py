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
import tempfile
import re
import uuid
import requests
from typing import Dict, Any, List, Optional, Annotated, Tuple
import typer


# FFmpeg 辅助函数和网络处理函数
# 获取程序指定的临时文件目录
# 这个目录将用于存放所有下载的视频和其他临时文件
def get_temp_directory() -> str:
    """获取程序指定的临时文件目录
    
    Returns:
        临时文件目录路径
    """
    temp_dir = os.path.join(tempfile.gettempdir(), "ffmpeg_mcp_temp")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def ensure_directory_exists(path: str) -> None:
    """确保目录存在，如果不存在则创建
    
    Args:
        path: 文件路径或目录路径
    """
    directory = os.path.dirname(path) if os.path.isfile(path) else path
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def is_url(path: str) -> bool:
    """判断路径是否为URL
    
    Args:
        path: 路径字符串
        
    Returns:
        是否为URL
    """
    # 简单的URL判断，检查是否以http://或https://开头
    return bool(re.match(r'^https?://', path))

def download_video(url: str) -> str:
    """下载网络视频到程序指定的临时目录
    
    Args:
        url: 视频URL
        
    Returns:
        本地文件路径
    """
    try:
        # 获取程序指定的临时目录
        temp_dir = get_temp_directory()
        
        # 生成唯一的临时文件名
        temp_filename = f"video_{uuid.uuid4().hex}.mp4"
        temp_filepath = os.path.join(temp_dir, temp_filename)
        
        # 下载视频文件
        response = requests.get(url, stream=True)
        response.raise_for_status()  # 如果请求失败则抛出异常
        
        # 写入临时文件
        with open(temp_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return temp_filepath
    except Exception as e:
        raise Exception(f"下载视频失败: {str(e)}")

def check_file_exists(file_path: str) -> bool:
    """检查文件是否存在
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件是否存在
    """
    # 如果是URL，返回假
    if is_url(file_path):
        return False
    return os.path.isfile(file_path)


def run_ffmpeg_command(cmd: List[str]) -> Dict[str, Any]:
    """运行FFmpeg命令并返回结果
    
    Args:
        cmd: FFmpeg命令列表
        
    Returns:
        包含执行结果的字典
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        else:
            return {
                "success": False,
                "error": f"FFmpeg命令执行错误: {result.stderr}",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"执行FFmpeg命令时出现异常: {str(e)}"
        }


def get_video_duration(video_path: str) -> Optional[float]:
    """获取视频时长（秒）
    
    Args:
        video_path: 视频文件路径
        
    Returns:
        视频时长（秒），如果出错则返回None
    """
    if not check_file_exists(video_path):
        return None
        
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", video_path
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
    """将秒数格式化为 HH:MM:SS.mmm 格式
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化后的时间字符串
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds_val = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds_val:06.3f}"


# 创建MCP服务器实例
mcp = FastMCP("ffmpeg_mcp")

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
def ffmpeg_convert_video(input_path: str, output_path: str, format: str = None) -> dict:
    """转换视频格式
    
    Args:
        input_path: 输入视频文件路径
        output_path: 输出视频文件路径
        format: 输出格式，如 mp4, avi, mkv 等，如果为 None 则从 output_path 推断
    
    Returns:
        包含转换结果的字典
    """
    try:
        if not check_file_exists(input_path):
            return {"error": f"输入文件不存在: {input_path}"}
        
        # 确保输出目录存在
        ensure_directory_exists(output_path)
        
        # 构建 FFmpeg 命令
        cmd = ["ffmpeg", "-i", input_path, "-y"]
        
        # 如果指定了格式，添加相应参数
        if format:
            cmd.extend(["-f", format])
        
        cmd.append(output_path)
        
        # 执行转换
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"文件转换成功: {output_path}",
                "output_path": output_path
            }
        else:
            return {
                "success": False,
                "error": f"FFmpeg 转换错误: {result.stderr}"
            }
    except Exception as e:
        return {"error": f"转换过程中出现异常: {str(e)}"}

@mcp.tool
def ffmpeg_extract_audio(video_path: str, audio_path: str, audio_format: str = "mp3") -> dict:
    """从视频中提取音频
    
    Args:
        video_path: 视频文件路径或URL
        audio_path: 输出音频文件路径
        audio_format: 音频格式，默认为 mp3
    
    Returns:
        包含提取结果的字典
    """
    try:
        local_video_path = video_path
        
        # 判断是否为网络地址，如果是则下载到本地
        if is_url(video_path):
            try:
                local_video_path = download_video(video_path)
                print(f"已下载网络视频到临时文件: {local_video_path}")
            except Exception as e:
                return {"error": f"下载视频失败: {str(e)}"}
        elif not check_file_exists(video_path):
            return {"error": f"视频文件不存在: {video_path}"}
        
        # 确保输出目录存在
        ensure_directory_exists(audio_path)
        
        # 构建 FFmpeg 命令
        cmd = [
            "ffmpeg", "-i", local_video_path, "-vn", "-acodec", "copy" if audio_format == "aac" else "libmp3lame",
            "-y", audio_path
        ]
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"音频提取成功: {audio_path}",
                "output_path": audio_path,
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
def ffmpeg_create_thumbnail(video_path: str, thumbnail_path: str, time_position: str = "00:00:05") -> dict:
    """从视频中提取特定时间点的缩略图
    
    Args:
        video_path: 视频文件路径
        thumbnail_path: 输出缩略图路径
        time_position: 时间点，格式为 HH:MM:SS，默认为 5 秒
    
    Returns:
        包含提取结果的字典
    """
    try:
        if not check_file_exists(video_path):
            return {"error": f"视频文件不存在: {video_path}"}
        
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

@mcp.tool
def ffmpeg_remove_watermark(video_path: str, output_path: str, x: int = 590, y: int=1200, width: int=100, height: int=40) -> dict:
    """去除视频中的水印
    
    Args:
        video_path: 输入视频文件路径
        output_path: 输出视频文件路径
        x: 水印左上角的x坐标
        y: 水印左上角的y坐标
        width: 水印宽度
        height: 水印高度
    
    Returns:
        包含处理结果的字典
    """
    try:
        if not check_file_exists(video_path):
            return {"error": f"视频文件不存在: {video_path}"}
        
        # 确保输出目录存在
        ensure_directory_exists(output_path)
        
        # 构建 FFmpeg 命令，使用 delogo 滤镜去除水印
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", f"delogo=x={x}:y={y}:w={width}:h={height}:show=0",
            "-c:a", "copy", "-y", output_path
        ]
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"水印去除成功: {output_path}",
                "output_path": output_path
            }
        else:
            return {
                "success": False,
                "error": f"FFmpeg 去除水印错误: {result.stderr}"
            }
    except Exception as e:
        return {"error": f"处理过程中出现异常: {str(e)}"}

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
def ffmpeg_concat_videos(video_paths: list, output_path: str, transition_duration: float = 0.5) -> dict:
    """合成多个视频文件为一个视频
    
    Args:
        video_paths: 视频文件路径列表
        output_path: 输出视频文件路径
        transition_duration: 过渡时间（秒），默认为0.5秒
    
    Returns:
        包含合成结果的字典
    """
    try:
        # 检查所有输入文件是否存在
        missing_files = []
        for video_path in video_paths:
            if not check_file_exists(video_path):
                missing_files.append(video_path)
        
        if missing_files:
            return {"error": f"以下视频文件不存在: {', '.join(missing_files)}"}
        
        if len(video_paths) < 2:
            return {"error": "至少需要两个视频文件才能进行合成"}
        
        # 确保输出目录存在
        ensure_directory_exists(output_path)
        
        # 创建临时文件列表文件
        temp_list_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt')
        
        # 写入文件列表
        for video_path in video_paths:
            temp_list_file.write(f"file '{os.path.abspath(video_path)}'\n")
        
        temp_list_file.close()
        
        # 构建 FFmpeg 命令
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", temp_list_file.name,
            "-c:v", "libx264", "-preset", "medium", "-c:a", "aac", "-y", output_path
        ]
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 删除临时文件
        try:
            os.unlink(temp_list_file.name)
        except:
            pass
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"视频合成成功: {output_path}",
                "output_path": output_path
            }
        else:
            return {
                "success": False,
                "error": f"FFmpeg 合成视频错误: {result.stderr}"
            }
    except Exception as e:
        return {"error": f"处理过程中出现异常: {str(e)}"}


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
    port: Annotated[int, typer.Option(help="服务器运行的端口号.")] = 9000
):
    """
    启动 FFmpeg MCP 服务器，监听网络接口。
    """
    typer.echo(f"启动FFmpeg MCP服务 (模式: host, 地址: {host_address}, 端口: {port}, 传输: {transport})...")
    typer.echo(f"服务将在 http://{host_address}:{port}/{transport} 上运行")
    mcp.run(transport="sse", host=host_address, port=port)


if __name__ == "__main__":
    app()
