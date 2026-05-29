# main.py
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget, 
                             QFrame, QListWidget, QListWidgetItem, QStatusBar)
from PyQt6.QtCore import Qt, QSize, QPoint
from core.database import initialize_database
from core.dynamic_loader import ModuleLoader
from auth import AuthDialog

import sys
import os

# 解决 PyInstaller 打包后动态加载 importlib 找不到路径的问题
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    if bundle_dir not in sys.path:
        sys.path.append(bundle_dir)
    # 确保把当前执行文件所在目录也加入环境变量
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir not in sys.path:
        sys.path.append(exe_dir)
class MainApplication(QMainWindow):
    def __init__(self, username):
        super().__init__()
        self.current_user = username
        self.drag_position = QPoint()
        
        # 1. 核心设置：隐藏 Windows 原生标题栏（解决双标题问题）
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        self.resize(1280, 800)
        
        # 统一全局暗黑科技感样式表 (QSS)
        self.apply_global_theme()
        self.init_ui()

    def init_ui(self):
        # 核心承载窗口
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 2. 顶置综合状态栏（还原初代扁平化排版，融入无边框控制组）
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_bar.setFixedHeight(65)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)

        # 标题组
        title_layout = QVBoxLayout()
        title_layout.setSpacing(1)
        lbl_title = QLabel("公路路基压实度实时监测与薄弱区识别系统")
        lbl_title.setStyleSheet("color: #f8fafc; font-size: 17px; font-weight: bold; font-family: 'Microsoft YaHei';")
        lbl_sub = QLabel("HIGHWAY SUBGRADE COMPACTION REAL-TIME MONITORING & ANOMALY DETECTION SYSTEM")
        lbl_sub.setStyleSheet("color: #0ea5e9; font-size: 8px; font-weight: bold; letter-spacing: 1px; font-family: 'Consolas';")
        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_sub)
        top_layout.addLayout(title_layout)
        
        top_layout.addStretch()

        # 还原您最喜欢的初代：横向清爽遥测数据文字排版
        self.lbl_gnss_status = QLabel("📡 GNSS基站: 正常连接 (RTK 固定解)")
        self.lbl_satellite = QLabel("🛰 锁星数量: 15颗")
        self.lbl_com_status = QLabel("⚡ 压实总网关: 12.4 kb/s")
        for lbl in (self.lbl_gnss_status, self.lbl_satellite, self.lbl_com_status):
            lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: 'Microsoft YaHei';")
            top_layout.addWidget(lbl)
            top_layout.addSpacing(15)

        # 全息热重载按键
        btn_hot_reload = QPushButton("🔄 热重载模块")
        btn_hot_reload.setObjectName("BtnReload")
        btn_hot_reload.setFixedSize(110, 30)
        btn_hot_reload.clicked.connect(self.trigger_hot_reload)
        top_layout.addWidget(btn_hot_reload)
        top_layout.addSpacing(15)

        # 3. 核心增加：无边框窗口右上角控制按钮组（最小化、最大化、关闭）
        window_controls = QHBoxLayout()
        window_controls.setSpacing(2)
        
        btn_min = QPushButton("—")
        btn_min.setObjectName("BtnWinMin")
        btn_min.setFixedSize(28, 28)
        btn_min.clicked.connect(self.showMinimized)
        
        btn_max = QPushButton("❑")
        btn_max.setObjectName("BtnWinMax")
        btn_max.setFixedSize(28, 28)
        btn_max.clicked.connect(self.toggle_maximize_restore)
        
        btn_close = QPushButton("✕")
        btn_close.setObjectName("BtnWinClose")
        btn_close.setFixedSize(28, 28)
        btn_close.clicked.connect(self.close)

        window_controls.addWidget(btn_min)
        window_controls.addWidget(btn_max)
        window_controls.addWidget(btn_close)
        top_layout.addLayout(window_controls)

        main_layout.addWidget(top_bar)

        # 4. 中部主体区 (左侧导航栏 + 右侧功能栈)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # 左侧边导航面板
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 15, 10, 15)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")
        self.nav_list.setIconSize(QSize(20, 20))
        self.nav_list.setSpacing(6)

        # 配置 9 个核心业务菜单
        self.menus_config = [
            ("实时监控与采集", "monitoring", "RealtimeMonitorWidget"),
            ("压实遍数分析", "pass_count", "PassCountWidget"),
            ("质量评估(CMV)", "quality_eval", "QualityEvalWidget"),
            ("薄弱区识别预警", "weak_zone", "WeakZoneWidget"),
            ("历史数据与追溯", "history", "HistoryQueryWidget"),
            ("土质物理击实标准", "soil_standard", "SoilStandardWidget"),
            ("压实机具设备台账", "machinery", "MachineryWidget"),
            ("标段与施工段段落", "section_mgr", "SectionMgrWidget"),
            ("统计分析与概率分布", "analytics", "AnalyticsWidget")
        ]

        for title, _, _ in self.menus_config:
            item = QListWidgetItem(f" ⚙  {title}")
            item.setSizeHint(QSize(200, 42))
            self.nav_list.addItem(item)

        sidebar_layout.addWidget(self.nav_list)
        
        # 底部操作人员卡片
        operator_card = QFrame()
        operator_card.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px solid #1e293b; padding: 10px;")
        op_layout = QVBoxLayout(operator_card)
        lbl_user_title = QLabel("💻 当前授权操作员")
        lbl_user_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: bold;")
        lbl_user_val = QLabel(self.current_user)
        lbl_user_val.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: bold; font-family: Consolas;")
        op_layout.addWidget(lbl_user_title)
        op_layout.addWidget(lbl_user_val)
        sidebar_layout.addWidget(operator_card)

        body_layout.addWidget(sidebar)

        # 右侧模块堆叠工作区
        self.work_stack = QStackedWidget()
        self.work_stack.setObjectName("WorkArea")
        body_layout.addWidget(self.work_stack, stretch=1)

        main_layout.addLayout(body_layout)

        # 5. 底部状态栏（执行 HIDE 隐藏操作，使主界面更加紧凑专业）
        self.status_bar = QStatusBar()
        self.status_bar.setObjectName("StatusBar")
        self.setStatusBar(self.status_bar)
        self.status_bar.hide() # 直接隐藏状态栏

        # 初始化加载并连接切换槽
        self.load_all_modules()
        self.nav_list.currentRowChanged.connect(self.work_stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

    # ================= 5. 无边框窗口鼠标拖拽移动支持 =================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 仅允许在顶部状态栏区域（高 65px）内进行拖拽
            if event.position().y() < 65:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def toggle_maximize_restore(self):
        """最大化和恢复切换"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def load_all_modules(self):
        """利用热加载引擎初始化载入所有功能子窗口"""
        for _, module_name, class_name in self.menus_config:
            widget = ModuleLoader.load_module_widget(module_name, class_name, parent=self)
            self.work_stack.addWidget(widget)

    def trigger_hot_reload(self):
        """热更新模块触发：动态载入修改后的文件，同步至物理内存中"""
        curr_idx = self.work_stack.currentIndex()
        _, module_name, class_name = self.menus_config[curr_idx]
        
        # 重新加载模块
        new_widget = ModuleLoader.load_module_widget(module_name, class_name, parent=self)
        
        # 替换旧窗口
        old_widget = self.work_stack.widget(curr_idx)
        self.work_stack.removeWidget(old_widget)
        self.work_stack.insertWidget(curr_idx, new_widget)
        self.work_stack.setCurrentIndex(curr_idx)

    def apply_global_theme(self):
        """设定暗海科技蓝风格样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #090d16;
            }
            QFrame#TopBar {
                background-color: #0f172a;
                border-bottom: 1px solid #1e293b;
            }
            QFrame#Sidebar {
                background-color: #0b0f19;
                border-right: 1px solid #1e293b;
            }
            QStackedWidget#WorkArea {
                background-color: #090d16;
            }
            
            /* 导航栏 QListWidget 样式 */
            QListWidget#NavList {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget#NavList::item {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding-left: 10px;
                font-family: 'Microsoft YaHei';
                font-size: 12px;
            }
            QListWidget#NavList::item:hover {
                background-color: #0f172a;
                border-color: #38bdf8;
                color: #38bdf8;
            }
            QListWidget#NavList::item:selected {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                                   stop:0 #0284c7, stop:1 #0f172a);
                border-left: 3px solid #0ea5e9;
                color: #ffffff;
                font-weight: bold;
            }
            
            /* 霓虹重载按键 */
            QPushButton#BtnReload {
                background-color: transparent;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
                font-family: 'Microsoft YaHei';
            }
            QPushButton#BtnReload:hover {
                background-color: rgba(14, 165, 233, 0.1);
                border-color: #38bdf8;
                color: white;
            }
            
            /* 无边框窗口控制按钮 QSS */
            QPushButton#BtnWinMin, QPushButton#BtnWinMax, QPushButton#BtnWinClose {
                background: transparent;
                border: none;
                color: #64748b;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton#BtnWinMin:hover, QPushButton#BtnWinMax:hover {
                background-color: #1e293b;
                color: #38bdf8;
            }
            QPushButton#BtnWinClose:hover {
                background-color: #ef4444;
                color: white;
            }
        """)

def main():
    initialize_database()
    app = QApplication(sys.argv)
    
    auth = AuthDialog()
    if auth.exec() == AuthDialog.DialogCode.Accepted:
        window = MainApplication(auth.username)
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()