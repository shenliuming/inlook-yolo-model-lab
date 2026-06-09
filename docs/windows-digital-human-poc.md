# Windows RTX 3070Ti Digital Human POC Plan

## 1. 背景

* Mac M5 已验证 Wav2Lip / LivePortrait / mouth overlay；
* 本地 Mac 效果和性能不适合正式数字人；
* Windows RTX 3070Ti 将作为数字人 POC 主机。

## 2. 目标

* 在 Windows + RTX 3070Ti 上验证 Duix-Avatar Lite；
* 输入 currentAudio.wav + avatar.mp4；
* 输出 talking.mp4；
* 暂不接入 INLOOK 主流程。

## 3. Windows 环境检查

* nvidia-smi；
* Docker Desktop；
* WSL2；
* docker --version；
* docker compose version；
* docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi。

## 4. POC 目录

* D:\poc\duix-avatar-poc
* 不放进 INLOOK 仓库。

## 5. 输入文件规范

* currentAudio.wav 来自 INLOOK TTS 输出；
* avatar.mp4 为自有或授权素材；
* 10-30 秒；
* 单人正脸；
* 嘴部无遮挡；
* 720p 优先；
* 不使用 reference.wav。

## 6. Duix POC 流程

* clone Duix-Avatar；
* 使用 docker-compose-lite；
* 启动 8383；
* POST /easy/submit；
* GET /easy/query；
* 输出 talking_duix_poc.mp4。

## 7. 验收标准

* 文件真实存在；
* 能播放；
* 有声音；
* 口型跟随；
* 无黑块；
* 无嘴边框；
* 无左上角小窗；
* 脸不严重糊；
* 身体不拉扯；
* 生成时间可接受。

## 8. 后续接入原则

* INLOOK 只做 digitalHumanProvider；
* 不把 Duix 代码塞进 INLOOK；
* 不提交模型和视频产物；
* 未来后端通过 provider 调用 Windows/远程服务；
* 未通过 POC 前不接入主流程。
