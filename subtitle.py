import sys
import pysubs2
import pytesseract
from PIL import Image, ImageOps
from io import BytesIO
from time import time
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QPushButton, QFileDialog, QHBoxLayout, QLineEdit, 
                             QCheckBox, QListWidget, QComboBox)
from PyQt6.QtCore import Qt, QTimer, QRect, QBuffer
from PyQt6.QtGui import QPainter, QColor, QPen

# --- TESSERACT PATH ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class SubtitleOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self.label = QLabel("Waiting to Sync...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: white; font-size: 32px; font-weight: bold; background-color: rgba(0,0,0,160); border-radius: 15px; padding: 15px;")
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        self.time_label = QLabel("00:00", self)
        self.time_label.setStyleSheet("color: #f39c12; font-size: 18px; font-weight: bold; background-color: transparent;")
        self.time_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.time_label.hide() 
        
        # --- NEW: Hover Pause Button ---
        self.btn_pause = QPushButton("⏸️ Pause Sync", self)
        self.btn_pause.setStyleSheet("background-color: rgba(41, 128, 185, 200); color: white; font-weight: bold; border-radius: 5px;")
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.hide() # Hidden until hovered
        
        screen = QApplication.primaryScreen().size()
        self.setGeometry(int(screen.width()*0.1), screen.height()-250, int(screen.width()*0.8), 120)

    # --- NEW: Hover Reveal Logic ---
    def enterEvent(self, event):
        self.btn_pause.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.btn_pause.hide()
        super().leaveEvent(event)
    # -------------------------------

    def resizeEvent(self, event):
        # Keeps timestamp top-right, and pause button bottom-right
        self.time_label.setGeometry(self.width() - 100, 15, 80, 25)
        self.btn_pause.setGeometry(self.width() - 130, self.height() - 40, 110, 30)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.dragPos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.dragPos)
            self.dragPos = event.globalPosition().toPoint()

class RedScannerBox(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("border: 2px solid #00ff00; background-color: rgba(0, 255, 0, 20);")
        self.setGeometry(0, 0, 0, 0)
        self.hide()

class SnippingWidget(QWidget):
    def __init__(self, main_controller):
        super().__init__()
        self.main_controller = main_controller
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def showEvent(self, event):
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.start_point = None
        self.end_point = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))
        if self.start_point and self.end_point:
            selection_rect = QRect(self.start_point, self.end_point).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event):
        self.start_point = event.position().toPoint()
        self.end_point = self.start_point
        self.update()

    def mouseMoveEvent(self, event):
        self.end_point = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        if self.start_point and self.end_point:
            final_rect = QRect(self.start_point, self.end_point).normalized()
            if final_rect.width() > 10 and final_rect.height() > 10:
                self.main_controller.apply_drawn_box(final_rect)
        self.hide()

class MainController(QWidget):
    def __init__(self):
        super().__init__()
        self.subs = None
        self.offset = 0               
        self.current_video_ms = 0     
        self.last_tick_time = 0       
        self.is_running = False 
        self.playback_speed = 1.0      
        
        self.overlay = SubtitleOverlay()
        self.overlay.show()
        
        # --- NEW: Connect the Pause Button ---
        self.overlay.btn_pause.clicked.connect(self.toggle_pause)
        
        self.eye = RedScannerBox()
        self.snipper = SnippingWidget(self)
        
        self.init_ui()
        
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.playback_engine)
        self.ocr_timer = QTimer()
        self.ocr_timer.timeout.connect(self.run_ocr)

    def init_ui(self):
        self.setWindowTitle("Real-Time Subtitle Sync PRO")
        self.setFixedWidth(520)
        layout = QVBoxLayout()
        
        top_row = QHBoxLayout()
        self.chk_visible = QCheckBox("Show Subtitles")
        self.chk_visible.setChecked(True)
        self.chk_visible.stateChanged.connect(lambda s: self.overlay.show() if s==2 else self.overlay.hide())
        
        self.chk_timestamp = QCheckBox("Show Timestamp")
        self.chk_timestamp.stateChanged.connect(lambda s: self.overlay.time_label.show() if s==2 else self.overlay.time_label.hide())
        
        self.btn_exit = QPushButton("❌ Exit App")
        self.btn_exit.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_exit.clicked.connect(self.close_everything)
        
        top_row.addWidget(self.chk_visible)
        top_row.addWidget(self.chk_timestamp)
        top_row.addWidget(self.btn_exit)
        layout.addLayout(top_row)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("<b>Playback Speed:</b>"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x", "2.5x", "3.0x"])
        self.combo_speed.setCurrentText("1.0x")
        self.combo_speed.currentTextChanged.connect(self.change_speed)
        speed_row.addWidget(self.combo_speed)
        speed_row.addStretch() 
        layout.addLayout(speed_row)

        ocr_row = QHBoxLayout()
        self.btn_draw = QPushButton("📐 Draw Scan Box")
        self.btn_draw.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; height: 30px;")
        self.btn_draw.clicked.connect(self.start_drawing)
        
        self.btn_stop_ocr = QPushButton("⏹️ Stop Scan")
        self.btn_stop_ocr.clicked.connect(self.stop_ocr)
        ocr_row.addWidget(self.btn_draw)
        ocr_row.addWidget(self.btn_stop_ocr)
        layout.addLayout(ocr_row)

        self.lbl_ocr_status = QLabel("OCR: Idle")
        self.lbl_ocr_status.setStyleSheet("color: #e67e22; font-weight: bold;")
        layout.addWidget(self.lbl_ocr_status)

        self.btn_load = QPushButton("📂 Load Subtitles")
        self.btn_load.clicked.connect(self.load_subs)
        layout.addWidget(self.btn_load)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search for the line you hear...")
        self.search_bar.textChanged.connect(self.filter_list)
        layout.addWidget(self.search_bar)
        
        self.sub_list = QListWidget()
        layout.addWidget(self.sub_list)

        layout.addWidget(QLabel("Type Anime Time (e.g. 02:48) for the selected line:"))
        sync_row = QHBoxLayout()
        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("02:48")
        self.btn_sync = QPushButton("🎯 Sync Subtitles")
        self.btn_sync.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_sync.clicked.connect(self.perform_sync)
        sync_row.addWidget(self.time_input)
        sync_row.addWidget(self.btn_sync)
        layout.addLayout(sync_row)

        self.setLayout(layout)

    # --- NEW: Pause Toggle Logic ---
    def toggle_pause(self):
        if not self.subs: return
        
        if self.is_running:
            self.is_running = False
            self.play_timer.stop()
            self.overlay.btn_pause.setText("▶️ Resume Sync")
            self.overlay.btn_pause.setStyleSheet("background-color: rgba(39, 174, 96, 200); color: white; font-weight: bold; border-radius: 5px;")
        else:
            self.is_running = True
            self.last_tick_time = time() * 1000  # Reset the clock so it doesn't jump forward
            self.play_timer.start(50)
            self.overlay.btn_pause.setText("⏸️ Pause Sync")
            self.overlay.btn_pause.setStyleSheet("background-color: rgba(41, 128, 185, 200); color: white; font-weight: bold; border-radius: 5px;")
    # -------------------------------

    def change_speed(self, text):
        try:
            self.playback_speed = float(text.replace("x", ""))
        except ValueError:
            self.playback_speed = 1.0

    def close_everything(self):
        self.overlay.close()
        self.eye.close()
        self.snipper.close()
        QApplication.instance().quit()

    def start_drawing(self):
        self.eye.hide()
        self.ocr_timer.stop()
        self.snipper.show()

    def stop_ocr(self):
        self.eye.hide()
        self.ocr_timer.stop()
        self.lbl_ocr_status.setText("OCR: Stopped.")

    def apply_drawn_box(self, rect):
        self.eye.setGeometry(rect)
        self.eye.show()
        self.ocr_timer.start(800) 
        self.lbl_ocr_status.setText("OCR: Scanning...")

    def load_subs(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Subs", "", "Subs (*.srt *.ass *.vtt)")
        if path:
            self.subs = pysubs2.load(path)
            self.sub_list.clear()
            for i, line in enumerate(self.subs):
                self.sub_list.addItem(f"{i} | [{line.start//1000}s] {line.plaintext}")

    def filter_list(self, query):
        for i in range(self.sub_list.count()):
            item = self.sub_list.item(i)
            item.setHidden(query.lower() not in item.text().lower())

    def perform_sync(self):
        if not self.subs or not self.sub_list.currentItem(): return
        try:
            vid_time = self.time_input.text().strip()
            parts = vid_time.split(":")
            if len(parts) == 2:
                vid_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
            elif len(parts) == 3:
                vid_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
            else:
                return
            
            selected = self.sub_list.currentItem().text()
            original_idx = int(selected.split(" | ")[0])
            sub_start_ms = self.subs[original_idx].start
            
            self.offset = vid_ms - sub_start_ms
            self.current_video_ms = vid_ms
            self.last_tick_time = time() * 1000
            self.is_running = True
            self.play_timer.start(50)
            
            self.overlay.label.setText("SYNC COMPLETE! Subtitles running...")
            self.overlay.btn_pause.setText("⏸️ Pause Sync")
            self.overlay.btn_pause.setStyleSheet("background-color: rgba(41, 128, 185, 200); color: white; font-weight: bold; border-radius: 5px;")
        except Exception as e:
            pass

    def run_ocr(self):
        if not self.eye.isVisible(): return
        
        geo = self.eye.geometry()
        
        self.eye.hide()
        QApplication.processEvents()
        
        screen = QApplication.primaryScreen()
        capture_rect = geo.adjusted(2, 2, -2, -2)
        screenshot_pixmap = screen.grabWindow(0, capture_rect.x(), capture_rect.y(), capture_rect.width(), capture_rect.height())
        
        self.eye.show()

        try:
            buffer = QBuffer()
            buffer.open(QBuffer.OpenModeFlag.ReadWrite)
            screenshot_pixmap.save(buffer, "PNG")
            img = Image.open(BytesIO(buffer.data()))

            img = img.convert('L')
            img = img.point(lambda p: 255 if p > 120 else 0)
            img = ImageOps.invert(img)
            img = img.resize((img.width * 3, img.height * 3), Image.Resampling.LANCZOS)
            img = ImageOps.expand(img, border=20, fill='white')
            
            text = pytesseract.image_to_string(img, config='--psm 7 -c tessedit_char_whitelist=0123456789:').strip()

            if not text:
                self.lbl_ocr_status.setText("OCR: [Timestamp Hidden / Cannot see numbers]")
                return

            if ":" in text:
                parts = text.split(":")
                try:
                    if len(parts) == 2:
                        scanned_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                    elif len(parts) == 3:
                        scanned_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                    else:
                        return
                except ValueError:
                    return

                self.current_video_ms = scanned_ms
                self.last_tick_time = time() * 1000 
                self.is_running = True 
                self.lbl_ocr_status.setText(f"OCR: Resynced to {text}")
                
                # Make sure the button shows "Pause" if the OCR forces it to run again
                self.overlay.btn_pause.setText("⏸️ Pause Sync")
                self.overlay.btn_pause.setStyleSheet("background-color: rgba(41, 128, 185, 200); color: white; font-weight: bold; border-radius: 5px;")
            else:
                self.lbl_ocr_status.setText(f"OCR Read Garbage: '{text}'")
                
        except Exception as e:
            self.lbl_ocr_status.setText("OCR CRASHED! See terminal.")
            print(f"\n--- OCR ERROR ---\n{e}\n-----------------\n")

    def playback_engine(self):
        if not self.subs or not self.is_running: return
        
        now = time() * 1000
        
        elapsed = (now - self.last_tick_time) * self.playback_speed
        
        self.current_video_ms += elapsed
        self.last_tick_time = now
        
        total_seconds = int(self.current_video_ms / 1000)
        m, s = divmod(total_seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            time_str = f"{h:02d}:{m:02d}:{s:02d}"
        else:
            time_str = f"{m:02d}:{s:02d}"
        self.overlay.time_label.setText(time_str)

        target_subtitle_time = self.current_video_ms - self.offset
        
        active_text = ""
        for line in self.subs:
            if line.start <= target_subtitle_time <= line.end:
                active_text = line.plaintext
                break
                
        self.overlay.label.setText(active_text)

    def closeEvent(self, event):
        self.close_everything()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ctrl = MainController()
    ctrl.show()
    sys.exit(app.exec())
