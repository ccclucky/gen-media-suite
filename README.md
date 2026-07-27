# Gen Media Suite

一个插件包，两个标准 skill（`gen-image` / `gen-video`），通过每位用户自己的 New API 网关生成并下载图片和文生视频。

- 生图模型：`wan2.7-image-pro`
- 文生视频模型：`happyhorse-1.1-t2v`
- 脚本纯 Python 标准库，无第三方依赖

## 仓库结构

```text
gen-media-suite/
  .claude-plugin/marketplace.json     # Claude Code 市场入口
  .agents/plugins/marketplace.json    # 通用 agents 市场入口（WorkBuddy 等）
  plugins/gen-media/
    .claude-plugin/plugin.json        # Claude Code 插件清单
    .codex-plugin/plugin.json         # Codex 插件清单
    skills/
      gen-image/                      # 标准 SKILL.md，可移植到任何支持 Agent Skills 的宿主
      gen-video/
```

每个 skill 文件夹自包含（SKILL.md + scripts/ + references/），可直接拷入任何 agent 的 skills 目录。

## 安装

### Claude Code

```text
/plugin marketplace add CCLUCKY/gen-media-suite
/plugin install gen-media
```

### Codex

仓库自带 `.codex-plugin/plugin.json`。若客户端版本不支持插件安装命令，用目录复制兜底（与 source-scout 同款做法）：

```powershell
git clone https://github.com/CCLUCKY/gen-media-suite.git
Copy-Item -Recurse gen-media-suite/plugins/gen-media/skills/gen-image $HOME/.codex/skills/gen-image
Copy-Item -Recurse gen-media-suite/plugins/gen-media/skills/gen-video $HOME/.codex/skills/gen-video
```

macOS / Linux 同理，目标目录为 `~/.codex/skills/`。新建任务或重载 skills 后生效。

### WorkBuddy

在 WorkBuddy 中贴仓库 URL（`https://github.com/CCLUCKY/gen-media-suite`）并说"装这个 skill"，其内置 install-github-skills 会先做安全审计再安装。或手动拷入 `~/.workbuddy/skills/`。

### Cursor

Cursor 暂无 skill 系统。把 `plugins/gen-media/skills/gen-image/SKILL.md` 的正文内容复制为 `.cursor/rules/gen-image.mdc`（gen-video 同理），脚本路径改为 skill 文件夹的绝对路径。

## 凭证配置（一次性，所有 agent 共用）

首次使用时 agent 会自动引导。手动配置：

```bash
python <skill目录>/scripts/gen_media.py configure --base-url "https://你的NewAPI地址"
```

API Key 通过隐藏输入提示录入，不进命令行历史、不进聊天记录。配置保存在：

- Windows：`%USERPROFILE%\.gen-media\config.json`
- macOS / Linux：`~/.gen-media/config.json`

该文件权限 600，不在任何项目目录内，不进 Git。企业 / CI 环境可用环境变量覆盖：`GEN_MEDIA_BASE_URL`、`GEN_MEDIA_API_KEY`。

其他命令：`show-config`（查看掩码配置）、`reset-config`（清除配置）、`version`。

## 模型选择（一次设置，随时切换）

模型目录来自阿里云百炼 Token Plan 团队版：

| 模型                 | 类型             | 定位                 |
| -------------------- | ---------------- | -------------------- |
| `wan2.7-image-pro`   | 图片（默认）     | 商业级画质           |
| `wan2.7-image`       | 图片             | 标准画质，省 Credits |
| `qwen-image-2.0-pro` | 图片             | 图内文字渲染强       |
| `qwen-image-2.0`     | 图片             | 轻量快速             |
| `happyhorse-1.1-t2v` | 文生视频（默认） | 文本生成视频         |

`happyhorse-1.1-i2v`（图生视频）/ `happyhorse-1.1-r2v`（参考生视频）需要图片输入，当前 skill 只走文本管线，脚本会拒绝并提示。

```bash
python <skill目录>/scripts/gen_media.py list-models          # 查看目录与当前选择
python <skill目录>/scripts/gen_media.py set-model --image qwen-image-2.0-pro   # 持久切换
```

选择写入同一份 `config.json`，所有 agent 共用。单次试验可在生成命令上加 `--model <model>`，不影响持久配置。私有网关的自定义模型也可直接传给 `set-model`（不在目录内会给出警告但照常保存）。

## 使用

```text
生成一张红金配色的能量饮料商业广告图，16:9
```

```text
生成一个 5 秒视频：一瓶饮料从冰块中升起，电影级广告镜头
```

skill 会先把需求打磨成生产级 prompt（图片补构图/光线/风格，视频补镜头运动/时间线节拍），视频提交前需用户确认 brief。

## 更新

- Claude Code：`/plugin update gen-media`
- Codex / WorkBuddy：`git -C gen-media-suite pull` 后重新复制 skill 文件夹（先删旧目录再拷，避免残留文件）

凭证配置在 skill 目录之外，更新不受影响。
