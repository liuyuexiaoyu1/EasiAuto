import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    InfoBar,
    LineEdit,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
    TableWidget,
    VerticalSeparator,
)

from ._release_core import (  # noqa: F401 (re-export)
    _detect_version,
    collect_release_assets,
    create_github_release,
    do_full_release,
    generate_release_body,
    update_manifest,
    upload_asset,
)
from ._shared import resolve_token

# ── Release Thread ─────────────────────────────────────────────────────


class ReleaseThread(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def run(self):
        try:
            cfg = self.config
            dist_dir = Path(cfg["dist_dir"])
            version = cfg["version"]
            is_dev = cfg["is_dev"]
            confirm_required = cfg["confirm_required"]
            desc = cfg.get("desc") or None
            highlights = cfg["highlights"]
            others = cfg["others"]
            push_to_beta = cfg.get("push_to_beta", False)

            self.log_signal.emit("📦 Collecting release assets...")
            assets = collect_release_assets(dist_dir, version)

            body = generate_release_body(desc, highlights, others)

            self.log_signal.emit(f"🚀 Creating GitHub Release v{version} ...")
            release_info = create_github_release(version=version, body=body, is_dev=is_dev)
            upload_url_template = release_info["upload_url"]
            release_assets = release_info.get("assets", [])

            for file_path in assets:
                self.log_signal.emit(f"⬆️ Uploading {file_path.name} ...")
                upload_asset(upload_url_template, file_path, release_assets)

            self.log_signal.emit("📝 Updating manifest...")
            update_manifest(
                dist_dir=dist_dir,
                version=version,
                is_dev=is_dev,
                confirm_required=confirm_required,
                desc=desc,
                highlights=highlights,
                others=others,
                push_to_beta=push_to_beta,
            )

            self.finished_signal.emit(True, f"版本 {version} 发版成功!")

        except Exception as e:
            traceback.print_exc()
            self.finished_signal.emit(False, str(e))


# ── Release Form UI ────────────────────────────────────────────────────


class ReleaseFormWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ReleaseFormWidget")
        self.release_thread = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        root.addWidget(SubtitleLabel("发版", self))

        content = QHBoxLayout()
        content.setContentsMargins(0, 12, 0, 0)
        content.setSpacing(0)

        # ── Left: version, description, highlights, others ──
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 16, 0)
        left_layout.setSpacing(10)

        version_row = QHBoxLayout()
        version_row.addWidget(StrongBodyLabel("版本:", left))
        self.version_label = QLabel("—", left)
        self.version_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px 0;")
        version_row.addWidget(self.version_label)
        version_row.addStretch(1)
        left_layout.addLayout(version_row)

        left_layout.addWidget(StrongBodyLabel("说明:", left))
        self.desc_edit = PlainTextEdit(left)
        self.desc_edit.setFixedHeight(80)
        left_layout.addWidget(self.desc_edit)

        left_layout.addWidget(StrongBodyLabel("亮点:", left))
        self.highlights_table = TableWidget(left)
        self.highlights_table.setColumnCount(2)
        self.highlights_table.setHorizontalHeaderLabels(["名称", "描述"])
        self.highlights_table.verticalHeader().hide()
        self.highlights_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.highlights_table.setFixedHeight(150)
        left_layout.addWidget(self.highlights_table)

        hl_btn_row = QHBoxLayout()
        self.add_hl_btn = PushButton("添加亮点", left)
        self.add_hl_btn.clicked.connect(self._add_highlight)
        self.remove_hl_btn = PushButton("移除选中", left)
        self.remove_hl_btn.clicked.connect(self._remove_highlight)
        hl_btn_row.addWidget(self.add_hl_btn)
        hl_btn_row.addWidget(self.remove_hl_btn)
        hl_btn_row.addStretch(1)
        left_layout.addLayout(hl_btn_row)

        left_layout.addWidget(StrongBodyLabel("其他更新 (每行一个):", left))
        self.others_edit = PlainTextEdit(left)
        self.others_edit.setFixedHeight(90)
        left_layout.addWidget(self.others_edit)

        left_layout.addStretch(1)

        # ── Separator ──
        separator = VerticalSeparator(self)

        # ── Right: switches, buttons, log ──
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 0, 0, 0)
        right_layout.setSpacing(10)

        right_layout.addWidget(StrongBodyLabel("构建产物目录:", right))
        dir_row = QHBoxLayout()
        self.dist_edit = LineEdit(right)
        self.dist_edit.setText("build")
        self.dist_edit.setPlaceholderText("构建产物目录")
        self.dist_btn = PushButton("浏览...", right)
        self.dist_btn.clicked.connect(self._browse_dist)
        dir_row.addWidget(self.dist_edit)
        dir_row.addWidget(self.dist_btn)
        right_layout.addLayout(dir_row)

        switch_row_1 = QHBoxLayout()
        switch_row_1.addWidget(StrongBodyLabel("测试版", right))
        self.is_dev_switch = SwitchButton(right)
        switch_row_1.addWidget(self.is_dev_switch)
        switch_row_1.addStretch(1)
        right_layout.addLayout(switch_row_1)

        switch_row_2 = QHBoxLayout()
        switch_row_2.addWidget(StrongBodyLabel("需要确认", right))
        self.confirm_switch = SwitchButton(right)
        switch_row_2.addWidget(self.confirm_switch)
        switch_row_2.addStretch(1)
        right_layout.addLayout(switch_row_2)

        switch_row_3 = QHBoxLayout()
        switch_row_3.addWidget(StrongBodyLabel("同步推送到测试版", right))
        self.push_to_beta_switch = SwitchButton(right)
        self.push_to_beta_switch.setOnText("是")
        self.push_to_beta_switch.setOffText("否")
        self.push_to_beta_switch.setDisabled(self.is_dev_switch.isChecked())
        self.is_dev_switch.checkedChanged.connect(self._on_is_dev_toggled)
        switch_row_3.addWidget(self.push_to_beta_switch)
        switch_row_3.addStretch(1)
        right_layout.addLayout(switch_row_3)

        right_layout.addSpacing(8)

        self.release_btn = PrimaryPushButton("发版", right)
        self.release_btn.setIcon(FluentIcon.UPDATE)
        self.release_btn.clicked.connect(self.do_release)
        right_layout.addWidget(self.release_btn)

        self.build_release_btn = PushButton("构建后发版", right)
        self.build_release_btn.setIcon(FluentIcon.CONSTRACT)
        self.build_release_btn.clicked.connect(self.do_build_and_release)
        right_layout.addWidget(self.build_release_btn)

        right_layout.addSpacing(8)
        right_layout.addWidget(StrongBodyLabel("日志:", right))
        self.log_view = PlainTextEdit(right)
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("发版日志将显示在这里...")
        right_layout.addWidget(self.log_view, 1)

        content.addWidget(left, 1)
        content.addWidget(separator)
        content.addWidget(right, 1)

        root.addLayout(content, 1)

        self._refresh_version()

    def _refresh_version(self):
        v = _detect_version()
        self.version_label.setText(v if v else "—")

    def _on_is_dev_toggled(self, checked: bool):
        self.push_to_beta_switch.setDisabled(checked)

    def _browse_dist(self):
        path = QFileDialog.getExistingDirectory(self, "选择构建产物目录", self.dist_edit.text())
        if path:
            self.dist_edit.setText(path)

    def _add_highlight(self):
        row = self.highlights_table.rowCount()
        self.highlights_table.insertRow(row)
        from PySide6.QtWidgets import QTableWidgetItem

        self.highlights_table.setItem(row, 0, QTableWidgetItem("新功能"))
        self.highlights_table.setItem(row, 1, QTableWidgetItem("描述"))

    def _remove_highlight(self):
        row = self.highlights_table.currentRow()
        if row >= 0:
            self.highlights_table.removeRow(row)

    def _collect_form_data(self) -> dict:
        version = self.version_label.text().strip()
        if not version or version == "—":
            raise ValueError("无法检测版本号，请在 EasiAuto/__init__.py 中设置 __version__")

        dist_dir = self.dist_edit.text().strip()
        if not Path(dist_dir).exists():
            raise ValueError(f"构建产物目录未找到: {dist_dir}")

        if not resolve_token():
            raise ValueError("需要 GitHub Token，请在配置页设置")

        desc = self.desc_edit.toPlainText().strip()

        highlights = []
        for row in range(self.highlights_table.rowCount()):
            name_item = self.highlights_table.item(row, 0)
            desc_item = self.highlights_table.item(row, 1)
            if name_item and desc_item:
                highlights.append({"name": name_item.text(), "description": desc_item.text()})

        others = [line.strip() for line in self.others_edit.toPlainText().split("\n") if line.strip()]

        return {
            "version": version,
            "dist_dir": dist_dir,
            "is_dev": self.is_dev_switch.isChecked(),
            "confirm_required": self.confirm_switch.isChecked(),
            "desc": desc,
            "highlights": highlights,
            "others": others,
            "push_to_beta": self.push_to_beta_switch.isChecked(),
        }

    def _set_buttons_enabled(self, enabled: bool):
        self.release_btn.setEnabled(enabled)
        self.build_release_btn.setEnabled(enabled)

    def _log(self, text: str):
        self.log_view.appendPlainText(text)

    def do_release(self):
        try:
            config = self._collect_form_data()
        except ValueError as e:
            InfoBar.error("错误", str(e), parent=self)
            return

        self._set_buttons_enabled(False)
        self.log_view.clear()

        self.release_thread = ReleaseThread(config)
        self.release_thread.log_signal.connect(self._log)
        self.release_thread.finished_signal.connect(self._on_release_finished)
        self.release_thread.start()

    def _on_release_finished(self, success: bool, message: str):
        self._set_buttons_enabled(True)
        if success:
            InfoBar.success("成功", message, parent=self)
            self._log(f"\n✅ {message}")
        else:
            InfoBar.error("发版失败", message, parent=self, duration=5000)
            self._log(f"\n❌ 发版失败: {message}")

    def do_build_and_release(self):
        try:
            config = self._collect_form_data()
        except ValueError as e:
            InfoBar.error("错误", str(e), parent=self)
            return

        from ._build import BuildManager

        self._set_buttons_enabled(False)
        self.log_view.clear()
        self._log("🔨 开始构建...")

        self._build_mgr = BuildManager()
        self._build_mgr.build_thread.finished_signal.connect(lambda success, _: self._on_build_done(success, config))
        self._build_mgr.start_build()

    def _on_build_done(self, success: bool, config: dict):
        if not success:
            self._set_buttons_enabled(True)
            self._log("❌ 构建失败，发版已取消")
            InfoBar.error("构建失败", "发版已取消", parent=self)
            return

        self._log("✅ 构建完成，开始发版...")

        self.release_thread = ReleaseThread(config)
        self.release_thread.log_signal.connect(self._log)
        self.release_thread.finished_signal.connect(self._on_release_finished)
        self.release_thread.start()
