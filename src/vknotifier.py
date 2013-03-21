import sys
import os
import threading
import time
import json
import socket
import collections

import win32api
import win32gui
import win32con
import winerror

from vk import api


def print_log(message):
    print(time.strftime('%a, %d %b %Y %X', time.localtime()), message)


class MainWindow:
    def __init__(self):
        msg_TaskbarRestart = win32gui.RegisterWindowMessage("TaskbarCreated")
        message_map = {msg_TaskbarRestart: self.OnRestart,
                       win32con.WM_DESTROY: self.OnDestroy,
                       win32con.WM_COMMAND: self.OnCommand,
                       win32con.WM_USER + 20: self.OnTaskbarNotify}
        # Register the Window class.
        wc = win32gui.WNDCLASS()
        hinst = wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "VKNotifier"
        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
        wc.hCursor = win32api.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32con.COLOR_WINDOW
        wc.lpfnWndProc = message_map  # could also specify a wndproc.
        # Don't blow up if class already registered to make testing easier
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error as err_info:
            if err_info.winerror != winerror.ERROR_CLASS_ALREADY_EXISTS:
                raise
        # Create the Window.
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(wc.lpszClassName, "VKNotifier",
                style, 0, 0, win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT,
                0, 0, hinst, None)
        win32gui.UpdateWindow(self.hwnd)
        self._DoCreateIcons()
        self.connected = False
        self.vk_api = api.API()
        with open(os.path.join(os.path.dirname(sys.argv[0]),
                               'settings.ini')) as f:
            settings = json.load(f)
        self.users = settings.setdefault('users', [])
        self.delay = settings.setdefault('delay', 5)
        self.statuses = collections.OrderedDict()
        self.gui_destroy = threading.Event()
        self.th = threading.Thread(target=self.checking_status,
                                   args=(self.delay,))
        self.th.start()

    def _DoCreateIcons(self):
        # Try and find a custom icon
        hinst = win32api.GetModuleHandle(None)
        iconPathName = os.path.join(os.path.dirname(sys.argv[0]),
                                    'img', 'vkd.ico')
        if os.path.isfile(iconPathName):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            hicon = win32gui.LoadImage(hinst, iconPathName,
                                         win32con.IMAGE_ICON, 0, 0, icon_flags)
        else:
            print("Can't find icon file - using default")
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        nid = (self.hwnd, 0, flags, win32con.WM_USER + 20,
               hicon, "VKNotifier\nПодключение...")
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        except win32gui.error:
            # This is common when windows is starting, and this code is hit
            # before the taskbar has been created.
            print("Failed to add the taskbar icon - is explorer running?")
            # but keep running anyway - when explorer starts, we get the
            # TaskbarCreated message.

    def OnRestart(self, hwnd, msg, wparam, lparam):
        self._DoCreateIcons()
        self.connected = False
        #self.checking_status()

    def OnDestroy(self, hwnd, msg, wparam, lparam):
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32gui.PostQuitMessage(0)  # Terminate the app.

    def OnTaskbarNotify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONUP:
            pass
        elif lparam == win32con.WM_LBUTTONDBLCLK:
            pass
        elif lparam == win32con.WM_RBUTTONUP:
            menu = win32gui.CreatePopupMenu()
            #win32gui.AppendMenu(menu, win32con.MF_STRING,
            #                    1023, "Settings")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1025, "Выход")
            pos = win32gui.GetCursorPos()
            win32gui.SetForegroundWindow(self.hwnd)
            win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, pos[0],
                                    pos[1], 0, self.hwnd, None)
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        return 1

    def OnCommand(self, hwnd, msg, wparam, lparam):
        id_ = win32api.LOWORD(wparam)
        if id_ == 1023:
            pass
        elif id_ == 1024:
            pass
        elif id_ == 1025:
            self.gui_destroy.set()
            win32gui.DestroyWindow(self.hwnd)
        else:
            print("Unknown command -", id_)

    def checking_status(self, delay=1):
        if not isinstance(delay, int) or delay < 1:
            raise TypeError('delay must be integer >= 1')
        while not self.gui_destroy.is_set():
            while True:
                if self.gui_destroy.is_set():
                    return
                try:
                    statuses = self.vk_api.request('getProfiles',
                            uids=','.join([str(uid) for uid in self.users]),
                            fields='online')
                    if not self.connected:
                        self.connected = True
                        self.toggle_icon(True)
                        self.toggle_tooltip(True)
                    break
                except socket.error as socket_error:
                    print_log(socket_error)
                    if self.connected:
                        self.connected = False
                        self.toggle_icon(False)
                        self.toggle_tooltip(False)
                    time.sleep(10)
            changes = []
            for status in statuses:
                uid = status['uid']
                info = (status['online'],
                        '{0[first_name]} {0[last_name]}'.format(status))
                last_info = self.statuses.get(uid)
                if not last_info or last_info[0] != info[0]:
                    self.statuses[uid] = info
                    changes.append(info)
            if changes:
                for change in changes:
                    print_log(change)
                msg = '\n'.join(['{0} {1}'.format(c[1],
                        'в сети' if c[0] == 1 else 'оффлайн')
                                for c in changes])
                self.show_balloon('Изменение статуса', msg)
                self.toggle_tooltip(True)
            time.sleep(delay)

    def show_balloon(self, title, message):
        nid = (self.hwnd, 0, win32gui.NIF_INFO, win32con.WM_USER + 20,
               None, 'VKNotifier', message, 4, title)
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)

    def change_tooltip(self, tooltip):
        nid = (self.hwnd, 0, win32gui.NIF_TIP, win32con.WM_USER + 20,
               None, tooltip)
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
        except win32gui.error:
            print("Failed to add the taskbar icon - is explorer running?")

    def toggle_tooltip(self, online):
        if online:
            tooltip = 'VKNotifier\nВ сети: {0} ({1})'.format(
                        len([v for v in self.statuses.values() if v[0] == 1]),
                        len(self.statuses))
        else:
            tooltip = 'VKNotifier\nПодключение...'
        self.change_tooltip(tooltip)

    def toggle_icon(self, online):
        if online:
            iconPathName = os.path.join(os.path.dirname(sys.argv[0]),
                                        'img', 'vk.ico')
        else:
            iconPathName = os.path.join(os.path.dirname(sys.argv[0]),
                                        'img', 'vkd.ico')
        hinst = win32api.GetModuleHandle(None)
        if os.path.isfile(iconPathName):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            hicon = win32gui.LoadImage(hinst, iconPathName,
                                       win32con.IMAGE_ICON, 0, 0, icon_flags)
        else:
            print("Can't find icon file - using default")
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        nid = (self.hwnd, 0, win32gui.NIF_ICON, win32con.WM_USER + 20, hicon)
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
        except win32gui.error:
            print("Failed to add the taskbar icon - is explorer running?")


def main():
    MainWindow()
    win32gui.PumpMessages()

if __name__ == '__main__':
    main()
