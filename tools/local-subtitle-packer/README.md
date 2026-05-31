# INLOOK Local Subtitle Packer

纯本地自动字幕打包工具：视频/音频 → Whisper 识别 → SRT/ASS 字幕 → FFmpeg 烧录成 MP4。

适合你的短视频工作流：

```text
录屏视频 + 真人语音
→ 本地语音识别
→ 白字黑描边字幕
→ 输出成片
```

## Download & Usage

下载后，你可以直接在自己的电脑上运行，不需要上传云端。

第一版提供两种入口：

- 命令行工具
- 本地 Web 版

## 安装

macOS 建议先装带 `libass` 的 FFmpeg，否则无法把 ASS/SRT 真正烧录进视频：

```bash
brew tap nepherte/ffmpeg
brew install --cask nepherte/ffmpeg/ffmpeg
brew install --cask nepherte/ffmpeg/ffprobe
```

安装后可以快速确认：

```bash
ffmpeg -filters | grep -E 'subtitles|ass'
```

如果能看到 `subtitles` 或 `ass`，说明字幕烧录环境已经就绪。

推荐使用 `uv` 管理 Python 环境：

```bash
cd tools/local-subtitle-packer
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

如果你还没装 `uv`：

```bash
brew install uv
```

## One-Click Start

### macOS

- 终端启动：

```bash
./start.sh
```

- Finder 双击启动：

```text
start.command
```

### Windows

双击：

```text
start.bat
```

启动后会自动：

- 创建虚拟环境
- 安装 `requirements.txt`
- 检查 `ffmpeg`
- 检查 `ffprobe`
- 启动本地 FastAPI 服务
- 打开浏览器 `http://127.0.0.1:7860`

## Local Web UI

Web 页面第一版支持：

- 选择视频
- 可选选择音频
- 开始生成字幕
- 显示日志
- 下载 `mp4 / srt / ass / txt`
- 修改 `ass` 后重新导出

## 环境检查

```bash
uv run python scripts/check_env.py
```

会检查：
- Python 版本
- ffmpeg
- ffprobe
- faster-whisper
- 字幕滤镜支持（`subtitles` / `ass`）

如果最后一项失败，说明你当前 ffmpeg 不能烧录字幕，需要换成带 `libass` 的版本。

## 模型说明

第一次运行会自动下载 faster-whisper 模型。

下载完成后：
- 模型会缓存在本地
- 后续可以离线运行
- 不需要上传云端

默认参数：

```text
模型：small
设备：cpu
计算类型：int8
```

模型可选：

```text
tiny / base / small / medium / large-v3
```

推荐：

```text
日常：small
更快：base
更准：medium / large-v3
```

## 推荐命令

### 1. 视频原声直接打字幕

```bash
uv run python scripts/subtitle_pack.py \
  --video input.mp4 \
  --output output_subtitled.mp4
```

### 2. 视频 + 单独真人语音

```bash
uv run python scripts/subtitle_pack.py \
  --video screen_record.mp4 \
  --audio voice.m4a \
  --output final.mp4
```

### 3. 明确指定默认推荐参数

```bash
uv run python scripts/subtitle_pack.py \
  --video input.mp4 \
  --model small \
  --device cpu \
  --compute-type int8 \
  --output final.mp4
```

### 4. 修改字幕后只重新烧录

第一次先生成字幕和成片：

```bash
uv run python scripts/subtitle_pack.py \
  --video input.mp4 \
  --output output_subtitled.mp4
```

如果字幕有错：

- 手动修改 `output_subtitled.ass`
- 或先改 `output_subtitled.srt`，再自行同步成 ASS

然后只重新烧录，不再重新跑 Whisper：

```bash
uv run python scripts/burn_subtitles.py \
  --video input.mp4 \
  --ass output_subtitled.ass \
  --output output_fixed.mp4
```

## Local Web Workflow

第一次先自动识别：

- 选择视频
- 可选选择音频
- 点击开始生成字幕

会生成：

- `mp4`
- `srt`
- `ass`
- `txt`

如果字幕有错：

- 手动修改 `.ass` 或 `.srt`
- 然后在 Web 页面里重新选择修改后的 `ass`
- 点击重新导出

这样不会重新跑 Whisper，只会重新烧录视频

## 输出

会生成：

```text
final.mp4   带字幕成片
final.srt   SRT 字幕
final.ass   ASS 样式字幕
final.txt   纯文本逐字稿
```

重新烧录字幕时，通常只会新增：

```text
output_fixed.mp4
```

## 第一版已经处理的问题

- 中文路径
- 空格路径
- ASS / subtitles 滤镜路径转义
- 避免字幕路径出现奇怪斜杠
- 有单独音频时替换原视频声音
- 没有单独音频时尽量保留原视频声音
- 修改 ASS 后可直接重新烧录，不必重复跑 Whisper

## 常用示例

更多例子见：

- `examples/example_usage.md`
- `PRODUCTION_WORKFLOW.md`

## 字幕风格

当前默认样式：

```text
白字
黑色粗描边
中下方偏上
不加黑底条
尽量单行
适合竖屏短视频
```

## 生产工作流

个人版：

```text
screen.mp4 录屏
voice.m4a 真人口播
↓
subtitle_pack.py
↓
final.mp4 / final.srt / final.ass / final.txt
```

服务端版可以扩展为：

```text
Vue 上传
↓
FastAPI 接收
↓
任务队列
↓
Worker 调用 faster-whisper + FFmpeg
↓
输出 MP4 下载
```

生产环境要增加：

```text
文件大小限制
格式校验
任务超时
失败重试
临时文件清理
日志
隐私保护
模型缓存
```

## 和 YOLO 组合

```text
YOLO：看画面，输出识别框
Whisper：听声音，输出字幕
FFmpeg：合成视频
```
