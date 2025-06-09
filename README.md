# FFmpeg MCP 服务

这是一个基于FastMCP框架的FFmpeg工具集合，提供了一系列视频处理功能的API接口。

## 功能特点

本服务提供以下视频处理功能：

1. **获取FFmpeg版本信息** - 查询当前系统安装的FFmpeg版本
2. **视频格式转换** - 将视频转换为不同的格式（如MP4、AVI、MKV等）
3. **提取音频** - 从视频文件中提取音频轨道
4. **创建缩略图** - 从视频中提取特定时间点的帧作为缩略图
5. **去除水印** - 从视频中移除指定区域的水印
6. **获取视频信息** - 获取视频的详细信息（分辨率、时长、编码格式等）
7. **合成视频** - 将多个视频文件合并为一个视频

## 安装要求

### 前提条件

- Python 3.8+
- FFmpeg（需要预先安装在系统中并添加到PATH环境变量）

### 安装步骤

1. 克隆此仓库并进入项目目录
   ```bash
   git clone <repository-url>
   cd <repository-directory-name> # 通常是 ffmpeg_mcp，即包含 pyproject.toml 的目录
   ```

2. 创建并激活虚拟环境
   ```bash
   python -m venv .venv # 或者使用 uv: uv venv
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

3. 安装依赖 (使用 `uv`)
   ```bash
   uv pip sync
   ```

## 使用方法

### 启动服务

本服务提供两种启动模式：

#### 本地模式 (stdio)

```bash
python ffmpeg_mcp/main.py local
```

这种模式通过标准输入/输出进行通信，适合本地 MCP 客户端使用。

#### 主机模式 (网络)

```bash
python ffmpeg_mcp/main.py host [--host-address HOST_ADDRESS] [--port PORT]
```

默认情况下，服务将在 `0.0.0.0:9000` 上启动，使用 SSE 传输协议。

### MCP 客户端配置

要使用此服务，你需要在 MCP 客户端中添加相应的配置。以下是配置示例：

```json
{
  "mcpServers": {
    "ffmpeg-mcp": {
      "disabled": false,
      "command": "uv",
      "args": [
        "run",
        "python",
        "E:\\pyproj\\FirstMcp\\ffmpeg_mcp\\ffmpeg_mcp\\main.py",
        "local"
      ]
    }
  }
}
```

这个配置告诉 MCP 客户端通过执行 `uv run python E:\pyproj\FirstMcp\ffmpeg_mcp\ffmpeg_mcp\main.py local` 命令来启动服务，并通过标准输入/输出与服务通信。使用 `uv run` 可以确保服务在正确的 Python 环境中运行。

如果你希望连接到已经运行的网络模式服务，可以使用以下配置：

```json
{
  "mcpServers": {
    "ffmpeg-mcp": {
      "serverUrl": "http://127.0.0.1:9000/sse"
    }
  }
}
```

### API 接口说明

#### 1. 获取FFmpeg版本信息

```python
ffmpeg_version()
```

#### 2. 视频格式转换

```python
ffmpeg_convert_video(input_path: str, output_path: str, format: str = None)
```

#### 3. 提取音频

```python
ffmpeg_extract_audio(video_path: str, audio_path: str, audio_format: str = "mp3")
```

#### 4. 创建缩略图

```python
ffmpeg_create_thumbnail(video_path: str, thumbnail_path: str, time_position: str = "00:00:05")
```

#### 5. 去除水印

```python
ffmpeg_remove_watermark(video_path: str, output_path: str, x: int = 590, y: int = 1200, width: int = 100, height: int = 40)
```

#### 6. 获取视频信息

```python
ffmpeg_get_video_info(video_path: str)
```

#### 7. 合成视频

```python
ffmpeg_concat_videos(video_paths: list, output_path: str, transition_duration: float = 0.5)
```

## 示例

### 获取视频信息

```python
from mcp_client import MCPClient

client = MCPClient("http://127.0.0.1:9000/sse")
response = client.call("ffmpeg_get_video_info", {"video_path": "path/to/video.mp4"})
print(response)
```

### 合成视频

```python
from mcp_client import MCPClient

client = MCPClient("http://127.0.0.1:9000/sse")
response = client.call("ffmpeg_concat_videos", {
    "video_paths": ["path/to/video1.mp4", "path/to/video2.mp4"],
    "output_path": "path/to/output.mp4",
    "transition_duration": 0.5
})
print(response)
```

## 项目结构

```
ffmpeg_mcp/
├── .git/              # Git仓库数据
├── .gitignore         # Git忽略文件
├── .venv/             # Python虚拟环境
├── LICENSE            # 许可证文件
├── README.md          # 项目文档
├── build/             # 构建目录
├── dist/              # 分发目录
├── ffmpeg_mcp/        # 主源代码目录
│   ├── __init__.py    # 包初始化文件
│   └── main.py        # 主入口文件，包含所有FFmpeg工具函数和服务启动逻辑
├── ffmpeg_mcp.egg-info/ # 包安装信息
├── pyproject.toml     # 项目配置和依赖
└── uv.lock            # uv依赖锁文件
```

## 注意事项

- 确保系统中已正确安装FFmpeg，并且可以在命令行中直接调用
- 所有路径参数应使用绝对路径或相对于当前工作目录的路径
- 视频合成功能需要输入至少两个视频文件

## 未来计划

### 视频处理功能

- 添加视频剪切功能
- 添加视频压缩功能
- 添加视频裁剪功能
- 添加视频旋转和翻转功能
- 添加添加水印功能
- 添加视频速度调整功能

### 服务功能增强

- 增强 host 模式功能，提供 Web 界面
- 实现视频上传和下载功能，支持远程文件管理
- 添加任务队列和处理进度监控
- 支持批量处理任务

## 许可证

[MIT License](LICENSE)
