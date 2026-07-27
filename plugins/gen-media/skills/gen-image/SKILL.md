---
name: gen-image
description: 生成或下载图片。用户要画/做/生成/下载 image、海报、插画、封面、产品图、广告图时启用。视频请用 gen-video。
argument-hint: "[图片描述]"
---

# 生图

通过用户自己的 New API 网关生图。脚本：本 skill 目录下的 `scripts/gen_media.py`。

> 语言铁律：所有面向用户的文字一律用中文，包括 brief 卡片、提问、报错解释。脚本 stdout 是英文，读完后翻译成中文再回复。

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

1. 跑 `list-models`，把目录（模型 + 一句定位）给用户看。
2. 按意图推荐默认：商业/产品图 → `wan2.7-image-pro`；图内文字多 → `qwen-image-2.0-pro`；省额度草稿 → `wan2.7-image`。
3. 持久化：`set-model --image <model>`。以后想换：同命令。单次试：生成命令加 `--model <model>`（不持久）。
4. 完成判定：`show-config` 打出所选图片模型。

## 打磨 brief（核心体验，别拿一句话直接去生成）

先补齐这五个槽位；能从请求推断的就填上并一句话声明假设，推断不了且猜错会浪费生成时才问（最多问 2 个）：

1. **主体** —— 是什么 + 什么状态（产品+材质/状态；人物+姿势；场景+焦点元素）。
2. **用途与画幅** —— 广告/海报/图标/壁纸 决定 size（见下表）。
3. **风格** —— 摄影/插画/3D/扁平矢量/水墨……
4. **光线与色彩** —— 具名光线 + 具名颜色，胜过形容词。
5. **图内文字** —— 逐字保留（用引号），或确认「不加字」。

- 模糊请求（「来张好看的」「随便」）→ 给 3 个方向（主体+风格+配色，每个一行），让用户挑；选完再补其余槽位。
- 完成判定：五槽位收敛成最终 prompt + size。

size —— 默认 `2048x2048`；16:9 `2720x1536`；9:16 `1536x2720`；4:3 `2304x1728`；3:4 `1728x2304`。

需求模糊或用户要更好效果 → 先读 `references/prompt-guide.md`（配方与词库在那）。

## 生成

```bash
python "<skill-dir>/scripts/gen_media.py" image --prompt "<prompt>" --size "<宽x高>"
```

回报每个文件的绝对路径 + 最终 prompt，方便「再来一版……」精确迭代。文件本地存在前不许声称成功。

## 迭代

交付后给一个具体的下一版方向（配色/角度/变体）。神图到手 → 建议用 gen-video 让它动起来。

## 规则

- 只用自带脚本，不临时拼 curl。
- 完整 API Key 绝不写进项目目录；回复里只用掩码，不复述完整 Key。
- 默认存当前工作目录，除非用户指定输出目录。

## 更新

用户要更新 gen-media → 走宿主的插件/技能更新机制（Claude Code：`/plugin update gen-media`；Codex/WorkBuddy：拉仓库重拷 skill 文件夹）。配置在 `~/.gen-media/config.json`，skill 目录之外，更新不影响。
