---
name: gen-video
description: 生成或下载文生视频。用户要做/生成/下载 video、视频、片段、动画、运镜、动态画面时启用。静态图请用 gen-image。
argument-hint: "[视频描述]"
---

# 生视频

通过用户自己的 New API 网关做文生视频。脚本：本 skill 目录下的 `scripts/gen_media.py`。

> 语言铁律：所有面向用户的文字一律用中文，包括 brief 卡片、确认门、提问、报错解释。脚本 stdout 是英文，读完后翻译成中文再回复。

## 首次配置（onboard）

1. 跑 `python "<skill-dir>/scripts/gen_media.py" show-config`。
   - 打出 Base URL + 掩码 Key → 配置完成，跳过本段。
   - stderr 含 `CONFIG_MISSING` → 继续。
2. 在对话里向用户收 **Base URL** 和 **API Key**（一句话一起问，或分两行收；别让用户切去终端跑命令）。
3. 收齐后跑：

   ```bash
   python "<skill-dir>/scripts/gen_media.py" configure --base-url "<url>" --api-key "<key>"
   ```

   Key 只在本次对话出现这一次；之后只用 `show-config` 的掩码输出，绝不在回复里复述完整 Key。

4. 再跑 `show-config` 验证，看到掩码 Key 即完成。

> 给用户的安全说明（一句话带过，别卡流程）：Key 会写入本地 `~/.gen-media/config.json`（权限 600），并经过本次对话一次；介意可改用环境变量 `GEN_MEDIA_BASE_URL` + `GEN_MEDIA_API_KEY`（不进对话）。

## 选模型（一次设置，随切随用）

1. 跑 `list-models`，把目录给用户看。
2. 文生视频默认：`happyhorse-1.1-t2v`。`i2v`/`r2v` 需要图片输入，本 skill 只走文本管线，脚本会拒绝。
3. 持久化：`set-model --video <model>`。单次试：生成命令加 `--model <model>`。
4. 完成判定：`show-config` 打出所选视频模型。

## 打磨 brief（核心体验，别拿一句话直接去生成）

先补齐这六个槽位；能从请求推断的就填上并一句话声明假设，推断不了且猜错会烧 Credits 时才问（最多问 2 个）：

1. **主体+动作** —— 什么在动、怎么动（一镜一主体；多主体会融化）。
2. **环境** —— 地点、时间、天气。
3. **镜头** —— 一镜一个运动：推进/拉远/摇/环绕/无人机俯冲。
4. **时间线节拍** —— 按时长切：0-2s 发生什么、2-4s、最后一秒。无节拍 = 静止帧。
5. **格式** —— 平台定比例：桌面广告 `16:9`，手机/短视频 `9:16`；分辨率默认 `1080P`（省额度草稿 `720P`）；时长默认 `5` 秒（3–15）。
6. **光线与情绪** —— 具名光线胜过形容词；单一情绪，别堆三个。

- 模糊请求（「随便来个视频」）→ 给 3 个方向（场景+镜头，每个一行），让用户挑；选完再补其余槽位。
- 不加 logo、字幕、人物，除非用户要。
- 完成判定：最终 prompt + 比例 + 分辨率 + 时长 全部确定。

镜头词汇、光线词、时间线模板、失败对策 → `references/prompt-guide.md`（需求模糊或用户要更好效果时加载）。

## 确认门

视频烧 Credits。先把完整 brief（prompt + 模型 + 比例 + 分辨率 + 时长）摆给用户，等他明确说「行/可以/生成」才提交。没说行，不提交。

## 生成

```bash
python "<skill-dir>/scripts/gen_media.py" video --prompt "<prompt>" --resolution "1080P" --ratio "16:9" --duration 5
```

脚本提交、轮询、下载 MP4、打路径；在脚本超时内等它跑完。回报最终文件路径 + 最终 prompt。MP4 本地存在前不许声称成功。

失败时：原文报 API 错误，再按此顺序排查 —— 模型权限 → 渠道模型列表 → 额度 → 任务轮询服务。

## 迭代

交付后给一个具体的下一版方向（新角度/更长切片/换光线）。

## 规则

- 只用自带脚本，不临时拼 curl。
- 完整 API Key 绝不写进项目目录；回复里只用掩码，不复述完整 Key。
- 默认存当前工作目录，除非用户指定输出目录。

## 更新

用户要更新 gen-media → 走宿主的插件/技能更新机制（Claude Code：`/plugin update gen-media`；Codex/WorkBuddy：拉仓库重拷 skill 文件夹）。配置在 `~/.gen-media/config.json`，skill 目录之外，更新不影响。
