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

在项目根目录下运行 (即包含 `pyproject.toml` 和 `ffmpeg_mcp` 子目录的目录)：
```bash
python ffmpeg_mcp/main.py
```

服务将在 http://127.0.0.1:9000/sse 上启动。

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
fastmcp_project/
├── fastmcp/           # 主源代码目录
│   ├── __init__.py    # 包初始化文件
│   ├── main.py        # 主入口文件，服务启动逻辑
│   ├── tools.py       # FFmpeg工具函数
│   └── utils/         # 工具函数目录
│       ├── __init__.py
│       └── ffmpeg_helpers.py # FFmpeg辅助函数
├── requirements.txt   # 项目依赖
├── README.md          # 项目文档
└── Resources/         # 资源文件夹，存放示例视频和输出文件
```

## 注意事项

- 确保系统中已正确安装FFmpeg，并且可以在命令行中直接调用
- 所有路径参数应使用绝对路径或相对于当前工作目录的路径
- 视频合成功能需要输入至少两个视频文件

## 未来计划

- 添加视频剪切功能
- 添加视频压缩功能
- 添加视频裁剪功能
- 添加视频旋转和翻转功能
- 添加添加水印功能
- 添加视频速度调整功能

## 许可证

[MIT License](LICENSE)
