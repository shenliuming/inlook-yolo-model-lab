# 蝉镜 / 蝉境定制数字人 POC

本仓库已接入一条独立的蝉镜定制数字人 POC 链路：

- 后端：`apps/yolo-api`
- 前端：`inlook-studio-web`
- 运行时目录：`apps/yolo-api/runtime/digital_human_poc/chanjing`
- SQLite：`apps/yolo-api/runtime/inlook_studio.db`

这条链路不会替换现有 mock 数字人接口，也不会替换 LatentSync。

## 环境变量

```env
CHANJING_APP_ID=
CHANJING_SECRET_KEY=
CHANJING_API_BASE_URL=https://open-api.chanjing.cc
CHANJING_API_BASE_PATH=/open/v1
CHANJING_ACCESS_TOKEN_HEADER=access_token
CHANJING_DEFAULT_MODEL=0
CHANJING_DEFAULT_SCREEN_WIDTH=1080
CHANJING_DEFAULT_SCREEN_HEIGHT=1920
CHANJING_TOKEN_EXPIRE_MARGIN_SECONDS=300
```

## 路由

- `GET /api/v1/studio/digital-human/chanjing/config/status`
- `GET /api/v1/studio/digital-human/chanjing/common-persons`
- `GET /api/v1/studio/digital-human/chanjing/common-audios`
- `GET /api/v1/studio/digital-human/chanjing/persons`
- `GET /api/v1/studio/digital-human/chanjing/custom-persons`
- `POST /api/v1/studio/digital-human/chanjing/custom-persons/train`
- `POST /api/v1/studio/digital-human/chanjing/custom-persons/train-upload`
- `GET /api/v1/studio/digital-human/chanjing/custom-persons/train/{job_id}`
- `POST /api/v1/studio/digital-human/chanjing/videos`
- `GET /api/v1/studio/digital-human/chanjing/videos/{job_id}`
- `GET /api/v1/studio/digital-human/chanjing/jobs`
- `POST /api/v1/studio/digital-human/chanjing/full-poc/jobs`
- `GET /api/v1/studio/digital-human/chanjing/full-poc/jobs/{job_id}`

## SQLite 表

- `digital_human_persons`
- `digital_human_jobs`
- `digital_human_settings`

数据库只存任务索引、数字人资产和非敏感默认设置。

- `CHANJING_SECRET_KEY` 不会入库
- `app_id` 不会返回给前端
- 原始请求响应和 `output.mp4` 继续保存在 runtime 目录

## Runtime 目录

```text
apps/yolo-api/runtime/digital_human_poc/chanjing/{job_id}/
```

其中会保存：

- `input/template.mp4`
- `upload/*.json`
- `training/*.json`
- `video/*.json`
- `output/output.mp4`
- `job.json`
- `logs.txt`

## 前端入口

主产品前端入口位于：

- [App.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/App.vue)
- [ChanjingDigitalHumanPanel.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/components/ChanjingDigitalHumanPanel.vue)

页面能力包括：

1. 配置检查
2. 上传模板视频训练数字人
3. 查看已训练数字人列表
4. 用 `wav_url` 或蝉镜 TTS 合成视频
5. 查看最近任务列表

## 命令行脚本

训练数字人：

```bash
python apps/yolo-api/scripts/poc_chanjing_train_person.py \
  --video "/absolute/path/template.mp4" \
  --name "INLOOK_测试数字人" \
  --train-type both \
  --resolution-rate 0
```

用外部音频合成：

```bash
python apps/yolo-api/scripts/poc_chanjing_create_video.py \
  --person-id "C-xxx" \
  --audio-type audio \
  --wav-url "https://example.com/audio.wav" \
  --screen-width 1080 \
  --screen-height 1920 \
  --model 0
```

用蝉镜 TTS 合成：

```bash
python apps/yolo-api/scripts/poc_chanjing_create_video.py \
  --person-id "C-xxx" \
  --audio-type tts \
  --text "你好，这是 INLOOK Studio 测试。" \
  --audio-man-id "C-xxx" \
  --screen-width 1080 \
  --screen-height 1920 \
  --model 0
```

完整流程：

```bash
python apps/yolo-api/scripts/poc_chanjing_full_flow.py \
  --video "/absolute/path/template.mp4" \
  --name "INLOOK_测试数字人" \
  --train-type both \
  --audio-type audio \
  --wav-url "https://example.com/audio.wav" \
  --screen-width 1080 \
  --screen-height 1920 \
  --model 0
```

列出人物/声音：

```bash
python apps/yolo-api/scripts/poc_chanjing_list_persons.py --type custom
python apps/yolo-api/scripts/poc_chanjing_list_persons.py --type common
python apps/yolo-api/scripts/poc_chanjing_list_persons.py --type audio
```

## 训练流程

1. 前端把模板视频上传到 FastAPI
2. FastAPI 保存到 runtime
3. 后端调用蝉镜 `create_upload_url`
4. 上传文件到签名地址
5. 轮询 `file_detail` / `file_list`
6. 调用 `create_customised_person`
7. 轮询 `customised_person`
8. 成功后同步入 SQLite `digital_human_persons`

## 合成流程

1. 前端选择已训练数字人
2. 提交 `wav_url` 或 `tts text + audio_man_id`
3. 后端调用 `create_video`
4. 轮询 `video`
5. 成功后立即下载 `output/output.mp4`
6. 更新 SQLite `digital_human_jobs`

## 常见问题

- 页面显示“未配置”
  - 请检查 `apps/yolo-api/.env.local` 中是否设置了 `CHANJING_APP_ID` 和 `CHANJING_SECRET_KEY`
- 训练长时间停留在 `training`
  - 蝉镜训练本身耗时可能较长，可稍后刷新任务状态
- 视频成功但没有本地文件
  - 检查 `video_url` 是否为空，以及 runtime 目录写权限
- SQLite 没创建
  - 检查 `SQLAlchemy` 依赖是否已安装，以及 `apps/yolo-api/runtime` 是否可写

## 注意

- 不要提交 `apps/yolo-api/.env.local`
- 不要把蝉镜密钥放到前端
- 前端只调用本项目 FastAPI，不直接调用 `open-api.chanjing.cc`
