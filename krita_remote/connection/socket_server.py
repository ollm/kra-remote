from abc import abstractmethod
from threading import Thread
from typing import Protocol, Optional
from random import randint
from socket import gethostbyname, gethostname
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt5.QtNetwork import QHostAddress
from PyQt5.QtCore import pyqtProperty
from ..websockets.src.websockets.sync.server import serve, ServerConnection, WebSocketServer

class ServerListener(Protocol):
    
    @abstractmethod
    @pyqtSlot()
    def onServerStopped(self) -> None:
        pass

    @abstractmethod
    @pyqtSlot(str)
    def onServerListening(self, address: str) -> None:
        pass
    
class ClientListener(Protocol):
    
    @abstractmethod
    @pyqtSlot()
    def onClientMessage(self) -> None:
        pass

    @abstractmethod
    @pyqtSlot()
    def onClientConnected(self) -> None:
        pass

    @abstractmethod
    @pyqtSlot()
    def onClientDisconnected(self) -> None:
        pass

class SocketServer(QObject):
    
    port: Optional[int] = None
    server: Optional[WebSocketServer] = None
    server_thread: Optional[Thread] = None
    client: bool = False
    connection: Optional[ServerConnection] = None
    
    serverListening = pyqtSignal(str)
    serverStopped = pyqtSignal()
    
    clientConnected = pyqtSignal()
    clientDisconnected = pyqtSignal()
    clientMessageReceived = pyqtSignal(str)

    action = pyqtSignal(str)
    press = pyqtSignal(str)
    release = pyqtSignal(str)
    tool = pyqtSignal(str)
    new_doc = pyqtSignal(str)
    set_color_space = pyqtSignal(str)
    set_layer_color_space = pyqtSignal(str)
    refresh_projection = pyqtSignal()
    resize = pyqtSignal(str)
    save_as = pyqtSignal(str)
    get_doc_info = pyqtSignal()
    get_layers = pyqtSignal()
    add_layer = pyqtSignal(str)
    select_layer = pyqtSignal(str)
    remove_layer = pyqtSignal(str)
    remove_layers = pyqtSignal(str)
    edit_layer = pyqtSignal(str)
    get_view = pyqtSignal()
    edit_view = pyqtSignal(str)
    selection = pyqtSignal(str)
    select_by_color = pyqtSignal(str)
    get_filters = pyqtSignal()
    get_filter_properties = pyqtSignal(str)
    get_resources = pyqtSignal(str)
    draw_line = pyqtSignal(str)
    draw_line_path = pyqtSignal(str)
    draw_cubic_line = pyqtSignal(str)
    get_canvas_image = pyqtSignal()
    get_layer_image = pyqtSignal(str)
    doc_wait_for_done = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.clientMessageReceived.connect(self.onMessage)

    @pyqtSlot(str)
    def onMessage(self, msg: str):
        if (msg.startswith("action:tool:")):
            action_name = msg.split(":")[2]
            self.tool.emit(action_name)
        elif (msg.startswith("action:")):
            action_name = msg.split(":")[1]
            self.action.emit(action_name)
        elif (msg.startswith("press:")):
            press = msg.split(":")[1]
            self.press.emit(press)
        elif (msg.startswith("release:")):
            release = msg.split(":")[1]
            self.release.emit(release)
        elif (msg.startswith("new_doc")):
            json = msg.split(":", 1)[1]
            self.new_doc.emit(json)
        elif (msg.startswith("set_color_space")):
            json = msg.split(":", 1)[1]
            self.set_color_space.emit(json)
        elif (msg.startswith("set_layer_color_space")):
            json = msg.split(":", 1)[1]
            self.set_layer_color_space.emit(json)
        elif (msg.startswith("refresh_projection")):
            self.refresh_projection.emit()
        elif (msg.startswith("resize:")):
            json = msg.split(":", 1)[1]
            self.resize.emit(json)
        elif (msg.startswith("save_as:")):
            json = msg.split(":", 1)[1]
            self.save_as.emit(json)
        elif (msg.startswith("get_doc_info")):
            self.get_doc_info.emit()
        elif (msg.startswith("get_layers")):
            self.get_layers.emit()
        elif (msg.startswith("add_layer:")):
            json = msg.split(":", 1)[1]
            self.add_layer.emit(json)
        elif (msg.startswith("select_layer:")):
            layer_name = msg.split(":", 1)[1]
            self.select_layer.emit(layer_name)
        elif (msg.startswith("remove_layer:")):
            json = msg.split(":", 1)[1]
            self.remove_layer.emit(json)
        elif (msg.startswith("remove_layers:")):
            json = msg.split(":", 1)[1]
            self.remove_layers.emit(json)
        elif (msg.startswith("edit_layer:")):
            json = msg.split(":", 1)[1]
            self.edit_layer.emit(json)
        elif (msg.startswith("get_view")):
            self.get_view.emit()
        elif (msg.startswith("edit_view:")):
            json = msg.split(":", 1)[1]
            self.edit_view.emit(json)
        elif (msg.startswith("selection:")):
            json = msg.split(":", 1)[1]
            self.selection.emit(json)
        elif (msg.startswith("select_by_color:")):
            json = msg.split(":", 1)[1]
            self.select_by_color.emit(json)
        elif (msg.startswith("get_filters")):
            self.get_filters.emit()
        elif (msg.startswith("get_filter_properties:")):
            json = msg.split(":", 1)[1]
            self.get_filter_properties.emit(json)
        elif (msg.startswith("get_resources")):
            json = msg.split(":", 1)[1]
            self.get_resources.emit(json)
        elif (msg.startswith("draw_line:")):
            json = msg.split(":", 1)[1]
            self.draw_line.emit(json)
        elif (msg.startswith("draw_line_path:")):
            json = msg.split(":", 1)[1]
            self.draw_line.emit(json)
        elif (msg.startswith("draw_cubic_line:")):
            points = msg.split(":", 1)[1]
            self.draw_cubic_line.emit(points)
        elif (msg.startswith("get_canvas_image")):
            self.get_canvas_image.emit()
        elif (msg.startswith("get_layer_image:")):
            json = msg.split(":", 1)[1]
            self.get_layer_image.emit(json)
        elif (msg.startswith("doc_wait_for_done")):
            self.doc_wait_for_done.emit()

    @pyqtSlot()
    def startListening(self):
        ip: QHostAddress = QHostAddress(gethostbyname(gethostname()))
        port = self.port or randint(9999,pow(2,16))
        self.port = port

        def handler(ws: ServerConnection) -> None:
            self.client = True
            self.connection = ws
            self.clientConnected.emit()
            for msg in ws:
                self.clientMessageReceived.emit(msg)
            self.clientDisconnected.emit()
            self.client = False

        self.server = serve(handler, "0.0.0.0", self.port)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.start()

        if (self.server_thread.is_alive()):
            self.serverListening.emit("ws://{}:{}".format(ip.toString(),str(port)))
        else:
            self.serverStopped.emit()

    @pyqtSlot()
    def stopListening(self):
        if (self.server_thread and self.server_thread.is_alive()):
            assert self.server
            assert self.client
            assert self.connection
            self.server.shutdown()
            self.connection.close()
            self.serverStopped.emit()
            self.server = None

    @pyqtProperty(str)
    def address(self) -> str | None:
        if (self.server_thread and self.server_thread.is_alive()):
            return "ws://{}:{}/".format(gethostbyname(gethostname()), self.port)
        else:
            return None

    def sendMessage(self, message: str) -> None:
        """Send a message to the connected client."""
        if self.client and self.connection:
            self.connection.send(message)

    def connectClientSignals(self, listener: ClientListener) -> None:
        self.clientMessageReceived.connect(listener.onClientMessage)
        self.clientConnected.connect(listener.onClientConnected)
        self.clientDisconnected.connect(listener.onClientDisconnected)
        
    def connectServerSignals(self, listener: ServerListener) -> None:
        self.serverListening.connect(listener.onServerListening)
        self.serverStopped.connect(listener.onServerStopped)
        