# auth.py
import hashlib
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox, QFrame, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QFont
from core.database import get_connection

class AuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_authenticated = False
        self.username = None
        
        # 拖拽窗口辅助变量
        self.drag_position = QPoint()

        # 初始化无边框与背景透明
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(450, 360)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 核心承载容器（实现圆角、渐变暗色背景与科技感边框）
        container = QFrame()
        container.setObjectName("Container")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(25, 20, 25, 30)
        
        # 窗口发光阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(14, 165, 233, 100)) # 科技蓝半透明发光
        shadow.setOffset(0, 0)
        container.setGraphicsEffect(shadow)

        # 1. 自定义顶部标题栏（含关闭按钮）
        title_bar = QHBoxLayout()
        lbl_tech_icon = QLabel("⚡")
        lbl_tech_icon.setStyleSheet("color: #0ea5e9; font-size: 16px;")
        
        lbl_title_text = QLabel("系统登录/注册")
        lbl_title_text.setStyleSheet("""
            color: #94a3b8; 
            font-family: 'Segoe UI', 'Microsoft YaHei'; 
            font-size: 11px; 
            font-weight: bold; 
            letter-spacing: 2px;
        """)
        
        btn_close = QPushButton("✕")
        btn_close.setObjectName("BtnClose")
        btn_close.setFixedSize(24, 24)
        btn_close.clicked.connect(self.reject)
        
        title_bar.addWidget(lbl_tech_icon)
        title_bar.addWidget(lbl_title_text)
        title_bar.addStretch()
        title_bar.addWidget(btn_close)
        container_layout.addLayout(title_bar)

        container_layout.addSpacing(15)

        # 2. 系统核心Logo与主标题
        lbl_main_title = QLabel("公路路基压实度实时监测与薄弱区识别系统")
        lbl_main_title.setObjectName("MainTitle")
        lbl_sub_title = QLabel("REAL-TIME COMPACTION MONITORING & ANOMALY DETECTION")
        lbl_sub_title.setObjectName("SubTitle")
        
        container_layout.addWidget(lbl_main_title)
        container_layout.addWidget(lbl_sub_title)
        container_layout.addSpacing(25)

        # 3. 输入控制区（账号与密码）
        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText(" 👤 键入操作员账号...")
        self.txt_username.setObjectName("Input")
        
        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText(" 🔒 键入安全准入密码...")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setObjectName("Input")

        container_layout.addWidget(self.txt_username)
        container_layout.addSpacing(12)
        container_layout.addWidget(self.txt_password)
        container_layout.addSpacing(25)

        # 4. 按钮交互区
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("授 权 登 录")
        self.btn_login.setObjectName("BtnLogin")
        
        self.btn_register = QPushButton("注 册 凭 证")
        self.btn_register.setObjectName("BtnRegister")
        
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_register)
        container_layout.addLayout(btn_layout)

        main_layout.addWidget(container)

        # 绑定核心逻辑信号
        self.btn_login.clicked.connect(self.handle_login)
        self.btn_register.clicked.connect(self.handle_register)

        # 应用定制科技QSS样式表
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet("""
            /* 主容器样式：暗灰蓝深色背景，微弱青色外边框 */
            QFrame#Container {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                                                   stop:0 #0f172a, stop:1 #1e293b);
                border: 1px solid #0f172a;
                border-top: 2px solid #0ea5e9; /* 顶部霓虹青亮条 */
                border-radius: 12px;
            }
            
            /* 关闭按钮 */
            QPushButton#BtnClose {
                background: transparent;
                color: #64748b;
                border: none;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#BtnClose:hover {
                background-color: #ef4444;
                color: white;
            }
            
            /* 标题文本 */
            QLabel#MainTitle {
                color: #f8fafc;
                font-family: 'Microsoft YaHei', sans-serif;
                font-size: 19px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QLabel#SubTitle {
                color: #38bdf8;
                font-family: 'Segoe UI', sans-serif;
                font-size: 8px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
            
            /* 拟物输入框样式：半透明黑色背景、无内凹、焦态蓝色呼吸边 */
            QLineEdit#Input {
                background-color: #0b0f19;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 13px;
                font-family: 'Microsoft YaHei';
            }
            QLineEdit#Input:focus {
                border: 1px solid #38bdf8;
                background-color: #020617;
            }
            
            /* 登录按钮：科技蓝渐变填充 */
            QPushButton#BtnLogin {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                                   stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 11px 0px;
                font-family: 'Microsoft YaHei';
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton#BtnLogin:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                                   stop:0 #0ea5e9, stop:1 #0284c7);
            }
            QPushButton#BtnLogin:pressed {
                background-color: #0369a1;
            }
            
            /* 注册按钮：扁平透明，虚边框 */
            QPushButton#BtnRegister {
                background-color: transparent;
                color: #94a3b8;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 11px 0px;
                font-family: 'Microsoft YaHei';
                font-size: 13px;
            }
            QPushButton#BtnRegister:hover {
                border-color: #94a3b8;
                color: #f1f5f9;
                background-color: rgba(255, 255, 255, 0.03);
            }
            QPushButton#BtnRegister:pressed {
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)

    # ================= 拖拽窗口底层事件支持 =================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    # ================= 核心安全逻辑控制 =================
    def _hash_pwd(self, pwd: str) -> str:
        return hashlib.sha256(pwd.encode('utf-8')).hexdigest()

    def handle_login(self):
        username = self.txt_username.text().strip()
        password = self.txt_password.text()
        
        if not username or not password:
            QMessageBox.warning(self, "输入提示", "账号与密码不能为空")
            return
            
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0] == self._hash_pwd(password):
            self.is_authenticated = True
            self.username = username
            self.accept()
        else:
            QMessageBox.critical(self, "认证失败", "您输入的操作员账号或安全密码有误，请核对后再试")

    def handle_register(self):
        username = self.txt_username.text().strip()
        password = self.txt_password.text()
        
        if len(username) < 4 or len(password) < 6:
            QMessageBox.warning(self, "安全合规校验", "注册失败：\n1. 操作员账号长度至少为 4 位\n2. 安全密码长度至少为 6 位")
            return
            
        conn = get_connection()
        cursor = conn.cursor()
        try:
            pwd_hash = self._hash_pwd(password)
            cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                           (username, pwd_hash, "engineer"))
            conn.commit()
            QMessageBox.information(self, "凭证管理", f"操作员账户 '{username}' 已成功登记在系统中。")
        except Exception:
            QMessageBox.warning(self, "安全错误", "登记失败：此账号已被其他操作员占用")
        finally:
            conn.close()