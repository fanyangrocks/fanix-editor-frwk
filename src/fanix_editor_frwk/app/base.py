from PySide6 import QtWidgets

from ..protocol.app_protocol import AppProtocol


class FEBaseApp:
    def __init__(self, app: AppProtocol = QtWidgets.QApplication([])):
        self._exec_app = app
