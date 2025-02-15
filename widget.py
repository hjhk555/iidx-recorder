from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from typing import List

class MaskWheelComboBox(QComboBox):
    def wheelEvent(self, e, QWheelEvent=None):
        pass

def new_label(text='', fixed=True, font='Arial', font_size=10, alignment=Qt.AlignCenter) -> QLabel:
    label = QLabel(text)
    label.setFont(QFont(font, font_size))
    label.setAlignment(alignment)
    label.adjustSize()
    label.setFixedHeight(label.height())
    if fixed:
        label.setFixedWidth(label.width())
    label.setScaledContents(True)
    return label

def new_layout_labeled_combo(text, combo: QComboBox = None, editable = True) -> tuple[QLayout, QComboBox]:
    layout = QHBoxLayout()
    layout.addWidget(new_label(text))
    if combo is None:
        combo = MaskWheelComboBox()
    if editable:
        combo.setEditable(True)
        combo.completer().setCompletionMode(0)
        combo.completer().setFilterMode(Qt.MatchContains)
    layout.addWidget(combo)
    return layout, combo

def add_widget_to_list(widget: QWidget, list: QListWidget) -> QListWidgetItem:
    item = QListWidgetItem()
    item.setSizeHint(widget.sizeHint())
    list.addItem(item)
    list.setItemWidget(item, widget)
    return item

class ColoredComboBox(MaskWheelComboBox):
    def __init__(self, parent = None):
        super().__init__(parent)

        self.font_color: List[QColor] = []

        self.currentIndexChanged.connect(lambda x: self.change_selected_color())
    def addColoredItem(self, text: str, font_color: QColor = QColor('black')):
        self.font_color.append(font_color)
        super().addItem(text)
        i = self.count()-1
        idx = self.model().index(i, 0)
        self.model().setData(idx, self.font_color[i], Qt.ForegroundRole)
    def clear(self):
        super().clear()
        self.font_color.clear()
    def change_selected_color(self):
        if self.count()==0:
            return
        i = self.currentIndex()
        font = self.font_color[i]
        self.setStyleSheet(f'color:rgb({font.getRgb()[0]},{font.getRgb()[1]},{font.getRgb()[2]})')

class DynamicWidgetDisplay(QWidget):
    def __init__(self):
        super().__init__()

        layout_main = QVBoxLayout()
        self.setLayout(layout_main)

        self.button_layout = QHBoxLayout()
        self.button_layout.setAlignment(Qt.AlignLeft)
        self.button_group = QButtonGroup(self)  # 创建按钮组
        self.button_group.setExclusive(True)    # 设置互斥

        self.stacked_widget = QStackedWidget()  # 用于切换显示的Widget

        layout_main.addLayout(self.button_layout)
        layout_main.addWidget(self.stacked_widget)
    def add_button_and_widget(self, button_text, widget) -> QPushButton:
        """添加按钮和对应的Widget"""
        # 创建按钮
        button = QPushButton(button_text)
        button.adjustSize()
        button.setFixedWidth(button.width())
        button.setCheckable(True)  # 设置为可选中
        self.button_group.addButton(button)
        self.button_layout.addWidget(button)
        self.stacked_widget.addWidget(widget)

        # 连接按钮点击事件
        button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(
            self.button_group.buttons().index(button)
        ))
        return button
    def show_widget(self, index: int):
        if index >= len(self.button_group.buttons()):
            return
        self.button_group.buttons()[index].setChecked(True)
        self.stacked_widget.setCurrentIndex(index)