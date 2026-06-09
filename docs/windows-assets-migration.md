# Windows Assets Migration Guide

## 一、必须迁移资源
1.  **CosyVoice 大模型** (`CosyVoice2-0.5B`)：体积约 5.2GB，是生成语音的核心。
2.  **MOSS-TTS 模型**：如果不使用 CosyVoice 作为备用，则必须有。
3.  **自定义音色库 (Voice Profiles)**：如果在 Mac 上训练或配置了自定义音色，包含了供 CosyVoice 克隆音色所必须的 `reference.wav`。

## 二、建议迁移资源
1.  **高清口播测试视频** (`口播数字训练.mp4` 等)：用于后续在 Windows 上测试 Digital Human。

## 三、不需要迁移资源
1.  `apps/yolo-api/runtime/content_lab/tts/tasks` (所有的临时 TTS 生成产物)。
2.  上传的临时测试素材和中间切片。
3.  `node_modules/`, `.venv/`, `__pycache__/` 等本地编译或依赖目录。

## 四、禁止进入 Git 的资源
1.  **模型权重文件** (`.pt`, `.onnx`, `.safetensors`, `.bin`, `.data`)。
2.  **大体积多媒体文件** (`.mp4`, `.wav`, `.m4a`, `.jpg`)。
3.  **密钥配置文件** (`.env.local`)。
以上文件均已被 `.gitignore` 规则拦截，严禁使用 `git add -f` 强制提交。

## 五、Windows 推荐目录结构
为防止 C 盘空间爆满和中文路径引发 Python 报错，建议在 Windows 上采用以下分离式目录结构：

```text
D:\
├── Workspace\
│   └── inlook-yolo-model-lab\          # 你的 Git 仓库代码
│       ├── apps\yolo-api\
│       │   ├── .env.local              # 本地配置文件 (由 example 复制而来)
│       │   └── runtime\content_lab\
│       │       └── voices\             # 从 Mac 打包拷贝过来的自定义音色库
│       └── inlook-studio-web\
└── Models\
    └── CosyVoice2-0.5B\                # 外部单独下载的 5.2GB 大模型
```

## 六、Windows 迁移操作顺序

### 1. 代码拉取与配置
1.  在 `D:\Workspace\` 执行 `git clone`.
2.  将 `scripts/example_yolo_api_env_windows.txt` 复制为 `apps/yolo-api/.env.local`。
3.  填写真实的 `LLM_API_KEY`。

### 2. 模型下载 (MOSS 已清空处理)
> 注：为了防止 Git 仓库臃肿，Mac 仓库已清空 `third_party/MOSS-TTS-Nano/models`。

**下载 CosyVoice：**
1.  打开 PowerShell，执行提供的下载脚本：
    ```powershell
    .\scripts\download_cosyvoice_windows.ps1 -ModelDir "D:\Models\CosyVoice2-0.5B" -Source "modelscope"
    ```
2.  等待 5.2GB 模型下载完毕。

### 3. 音色库导入
1.  在 Mac 端执行 `scripts/pack_voice_assets_mac.sh`，生成 `inlook_voices_backup.tar.gz` (在桌面)。
2.  将压缩包拷贝到 Windows。
3.  在 Windows 的 `D:\Workspace\inlook-yolo-model-lab\apps\yolo-api\runtime\content_lab\` 目录下解压，确保 `voices` 文件夹正确还原。

### 4. 验证启动
1.  启动前端 (Node.js)。
2.  启动后端 (uv + Python)。
3.  检查 API 连通性，进行一次完整的改写和 TTS 生成测试。
