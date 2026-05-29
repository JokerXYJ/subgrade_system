# modules/machinery.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QMessageBox, QLabel, QFrame)
from core.database import get_connection

class MachineryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 登记表单区
        form_panel = QFrame()
        form_panel.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        form_layout = QHBoxLayout(form_panel)
        form_layout.setContentsMargins(15, 10, 15, 10)

        lbl_reg = QLabel("⚙ 新设备登记:")
        lbl_reg.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        form_layout.addWidget(lbl_reg)

        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("钢轮压路机编号 (例: #R-109)")
        self.txt_code.setStyleSheet("background-color: #0f172a; color: white; border: 1px solid #334155; padding: 6px; border-radius: 4px;")
        form_layout.addWidget(self.txt_code)

        self.txt_weight = QLineEdit()
        self.txt_weight.setPlaceholderText("装备自重吨位 (吨)")
        self.txt_weight.setStyleSheet("background-color: #0f172a; color: white; border: 1px solid #334155; padding: 6px; border-radius: 4px;")
        form_layout.addWidget(self.txt_weight)

        self.btn_save = QPushButton("💾 登记设备入库")
        self.btn_save.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; border: none; border-radius: 4px; padding: 7px 15px; font-weight: bold; }
            QPushButton:hover { background-color: #34d399; }
        """)
        self.btn_save.clicked.connect(self.save_machinery)
        form_layout.addWidget(self.btn_save)

        self.btn_del = QPushButton("🗑 报废下线")
        self.btn_del.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; border: none; border-radius: 4px; padding: 7px 15px; }
            QPushButton:hover { background-color: #f87171; }
        """)
        self.btn_del.clicked.connect(self.delete_machinery)
        form_layout.addWidget(self.btn_del)

        layout.addWidget(form_panel)

        # 展示列表表格区
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["库联自增编号 ID", "重型钢轮机编码", "自重额定质量 (吨)"])
        self.table.setStyleSheet("""
            QTableWidget { background-color: #1e293b; color: #f1f5f9; border: 1px solid #334155; gridline-color: #334155; }
            QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #334155; font-weight: bold; }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        self.refresh()

    def refresh(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, machine_code, weight FROM machinery")
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(0)
        for r_idx, r_data in enumerate(rows):
            self.table.insertRow(r_idx)
            for c_idx, val in enumerate(r_data):
                self.table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))

    def save_machinery(self):
        code = self.txt_code.text().strip()
        weight = self.txt_weight.text().strip()
        if not code or not weight:
            QMessageBox.warning(self, "校验不符", "编码与重量输入不能为空。")
            return
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO machinery (machine_code, weight, vibration_freq, amplitude) VALUES (?, ?, ?, ?)",
                           (code, float(weight), 30.0, 1.4))
            conn.commit()
            conn.close()
            self.refresh()
            self.txt_code.clear()
            self.txt_weight.clear()
        except Exception as e:
            QMessageBox.critical(self, "数据库错误", str(e))

    def delete_machinery(self):
        curr_row = self.table.currentRow()
        if curr_row < 0:
            QMessageBox.warning(self, "选择错误", "请选中表单中的一行数据进行报废。")
            return
        db_id = self.table.item(curr_row, 0).text()
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM machinery WHERE id=?", (db_id,))
        conn.commit()
        conn.close()
        self.refresh()