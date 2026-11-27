import os
import re
import sys
import time
import requests
from pypresence import Presence

# ==================== 配置区 ====================
BASE_URL = "http://localhost:9863"
SHOW_LYRIC_ON_HOVER = True   # True: 悬停封面显示实时歌词; False: 显示专辑名
NO_LYRIC_HOVER_TEXT = "纯音乐，请欣赏"  # 歌词功能开启但该歌曲无歌词时的悬停文案；留空 "" 则回退显示专辑名
SWITCH_GRACE_SEC = 3.0       # 切歌/状态检测防抖缓冲时间（秒），缓冲期内的状态波动直接忽略
GAP_MAX_HOLD_SEC = 1800      # 切歌空档最多保留上一首卡片多久（秒），超时降级为仅显示应用名；0 = 永不超时
PLATFORM_REFRESH_SEC = 30    # 轮询 /api/settings/general 检测当前平台的间隔（秒）
COVER_WAIT_TIMEOUT_SEC = 10  # 新歌封面等待时限（秒）：超时仍未就绪就回退为默认图标，避免错误封面久留
FALLBACK_COVER_ASSET = ""    # 可选：在 Developer Portal 的 Rich Presence Art Assets 里上传兜底大图后填其名称；留空则只显示应用图标
PLACEHOLDER_COVER_KEYS = ("spotify_no_cover", "no_cover")  # 后端兜底占位图的 URL 关键字，命中即视为无效封面
ENABLE_FILE_LOG = True       # 无控制台运行（pythonw/.vbs 隐藏启动）时，把输出写入 logs 目录，便于排查问题
LOG_DIR_NAME = "logs"        # 日志目录名（位于脚本所在目录）

# Discord Application 的 Client ID 按平台填写。
# 使用方法：在 https://discord.com/developers/applications 为每个平台各创建一个 Application，
# Application 的 Name 会直接显示为 Discord 状态栏上的“正在听 XXX”，
# 然后把各应用的 Application ID 填入下表。未填写的平台会回退到 DEFAULT_CLIENT_ID。
PLATFORM_CLIENT_IDS = {
    "netease": "",   # 网易云音乐
    "qq": "",        # QQ音乐
    "kugou": "",     # 酷狗音乐
    "kuwo": "",      # 酷我音乐
    "soda": "",      # 汽水音乐
    "wesing": "",    # 全民K歌
}
DEFAULT_CLIENT_ID = ""  # 兜底 Application（如原来的“网易云音乐”应用）

# 平台标识 -> 中文展示名（日志用）
PLATFORM_NAMES = {
    "netease": "网易云音乐",
    "qq": "QQ音乐",
    "kugou": "酷狗音乐",
    "kuwo": "酷我音乐",
    "soda": "汽水音乐",
    "wesing": "全民K歌",
}
# ================================================


def setup_file_logging():
    """无控制台启动（pythonw 等）时把输出重定向到日志文件。

    pythonw 下 sys.stdout / sys.stderr 均为 None，print 的内容会被直接丢弃，
    出错时无从排查。这里改为按日期写入 logs 目录，console 运行方式不受影响。
    """
    if not ENABLE_FILE_LOG or sys.stdout is not None:
        return None
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base_dir, LOG_DIR_NAME)
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, time.strftime("ncm_rpc-%Y%m%d.log"))
        # buffering=1 即行缓冲，保证日志可实时 tail，且进程被强杀时不至于丢太多
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
        print(f"\n===== 启动 {time.strftime('%Y-%m-%d %H:%M:%S')} =====")
        return log_file
    except Exception:
        # 日志初始化失败不应影响主功能，退回静默
        return None


def parse_lrc(lrc_text: str):
    if not lrc_text:
        return []
    pattern = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)")
    lines = []
    for line in lrc_text.splitlines():
        m = pattern.match(line.strip())
        if m:
            mins, secs, ms_str, text = m.groups()
            text = text.strip()
            if not text:
                continue
            ms = int(ms_str) * (10 if len(ms_str) == 2 else 1)
            total_ms = (int(mins) * 60 + int(secs)) * 1000 + ms
            lines.append((total_ms, text))
    lines.sort(key=lambda x: x[0])
    return lines


def get_current_lyric(lrc_lines, pos_ms: int) -> str:
    current = ""
    for ts, text in lrc_lines:
        if pos_ms >= ts:
            current = text
        else:
            break
    return current


def clamp_field(value, fallback: str, min_len: int = 2, max_len: int = 128) -> str:
    """Discord 要求 details/state 非空且至少 2 个字符，空值或过短时用占位文案兜底"""
    text = str(value).strip() if value is not None else ""
    if len(text) < min_len:
        text = fallback
    return text[:max_len]


def connect_discord(client_id: str):
    while True:
        try:
            rpc = Presence(client_id)
            rpc.connect()
            print(f"[OK] 已成功连接至 Discord 客户端 (Client ID: {client_id})")
            return rpc
        except Exception as e:
            print(f"[等待] 未检测到 Discord 客户端 ({e})，3秒后重试...")
            time.sleep(3)


def check_player_connected() -> bool:
    """调用 /api/query/isConnected 检测播放器是否已打开"""
    try:
        res = requests.get(f"{BASE_URL}/api/query/isConnected", timeout=1.5).json()
        return bool(res.get("data", False))
    except Exception:
        return False


def detect_platform() -> str:
    """调用 /api/settings/general 读取当前检测平台，失败时返回空字符串"""
    try:
        res = requests.get(f"{BASE_URL}/api/settings/general", timeout=2).json()
        platform = res.get("platform", "")
        if isinstance(platform, str):
            return platform.strip()
    except Exception:
        pass
    return ""


def resolve_client_id(platform: str) -> str:
    """根据平台返回对应的 Client ID，未配置则回退到默认应用"""
    cid = PLATFORM_CLIENT_IDS.get(platform, "")
    return cid if cid else DEFAULT_CLIENT_ID


def cover_is_usable(cover: str, prev_cover: str, prev_album: str, album: str) -> bool:
    """判断封面 URL 是否可用于展示。

    过滤四类无效封面：
      1. 空值或非 http(s) 地址；
      2. 超出 Discord 长度限制的地址；
      3. 后端兜底占位图（如 spotify_no_cover.jpg）；
      4. 与上一首完全相同、但专辑名已经变化——说明是上一首残留的旧封面。
    """
    if not cover or not isinstance(cover, str):
        return False
    if not cover.startswith(("http://", "https://")) or len(cover) > 256:
        return False
    lowered = cover.lower()
    if any(key in lowered for key in PLACEHOLDER_COVER_KEYS):
        return False
    if prev_cover and cover == prev_cover and album != prev_album:
        return False
    return True


class RpcManager:
    """按平台管理 Discord Presence 连接，平台变化时热切换"""

    def __init__(self, initial_platform: str):
        self.platform = initial_platform
        self.client_id = resolve_client_id(initial_platform)
        self.rpc = connect_discord(self.client_id)

    def switch_if_needed(self, platform: str) -> bool:
        """平台对应的 Client ID 变化时，断开旧连接并用新应用重连。返回是否发生了重连"""
        if not platform or platform == self.platform:
            return False
        new_client_id = resolve_client_id(platform)
        if new_client_id == self.client_id:
            # 同一应用覆盖多个平台（例如没配置新平台回退默认），只记录平台即可
            self.platform = platform
            return False
        print(f"[切换] 平台变化: {PLATFORM_NAMES.get(self.platform, self.platform)} "
              f"-> {PLATFORM_NAMES.get(platform, platform)}，重新连接 Discord 应用...")
        try:
            self.rpc.clear()
            self.rpc.close()
        except Exception:
            pass
        self.platform = platform
        self.client_id = new_client_id
        self.rpc = connect_discord(new_client_id)
        return True

    def reconnect(self):
        """Discord IPC 异常断开后的重连（沿用当前 Client ID）"""
        try:
            self.rpc.close()
        except Exception:
            pass
        self.rpc = connect_discord(self.client_id)

    def update(self, **kwargs):
        self.rpc.update(**kwargs)

    def clear(self):
        self.rpc.clear()


def main():
    setup_file_logging()

    try:
        from pypresence.types import ActivityType
        extra_kwargs = {"activity_type": ActivityType.LISTENING}
    except Exception:
        extra_kwargs = {}

    # 首次先探测平台，再连接对应的 Discord 应用
    platform = detect_platform()
    if platform:
        print(f"[信息] 当前平台: {PLATFORM_NAMES.get(platform, platform)}")

    # 未配置任何 Client ID 时给出明确提示，否则只会一直卡在“等待 Discord 客户端”
    if not resolve_client_id(platform):
        print("[错误] 尚未配置 Discord Application ID。")
        print("       请编辑本文件顶部 PLATFORM_CLIENT_IDS / DEFAULT_CLIENT_ID 后重新启动。")
        print("       创建方法见 README.md 的「Discord Application 配置」一节。")
        return

    rpc_mgr = RpcManager(platform)

    # 状态记录：
    # 'NONE'(无状态/播放器关闭) | 'IDLE'(仅显示应用名) | 'PLAYING'(完整卡片+进度条)
    # 'PAUSED'(暂停：冻结的完整卡片) | 'GAP'(切歌空档：保留上一首冻结卡片)
    current_mode = "NONE"
    last_song_id = None
    lyric_song_id = None     # 当前 cached_lrc 所属歌曲的 id，与卡片状态解耦，防止暂停切歌后歌词不刷新
    expected_start_ts = 0
    cached_lrc = []
    pause_since = None      # 进入暂停/切歌空档的时间戳（防抖用）
    gap_since = None        # 进入 GAP 的时间戳（30 分钟兜底用）
    last_card_payload = None  # 最近一次完整卡片参数，进入空档时用于冻结重发
    last_platform_check = 0.0
    # 封面状态：'ready'(可用) | 'waiting'(等待就绪) | 'fallback'(已回退默认图标)
    cover_mode = "ready"
    cover_pending_since = None  # 开始等待当前歌曲封面的时间戳
    cover_eval_song = None      # 已校验过封面的歌曲 id
    last_good_cover = ""        # 上一首确认可用的封面，用于识别残留
    last_album = ""             # 上一首专辑名，用于识别残留

    while True:
        try:
            # 0. 低频刷新当前平台，变化时热切换 Discord 应用
            if time.time() - last_platform_check >= PLATFORM_REFRESH_SEC:
                new_platform = detect_platform()
                if new_platform:
                    if new_platform != platform:
                        print(f"[信息] 平台切换为: {PLATFORM_NAMES.get(new_platform, new_platform)}")
                    platform = new_platform
                    if rpc_mgr.switch_if_needed(platform):
                        # 新 IPC 连接上没有旧卡片，重置状态机，本轮按当前播放状态强制重发
                        current_mode = "NONE"
                        last_song_id = None
                        lyric_song_id = None
                        pause_since = None
                        gap_since = None
                last_platform_check = time.time()

            # 1. 先检查播放器是否打开
            if not check_player_connected():
                if current_mode != "NONE":
                    rpc_mgr.clear()
                    current_mode = "NONE"
                    last_song_id = None
                    lyric_song_id = None
                    pause_since = None
                    gap_since = None
                    print("[状态] 播放器已关闭，清除 Discord 状态")
                time.sleep(2)
                continue

            # 2. 获取播放器与歌曲状态
            resp = requests.get(f"{BASE_URL}/api/query", timeout=2).json()
            player = resp.get("player", {})
            track = resp.get("track", {})

            has_song = player.get("hasSong", False)
            is_paused = player.get("isPaused", True)
            title = track.get("title", "")
            # 不再要求 title 非空：空标题由 clamp_field 兜底，避免纯音乐/异常数据整张卡片发不出去
            is_playing = has_song and (not is_paused)

            # 3. 情况 A：正在播放歌曲
            if is_playing:
                pause_since = None  # 重置暂停计时
                gap_since = None    # 重置空档计时
                song_id = str(track.get("id", ""))
                author = track.get("author", "未知歌手")
                album = track.get("album", "")
                cover = track.get("cover", "")
                duration = int(track.get("duration", 0))
                pos_sec = int(player.get("seekbarCurrentPosition", 0))

                if song_id != lyric_song_id and SHOW_LYRIC_ON_HOVER:
                    try:
                        lrc_resp = requests.get(f"{BASE_URL}/api/lyric", timeout=2).json()
                        cached_lrc = parse_lrc(lrc_resp.get("lrc", "")) if lrc_resp.get("hasLyric") else []
                    except Exception:
                        cached_lrc = []
                    # 无论成功与否都标记，避免同一首歌反复请求；切歌后 lyric_song_id 变化会重新拉取
                    lyric_song_id = song_id

                now = int(time.time())
                calc_start_ts = now - pos_sec

                # ---- 封面就绪检测（策略 1：卡片先出，封面后补；超时回退默认图标）----
                song_changed = song_id != last_song_id
                prev_cover_mode = cover_mode
                if song_id != cover_eval_song:
                    # 新歌（含暂停状态下切歌后恢复播放）：用上一首的封面/专辑做残留比对
                    cover_eval_song = song_id
                    if cover_is_usable(cover, last_good_cover, last_album, album):
                        cover_mode = "ready"
                        cover_pending_since = None
                        last_good_cover = cover
                        last_album = album
                    else:
                        cover_mode = "waiting"
                        cover_pending_since = now
                        print(f"[封面] 封面尚未就绪，先显示歌曲卡片，稍后自动补齐: {title}")
                elif cover_mode == "waiting":
                    # 等待期间继续用「上一首」的基线比对，避免旧封面被误判为合法
                    if cover_is_usable(cover, last_good_cover, last_album, album):
                        cover_mode = "ready"
                        cover_pending_since = None
                        last_good_cover = cover
                        last_album = album
                        print(f"[封面] 封面已补齐: {title}")
                    elif cover_pending_since and now - cover_pending_since >= COVER_WAIT_TIMEOUT_SEC:
                        cover_mode = "fallback"
                        cover_pending_since = None
                        last_album = album
                        print(f"[封面] 等待 {COVER_WAIT_TIMEOUT_SEC} 秒仍未就绪，回退为默认图标: {title}")

                need_update = (
                    current_mode != "PLAYING"
                    or song_changed
                    or cover_mode != prev_cover_mode
                    or abs(calc_start_ts - expected_start_ts) > 2
                )

                hover_text = album
                if SHOW_LYRIC_ON_HOVER and cached_lrc:
                    try:
                        prog_resp = requests.get(f"{BASE_URL}/api/query/progress", timeout=1).json()
                        pos_ms = int(prog_resp.get("progress", pos_sec * 1000))
                    except Exception:
                        pos_ms = pos_sec * 1000
                    lyric_line = get_current_lyric(cached_lrc, pos_ms)
                    if lyric_line:
                        hover_text = f"♪ {lyric_line}"
                elif SHOW_LYRIC_ON_HOVER and not cached_lrc and NO_LYRIC_HOVER_TEXT.strip():
                    # 无歌词（如纯音乐）：显示固定文案；配置留空则沿用专辑名
                    hover_text = NO_LYRIC_HOVER_TEXT.strip()

                if need_update or (SHOW_LYRIC_ON_HOVER and cached_lrc):
                    payload = {
                        "details": clamp_field(title, "未知歌曲"),
                        "state": clamp_field(author, "未知歌手"),
                        **extra_kwargs,
                    }
                    # 封面未就绪/已回退时不下发 large_image，避免 Discord 继续沿用上一首的封面
                    if cover_mode == "ready":
                        payload["large_image"] = cover
                    elif FALLBACK_COVER_ASSET:
                        payload["large_image"] = FALLBACK_COVER_ASSET
                    if hover_text:
                        payload["large_text"] = hover_text[:128]
                    # 仅在播放中下发 start/end，由 Discord 渲染走动的进度条
                    if duration > 0:
                        payload["start"] = calc_start_ts
                        payload["end"] = calc_start_ts + duration

                    rpc_mgr.update(**payload)
                    last_card_payload = dict(payload)

                    if song_id != last_song_id or current_mode != "PLAYING":
                        print(f"[同步] 正在播放: {title} - {author}")

                    current_mode = "PLAYING"
                    last_song_id = song_id
                    expected_start_ts = calc_start_ts

            # 4. 情况 B：播放器开着，但当前没在播放
            else:
                # 4.1 手动暂停：hasSong=True，保留完整卡片但冻结进度条
                if has_song:
                    if current_mode == "PLAYING":
                        # 防抖：刚从播放停下来，缓冲期内先不更新，避免检测抖动导致闪烁
                        if pause_since is None:
                            pause_since = time.time()
                        if time.time() - pause_since < SWITCH_GRACE_SEC:
                            time.sleep(0.8)
                            continue

                    paused_song_id = str(track.get("id", ""))
                    # 暂停状态下也可能切歌（暂停时点下一首），歌曲变化时需重建冻结卡片
                    if current_mode != "PAUSED" or paused_song_id != last_song_id:
                        payload = {
                            "details": clamp_field(title, "未知歌曲"),
                            "state": clamp_field(track.get("author", ""), "未知歌手"),
                            **extra_kwargs,
                        }
                        # 仅使用已确认可用的封面，避免把上一首的残留封面带上卡片
                        paused_cover = track.get("cover", "")
                        if paused_cover and paused_cover == last_good_cover:
                            payload["large_image"] = paused_cover
                        elif FALLBACK_COVER_ASSET:
                            payload["large_image"] = FALLBACK_COVER_ASSET
                        # 悬停文本：暂停标识 + 专辑名（暂停后歌词冻结，不再逐秒刷新）
                        hover_text = track.get("album", "")
                        if hover_text:
                            payload["large_text"] = f"⏸ {hover_text}"[:128]
                        # 注意：不传 start/end，进度条冻结、不再继续走动
                        rpc_mgr.update(**payload)
                        last_card_payload = dict(payload)
                        last_song_id = paused_song_id
                        # 恢复播放时要按新歌重新校验封面，避免用错误的图
                        cover_eval_song = None
                        current_mode = "PAUSED"
                        print("[状态] 已暂停，保留当前歌曲卡片（进度条已冻结）")

                # 4.2 切歌空档：hasSong=False，保持上一首卡片，直到下一首开始
                else:
                    if current_mode in ("PLAYING", "PAUSED"):
                        # 防抖：缓冲期内当作检测抖动，继续保持当前卡片
                        if pause_since is None:
                            pause_since = time.time()
                        if time.time() - pause_since < SWITCH_GRACE_SEC:
                            time.sleep(0.8)
                            continue
                        # 确认进入真实空档：重发一次去掉 start/end 的上一首卡片，
                        # 让进度条精确冻结在当前位置，内容原样保留直到下一首开始
                        if gap_since is None:
                            gap_since = time.time()
                            if last_card_payload:
                                frozen = {k: v for k, v in last_card_payload.items()
                                          if k not in ("start", "end")}
                                rpc_mgr.update(**frozen)
                            current_mode = "GAP"
                            print("[状态] 切歌空档，保持上一首歌曲卡片（进度条已冻结）")

                    if current_mode == "GAP":
                        # 持续空档：仅检查兜底超时，卡片继续保留，等下一首 PLAYING 直接替换
                        if GAP_MAX_HOLD_SEC > 0 and gap_since and \
                                time.time() - gap_since > GAP_MAX_HOLD_SEC:
                            rpc_mgr.update(**extra_kwargs)
                            current_mode = "IDLE"
                            last_song_id = None
                            lyric_song_id = None
                            gap_since = None
                            print("[状态] 空档超过保留时限，降级为仅显示播放器名称")
                    elif current_mode not in ("PLAYING", "PAUSED"):
                        # NONE / IDLE：播放器刚打开还没播过歌，只显示应用名
                        if current_mode != "IDLE":
                            rpc_mgr.update(**extra_kwargs)
                            current_mode = "IDLE"
                            last_song_id = None
                            lyric_song_id = None
                            print("[状态] 播放器已打开（空闲/待机），仅显示播放器名称")

        except requests.exceptions.RequestException:
            if current_mode != "NONE":
                try:
                    rpc_mgr.clear()
                except Exception:
                    pass
                current_mode = "NONE"
                last_song_id = None
                lyric_song_id = None
                pause_since = None
                gap_since = None
            print("[等待] Now Playing 服务未响应，2秒后重试...")
        except Exception as e:
            print(f"[异常] {e}，尝试重新连接 Discord...")
            current_mode = "NONE"
            last_song_id = None
            lyric_song_id = None
            pause_since = None
            gap_since = None
            rpc_mgr.reconnect()

        time.sleep(1.2)


if __name__ == "__main__":
    main()
