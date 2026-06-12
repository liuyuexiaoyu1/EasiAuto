"""EasiAuto 发行中心。

提供 CLI（无需 Qt）和 GUI（需要 PySide6 + qfluentwidgets）两种使用方式。

CLI 入口::

    dist-center update-manifest --version 1.2.0 ...
    dist-center release --version 1.2.0 ...
    dist-center pull / push ...
    dist-center ui          # 启动 GUI

编程调用::

    from tools.distribution_center import main
    main(["update-manifest", "--version", "1.2.0", ...])
"""

from ._cli import main  # noqa: F401
