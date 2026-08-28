# -*- coding: utf-8 -*-
"""
키매크로 - 키 연타 + 좌클릭 꾹 누르기 + 자동 꾹누름 반복 매크로
- F1 = ① 연타,  F2 = ② 좌클릭 꾹누름,  F3 = ③ 자동 꾹누름 반복
- 각 매크로는 체크박스로 개별 활성/비활성
- ③: 특정 키를 설정 시간만큼 눌렀다 떼기를 종료까지 반복
- 관리자 권한 기본 실행
순수 표준 라이브러리(ctypes + tkinter)만 사용
"""

import os
import sys
import json
import time
import queue
import threading
import ctypes
from ctypes import wintypes

import tkinter as tk
from tkinter import ttk, messagebox

# ---------------------------------------------------------------------------
# 관리자 권한 확보 (빌드 시 --uac-admin 매니페스트가 우선, 아래는 .py 실행 시 보조)
# ---------------------------------------------------------------------------
def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def ensure_admin():
    if is_admin():
        return
    if os.environ.get("KEYMACRO_NO_ELEVATE") == "1":
        return
    try:
        if getattr(sys, "frozen", False):
            exe = sys.executable
            params = ""
        else:
            exe = sys.executable
            params = '"%s"' % os.path.abspath(__file__)
        # ShellExecuteW 로 관리자 권한 재실행 (runas)
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        if ret > 32:
            sys.exit(0)  # 새 관리자 프로세스가 떴으므로 현재 프로세스 종료
        # ret <= 32 : 사용자가 거부/실패 -> 비관리자 상태로 계속 진행
    except Exception:
        pass

ensure_admin()

# ---------------------------------------------------------------------------
# Win32 API (ctypes)
# ---------------------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)

ULONG_PTR = ctypes.wintypes.WPARAM

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]

class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC = 0

VK_LBUTTON = 0x01
VK_F1 = 0x70    # ① 연타 매크로 켜기/끄기
VK_F2 = 0x71    # ② 꾹누름 매크로 켜기/끄기
VK_F3 = 0x72    # ③ 자동 꾹누름 반복 매크로 켜기/끄기
VK_PGUP = 0x21  # 꾹누름 시간 +0.0001
VK_PGDN = 0x22  # 꾹누름 시간 -0.0001

# 확장 스캔코드가 필요한 VK 목록
EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,  # PgUp/PgDn/End/Home/방향키
    0x2D, 0x2E,                                        # Insert/Delete
    0x2C,                                              # PrintScreen
    0x90,                                              # NumLock
    0xA3, 0xA5,                                        # RControl/RMenu
    0x6F,                                              # Numpad Divide
    0x5B, 0x5C, 0x5D,                                  # LWin/RWin/Apps
}

# VK -> 표시 이름
VK_NAMES = {
    0x01: "좌클릭", 0x02: "우클릭", 0x04: "휠클릭",
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter",
    0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt", 0x13: "Pause",
    0x14: "CapsLock", 0x1B: "Esc", 0x20: "Space",
    0x21: "PgUp", 0x22: "PgDn", 0x23: "End", 0x24: "Home",
    0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2C: "PrtSc", 0x2D: "Insert", 0x2E: "Delete",
    0x5B: "LWin", 0x5C: "RWin", 0x5D: "Apps",
    0x90: "NumLock", 0x91: "ScrollLock",
    0xA0: "LShift", 0xA1: "RShift", 0xA2: "LCtrl", 0xA3: "RCtrl",
    0xA4: "LAlt", 0xA5: "RAlt",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/",
    0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
}
for i in range(0x30, 0x3A):      # 0-9
    VK_NAMES.setdefault(i, chr(i))
for i in range(0x41, 0x5B):      # A-Z
    VK_NAMES.setdefault(i, chr(i))
for i in range(0x70, 0x88):      # F1-F24
    VK_NAMES.setdefault(i, "F%d" % (i - 0x6F))
for i in range(0x60, 0x6A):      # Numpad 0-9
    VK_NAMES.setdefault(i, "Num%d" % (i - 0x60))
VK_NAMES[0x6A] = "Num*"; VK_NAMES[0x6B] = "Num+"
VK_NAMES[0x6D] = "Num-"; VK_NAMES[0x6E] = "Num."; VK_NAMES[0x6F] = "Num/"

def vk_name(vk):
    return VK_NAMES.get(vk, "VK_%d" % vk)

def scan_for_vk(vk):
    return user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)

def is_pressed(vk):
    return (user32.GetAsyncKeyState(vk) & 0x8000) != 0

def send_key(vk, scan, ext, up):
    """스캔코드가 있으면 스캔코드로, 없으면 VK로 키 이벤트 전송"""
    if scan:
        flags = KEYEVENTF_SCANCODE
        if ext:
            flags |= KEYEVENTF_EXTENDEDKEY
        if up:
            flags |= KEYEVENTF_KEYUP
        ki = KEYBDINPUT(0, scan, flags, 0, 0)
    else:
        flags = 0
        if up:
            flags |= KEYEVENTF_KEYUP
        ki = KEYBDINPUT(vk, 0, flags, 0, 0)
    inp = INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=ki))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def tap_key(vk, scan, ext, hold_ms=0):
    """키를 눌렀다 뗌. hold_ms 만큼 눌린 상태를 유지해야
    게임/프로그램이 입력을 놓치지 않음."""
    send_key(vk, scan, ext, False)
    if hold_ms > 0:
        time.sleep(hold_ms / 1000.0)
    send_key(vk, scan, ext, True)

# ---------------------------------------------------------------------------
# 설정 저장/로드
# ---------------------------------------------------------------------------
def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(base_dir(), "config.json")

DEFAULT_CONFIG = {
    # 연타 매크로
    "spam_enabled": True,
    "spam_vk": 84, "spam_scan": 20, "spam_ext": False, "spam_name": "T",
    "toggle_vk": 81, "toggle_scan": 16, "toggle_ext": False, "toggle_name": "Q",
    "rate": 7.0,
    "mode": "hold",          # "toggle" | "hold"
    # 좌클릭 꾹 누르기 매크로
    "hold_enabled": False,
    "hold_seconds": 1.5,
    "hold_vk": 82, "hold_scan": 19, "hold_ext": False, "hold_name": "R",
    "hold_adjust_enabled": False,   # PgUp/PgDn 로 꾹누름 시간 ±0.0001 조절
    "press_ms": 50,          # 키를 눌린 상태로 유지하는 시간(ms) - 게임 인식률용
    # 자동 꾹누름 반복 매크로 (특정 키를 설정 시간만큼 누르고 떼기를 반복)
    "hold3_enabled": False,
    "hold3_seconds": 3.8,
    "hold3_vk": 81, "hold3_scan": 16, "hold3_ext": False, "hold3_name": "Q",
    # 매크로별 켜기/끄기 단축키: ①=F1, ②=F2, ③=F3 (고정)
}

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update({k: data[k] for k in data if k in DEFAULT_CONFIG})
    except Exception:
        pass
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 매크로 워커 (백그라운드 스레드)
# ---------------------------------------------------------------------------
class MacroWorker(threading.Thread):
    def __init__(self, state, evq):
        super().__init__(daemon=True)
        self.state = state          # 공유 설정 dict (UI가 갱신)
        self.evq = evq              # UI로 보낼 이벤트 큐
        self.running = True
        self.capture_target = None  # 키 캡처 대상 필드 접두어("spam"/"toggle"/"hold")

    def stop(self):
        self.running = False

    def _adjust_hold(self, s, delta):
        """꾹누름 시간(초)을 delta 만큼 조절(0.0001~60, 소수 4자리)"""
        v = round(s["hold_seconds"] + delta, 4)
        v = max(0.0001, min(60.0, v))
        if v != s["hold_seconds"]:
            s["hold_seconds"] = v
            self.evq.put(("hold_seconds", v))

    def run(self):
        # 타이머 해상도 1ms로 상향 → sleep/폴링 정밀도 향상 (오차 감소)
        try:
            self._winmm = ctypes.WinDLL("winmm")
            self._winmm.timeBeginPeriod(1)
        except Exception:
            self._winmm = None
        try:
            self._run(self.state)
        finally:
            if self._winmm is not None:
                try:
                    self._winmm.timeEndPeriod(1)
                except Exception:
                    pass

    def _run(self, s):
        prev_f1 = is_pressed(VK_F1)
        prev_f2 = is_pressed(VK_F2)
        prev_f3 = is_pressed(VK_F3)
        # ③ 자동 꾹누름 반복 상태
        h3_down = False         # 대상 키가 현재 눌린 상태인지
        h3_press_t = 0.0        # 이번 눌림 시작 시각
        h3_release_t = -1e9     # 마지막 뗌 시각(첫 눌림 즉시 시작)
        prev_toggle = False
        spam_on = False
        prev_lbtn = is_pressed(VK_LBUTTON)
        lbtn_fired = False
        lbtn_down_t = 0.0
        last_spam = 0.0
        last_lb_emit = -1.0     # 실시간 경과 표시용 스로틀
        # PgUp/PgDn 시간 조절용 상태
        pg_prev = {VK_PGUP: False, VK_PGDN: False}
        pg_next = {VK_PGUP: 0.0, VK_PGDN: 0.0}
        # 캡처용 상태
        cap_wait_release = False

        while self.running:
            now = time.perf_counter()

            # --- 키 캡처 모드 ---
            if self.capture_target:
                if cap_wait_release:
                    # 이전에 눌린 키가 완전히 떨어질 때까지 대기
                    if not any(is_pressed(vk) for vk in range(0x07, 0xFF)):
                        cap_wait_release = False
                    time.sleep(0.01)
                    continue
                found = None
                for vk in range(0x07, 0xFF):  # 마우스 버튼(0x01~0x06) 제외
                    if is_pressed(vk):
                        found = vk
                        break
                if found is not None:
                    self.evq.put(("captured", self.capture_target, found))
                    self.capture_target = None
                    cap_wait_release = True
                time.sleep(0.008)
                continue

            # --- F1: ① 연타 켜기/끄기,  F2: ② 꾹누름 켜기/끄기 ---
            f1 = is_pressed(VK_F1)
            if f1 and not prev_f1:
                s["spam_enabled"] = not s["spam_enabled"]
                self.evq.put(("spam_enabled", s["spam_enabled"]))
            prev_f1 = f1

            f2 = is_pressed(VK_F2)
            if f2 and not prev_f2:
                s["hold_enabled"] = not s["hold_enabled"]
                self.evq.put(("hold_enabled", s["hold_enabled"]))
            prev_f2 = f2

            f3 = is_pressed(VK_F3)
            if f3 and not prev_f3:
                s["hold3_enabled"] = not s["hold3_enabled"]
                self.evq.put(("hold3_enabled", s["hold3_enabled"]))
            prev_f3 = f3

            # --- PgUp/PgDn: 꾹누름 시간 ±0.0001 (체크 시) ---
            if s.get("hold_adjust_enabled"):
                for vk, delta in ((VK_PGUP, 0.0001), (VK_PGDN, -0.0001)):
                    down = is_pressed(vk)
                    if down and not pg_prev[vk]:            # 눌린 순간 1스텝
                        self._adjust_hold(s, delta)
                        pg_next[vk] = now + 0.35            # 반복 시작 지연
                    elif down and pg_prev[vk] and now >= pg_next[vk]:
                        self._adjust_hold(s, delta)         # 계속 누르면 반복
                        pg_next[vk] = now + 0.03
                    pg_prev[vk] = down
            else:
                pg_prev[VK_PGUP] = pg_prev[VK_PGDN] = False

            # --- 연타 매크로 ---
            if s["mode"] == "toggle":
                t = is_pressed(s["toggle_vk"])
                if t and not prev_toggle:
                    spam_on = not spam_on
                    self.evq.put(("spam_state", spam_on))
                prev_toggle = t
            else:  # hold
                new_spam = is_pressed(s["toggle_vk"])
                if new_spam != spam_on:
                    spam_on = new_spam
                    self.evq.put(("spam_state", spam_on))

            active_spam = s["spam_enabled"] and spam_on
            if active_spam and s["rate"] > 0:
                interval = 1.0 / s["rate"]
                if now - last_spam >= interval:
                    tap_key(s["spam_vk"], s["spam_scan"], s["spam_ext"], s["press_ms"])
                    last_spam = now

            # --- 좌클릭 꾹 누르기 매크로 ---
            lb = is_pressed(VK_LBUTTON)
            if lb and not prev_lbtn:          # 누르기 시작
                lbtn_down_t = now
                lbtn_fired = False
                last_lb_emit = -1.0
            if (not lb) and prev_lbtn:        # 뗌
                self.evq.put(("lb_release", None))
            if not lb:
                lbtn_fired = False
            prev_lbtn = lb

            if lb:
                elapsed = now - lbtn_down_t
                # 발동 조건: ② 활성 + 아직 미발동
                if s["hold_enabled"] and not lbtn_fired:
                    remaining = s["hold_seconds"] - elapsed
                    # 임계 4ms 이내면 busy-wait로 정밀 발동 (오차 ~수 μs)
                    if remaining <= 0.004:
                        while is_pressed(VK_LBUTTON):
                            e2 = time.perf_counter() - lbtn_down_t
                            if e2 >= s["hold_seconds"]:
                                tap_key(s["hold_vk"], s["hold_scan"],
                                        s["hold_ext"], s["press_ms"])
                                lbtn_fired = True
                                self.evq.put(("hold_fired", e2))
                                break
                        # 버튼을 미리 떼면 while 탈출(미발동)
                # 실시간 경과 시간 표시 (약 40ms 간격)
                if last_lb_emit < 0 or now - last_lb_emit >= 0.04:
                    self.evq.put(("lb_tick", elapsed, lbtn_fired))
                    last_lb_emit = now

            # --- ③ 자동 꾹누름 반복 매크로 ---
            if s["hold3_enabled"]:
                gap = s["press_ms"] / 1000.0     # 뗌 → 재눌림 사이 간격
                if h3_down:
                    # 눌린 상태: 설정 시간 경과하면 뗌 (임계 4ms 이내 정밀 발동)
                    remaining = s["hold3_seconds"] - (now - h3_press_t)
                    if remaining <= 0.004:
                        while s["hold3_enabled"]:
                            held = time.perf_counter() - h3_press_t
                            if held >= s["hold3_seconds"]:
                                send_key(s["hold3_vk"], s["hold3_scan"],
                                         s["hold3_ext"], True)   # 키 뗌
                                h3_down = False
                                h3_release_t = time.perf_counter()
                                self.evq.put(("hold3_cycle", held))
                                break
                else:
                    # 뗀 상태: 간격 지나면 다시 누름
                    if now - h3_release_t >= gap:
                        send_key(s["hold3_vk"], s["hold3_scan"],
                                 s["hold3_ext"], False)          # 키 누름
                        h3_down = True
                        h3_press_t = now
                        self.evq.put(("hold3_press", None))
            else:
                # 매크로 꺼지면 눌린 키는 반드시 뗌
                if h3_down:
                    send_key(s["hold3_vk"], s["hold3_scan"], s["hold3_ext"], True)
                    h3_down = False
                    h3_release_t = now

            time.sleep(0.001)

        # 종료 시 눌린 키 정리
        if h3_down:
            try:
                send_key(s["hold3_vk"], s["hold3_scan"], s["hold3_ext"], True)
            except Exception:
                pass

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        cfg = load_config()

        # 워커와 공유하는 설정 dict
        self.state = dict(cfg)

        self.evq = queue.Queue()
        self.worker = MacroWorker(self.state, self.evq)
        self.worker.start()

        root.title("키매크로")
        root.resizable(False, False)
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass

        pad = {"padx": 8, "pady": 4}
        row = 0

        # 단축키 안내 + 로그 열기/닫기 버튼
        top = ttk.Frame(root)
        top.grid(row=row, column=0, columnspan=3, sticky="we", padx=8, pady=(10, 2))
        ttk.Label(top, text="F1=① 연타   F2=② 꾹누름   F3=③ 반복  켜기/끄기",
                  font=("맑은 고딕", 9, "bold")).pack(side="left")
        self.log_visible = True
        self.log_toggle_btn = ttk.Button(top, text="로그 닫기 ▶", width=11,
                                          command=self.toggle_log)
        self.log_toggle_btn.pack(side="right")
        row += 1
        ttk.Separator(root, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="we", padx=8, pady=4)
        row += 1

        # ===== 연타 매크로 =====
        self.spam_enabled = tk.BooleanVar(value=self.state["spam_enabled"])
        ttk.Checkbutton(root, text="① 연타 매크로 (F1)", variable=self.spam_enabled,
                        command=self.on_change).grid(row=row, column=0, columnspan=2,
                                                     sticky="w", **pad)
        self.spam_status_lbl = tk.Label(root, text="● 활성", font=("맑은 고딕", 9, "bold"))
        self.spam_status_lbl.grid(row=row, column=2, **pad)
        row += 1

        ttk.Label(root, text="연타할 키").grid(row=row, column=0, sticky="w", **pad)
        self.spam_key_lbl = ttk.Label(root, text=self.state["spam_name"], width=12,
                                      relief="groove", anchor="center")
        self.spam_key_lbl.grid(row=row, column=1, **pad)
        ttk.Button(root, text="설정", width=6,
                   command=lambda: self.capture("spam")).grid(row=row, column=2, **pad)
        row += 1

        ttk.Label(root, text="실행 토글 키").grid(row=row, column=0, sticky="w", **pad)
        self.toggle_key_lbl = ttk.Label(root, text=self.state["toggle_name"], width=12,
                                        relief="groove", anchor="center")
        self.toggle_key_lbl.grid(row=row, column=1, **pad)
        ttk.Button(root, text="설정", width=6,
                   command=lambda: self.capture("toggle")).grid(row=row, column=2, **pad)
        row += 1

        ttk.Label(root, text="초당 횟수").grid(row=row, column=0, sticky="w", **pad)
        self.rate_var = tk.DoubleVar(value=self.state["rate"])
        rate_spin = ttk.Spinbox(root, from_=0.5, to=100, increment=0.5, width=8,
                                textvariable=self.rate_var, command=self.on_change)
        rate_spin.grid(row=row, column=1, sticky="w", **pad)
        rate_spin.bind("<KeyRelease>", lambda e: self.on_change())
        self.spam_state_lbl = ttk.Label(root, text="정지", foreground="gray",
                                        width=10, anchor="w")
        self.spam_state_lbl.grid(row=row, column=2, sticky="w", **pad)
        row += 1

        ttk.Label(root, text="모드").grid(row=row, column=0, sticky="w", **pad)
        self.mode_var = tk.StringVar(value=self.state["mode"])
        mframe = ttk.Frame(root)
        mframe.grid(row=row, column=1, columnspan=2, sticky="w", **pad)
        ttk.Radiobutton(mframe, text="토글", value="toggle", variable=self.mode_var,
                        command=self.on_change).pack(side="left")
        ttk.Radiobutton(mframe, text="누르는 동안만", value="hold", variable=self.mode_var,
                        command=self.on_change).pack(side="left", padx=(8, 0))
        row += 1

        ttk.Separator(root, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="we", padx=8, pady=6)
        row += 1

        # ===== 좌클릭 꾹 누르기 매크로 =====
        self.hold_enabled = tk.BooleanVar(value=self.state["hold_enabled"])
        ttk.Checkbutton(root, text="② 좌클릭 꾹누름 매크로 (F2)",
                        variable=self.hold_enabled,
                        command=self.on_change).grid(row=row, column=0, columnspan=2,
                                                     sticky="w", **pad)
        self.hold_status_lbl = tk.Label(root, text="● 비활성", font=("맑은 고딕", 9, "bold"))
        self.hold_status_lbl.grid(row=row, column=2, **pad)
        row += 1

        ttk.Label(root, text="누를 키").grid(row=row, column=0, sticky="w", **pad)
        self.hold_key_lbl = ttk.Label(root, text=self.state["hold_name"], width=12,
                                      relief="groove", anchor="center")
        self.hold_key_lbl.grid(row=row, column=1, **pad)
        ttk.Button(root, text="설정", width=6,
                   command=lambda: self.capture("hold")).grid(row=row, column=2, **pad)
        row += 1

        ttk.Label(root, text="꾹 누름 시간(초)").grid(row=row, column=0, sticky="w", **pad)
        self.hold_sec_var = tk.DoubleVar(value=self.state["hold_seconds"])
        hs = ttk.Spinbox(root, from_=0.0001, to=60, increment=0.0001, width=10,
                         format="%.4f", textvariable=self.hold_sec_var,
                         command=self.on_change)
        hs.grid(row=row, column=1, sticky="w", **pad)
        hs.bind("<KeyRelease>", lambda e: self.on_change())
        self.hold_state_lbl = ttk.Label(root, text="대기", foreground="gray",
                                        width=20, anchor="w")
        self.hold_state_lbl.grid(row=row, column=2, sticky="w", **pad)
        row += 1

        self.hold_adjust_enabled = tk.BooleanVar(value=self.state["hold_adjust_enabled"])
        ttk.Checkbutton(root, text="PgUp/PgDn 으로 시간 조절 (±0.0001)",
                        variable=self.hold_adjust_enabled,
                        command=self.on_change).grid(row=row, column=0, columnspan=3,
                                                     sticky="w", **pad)
        row += 1

        ttk.Separator(root, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="we", padx=8, pady=6)
        row += 1

        # ===== ③ 자동 꾹누름 반복 매크로 =====
        self.hold3_enabled = tk.BooleanVar(value=self.state["hold3_enabled"])
        ttk.Checkbutton(root, text="③ 자동 꾹누름 반복 매크로 (F3)",
                        variable=self.hold3_enabled,
                        command=self.on_change).grid(row=row, column=0, columnspan=2,
                                                     sticky="w", **pad)
        self.hold3_status_lbl = tk.Label(root, text="● 비활성", font=("맑은 고딕", 9, "bold"))
        self.hold3_status_lbl.grid(row=row, column=2, **pad)
        row += 1

        ttk.Label(root, text="누를 키").grid(row=row, column=0, sticky="w", **pad)
        self.hold3_key_lbl = ttk.Label(root, text=self.state["hold3_name"], width=12,
                                       relief="groove", anchor="center")
        self.hold3_key_lbl.grid(row=row, column=1, **pad)
        ttk.Button(root, text="설정", width=6,
                   command=lambda: self.capture("hold3")).grid(row=row, column=2, **pad)
        row += 1

        ttk.Label(root, text="누름 시간(초)").grid(row=row, column=0, sticky="w", **pad)
        self.hold3_sec_var = tk.DoubleVar(value=self.state["hold3_seconds"])
        h3s = ttk.Spinbox(root, from_=0.0001, to=60, increment=0.1, width=10,
                          format="%.4f", textvariable=self.hold3_sec_var,
                          command=self.on_change)
        h3s.grid(row=row, column=1, sticky="w", **pad)
        h3s.bind("<KeyRelease>", lambda e: self.on_change())
        self.hold3_state_lbl = ttk.Label(root, text="정지", foreground="gray",
                                         width=20, anchor="w")
        self.hold3_state_lbl.grid(row=row, column=2, sticky="w", **pad)
        row += 1

        ttk.Label(root, text="설정 시간만큼 누르고 뗌을 종료까지 반복합니다.",
                  foreground="gray").grid(row=row, column=0, columnspan=3,
                                          sticky="w", padx=8)
        row += 1

        ttk.Separator(root, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="we", padx=8, pady=6)
        row += 1

        self.hint = ttk.Label(root, text="설정 자동 저장.  F1=① · F2=② · F3=③ 켜고 끄기",
                              foreground="gray")
        self.hint.grid(row=row, column=0, columnspan=3, pady=(0, 8))
        total_rows = row + 1

        # ===== 우측: 작동 로그 =====
        self.log_entries = []          # (ts, cat, msg) 전체 보관
        self.LOG_CATS = ["전체 작동 로그", "② 꾹누름", "③ 반복", "① 연타", "상태", "키설정"]

        self.logf = ttk.LabelFrame(root, text="작동 로그")
        self.logf.grid(row=0, column=3, rowspan=total_rows, sticky="ns",
                       padx=(4, 8), pady=10)
        logf = self.logf

        # 상단: 항목(카테고리) 선택
        filt = ttk.Frame(logf)
        filt.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 4))
        ttk.Label(filt, text="항목:").pack(side="left")
        self.log_filter = tk.StringVar(value=self.LOG_CATS[0])
        cb = ttk.Combobox(filt, textvariable=self.log_filter, values=self.LOG_CATS,
                          state="readonly", width=16)
        cb.pack(side="left", padx=(4, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self.render_log())

        # 로그 본문 (폭 2배: 30 -> 62) + 세로/가로 스크롤
        self.log_text = tk.Text(logf, width=62, height=20, state="disabled",
                                wrap="none", font=("Consolas", 9),
                                bg="#101418", fg="#d6e2e9")
        sb = ttk.Scrollbar(logf, orient="vertical", command=self.log_text.yview)
        hb = ttk.Scrollbar(logf, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=sb.set, xscrollcommand=hb.set)
        self.log_text.grid(row=1, column=0, sticky="nsew")
        sb.grid(row=1, column=1, sticky="ns")
        hb.grid(row=2, column=0, sticky="we")

        btnrow = ttk.Frame(logf)
        btnrow.grid(row=3, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.log_count_lbl = ttk.Label(btnrow, text="", foreground="gray")
        self.log_count_lbl.pack(side="left")
        ttk.Button(btnrow, text="지우기", width=8,
                   command=self.clear_log).pack(side="right")

        self.capturing = False
        self.update_status_labels()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(30, self.poll_events)
        self.log("프로그램 시작 (관리자=%s)" % ("예" if is_admin() else "아니오"))
        self.log("① 연타 %s / ② 꾹누름 %s / ③ 반복 %s" % (
            "활성" if self.state["spam_enabled"] else "비활성",
            "활성" if self.state["hold_enabled"] else "비활성",
            "활성" if self.state["hold3_enabled"] else "비활성"))

    def update_status_labels(self):
        def paint(lbl, on):
            lbl.config(text="● 활성" if on else "● 비활성",
                       fg="#2e7d32" if on else "#c62828")
        paint(self.spam_status_lbl, self.state["spam_enabled"])
        paint(self.hold_status_lbl, self.state["hold_enabled"])
        paint(self.hold3_status_lbl, self.state["hold3_enabled"])

    # --- 키 캡처 ---
    def capture(self, target):
        if self.capturing:
            return
        self.capturing = True
        lbl = self._label_for(target)
        self._prev_text = lbl.cget("text")
        lbl.config(text="키 누르세요…")
        self.worker.capture_target = target

    def _label_for(self, target):
        return {"spam": self.spam_key_lbl,
                "toggle": self.toggle_key_lbl,
                "hold": self.hold_key_lbl,
                "hold3": self.hold3_key_lbl}[target]

    # --- 설정 변경 -> state 반영 + 저장 ---
    def on_change(self, *_):
        try:
            rate = float(self.rate_var.get())
        except Exception:
            rate = self.state["rate"]
        try:
            hsec = round(float(self.hold_sec_var.get()), 4)  # 소수점 4자리
        except Exception:
            hsec = self.state["hold_seconds"]
        try:
            h3sec = round(float(self.hold3_sec_var.get()), 4)
        except Exception:
            h3sec = self.state["hold3_seconds"]

        self.state["spam_enabled"] = bool(self.spam_enabled.get())
        self.state["hold_enabled"] = bool(self.hold_enabled.get())
        self.state["hold_adjust_enabled"] = bool(self.hold_adjust_enabled.get())
        self.state["hold3_enabled"] = bool(self.hold3_enabled.get())
        self.state["rate"] = rate
        self.state["hold_seconds"] = hsec
        self.state["hold3_seconds"] = h3sec
        self.state["mode"] = self.mode_var.get()
        self.update_status_labels()
        self.persist()

    def persist(self):
        cfg = {k: self.state[k] for k in DEFAULT_CONFIG}
        save_config(cfg)

    def _schedule_save(self):
        """PgUp/PgDn 반복 조절 시 디스크 저장을 400ms 디바운스"""
        job = getattr(self, "_save_job", None)
        if job:
            self.root.after_cancel(job)
        self._save_job = self.root.after(400, self._do_save)

    def _do_save(self):
        self._save_job = None
        self.persist()

    # --- 워커 이벤트 처리 ---
    def poll_events(self):
        try:
            while True:
                kind, *args = self.evq.get_nowait()
                if kind == "captured":
                    target, vk = args
                    self.apply_capture(target, vk)
                elif kind == "spam_enabled":
                    self.spam_enabled.set(args[0])
                    self.update_status_labels()
                    self.persist()
                    self.log("① 연타 %s (F1)" % ("활성" if args[0] else "비활성"),
                             "① 연타")
                elif kind == "hold_enabled":
                    self.hold_enabled.set(args[0])
                    self.update_status_labels()
                    self.persist()
                    self.log("② 꾹누름 %s (F2)" % ("활성" if args[0] else "비활성"),
                             "② 꾹누름")
                elif kind == "hold_seconds":
                    self.hold_sec_var.set(args[0])
                    self._schedule_save()
                elif kind == "spam_state":
                    on = args[0]
                    self.spam_state_lbl.config(
                        text="연타 중" if on else "정지",
                        foreground="red" if on else "gray")
                    self.log("① 연타 %s [%s]" % (
                        "시작" if on else "정지", self.state["spam_name"]), "① 연타")
                elif kind == "lb_tick":
                    elapsed, fired = args
                    setp = self.state["hold_seconds"]
                    if fired:
                        self.hold_state_lbl.config(
                            text="발동됨 %.3fs" % elapsed, foreground="red")
                    else:
                        self.hold_state_lbl.config(
                            text="유지 %.3f/%.4f" % (elapsed, setp),
                            foreground="#1565c0")
                elif kind == "lb_release":
                    self.hold_state_lbl.config(text="대기", foreground="gray")
                elif kind == "hold_fired":
                    elapsed = args[0]
                    setp = self.state["hold_seconds"]
                    err = elapsed - setp
                    self.log("② 발동 → [%s]  실제 %.4fs (설정 %.4fs, 오차 %+.4fs)"
                             % (self.state["hold_name"], elapsed, setp, err), "② 꾹누름")
                elif kind == "hold3_enabled":
                    self.hold3_enabled.set(args[0])
                    self.update_status_labels()
                    self.persist()
                    if not args[0]:
                        self.hold3_state_lbl.config(text="정지", foreground="gray")
                    self.log("③ 반복 %s (F3)" % ("활성" if args[0] else "비활성"),
                             "③ 반복")
                elif kind == "hold3_press":
                    self.hold3_state_lbl.config(
                        text="누르는 중 [%s]" % self.state["hold3_name"],
                        foreground="#1565c0")
                elif kind == "hold3_cycle":
                    held = args[0]
                    self._h3_count = getattr(self, "_h3_count", 0) + 1
                    self.hold3_state_lbl.config(
                        text="뗌 (%d회, %.4fs)" % (self._h3_count, held),
                        foreground="red")
                    self.log("③ 1회 완료 → [%s] %.4fs 유지 (설정 %.4fs, 누적 %d회)"
                             % (self.state["hold3_name"], held,
                                self.state["hold3_seconds"], self._h3_count), "③ 반복")
        except queue.Empty:
            pass
        self.root.after(30, self.poll_events)

    def apply_capture(self, target, vk):
        self.capturing = False
        scan = scan_for_vk(vk)
        ext = vk in EXTENDED_VKS
        name = vk_name(vk)
        self.state[target + "_vk"] = vk
        self.state[target + "_scan"] = scan
        self.state[target + "_ext"] = ext
        self.state[target + "_name"] = name
        self._label_for(target).config(text=name)
        self.persist()
        tnm = {"spam": "연타할 키", "toggle": "토글 키", "hold": "꾹누름 키",
               "hold3": "반복 누를 키"}.get(target, target)
        self.log("키 설정: %s = [%s]" % (tnm, name), "키설정")

    # --- 로그 ---
    def log(self, msg, cat="상태"):
        ts = time.strftime("%H:%M:%S")
        self.log_entries.append((ts, cat, msg))
        if len(self.log_entries) > 2000:        # 최근 2000줄 보관
            self.log_entries = self.log_entries[-2000:]
        # 현재 필터에 걸리면 바로 한 줄 추가, 아니면 보관만
        if self._cat_visible(cat):
            self._append_line(ts, cat, msg)
        self._update_count()

    def _cat_visible(self, cat):
        sel = self.log_filter.get()
        return sel == self.LOG_CATS[0] or sel == cat

    def _append_line(self, ts, cat, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", "[%s] %s\n" % (ts, msg))
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def render_log(self):
        """선택한 항목만 다시 그림"""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        for ts, cat, msg in self.log_entries:
            if self._cat_visible(cat):
                self.log_text.insert("end", "[%s] %s\n" % (ts, msg))
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self._update_count()

    def _update_count(self):
        sel = self.log_filter.get()
        if sel == self.LOG_CATS[0]:
            n = len(self.log_entries)
        else:
            n = sum(1 for _, c, _ in self.log_entries if c == sel)
        self.log_count_lbl.config(text="%s: %d줄" % (sel, n))

    def clear_log(self):
        self.log_entries = []
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self._update_count()

    def toggle_log(self):
        """작동 로그 패널 열기/닫기 (창 폭이 함께 줄었다 늘어남)"""
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.logf.grid()
            self.log_toggle_btn.config(text="로그 닫기 ▶")
        else:
            self.logf.grid_remove()
            self.log_toggle_btn.config(text="로그 열기 ◀")

    def on_close(self):
        self.worker.stop()
        self.persist()
        self.root.destroy()

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
