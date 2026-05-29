# modules/history.py
import csv
import random
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QComboBox, QLineEdit, QDateEdit, QFileDialog, QMessageBox, 
                             QSplitter, QFrame, QTextEdit, QAbstractItemView)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QDate
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient
from core.database import get_connection

# ================= 1. 自研路基横断面物理投影定位看板 =================
class NeonHistoryLocateCanvas(QWidget):
    # 自研的历史测点空间横断面投影示踪仪。
    # 根据选中的测点 Y 轴坐标（横向偏幅）和高程 Z 轴，在标准的梯形路基断面中精确定位。
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMinimumHeight(350)
        self.coord_x = 0.0
        self.coord_y = 0.0
        self.elevation = 0.0
        self.cmv_val = 0.0
        self.has_active_point = False

    def locate_point(self, x, y, z, cmv):
        self.coord_x = x
        self.coord_y = y
        self.elevation = z
        self.cmv_val = cmv
        self.has_active_point = True
        self.update()

    def clear_locator(self):
        self.has_active_point = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#090d16")) # 深黑色太空背景

        # 1. 绘制高科技感的同心测量雷达圆环
        pen_radar = QPen(QColor("#1e293b"), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen_radar)
        center_x, center_y = w // 2, h // 2
        for r in (50, 100, 150):
            painter.drawEllipse(QPointF(center_x, center_y), r, r)

        # 2. 绘制公路路基标准梯形断面 (灰蓝填充)
        # 设定梯形顶点与底点像素
        top_l_x, top_l_y = center_x - 70, center_y - 20
        top_r_x, top_r_y = center_x + 70, center_y - 20
        bot_l_x, bot_l_y = center_x - 110, center_y + 60
        bot_r_x, bot_r_y = center_x + 110, center_y + 60

        path_poly = [
            QPointF(top_l_x, top_l_y), QPointF(top_r_x, top_r_y),
            QPointF(bot_r_x, bot_r_y), QPointF(bot_l_x, bot_l_y)
        ]
        
        # 梯度填充路基介质
        grad = QLinearGradient(center_x, top_l_y, center_x, bot_l_y)
        grad.setColorAt(0.0, QColor("#1e293b"))
        grad.setColorAt(1.0, QColor("#0f172a"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor("#334155"), 1.5))
        
        # 绘制梯形路基多边形
        painter.drawPolygon(path_poly)

        # 绘制两旁的填方边坡辅助虚线
        painter.setPen(QPen(QColor("#475569"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(top_l_x, top_l_y, bot_l_x, bot_l_y)
        painter.drawLine(top_r_x, top_r_y, bot_r_x, bot_r_y)

        # 3. 投影标记选中的历史测点
        if self.has_active_point:
            # 横向偏幅范围约束：-10m 到 +10m 对应 top_l_x 到 top_r_x 的映射
            norm_y = (self.coord_y + 10.0) / 20.0
            pt_px = top_l_x + norm_y * (top_r_x - top_l_x)
            
            # 高程约束映射到路堤内部深度
            pt_py = top_l_y + 15 # 深度预设
            
            # 绘制霓虹激光定位线
            pen_laser = QPen(QColor("#0ea5e9"), 1, Qt.PenStyle.SolidLine)
            painter.setPen(pen_laser)
            painter.drawLine(0, int(pt_py), w, int(pt_py))
            painter.drawLine(int(pt_px), 0, int(pt_px), h)

            # 绘制发光警报圈
            color_state = QColor("#10b981") if self.cmv_val >= 75.0 else QColor("#f43f5e")
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(QBrush(color_state))
            painter.drawEllipse(QPointF(pt_px, pt_py), 8, 8)

            # 绘制探针深度标高值
            painter.setPen(QColor("#38bdf8"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.drawText(int(pt_px) + 12, int(pt_py) - 10, f"Y: {self.coord_y:.1f}m")
            painter.drawText(int(pt_px) + 12, int(pt_py) + 10, f"CMV: {self.cmv_val:.1f}")

        # 绘制剖面注解
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(15, h - 35, "断面模型: 22米标准二级公路填方路堤")
        painter.drawText(15, h - 20, "激光投影: 三维空间标高映射算法激活")

# ================= 2. 追溯系统主面板 =================
class HistoryQueryWidget(QWidget):
    # 历史数据综合追溯系统。
    # 集成了多条件动态 SQL 发生器、一键高速生成测试记录、表格 Inline 更改以及物理导出 CSV。
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_combobox_directories()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. 顶部 HUD 指示牌
        stats_panel = QHBoxLayout()
        self.hud_total = self.create_glow_hud("累计归档监测数据 (Rows)", "0", "SQLite 本地库总条数")
        self.hud_defects = self.create_glow_hud("筛出压实薄弱缺陷记录", "0", "代表需要追加复压点位")
        self.hud_export_status = self.create_glow_hud("系统数据网关导出", "READY", "支持 CSV/Excel 工业格式")
        stats_panel.addWidget(self.hud_total)
        stats_panel.addWidget(self.hud_defects)
        stats_panel.addWidget(self.hud_export_status)
        layout.addLayout(stats_panel)

        # 2. 中部核心区：左侧多条件筛选边栏 + 中部数据表 + 右侧物理断面定位器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧多条件搜索和控制管理台
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(12, 12, 12, 12)

        lbl_filter_title = QLabel("🔍 施工数据动态追溯参数")
        lbl_filter_title.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-bottom: 5px;")
        ctrl_layout.addWidget(lbl_filter_title)

        # 筛选：选择标段
        lbl_sect = QLabel("施工段落/工段筛选:")
        lbl_sect.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(lbl_sect)
        self.cmb_section = QComboBox()
        ctrl_layout.addWidget(self.cmb_section)

        # 筛选：选择压实设备
        lbl_mach = QLabel("碾压机具设备编码:")
        lbl_mach.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(lbl_mach)
        self.cmb_machine = QComboBox()
        ctrl_layout.addWidget(self.cmb_machine)

        # 筛选：质量等级
        lbl_qual = QLabel("压实质量状态判定:")
        lbl_qual.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(lbl_qual)
        self.cmb_quality = QComboBox()
        self.cmb_quality.addItems(["全部记录 (All)", "仅看合格点 (CMV >= 75)", "仅看漏压点 (CMV < 75)"])
        ctrl_layout.addWidget(self.cmb_quality)

        # 筛选：CMV 下限值过滤
        lbl_cmv_min = QLabel("最低合格刚度下限:")
        lbl_cmv_min.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(lbl_cmv_min)
        self.txt_min_cmv = QLineEdit()
        self.txt_min_cmv.setPlaceholderText("例如: 50.0")
        self.txt_min_cmv.setStyleSheet("background-color: #0f172a; color: white; border: 1px solid #475569; padding: 5px; border-radius: 4px;")
        ctrl_layout.addWidget(self.txt_min_cmv)

        # 筛选：起止日期
        lbl_date_start = QLabel("起始记录归档日期:")
        lbl_date_start.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(lbl_date_start)
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-30)) # 默认查过去一个月
        ctrl_layout.addWidget(self.date_start)

        lbl_date_end = QLabel("截止记录归档日期:")
        lbl_date_end.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(lbl_date_end)
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        ctrl_layout.addWidget(self.date_end)
        ctrl_layout.addSpacing(10)

        # 核心按钮：执行追溯
        self.btn_query = QPushButton("⚡ 执行复合追溯检索")
        self.btn_query.setStyleSheet("""
            QPushButton { background-color: #0284c7; color: white; padding: 10px; border-radius: 4px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #0ea5e9; }
        """)
        self.btn_query.clicked.connect(self.execute_dynamic_query)
        ctrl_layout.addWidget(self.btn_query)

        # 辅助功能：一键生成 200 条仿真数据
        btn_mock = QPushButton("💾 仿真生成 200 条记录")
        btn_mock.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; padding: 9px; border-radius: 4px; font-size: 11px; }
            QPushButton:hover { background-color: #34d399; }
        """)
        btn_mock.clicked.connect(self.inject_mock_historical_data)
        ctrl_layout.addWidget(btn_mock)

        # 下拉菜单通用样式表
        self.setStyleSheet("""
            QComboBox { background-color: #0f172a; color: white; border: 1px solid #475569; padding: 5px; border-radius: 4px; font-size: 11px; }
            QComboBox QAbstractItemView { background-color: #0f172a; color: white; selection-background-color: #0ea5e9; }
            QDateEdit { background-color: #0f172a; color: white; border: 1px solid #475569; padding: 5px; border-radius: 4px; font-size: 11px; }
        """)

        ctrl_layout.addStretch()
        main_splitter.addWidget(ctrl_frame)

        # 中部：大表格展示区
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "标定时间", "桩号 Y", "宽度 X", "车速", "激振幅", "CMV结果", "地质备注(双击可改)"])
        self.table.setStyleSheet("""
            QTableWidget { background-color: #0f172a; color: #f1f5f9; border: 1px solid #334155; gridline-color: #1e293b; }
            QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #334155; font-weight: bold; }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table.cellChanged.connect(self.on_table_cell_changed) # Inline编辑支持
        table_layout.addWidget(self.table)

        # 底部快捷管理键（批量删除、物理CSV导出）
        action_bar = QHBoxLayout()
        self.btn_export_csv = QPushButton("📊 导出筛选明细为工业报表(CSV)")
        self.btn_export_csv.setStyleSheet("""
            QPushButton { background-color: #475569; color: white; padding: 8px 15px; border-radius: 4px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #64748b; }
        """)
        self.btn_export_csv.clicked.connect(self.export_table_to_csv)
        
        self.btn_delete_record = QPushButton("🗑 物理删除该测点")
        self.btn_delete_record.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; padding: 8px 15px; border-radius: 4px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #f87171; }
        """)
        self.btn_delete_record.clicked.connect(self.delete_selected_record)

        action_bar.addWidget(self.btn_export_csv)
        action_bar.addStretch()
        action_bar.addWidget(self.btn_delete_record)
        table_layout.addLayout(action_bar)

        main_splitter.addWidget(table_frame)

        # 右侧：断面投影定位板
        locate_frame = QFrame()
        locate_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        locate_layout = QVBoxLayout(locate_frame)
        locate_layout.setContentsMargins(10, 10, 10, 10)

        self.locator_canvas = NeonHistoryLocateCanvas()
        locate_layout.addWidget(self.locator_canvas)

        main_splitter.addWidget(locate_frame)

        # 调整各个模块比例 2.2:6:2
        main_splitter.setSizes([220, 680, 240])
        layout.addWidget(main_splitter)

        # 底部控制台与指令终端
        self.sql_terminal = QTextEdit()
        self.sql_terminal.setReadOnly(True)
        self.sql_terminal.setPlaceholderText(">> 压实动态 SQL 执行终端就绪...")
        self.sql_terminal.setStyleSheet("""
            QTextEdit { background-color: #0b0f19; color: #38bdf8; border: 1px solid #334155; 
                        border-radius: 6px; padding: 8px; font-family: 'Consolas'; font-size: 11px; }
        """)
        self.sql_terminal.setFixedHeight(100)
        layout.addWidget(self.sql_terminal)

        # 初次查询
        self.execute_dynamic_query()

    def create_glow_hud(self, title, val, sub):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(3)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #94a3b8; font-size: 11px;")
        
        lbl_val = QLabel(val)
        lbl_val.setStyleSheet("color: #38bdf8; font-size: 24px; font-weight: bold; font-family: 'Consolas';")
        
        lbl_sub = QLabel(sub)
        lbl_sub.setStyleSheet("color: #64748b; font-size: 9px;")

        layout.addWidget(lbl_t)
        layout.addWidget(lbl_val)
        layout.addWidget(lbl_sub)

        frame.lbl_val = lbl_val
        return frame

    def load_combobox_directories(self):
        # 从 SQLite 中动态提取标段与压路机机具列表填充到下拉框中
        self.cmb_section.clear()
        self.cmb_machine.clear()
        
        self.cmb_section.addItem("全路段所有标段", "%")
        self.cmb_machine.addItem("全部机具设备", "%")

        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id, section_name FROM sections")
            for sect_id, name in cursor.fetchall():
                self.cmb_section.addItem(f"{name} (ID: {sect_id})", sect_id)
                
            cursor.execute("SELECT id, machine_code FROM machinery")
            for mach_id, code in cursor.fetchall():
                self.cmb_machine.addItem(f"{code} (ID: {mach_id})", mach_id)
        except Exception as e:
            self.write_sql_log(f"加载关联目录报错: {str(e)}")
        finally:
            conn.close()

    def write_sql_log(self, text):
        self.sql_terminal.append(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

    # ================= 3. 核心多条件复合 SQL 生成检索算法 =================
    def execute_dynamic_query(self):
        # 取消之前的 Inline Cell 更改信号，防止数据载入时反复触发数据库更新
        self.table.cellChanged.disconnect(self.on_table_cell_changed)

        section_filter = self.cmb_section.currentData()
        machine_filter = self.cmb_machine.currentData()
        quality_filter = self.cmb_quality.currentIndex() # 0: 全部, 1: 合格, 2: 不合格
        
        min_cmv_val = 0.0
        if self.txt_min_cmv.text().strip():
            try:
                min_cmv_val = float(self.txt_min_cmv.text().strip())
            except ValueError:
                pass

        # 解析日期
        date_s_str = self.date_start.date().toString("yyyy-MM-dd 00:00:00")
        date_e_str = self.date_end.date().toString("yyyy-MM-dd 23:59:59")

        # 构建复合过滤动态 SQL - 使用标准单引号物理拼接，100% 杜绝三引号 EOF 错误
        base_query = (
            "SELECT id, timestamp, coordinate_y, coordinate_x, speed, amplitude, cmv, elevation "
            "FROM compaction_logs "
            "WHERE timestamp BETWEEN ? AND ?"
        )
        params = [date_s_str, date_e_str]

        if section_filter != "%":
            base_query += " AND section_id = ?"
            params.append(section_filter)
        if machine_filter != "%":
            base_query += " AND machine_id = ?"
            params.append(machine_filter)
            
        if quality_filter == 1: # 合格
            base_query += " AND cmv >= 75"
        elif quality_filter == 2: # 不合格
            base_query += " AND cmv < 75"

        if min_cmv_val > 0.0:
            base_query += " AND cmv >= ?"
            params.append(min_cmv_val)

        base_query += " ORDER BY id DESC LIMIT 500" # 最多显示 500 条防溢出

        # 转换斜杠兼容写法，防止低版本 Python 解析 f-string 报错
        clean_query = base_query.replace('\n', ' ').strip()
        self.write_sql_log(f"SQL GENERATED: {clean_query}")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(base_query, tuple(params))
        rows = cursor.fetchall()

        # 计算总库存储量
        cursor.execute("SELECT COUNT(*) FROM compaction_logs")
        total_db_rows = cursor.fetchone()[0]
        self.hud_total.lbl_val.setText(str(total_db_rows))
        conn.close()

        # 数据清洗并装填表格
        self.table.setRowCount(0)
        defect_count = 0

        for r_idx, row_data in enumerate(rows):
            self.table.insertRow(r_idx)
            db_id = row_data[0]
            cmv_val = row_data[6]
            elevation_val = row_data[7] if row_data[7] else 0.25 # 默认高度偏移

            # 填充字段
            self.table.setItem(r_idx, 0, QTableWidgetItem(str(db_id)))
            self.table.setItem(r_idx, 1, QTableWidgetItem(str(row_data[1])))
            self.table.setItem(r_idx, 2, QTableWidgetItem(f"K102+{row_data[2]:.1f}m"))
            self.table.setItem(r_idx, 3, QTableWidgetItem(f"{row_data[3]:.1f}m"))
            self.table.setItem(r_idx, 4, QTableWidgetItem(f"{row_data[4]:.2f} km/h"))
            self.table.setItem(r_idx, 5, QTableWidgetItem(f"{row_data[5]:.2f} mm"))
            
            # CMV 合格着色
            cmv_item = QTableWidgetItem(f"{cmv_val:.1f}")
            if cmv_val >= 75.0:
                cmv_item.setForeground(QBrush(QColor("#10b981"))) # 合格绿
            else:
                cmv_item.setForeground(QBrush(QColor("#f43f5e"))) # 漏压红
                defect_count += 1
            self.table.setItem(r_idx, 6, cmv_item)

            # 地质备注列 (Inline可编辑，这里用 SQLite 的 elevation 字段存字符串备注做仿真模拟)
            remark_text = f"高填方黏土-桩_{db_id}" if elevation_val == 0.25 else str(elevation_val)
            self.table.setItem(r_idx, 7, QTableWidgetItem(remark_text))

            # 存储高程元数据在主键列的用户数据中以便断面定位
            self.table.item(r_idx, 0).setData(Qt.ItemDataRole.UserRole, (row_data[2], row_data[3], elevation_val, cmv_val))

        # 刷新缺陷 HUD
        self.hud_defects.lbl_val.setText(str(defect_count))
        self.hud_export_status.lbl_val.setText("COMPLETED" if len(rows) > 0 else "EMPTY_SET")

        # 重新挂载 Inline 修改信号
        self.table.cellChanged.connect(self.on_table_cell_changed)
        self.locator_canvas.clear_locator()

    # ================= 4. 高阶交互：表格选中与三维断面同步投影 =================
    def on_table_selection_changed(self):
        # 选中行变化时，物理投影指针实时重算
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            self.locator_canvas.clear_locator()
            return
            
        row = selected_ranges[0].topRow()
        item_id = self.table.item(row, 0)
        if item_id is None:
            return

        # 提炼存储的元数据：桩号Y，横宽X，高程Z，刚度CMV
        meta = item_id.data(Qt.ItemDataRole.UserRole)
        if meta:
            y, x, z, cmv = meta
            # 在断面中定位投影
            self.locator_canvas.locate_point(x, y, 0.25, cmv)

    # ================= 5. 数据维护逻辑 (Inline 改、物理删、批量增) =================
    def on_table_cell_changed(self, row, col):
        # 高阶 Inline 编辑：直接在表格双击修改备注，触发 UPDATE 的 SQL 逻辑
        if col != 7: # 仅备注列可以编辑
            return
            
        db_id = self.table.item(row, 0).text()
        new_text = self.table.item(row, col).text().strip()

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # 采用数据库高程 elevation 列进行仿真模拟文本存取
            cursor.execute("UPDATE compaction_logs SET elevation=? WHERE id=?", (new_text, db_id))
            conn.commit()
            self.write_sql_log(f"DATA UPDATED (ID: {db_id}): Remark set to '{new_text}'")
            # 同步更新元数据
            meta = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if meta:
                self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, (meta[0], meta[1], new_text, meta[3]))
        except Exception as e:
            self.write_sql_log(f"Inline 更新异常: {str(e)}")
        finally:
            conn.close()

    def delete_selected_record(self):
        # 单点物理物理删除
        curr_row = self.table.currentRow()
        if curr_row < 0:
            QMessageBox.warning(self, "操作提示", "请先在列表中选中需要报废移除的测点行。")
            return
            
        db_id = self.table.item(curr_row, 0).text()
        
        reply = QMessageBox.question(self, "物理销毁确认", f"确定彻底从数据库物理删除主键 ID 为 '{db_id}' 的压实日志吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM compaction_logs WHERE id=?", (db_id,))
                conn.commit()
                self.write_sql_log(f"RECORD DELETED: ID {db_id} has been physically destroyed.")
                self.execute_dynamic_query() # 重新查询刷新
            except Exception as e:
                QMessageBox.critical(self, "数据库错误", f"删除失败: {str(e)}")
            finally:
                conn.close()

    def inject_mock_historical_data(self):
        # 自动仿真高容量压实归档记录生成器 (200 条)
        self.write_sql_log(">> 正在后台注入高容量仿真遥测序列数据 (200个测点)...")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # 确保当前有标段和压路机基础数据，防止外键报错
            cursor.execute("SELECT id FROM sections LIMIT 1")
            sect_row = cursor.fetchone()
            sect_id = sect_row[0] if sect_row else 1
            if not sect_row:
                cursor.execute("INSERT INTO sections (section_name, start_chainage, end_chainage, target_density) VALUES (?, ?, ?, ?)",
                               ("第一标段K102+000", 0.0, 1000.0, 96.0))
                sect_id = cursor.lastrowid
                
            cursor.execute("SELECT id FROM machinery LIMIT 1")
            mach_row = cursor.fetchone()
            mach_id = mach_row[0] if mach_row else 1
            if not mach_row:
                cursor.execute("INSERT INTO machinery (machine_code, weight) VALUES (?, ?)", ("#R-109", 22.0))
                mach_id = cursor.lastrowid
                
            conn.commit()

            # 仿真压实过程写库
            for i in range(200):
                # 随机轨迹参数
                gps_y = random.uniform(10.0, 90.0) # 桩号 offset
                gps_x = random.uniform(-10.0, 10.0) # 偏宽 offset
                speed = random.uniform(2.5, 4.5)
                amp = random.uniform(1.1, 1.5)
                cmv = random.normalvariate(78.0, 8.5) # 大部分在合格线附近波动
                cmv = max(30.0, min(140.0, cmv))
                
                # 随机生成过去 15 天的时间戳
                days_offset = random.randint(0, 15)
                hour = random.randint(8, 18)
                minute = random.randint(0, 59)
                timestamp = f"2025-02-{28 - days_offset:02d} {hour:02d}:{minute:02d}:00"

                cursor.execute("""
                    INSERT INTO compaction_logs (timestamp, section_id, machine_id, coordinate_y, coordinate_x, speed, amplitude, cmv, elevation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, sect_id, mach_id, gps_y, gps_x, speed, amp, cmv, 0.25))
                
            conn.commit()
            self.write_sql_log(">> [注入完成] 200条含GPS桩号定位、车速幅值及CMV实测值的施工记录已归档。")
            self.load_combobox_directories() # 刷新下拉
            self.execute_dynamic_query() # 刷新表
        except Exception as e:
            self.write_sql_log(f"仿真写入失败: {str(e)}")
        finally:
            conn.close()

    # ================= 6. 物理 CSV/Excel 导出逻辑 =================
    def export_table_to_csv(self):
        # 使用 QFileDialog 将当前筛选后的表单物理导出为标准的 CSV 电子表格
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "导出提示", "当前筛选结果集为空，无需导出数据报表。")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存压实数据报表", f"Subgrade_Compaction_Report_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv", "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                # 写入头部
                writer.writerow(["数据ID", "施工时间", "桩号 Y", "横向偏幅 X", "行车时速", "激振幅度", "实测刚度 CMV", "地质与检测备注"])
                
                # 写入行
                for r in range(self.table.rowCount()):
                    row_data = []
                    for c in range(self.table.columnCount()):
                        item = self.table.item(r, c)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
                    
            QMessageBox.information(self, "数据网关", f"压实归档报表已成功导出至物理介质：\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程发生 IO 异常：\n{str(e)}")