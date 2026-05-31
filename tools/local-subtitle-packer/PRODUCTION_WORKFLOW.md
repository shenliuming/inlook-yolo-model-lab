# 生产可用工作流说明

## 1. 本地个人工作流

```text
输入：
- 录屏视频 screen.mp4
- 真人语音 voice.m4a

处理：
- 提取语音
- faster-whisper 本地识别
- 生成 SRT / ASS / TXT
- FFmpeg 烧录字幕
- 用真人语音替换视频原声

输出：
- final.mp4
- final.srt
- final.ass
- final.txt
```

## 2. 半自动任务目录

```text
jobs/
  2026-xx-xx-001/
    input.mp4
    voice.m4a
    result.mp4
    result.srt
    result.ass
    result.txt
    log.txt
```

## 3. 服务端扩展

```text
Frontend Vue
↓
FastAPI
↓
Redis Queue / Celery / RQ
↓
Worker
  - FFmpeg
  - faster-whisper
  - ASS 字幕样式
  - 输出 MP4
↓
Nginx 下载结果
```

## 4. 模型选择

```text
tiny       很快，准确率一般
base       快，适合草稿
small      推荐默认
medium     更准
large-v3   更准，但慢
```

## 5. 安全和隐私

- 不上传云端，默认本地处理
- 服务端部署时不长期保存原始音视频
- 上传文件必须限制大小和格式
- 临时目录要定时清理
- 不要把模型、视频、音频、输出结果提交 Git
