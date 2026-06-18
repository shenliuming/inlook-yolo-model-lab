# Template Clip Bank Handoff

## 项目目标

`Template Clip Bank MVP` 的目标是把一段 `60~120s` 的真人模板视频，切成可复用候选片段，经过人工或 mock AI 选片后，拼成一个时长与口播音频基本一致的 `prepared_template.mp4`，再导出为标准 `LatentSync` job package，方便后续上传到云 GPU 做换台词口播生成。

当前阶段的定位不是“完整数字人产品”，而是一个稳定、可复用、可验证的模板视频准备层。

主链路：

`script.txt -> script_segments.json -> candidates_ai_scored.json -> timeline_plan.json -> prepared_template.mp4 -> qa_report.json -> export_latentsync_job -> import_latentsync_result`

## 当前进度

当前本地 MVP 主链路已经跑通，并已完成这些阶段：

- 候选片段切片
- 候选片段预览图生成
- 人工备注合并
- mock AI 评分
- script 文案自动分段
- 人工 timeline 生成
- AI mock timeline 生成
- `prepared_template.mp4` 拼接
- 本地 QA 报告生成
- LatentSync job package 导出
- LatentSync 结果本地回收与最终 QA
- 云端 smoke test runbook 文档

当前 runtime 中已经存在一套实际产物，路径在：

- [apps/yolo-api/runtime/template_bank](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/runtime/template_bank)

## 文件结构

核心代码目录：

- [apps/yolo-api/engines/latentsync/template_bank](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank)

主要脚本：

- [extract_candidates.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/extract_candidates.py)：按滑窗切候选片段
- [make_candidate_sheet.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/make_candidate_sheet.py)：生成每个 clip 的 6 帧预览图和总览页
- [merge_manual_clip_notes.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/merge_manual_clip_notes.py)：把人工备注合并到候选片段元数据
- [score_candidates_ai.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/score_candidates_ai.py)：mock AI 评分协议层
- [build_script_segments_mock.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/build_script_segments_mock.py)：从 `script.txt` + `narration.wav` 生成 `script_segments.json`
- [build_timeline_manual.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/build_timeline_manual.py)：人工 `selected_clips.json` 路线
- [build_timeline_ai.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/build_timeline_ai.py)：AI mock 选片路线
- [render_prepared_template.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/render_prepared_template.py)：按 timeline 拼出 `prepared_template.mp4`
- [qa_report.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/qa_report.py)：准备视频 QA
- [export_latentsync_job.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/export_latentsync_job.py)：导出 LatentSync job package
- [import_latentsync_result.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/import_latentsync_result.py)：回收云端 LatentSync 结果
- [run_pipeline.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/run_pipeline.py)：标准流水线入口

示例与说明：

- [README.md](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/README.md)
- [config.example.json](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/config.example.json)
- [manual_clip_notes.example.json](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/manual_clip_notes.example.json)
- [script_segments.example.json](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/engines/latentsync/template_bank/script_segments.example.json)
- [latentsync_cloud_smoke_test.md](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/docs/runbooks/latentsync_cloud_smoke_test.md)

runtime 目录约定：

- `input/`：模板视频、音频、文案、人工选择、人工备注
- `candidates/`：切出来的候选片段
- `sheets/`：候选片段预览图
- `output/`：`prepared_template.mp4`
- `reports/`：所有中间报告和 QA JSON
- `latentsync_jobs/`：导出的 LatentSync job 包
- `final/`：LatentSync 最终回收结果

## 核心逻辑

### 1. 候选切片

`extract_candidates.py` 默认使用：

- `segment_length = 5`
- `step = 2`

也就是 5 秒窗口、2 秒步进的滑窗切片。每个 clip 会记录：

- `clip_id`
- `start`
- `end`
- `duration`
- `path`
- `source_group`
- `content_hint`
- `motion_hint`
- `tags`
- `usable`
- `manual_note`

### 2. 预览与人工标注

`make_candidate_sheet.py` 会从每个 clip 抽 6 帧，生成：

- `sheets/clip_001.jpg`
- `sheets/candidate_sheet.jpg`
- 候选较多时的 `candidate_sheet_page_001.jpg`

人工可以根据预览填写 `manual_clip_notes.json`，再由 `merge_manual_clip_notes.py` 合并到 `candidates_enriched.json`。

### 3. mock AI 评分

`score_candidates_ai.py` 目前不接真实模型，只生成统一协议：

- `candidates_ai_scored.json`
- `vision_review_prompt.md`

核心作用是先把“AI 评分结构”固定下来，后续可以替换成真实视觉模型而不改上下游协议。

### 4. script 自动分段

`build_script_segments_mock.py` 读取：

- `input/script.txt`
- `input/narration.wav`

按中文标点拆句，并按字数比例分配 duration，产出 `input/script_segments.json`。

### 5. timeline 生成

有两条路线：

- `build_timeline_manual.py`
  使用 `selected_clips.json`
- `build_timeline_ai.py`
  使用 `candidates_ai_scored.json`

`build_timeline_ai.py` 支持：

- `ai_mock_score`
- `ai_mock_script_aware`

其中 `script-aware` 模式会优先考虑多样性，尽量避免：

- 重复 `clip_id`
- 重复 `source_group`
- `source_start` 太近

并在 `timeline_plan.json` 中输出：

- `base_match_score`
- `diversity_penalty`
- `final_match_score`
- `selection_stage`
- `matched_tags`

### 6. prepared template 渲染

`render_prepared_template.py` 优先读取：

- `reports/timeline_plan.json`

如果不存在，才 fallback 到旧的 `selected_clips.json` 逻辑。

最终产出：

- `output/prepared_template.mp4`
- `reports/prepare_report.json`

### 7. 本地 QA

`qa_report.py` 读取：

- `prepared_template.mp4`
- `narration.wav`

检查：

- 时长
- fps
- frame_count
- 编码
- file_size
- 是否一帧内对齐
- timeline 是否有重复 clip / source_group

最终产出：

- `reports/qa_report.json`

### 8. LatentSync 导出与回收

`export_latentsync_job.py` 会把：

- `prepared_template.mp4`
- `narration.wav`
- timeline / qa / pipeline / ai scored / script 相关上下文

打成标准 job 目录，产出：

- `job_config.json`
- `manifest.json`
- `run_latentsync.sh`

`import_latentsync_result.py` 会把云端产出的：

- `latentsync_output.mp4`

导回本地，复制为：

- `final/final_latentsync_output.mp4`

并生成：

- `reports/final_qa_report.json`
- `final/final_report.json`

## 已完成内容

- Template Clip Bank 基础目录和 README
- 候选片段滑窗切片
- 候选片段 6 帧预览图
- 候选片段分页总览图
- `clips` / `candidates` 两种 JSON 结构兼容
- 候选片段内容描述字段扩展
- 人工备注合并
- 手工 timeline 构建
- mock AI 评分协议层
- mock script 自动分段
- AI mock timeline 构建
- script-aware 多样性优先选片策略
- `prepared_template.mp4` 渲染
- `qa_report.json` 自动质检
- 一键流水线 `run_pipeline.py`
- LatentSync job package 导出
- LatentSync 结果导入与最终 QA
- 云端 smoke test runbook

## 未完成内容

- 未接入真实视觉 AI 评分模型
- 未接入 DeepSeek 或其他 LLM 进行 script-aware 编排
- 未接入真实 LatentSync 云执行链路
- 未做自动上传、自动拉回、自动云端执行
- 未做 crossfade / 节奏级镜头过渡
- 未做基于语义的片段质量排序
- 未做更细的动作去重策略
- 未做产品级 UI
- 未做任务队列、调度、云状态同步
- 未做正式生产环境错误恢复机制

## 已知问题

- 当前 `score_candidates_ai.py` 仍是 mock provider，不代表真实视觉评分能力。
- 当前 `build_timeline_ai.py` 的“AI”本质上仍是规则 + mock score，不是外部智能模型。
- `prepared_template.mp4` 目前是硬切拼接，没有 crossfade。
- 候选很多时 `candidate_sheet.jpg` 仍然可能较大，虽然已支持分页。
- runtime 目录里目前存在 `.DS_Store` 和历史测试 job，后续如果要做更干净的交付，建议整理。
- `run_pipeline.py --import-latentsync-result` 现在是可选附加步骤，不是默认主流程的一部分。
- 当前 smoke test runbook 是纯手工流程，没有自动 SSH / SCP 封装。

## 环境变量

当前这套 Template Clip Bank MVP 没有强依赖自定义环境变量。

默认依赖的是本机可用环境：

- `python3`
- `ffmpeg`
- `ffprobe`
- Python 运行环境中可导入 `cv2`
- Python 运行环境中可导入 `numpy`

`run_pipeline.py` 会自动选择一个可用 Python 解释器，并检查：

- `cv2`
- `numpy`

如果后续接真实云端或真实 AI，再补充新的环境变量说明。

## 启动命令

### 1. 手工主链路

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/extract_candidates.py \
  --runtime-dir apps/yolo-api/runtime/template_bank

python3 apps/yolo-api/engines/latentsync/template_bank/make_candidate_sheet.py \
  --runtime-dir apps/yolo-api/runtime/template_bank

python3 apps/yolo-api/engines/latentsync/template_bank/merge_manual_clip_notes.py \
  --runtime-dir apps/yolo-api/runtime/template_bank

python3 apps/yolo-api/engines/latentsync/template_bank/build_script_segments_mock.py \
  --runtime-dir apps/yolo-api/runtime/template_bank

python3 apps/yolo-api/engines/latentsync/template_bank/score_candidates_ai.py \
  --runtime-dir apps/yolo-api/runtime/template_bank

python3 apps/yolo-api/engines/latentsync/template_bank/build_timeline_ai.py \
  --runtime-dir apps/yolo-api/runtime/template_bank \
  --script-segments apps/yolo-api/runtime/template_bank/input/script_segments.json

python3 apps/yolo-api/engines/latentsync/template_bank/render_prepared_template.py \
  --runtime-dir apps/yolo-api/runtime/template_bank

python3 apps/yolo-api/engines/latentsync/template_bank/qa_report.py \
  --runtime-dir apps/yolo-api/runtime/template_bank
```

### 2. 一键本地流水线

人工路线：

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/run_pipeline.py \
  --runtime-dir apps/yolo-api/runtime/template_bank
```

AI mock + script-aware 路线：

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/run_pipeline.py \
  --runtime-dir apps/yolo-api/runtime/template_bank \
  --build-script-segments \
  --run-ai-score \
  --use-ai-timeline \
  --use-script-segments
```

### 3. 导出 LatentSync job

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/export_latentsync_job.py \
  --runtime-dir apps/yolo-api/runtime/template_bank \
  --job-id job_test_002 \
  --enable-deepcache
```

或者：

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/run_pipeline.py \
  --runtime-dir apps/yolo-api/runtime/template_bank \
  --build-script-segments \
  --run-ai-score \
  --use-ai-timeline \
  --use-script-segments \
  --export-latentsync-job
```

### 4. 导回 LatentSync 最终结果

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/import_latentsync_result.py \
  --runtime-dir apps/yolo-api/runtime/template_bank \
  --job-dir apps/yolo-api/runtime/template_bank/latentsync_jobs/job_test_002 \
  --result-video apps/yolo-api/runtime/template_bank/latentsync_jobs/job_test_002/output/latentsync_output.mp4
```

### 5. 云端 smoke test 文档

参考：

- [docs/runbooks/latentsync_cloud_smoke_test.md](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/docs/runbooks/latentsync_cloud_smoke_test.md)

## 建议下一步

建议按这个顺序继续：

1. 接真实视觉评分模型，替换 `score_candidates_ai.py` 的 mock provider。
2. 接真实 script-aware 编排模型，替换 `build_timeline_ai.py` 的规则层。
3. 打通云端 LatentSync 任务执行与结果回收闭环。
4. 在 timeline 渲染层增加更自然的片段过渡策略。
5. 再考虑把整条链路收敛成产品化服务或 UI。
