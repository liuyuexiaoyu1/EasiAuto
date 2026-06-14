from typing import Any

from loguru import logger

from PySide6.QtCore import QObject, Signal

from EasiAuto.core.automator import BaseAutomator


class AutomationManager(QObject):
    started = Signal()
    finished = Signal()
    successed = Signal()
    interrupted = Signal()
    failed = Signal(str)
    task_updated = Signal(str)
    progress_updated = Signal(str)

    def __init__(self):
        super().__init__()
        self._automator: BaseAutomator | None = None

    def run(self, type: str, credentials: Any):
        if self._automator and self._automator.isRunning():
            logger.warning("已有一个正在运行的登录任务")
            return

        from EasiAuto.core.automator.qrcode import QRCodeAutomator, fetch_password_token

        if type == "qrcode":
            logger.info("检测到二维码档案")
            token_data = credentials
        else:
            account, password = credentials
            logger.info(f"密码档案, 请求 token: {account}")
            token_data = fetch_password_token(account, password)
            if not token_data:
                from EasiAuto.core.automator.base import LoginError

                self.failed.emit("Token 获取失败，请检查账号密码是否正确")
                return

        self._automator = QRCodeAutomator(token_data)

        self._automator.started.connect(self.started)
        self._automator.finished.connect(self.finished)
        self._automator.successed.connect(self.successed)
        self._automator.interrupted.connect(self.interrupted)
        self._automator.failed.connect(self.failed)
        self._automator.task_updated.connect(self.task_updated)
        self._automator.progress_updated.connect(self.progress_updated)

        self._automator.start()

    def stop(self):
        """停止当前任务"""
        if self._automator and self._automator.isRunning():
            logger.info("正在停止当前任务")
            self._automator.requestInterruption()


automation_manager = AutomationManager()
