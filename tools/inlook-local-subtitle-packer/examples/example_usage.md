# Example Usage

## 1. 先检查环境

```bash
uv run python scripts/check_env.py
```

## 2. 视频原声直接打字幕

```bash
uv run python scripts/subtitle_pack.py \
  --video ./input.mp4 \
  --output ./output_subtitled.mp4
```

## 3. 录屏视频 + 单独真人语音

```bash
uv run python scripts/subtitle_pack.py \
  --video ./screen_record.mp4 \
  --audio ./voice.m4a \
  --output ./final.mp4
```

## 4. 指定更快或更准的模型

```bash
uv run python scripts/subtitle_pack.py \
  --video ./input.mp4 \
  --model base \
  --output ./fast_version.mp4
```

```bash
uv run python scripts/subtitle_pack.py \
  --video ./input.mp4 \
  --model medium \
  --output ./better_accuracy.mp4
```

## 5. 路径里有中文或空格

```bash
uv run python scripts/subtitle_pack.py \
  --video "/Users/shen/Desktop/视频素材/第1集 录屏.mp4" \
  --audio "/Users/shen/Desktop/语音/我的口播 01.m4a" \
  --output "/Users/shen/Desktop/输出/final output.mp4"
```

## 6. 不保留原视频声音

```bash
uv run python scripts/subtitle_pack.py \
  --video ./input.mp4 \
  --no-audio \
  --output ./muted_subtitle.mp4
```
