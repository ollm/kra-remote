from typing import Any
from krita import Extension, Selection, QByteArray, ManagedColor, Palette, Preset, InfoObject, Krita as ApiKrita # type: ignore
from PyQt5.QtCore import pyqtProperty, pyqtSlot, QEvent, Qt, QPoint, QPointF, QBuffer, QIODevice
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QKeyEvent, QIcon, QPainterPath, QImage
from PyQt5.QtGui import QColor
from .connection import SocketServer
from .api_krita import Krita
from .api_krita.enums import Tool
from .connection.web_server import WebServer
import base64
import json
import time
import gzip

class KritaRemoteExtension(Extension):

    _socket: SocketServer
    _server: WebServer
    _canvas: Any

    def __init__(self, parent):
        super().__init__(parent)

        print("KritaRemoteExtension init")

        # self.setup();

    def onClientConnected(self):
        pass
            
    def onClientDisconnected(self):
        pass

    def onClientMessage(self):
        pass

    def setup(self):
        self._socket = SocketServer()
        self._socket.port = 49120; # use always the same port
        self._socket.action.connect(self.action)
        self._socket.press.connect(self.press)
        self._socket.release.connect(self.release)
        self._socket.tool.connect(self.tool)
        self._socket.new_doc.connect(self.new_doc)
        self._socket.set_color_space.connect(self.set_color_space)
        self._socket.set_layer_color_space.connect(self.set_layer_color_space)
        self._socket.refresh_projection.connect(self.refresh_projection)
        self._socket.resize.connect(self.resize)
        self._socket.save_as.connect(self.save_as)
        self._socket.get_doc_info.connect(self.get_doc_info)
        self._socket.get_layers.connect(self.get_layers)
        self._socket.add_layer.connect(self.add_layer)
        self._socket.select_layer.connect(self.select_layer)
        self._socket.remove_layer.connect(self.remove_layer)
        self._socket.remove_layers.connect(self.remove_layers)
        self._socket.edit_layer.connect(self.edit_layer)
        self._socket.get_view.connect(self.get_view)
        self._socket.edit_view.connect(self.edit_view)
        self._socket.selection.connect(self.selection)
        self._socket.select_by_color.connect(self.select_by_color)
        self._socket.get_filters.connect(self.get_filters)
        self._socket.get_filter_properties.connect(self.get_filter_properties)
        self._socket.get_resources.connect(self.get_resources)
        self._socket.draw_line.connect(self.draw_line)
        self._socket.draw_line_path.connect(self.draw_line_path)
        self._socket.draw_cubic_line.connect(self.draw_cubic_line)
        self._socket.get_canvas_image.connect(self.get_canvas_image)
        self._socket.get_layer_image.connect(self.get_layer_image)
        self._socket.doc_wait_for_done.connect(self.doc_wait_for_done)

        self._server = WebServer()

        # Start server inmediately
        self._socket.connectClientSignals(self)
        self._socket.startListening()

    def createActions(self, window):
        pass

    @pyqtProperty(SocketServer)
    def socket(self) -> SocketServer:
        return self._socket

    @pyqtProperty(WebServer)
    def server(self) -> WebServer:
        return self._server

    @pyqtSlot()
    def send_done(self):

        server = self._socket;
        server.sendMessage(f"done")

    @pyqtSlot()
    def doc_wait_for_done(self):

        doc = Krita.instance.activeDocument()
        if doc:
            doc.waitForDone()

        # Krita.instance.activeWindow().activeView().showFloatingMessage(
        #    f"Document operations completed", QIcon(), 2000, 2)

        server = self._socket;
        server.sendMessage(f"doc_done")

    @pyqtSlot(str)
    def press(self, key: str):
        if self._canvas:
            press = QKeyEvent(QEvent.KeyPress, getattr(Qt, key), Qt.NoModifier)
            if not self._canvas.isActiveWindow():
                self._canvas.activateWindow()
            QApplication.sendEvent(self._canvas, press)

        self.send_done()

    @pyqtSlot(str)
    def release(self, key: str):
        if self._canvas:
            release = QKeyEvent(QEvent.KeyRelease, getattr(Qt, key), Qt.NoModifier)
            if not self._canvas.isActiveWindow():
                self._canvas.activateWindow()
            QApplication.sendEvent(self._canvas, release)

        self.send_done()

    @pyqtSlot(str)
    def action(self, action_name: str):
        Krita.trigger_action(action_name)
        self.send_done()

    @pyqtSlot(str)
    def tool(self, tool_name: str):
        Krita.active_tool = Tool(tool_name)
        self.send_done()

    @pyqtSlot(str)
    def get_layer(self, data: Any = None, activeLayer: bool = False):

        name = data.get('name', None)
        index = data.get('index', None)

        doc = Krita.instance.activeDocument()
        root = doc.rootNode()

        layers = self._get_layers(root, multidimension = False);

        for key, value in layers.items():
            if value["name"] == name or value["index"] == index:
                return value["node"]

        if activeLayer:
            return doc.activeNode()

        return None

    @pyqtSlot(str)
    def match_layer(self, layer1, layer2):

        if layer1.name() == layer2.name() and layer1.index() == layer2.index():
            return True

        return False


    @pyqtSlot(str)
    def new_doc(self, _json: str):

        data = json.loads(_json)

        width = data.get("width", 800)
        height = data.get("height", 600)
        name = data.get("name", "Untitled")
        resolution = data.get("resolution", 300)
        colorModel = data.get("colorModel", "RGBA")
        colorDepth = data.get("colorDepth", "U8")

        current_doc = Krita.instance.activeDocument()

        doc = Krita.instance.createDocument(width, height, name, colorModel, colorDepth, "", resolution)
        Krita.instance.activeWindow().addView(doc)
        # Krita.instance.setActiveDocument(doc)

        if data.get("closeCurrent"):
            if current_doc:
                current_doc.close()

        self.send_done()

    @pyqtSlot(str)
    def set_color_space(self, _json: str):

        data = json.loads(_json)

        colorModel = data.get("colorModel", "RGBA")
        colorDepth = data.get("colorDepth", "U8")

        profiles = Krita.instance.profiles(colorModel, colorDepth)
        colorProfile = profiles[0]

        doc = Krita.instance.activeDocument()
        doc.setColorSpace(colorModel, colorDepth, colorProfile)

        self.send_done()

    @pyqtSlot(str)
    def set_layer_color_space(self, _json: str):

        data = json.loads(_json)

        layer = self.get_layer(data)

        if not layer:
            self.send_done()
            return

        colorModel = data.get("colorModel", "RGBA")
        colorDepth = data.get("colorDepth", "U8")

        profiles = Krita.instance.profiles(colorModel, colorDepth)
        colorProfile = profiles[0]

        layer.setColorSpace(colorModel, colorDepth, colorProfile)

        self.send_done()

    @pyqtSlot()
    def refresh_projection(self):

        doc = Krita.instance.activeDocument()

        if doc:
            doc.refreshProjection()

        doc.waitForDone()

        self.send_done()

    @pyqtSlot(str)
    def resize(self, _json: str):

        data = json.loads(_json)

        width = data.get("width", 800)
        height = data.get("height", 600)

        doc = Krita.instance.activeDocument()

        if doc and not data.get("scale", False):
            doc.resizeImage(0, 0, width, height)

        if doc and data.get("scale", False):
            doc.scaleImage(width, height, 300, 300, "Box")

        doc.waitForDone()
        self.send_done()

    @pyqtSlot(str)
    def save_as(self, _json: str):

        data = json.loads(_json)
        filename = data.get("filename", "")

        doc = Krita.instance.activeDocument()

        if doc and filename:
            doc.saveAs(filename)

        doc.waitForDone()
        self.send_done()

    @pyqtSlot()
    def get_doc_info(self):

        server = self._socket;

        doc = Krita.instance.activeDocument()

        info = {
            "width": doc.width(),
            "height": doc.height(),
            "resolution": doc.resolution(),
            "colorModel": doc.colorModel(),
            "colorDepth": doc.colorDepth(),
            "numberOfLayers": len(doc.topLevelNodes()),
            "activeLayer": doc.activeNode().name() if doc.activeNode() else None,
        }

        server.sendMessage(f"doc_info:{info}")

    @pyqtSlot()
    def _get_layers(self, node, multidimension: bool = True):

        layers = {}

        for child in node.childNodes():

            children = self._get_layers(child, multidimension);

            layers[child.name()] = {
                "node": child,
                "name": child.name(),
                "type": child.type(),
                "index": child.index(),
                "children": children,
            }

            if not multidimension:
                for key, value in children.items():
                    layers[key] = value

        return layers

    @pyqtSlot()
    def _get_layers_serialization(self, node, multidimension: bool = True):

        layers = {}

        for child in node.childNodes():

            children = self._get_layers_serialization(child, multidimension);

            layers[child.name()] = {
                "name": child.name(),
                "type": child.type(),
                "index": child.index(),
                "children": children,
            }

            if not multidimension:
                for key, value in children.items():
                    layers[key] = value

        return layers

    @pyqtSlot()
    def get_layers(self):

        server = self._socket;

        doc = Krita.instance.activeDocument()
        root = doc.rootNode()

        layers = self._get_layers_serialization(root)

        server.sendMessage(f"layers:{layers}")

    @pyqtSlot(str)
    def add_layer(self, _json: str):

        data = json.loads(_json)
        inside = self.get_layer(data.get("inside", {}))
        above = self.get_layer(data.get("above", {}))
        below = self.get_layer(data.get("below", {}))

        doc = Krita.instance.activeDocument()
        root = doc.rootNode()

        if below:
            above = self.get_layer({"index": below.index() - 1})

        new_layer = None

        if data.get("filter"):

            _filter = Krita.instance.filter(data["filter"])
            new_layer = doc.createFilterMask(data["name"], _filter, inside)

            #if layer:
            #    layer.addChildNode(new_layer, None)

        elif data.get("fill"):

            selection = Selection();
            selection.select(0, 0, doc.width(), doc.height(), 255)

            info = InfoObject();

            for key, value in data.get("properties", {}).items():
                info.setProperty(key, value)

            new_layer = doc.createFillLayer(data["name"], data["fill"], info, selection)

        elif data.get("clone"):

            source_layer = self.get_layer(data.get("clone", {}))

            if source_layer:
                new_layer = source_layer.clone()
                new_layer.setName(data["name"])

        else:
            new_layer = doc.createNode(data["name"], data["type"])

        self._edit_layer(new_layer, data)

        if inside:
            inside.addChildNode(new_layer, above)
        elif not data.get("filter"):
            root.addChildNode(new_layer, above)

        doc.waitForDone()
        self.send_done()

    @pyqtSlot(str)
    def select_layer(self, _json: str):

        data = json.loads(_json)
        layer = self.get_layer(data)

        if layer:
            doc = Krita.instance.activeDocument()
            doc.setActiveNode(layer)
            doc.waitForDone()

        self.send_done()

    @pyqtSlot(str)
    def remove_layer(self, _json: str):

        data = json.loads(_json)
        layer = self.get_layer(data)

        if layer:
            layer.parentNode().removeChildNode(layer)

        doc = Krita.instance.activeDocument()
        doc.waitForDone()
        self.send_done()

    @pyqtSlot(str)
    def remove_layers(self, _json: str):

        layers = json.loads(_json)

        for layer_data in layers:

            layer = self.get_layer(layer_data)

            if layer:
                layer.parentNode().removeChildNode(layer)

        doc = Krita.instance.activeDocument()
        doc.waitForDone()
        self.send_done()

    @pyqtSlot(str)
    def edit_layer(self, _json: str):

        data = json.loads(_json)
        layer = self.get_layer(data, True)

        self._edit_layer(layer, data)
        self.send_done()

    @pyqtSlot(str)
    def _edit_layer(self, layer, data: dict):

        if layer and layer.type() in ["filtermask"] and data.get("properties"):

            _filter = layer.filter()
            config = _filter.configuration()

            for key, value in data.get("properties", {}).items():
                config.setProperty(key, value)

            _filter.setConfiguration(config)

        """
        if layer and layer.type() in ["filllayer"] and data.get("properties"):

            _filter = layer.filter()
            config = _filter.configuration()

            for key, value in data.get("properties", {}).items():
                config.setProperty(key, value)

            _filter.setConfiguration(config)
        """

        if data.get("blendingMode"):
            layer.setBlendingMode(data.get("blendingMode"))

        if data.get("opacity"):
            layer.setOpacity(data.get("opacity"))

        if data.get("locked") or data.get("locked") == False:
            layer.setLocked(data.get("locked"))

        if data.get("visible") or data.get("visible") == False:
            layer.setVisible(data.get("visible"))

        if data.get("rename"):
            layer.setName(data.get("rename"))

        if data.get("useEdgeDetection") or data.get("useEdgeDetection") == False:
            layer.setUseEdgeDetection(data.get("useEdgeDetection"))

        if data.get("edgeDetectionSize"):
            layer.setEdgeDetectionSize(data.get("edgeDetectionSize"))

        if data.get("cleanUpAmount"):
            layer.setCleanUpAmount(data.get("cleanUpAmount"))

        if data.get("limitToDeviceBounds") or data.get("limitToDeviceBounds") == False:
            layer.setLimitToDeviceBounds(data.get("limitToDeviceBounds"))

        if data.get("updateMask"):
            layer.updateMask(True)

        doc = Krita.instance.activeDocument()
        doc.waitForDone()

    @pyqtSlot(str)
    def rgba_to_managed_color(self, _rgba: dict) -> ManagedColor:

        r = _rgba.get("r", 0)
        g = _rgba.get("g", 0)
        b = _rgba.get("b", 0)
        a = _rgba.get("a", 255)

        color = ManagedColor("RGBA", "U8", "")

        components = [
            b / 255.0,
            g / 255.0,
            r / 255.0,
            a / 255.0,
        ]

        color.setComponents(components)

        return color

    @pyqtSlot()
    def get_view(self):

        server = self._socket;

        view = Krita.instance.activeWindow().activeView()

        info = {
            "foregroundColor": {},
            "backgroundColor": {},
            "brushSize": view.brushSize(),
            "patternSize": view.patternSize(),
            "paintingOpacity": view.paintingOpacity(),
            "paintingFlow": view.paintingFlow(),
            "disablePressure": view.disablePressure(),
            "currentPattern": view.currentPattern().name() if view.currentPattern() else None,
            "currentBrushPreset": view.currentBrushPreset().name() if view.currentBrushPreset() else None,
            "currentGradient": view.currentGradient().name() if view.currentGradient() else None,
            "currentBlendingMode": view.currentBlendingMode(),
        }

        fg = view.foregroundColor()
        fg_components = fg.components()
        info["foregroundColor"] = {
            "r": round(fg_components[2] * 255, 3),
            "g": round(fg_components[1] * 255),
            "b": round(fg_components[0] * 255),
            "a": round(fg_components[3] * 255),
        }

        bg = view.backgroundColor()
        bg_components = bg.components()
        info["backgroundColor"] = {
            "r": round(bg_components[2] * 255, 3),
            "g": round(bg_components[1] * 255),
            "b": round(bg_components[0] * 255),
            "a": round(bg_components[3] * 255),
        }

        server.sendMessage(f"view:{info}")

    @pyqtSlot(str)
    def edit_view(self, _json: str):

        data = json.loads(_json)
        self._edit_view(data)

        doc = Krita.instance.activeDocument()
        doc.waitForDone()

        self.send_done()

    @pyqtSlot(str)
    def _edit_view(self, data: dict):

        view = Krita.instance.activeWindow().activeView()

        if data.get("foregroundColor"):
            view.setForeGroundColor(self.rgba_to_managed_color(data.get("foregroundColor", {})))

        if data.get("backgroundColor"):
            view.setBackGroundColor(self.rgba_to_managed_color(data.get("backgroundColor", {})))

        if data.get("brushSize"):
            view.setBrushSize(data.get("brushSize"))

        if data.get("patternSize"):
            view.setPatternSize(data.get("patternSize"))

        if data.get("paintingOpacity"):
            view.setPaintingOpacity(data.get("paintingOpacity"))

        if data.get("paintingFlow"):
            view.setPaintingFlow(data.get("paintingFlow"))

        if data.get("disablePressure"):
            view.setDisablePressure(data.get("disablePressure"))

        if data.get("currentPattern"):
            view.setCurrentPattern(self.get_resource("pattern", data.get("currentPattern", "")))

        if data.get("currentBrushPreset"):
            view.setCurrentBrushPreset(self.get_resource("preset", data.get("currentBrushPreset", "")))

        if data.get("currentGradient"):
            view.setCurrentGradient(self.get_resource("gradient", data.get("currentGradient", "")))

        if data.get("currentBlendingMode"):
            view.setCurrentBlendingMode(data.get("currentBlendingMode"))


    @pyqtSlot(str)
    def selection(self, gzip_b64: str):

        try:

            compressed = base64.b64decode(gzip_b64)
            _json = gzip.decompress(compressed)

            # _json = [b, g, r, a, b, g, r, a, ...]
            data = json.loads(_json)

            doc = Krita.instance.activeDocument()
            width = doc.width()
            height = doc.height()

            selection = Selection()
            selection.select(0, 0, width, height, 0)

            selPixelData = bytearray(data)
            selection.setPixelData(QByteArray(selPixelData), 0, 0, width, height)

            doc.setSelection(selection)
            
        except Exception as e:
            Krita.instance.activeWindow().activeView().showFloatingMessage(
                f"Error setting selection: {str(e)}", QIcon(), 6000, 1)

        self.send_done()

    @pyqtSlot(str)
    def select_by_color(self, _json: str):

        data = json.loads(_json)

        r = data.get("r", 0)
        g = data.get("g", 0)
        b = data.get("b", 0)
        a = data.get("a", 255)

        doc = Krita.instance.activeDocument()
        node = doc.activeNode()
        width = doc.width()
        height = doc.height()

        selection = Selection()
        selection.select(0, 0, width, height, 0)
        selPixelData = bytearray(selection.pixelData(0, 0, width, height))

        pixelData = bytearray(node.pixelData(0, 0, width, height))

        ts = time.time()
        nbMatching = 0
        offset = 0
        
        target_color = (b, g, r, a)
        
        """
        r = range(0, len(pixelData), 4)
        for i in r:
            if (pixelData[i], pixelData[i+1], pixelData[i+2], pixelData[i+3]) == target_color:
                nbMatching += 1
                selPixelData[offset] = 255
            offset += 1
        """

        r = range(0, len(pixelData), 4)
        for i in r:
            if pixelData[i] == b and pixelData[i+1] == g and pixelData[i+2] == r and pixelData[i+3] == a:
                nbMatching += 1
                selPixelData[offset] = 255
            offset += 1

        selection.setPixelData(QByteArray(selPixelData), 0, 0, width, height)

        doc.setSelection(selection)

        Krita.instance.activeWindow().activeView().showFloatingMessage(
            f"Nb pixels analyzed {offset} matching {nbMatching}, duration {round(time.time()-ts, 4)}s, first pixel colors RGBA({pixelData[0]},{pixelData[1]},{pixelData[2]},{pixelData[3]})", QIcon(), 4000, 1)

        self.send_done()

    @pyqtSlot()
    def get_filters(self):

        server = self._socket;
        filters = {}

        for key in Krita.instance.filters():
            filters[key] = key

        # Send the filter properties
        server.sendMessage(f"filters:{filters}")

    @pyqtSlot(str)
    def _filter(self, filter_name: str):

        server = self._socket;

        doc = Krita.instance.activeDocument()
        node = doc.activeNode()

        if node.type() in ["transparencymask", "filtermask", "transformmask", "selectionmask", "colorizemask"]:

            # get filter object
            _filter = node.filter()
            config = _filter.configuration()

            config.setProperty("pattern", "dot")
            config.setProperty("size", 12.0)

            _filter.setConfiguration(config)
           # node.setFilter(_filter)

            # print configuration
            # print(_filter, _filter.name(), config.properties())

            Krita.instance.activeWindow().activeView().showFloatingMessage(
                            f"test_filter:{filter_name}:{_filter.name()}", QIcon(), 6000, 1)

            server.sendMessage(f"test_filter:{filter_name}:{_filter.name()}")

        else:

            # create filter
            _filter = Krita.instance.filter(filter_name)

            config = _filter.configuration()

            config.setProperty("mode", "alpha")
            config.setProperty("pattern", "dot")
            config.setProperty("size", 12.0)

            _filter.setConfiguration(config)

            # create filter mask from filter and use cloned layer as selection source 
            filterMask = doc.createFilterMask("Filter", _filter, node)

            # add filter mask to clone layer
            node.addChildNode(filterMask, None)

            Krita.instance.activeWindow().activeView().showFloatingMessage(
                            f"Active layer is not a filter mask", QIcon(), 6000, 1)

            server.sendMessage(f"error:Active layer is not a filter mask")

        # doc.refreshProjection()
        # app.processEvents()

    @pyqtSlot(str)
    def get_filter_properties(self, _json: str):

        data = json.loads(_json)
        server = self._socket;

        layer = self.get_layer(data, False)

        if layer:
            select_filter = layer.filter()
        else:
            select_filter = Krita.instance.filter(data.get("filter", ""))

        config = select_filter.configuration();

        """
        properties = [];

        for key in config.properties():
            properties.append(f"{key},{config.property(key)}")
        """

        # Send the filter properties
        server.sendMessage(f"filter_properties:{select_filter.name()}:{config.properties()}")

    @pyqtSlot(str, str)
    def get_resource(self, type: str, name: str):

        resources = Krita.instance.resources(type)
        resource = None

        for (key, value) in resources.items():
            if key == name:
                resource = value
                break

        return resource

    @pyqtSlot(str)
    def get_resources(self, _json: str):

        server = self._socket

        data = json.loads(_json)
        type = data.get("type", "palette")

        resources = Krita.instance.resources(type == "preset_xml" and "preset" or type)

        _resources = {}

        if type == "palette":

            for (key, value) in resources.items():

                palette = Palette(value)
                _palette = []

                for index in range(palette.numberOfEntries()):

                    entry = palette.entryByIndex(index)
                    color = entry.color()
                    components = color.components()

                    _palette.append({
                        "index": index,
                        "name": entry.name(),
                        "id": entry.id(),
                        "spotColor": entry.spotColor(),
                        "filename": value.filename(),
                        "color": {
                            "r": round(components[2] * 255, 3),
                            "g": round(components[1] * 255),
                            "b": round(components[0] * 255),
                            "a": round(components[3] * 255),
                            "depth": color.colorDepth(),
                        }
                    })

                _resources[key] = _palette

        elif type == "preset":

            for (key, value) in resources.items():

                preset = Preset(value)
                _resources[key] = {
                    "name": value.name(),
                    "filename": value.filename(),
                }

        elif type == "preset_xml":

            for (key, value) in resources.items():

                preset = Preset(value)
                _resources[key] = {
                    "name": value.name(),
                    "filename": value.filename(),
                    "xml": preset.toXML(),
                }

        else:

            for (key, value) in resources.items():
                _resources[key] = {
                    "name": value.name(),
                    "filename": value.filename(),
                }

        server.sendMessage(f"resources:{_resources}")

    @pyqtSlot(str)
    def draw_line(self, _json: str):

        data = json.loads(_json)
        layer = self.get_layer(data, True)

        if layer is None:
            self.send_done()
            return

        try:

            doc = Krita.instance.activeDocument()

            for line in data.get("lines", []):

                points = line.get("points", [])
                one = QPoint(int(points[0]), int(points[1]))
                two = QPoint(int(points[2]), int(points[3]))

                #one = QPointF(float(points[0]), float(points[1]))
                #two = QPointF(float(points[2]), float(points[3]))

                pressure_one = line.get("pressureOne", 1.0)
                pressure_two = line.get("pressureTwo", 1.0)

                layer.paintLine(one, two, pressure_one, pressure_two)

            doc.waitForDone()

        except Exception as e:
            Krita.instance.activeWindow().activeView().showFloatingMessage(
                f"Error drawing line: {str(e)}", QIcon(), 6000, 1)

        self.send_done()

    @pyqtSlot(str)
    def draw_line_path(self, _json: str):

        data = json.loads(_json)
        layer = self.get_layer(data, True)

        if layer is None:
            self.send_done()
            return

        try:
            points = []
            for pair in data.get("points", []):
                x, y = float(pair[0]), float(pair[1])
                points.append(QPointF(x, y))
            
            if len(points) < 2:
                Krita.instance.activeWindow().activeView().showFloatingMessage(
                    "Need at least 2 points to draw a line", QIcon(), 6000, 1)
                return

            doc = Krita.instance.activeDocument()
            
            # Create a QPainterPath to draw the line through all points
            path = QPainterPath()
            path.moveTo(points[0])
            
            # Add lines to each subsequent point
            for i in range(1, len(points)):
                path.lineTo(points[i])
            
            # Paint the path on the node using Krita's paintPath API
            # This uses the current brush settings (size, opacity, flow, preset)
            layer.paintPath(path)
            doc.waitForDone()
            
        except Exception as e:
            Krita.instance.activeWindow().activeView().showFloatingMessage(
                f"Error drawing line: {str(e)}", QIcon(), 6000, 1)

        self.send_done()

    @pyqtSlot(str)
    def draw_cubic_line(self, _json: str):

        data = json.loads(_json)
        layer = self.get_layer(data, True)

        if layer is None:
            self.send_done()
            return

        try:
            # Parse points from the string
            points = []
            for pair in data.get("points", []):
                x, y = float(pair[0]), float(pair[1])
                points.append(QPointF(x, y))
            if len(points) < 4 or (len(points) - 1) % 3 != 0:
                Krita.instance.activeWindow().activeView().showFloatingMessage(
                    "Need at least 4 points and (number of points - 1) must be divisible by 3 to draw cubic Bezier curves", QIcon(), 6000, 1)
                return

            doc = Krita.instance.activeDocument()

            # Create a QPainterPath to draw the cubic Bezier curves
            path = QPainterPath()
            path.moveTo(points[0])

            # Add cubic Bezier curves
            for i in range(1, len(points), 3):
                if i + 2 < len(points):
                    path.cubicTo(points[i], points[i + 1], points[i + 2])

            # Paint the path on the node using Krita's paintPath API
            layer.paintPath(path)
            doc.waitForDone()
            
        except Exception as e:
            Krita.instance.activeWindow().activeView().showFloatingMessage(
                f"Error drawing cubic line: {str(e)}", QIcon(), 6000, 1)

        self.send_done()


    @pyqtSlot()
    def get_canvas_image(self):

        server = self._socket;

        """Get the full canvas image and send it via websocket."""
        try:
            # Get the active document
            doc = Krita.instance.activeDocument()
            if doc is None:
                server.sendMessage("error:No active document")
                return
            
            # Get pixel data for the entire canvas
            qimage = doc.projection()

            root = doc.rootNode()
            width = doc.width()
            height = doc.height()

            # Forces a true composited render
            pixel_data = root.projectionPixelData(0, 0, width, height)

            qimage = QImage(pixel_data, width, height, QImage.Format_ARGB32).copy()

            # Convert QImage to base64 encoded PNG
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            qimage.save(buffer, "PNG")
            buffer.close()
            
            image_base64 = base64.b64encode(buffer.data()).decode('utf-8')
            
            # Send the image data
            server.sendMessage(f"canvas_image:{image_base64}")
            
            # Krita.instance.activeWindow().activeView().showFloatingMessage(
            #     f"Canvas image sent ({width}x{height})", QIcon(), 1000, 2)

            del pixel_data
            del qimage
            del buffer

        except Exception as e:
            server.sendMessage(f"error:{str(e)}")
            Krita.instance.activeWindow().activeView().showFloatingMessage(
                f"Error getting canvas image: {str(e)}", QIcon(), 6000, 1)

    @pyqtSlot(str)
    def get_layer_image(self, _json: str):

        server = self._socket;

        data = json.loads(_json)
        layer = self.get_layer(data, True)

        if layer is None:
            server.sendMessage("error:Layer not found")
            return

        try:

            doc = Krita.instance.activeDocument()

            # Get the bounds of the layer
            """
            bounds = node.bounds()
            x = bounds.x()
            y = bounds.y()
            width = bounds.width()
            height = bounds.height()

            # Get pixel data for the layer
            if include_mask:
                pixel_data = node.projectionPixelData(x, y, width, height)
            else:
                pixel_data = node.pixelData(x, y, width, height)

            """

            width = doc.width()
            height = doc.height()

            # Get pixel data for the layer
            if data.get("includeMask", False):
                pixel_data = layer.projectionPixelData(0, 0, width, height)
            else:
                pixel_data = layer.pixelData(0, 0, width, height)
            
            # Convert to QImage
            qimage = QImage(pixel_data, width, height, QImage.Format_ARGB32).copy()
            
            # Convert QImage to base64 encoded PNG
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            qimage.save(buffer, "PNG")
            buffer.close()
            
            image_base64 = base64.b64encode(buffer.data()).decode('utf-8')
            
            # Send the image data with layer info
            server.sendMessage(f"layer_image:{width},{height}:{image_base64}")

            del pixel_data
            del qimage
            del buffer


            # Krita.instance.activeWindow().activeView().showFloatingMessage(
            #     f"Layer '{node.name()}' image sent ({width}x{height})", QIcon(), 1000, 2)
 
        except Exception as e:
            server.sendMessage(f"error:{str(e)}")
            Krita.instance.activeWindow().activeView().showFloatingMessage(
                f"Error getting layer image: {str(e)}", QIcon(), 6000, 1)