# Now Playing → Discord Rich Presence

把 [Now Playing](https://github.com/Widdit/now-playing-service) 的正在播放信息推送到 Discord 个人资料：
歌名、歌手、专辑封面、实时进度条，鼠标悬停封面还能看到滚动歌词。

支持 **网易云音乐 / QQ音乐 / 酷狗音乐 / 酷我音乐 / 汽水音乐 / 全民K歌** 六个国内平台，
会根据 Now Playing 当前检测的平台自动切换对应的 Discord Application。

> **声明**：本项目是第三方工具，仅通过 Now Playing 提供的本地 API（`http://localhost:9863`）
> 读取播放信息。项目与 Now Playing 作者无隶属关系，也未获官方背书；「Now Playing」名称与
> 图标归其作者所有，本项目仅作描述性说明。

## 特性

- **多平台**：按平台自动切换 Discord 应用，状态栏能正确显示「正在听 网易云音乐 / QQ音乐 / …」
- **进度条**：交给 Discord 自行渲染，无需高频刷新
- **暂停不消失**：暂停时保留当前歌曲卡片，进度条冻结（而不是掉回「正在听 XXX」）
- **切歌无空档**：一首歌结束到下一首开始之间保持上一首卡片，不闪现空状态
- **封面容错**：新歌封面尚未就绪时先出卡片，几秒内自动补齐；超过时限则回退为应用图标，不会挂着上一首的错误封面
- **歌词悬停**：读取 LRC 并按毫秒进度匹配，悬停封面显示当前歌词
- **无控制台运行**：提供隐藏窗口启动器，并自动把日志写入文件

## 环境要求

- Windows 10 / 11
- Python 3.9+
- Now Playing 正在运行（默认 `http://localhost:9863`）
- Discord 桌面客户端已登录

```bash
pip install pypresence requests
```

## Discord Application 配置

Discord 状态栏里「正在听 XXX」的 XXX 来自 Application 的**名称**，无法动态修改，
所以需要给每个平台各建一个 Application：

1. 打开 [Discord Developer Portal](https://discord.com/developers/applications)，点击 **New Application**；
2. 名称填你想显示的平台名（例如 `网易云音乐`、`QQ音乐`），可顺便在 **General Information** 上传图标；
3. 复制 **Application ID**，填入 `ncm_rpc.py` 顶部 `PLATFORM_CLIENT_IDS` 对应的位置：
   ```python
   PLATFORM_CLIENT_IDS = {
       "netease": "你的网易云应用ID",
       "qq":      "你的QQ音乐应用ID",
       "kugou":   "你的酷狗应用ID",
       "kuwo":    "你的酷我应用ID",
       "soda":    "你的汽水应用ID",
       "wesing":  "你的全民K歌应用ID",
   }
   DEFAULT_CLIENT_ID = "兜底应用ID"   # 未单独配置的平台会用它
   ```
4. 只配一个也可以：把 ID 填到 `DEFAULT_CLIENT_ID`，所有平台都会显示同一个名字。

## 使用

| 文件 | 作用 |
|---|---|
| `start_ncm.vbs` | 静默启动（隐藏窗口，等待 20 秒让 Discord / Now Playing 就绪，带单实例保护） |
| `stop_ncm.cmd` | 停止正在运行的实例 |
| `view_log.cmd` | 实时查看今日日志 |
| `install_autostart.vbs` | 安装开机自启（写入当前用户启动文件夹，无需管理员） |
| `uninstall_autostart.vbs` | 取消开机自启 |
| `logs/` | 日志目录（仅无控制台运行时生成），按日期分文件 |

调试时也可以直接 `python ncm_rpc.py`，此时输出到控制台、不写日志文件。

## 配置项

| 配置项 | 默认 | 说明 |
|---|---|---|
| `BASE_URL` | `http://localhost:9863` | Now Playing 服务地址 |
| `SHOW_LYRIC_ON_HOVER` | `True` | 悬停显示歌词；`False` 则显示专辑名 |
| `NO_LYRIC_HOVER_TEXT` | `"纯音乐，请欣赏"` | 歌词功能开启但该歌曲无歌词（如纯音乐）时的悬停文案；留空 `""` 则回退显示专辑名 |
| `COVER_WAIT_TIMEOUT_SEC` | `10` | 封面等待上限（秒），超时回退为应用图标 |
| `FALLBACK_COVER_ASSET` | `""` | 可选：Art Assets 兜底大图名称，留空则只显示应用图标 |
| `GAP_MAX_HOLD_SEC` | `1800` | 切歌空档最多保留上一首卡片多久（秒），`0` = 永不超时 |
| `SWITCH_GRACE_SEC` | `3.0` | 状态检测防抖时间（秒） |
| `PLATFORM_REFRESH_SEC` | `30` | 轮询当前平台的间隔（秒） |
| `ENABLE_FILE_LOG` | `True` | 无控制台运行时是否写日志 |

## 已知限制

- 封面和歌曲信息由 Now Playing 提供，若上游在整首歌生命周期内都没取到封面，本工具只能回退为应用图标，无法凭空生成正确封面；
- Discord 对 Rich Presence 更新有频率限制（约每 20 秒 5 次），歌词悬停的刷新频率受此约束；
- 只处理标准 LRC 歌词，不支持一行多时间标签或逐字歌词。

## 致谢

- [Widdit/now-playing-service](https://github.com/Widdit/now-playing-service) — 提供歌曲信息与歌词 API
- [Widdit/now-playing-frontend](https://github.com/Widdit/now-playing-frontend) — Now Playing 前端
- [pypresence](https://github.com/qwertyquerty/pypresence) — Discord IPC 封装

## 许可证

本项目基于 [MIT License](LICENSE) 开源，可自由使用、修改与分发。
