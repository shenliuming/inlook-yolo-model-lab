# INLOOK Studio Web

`inlook-studio-web` 是当前仓库内新增的独立 Vue 3 + Vite 前端应用，用于承载 INLOOK Studio / Studio Alpha 的内容生产前端。

## 特点

- 与现有 `apps/yolo-web` 完全分离
- 与现有 `apps/yolo-api` 通过 RESTful 接口联调
- 素材导入、文案提取、字幕下载、TTS 训练与配音读取真实任务状态
- 适合作为后续 Electron 桌面端壳子的前端基础

## 安装依赖

```bash
cd inlook-studio-web
npm install
```

## 启动开发环境

```bash
npm run dev
```

默认访问地址：

- [http://127.0.0.1:5180](http://127.0.0.1:5180)

## 当前已接入能力

- 本地视频上传素材
- 抖音 / B 站链接创建素材获取任务
- 基于素材发起转写任务
- 回填原始文案
- 下载 `srt / vtt`
- 上传参考音频创建音色训练任务
- 发起 TTS 合成任务
- 生成后在线播放 / 下载音频
- 底部任务队列读取真实任务状态

## 暂未接入能力

- AI 改写与增强
- 数字人生成
- 成片导出
