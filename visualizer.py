import time
import re
import math
import tkinter as tk
from tkinter import ttk

import serial
from serial.tools import list_ports

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Serial communication settings
BAUD = 115200

# Joystick center reference values
CENTER_Y = 509
CENTER_X = 512

# Ignore very small brightness values near center
DEADZONE = 15


def autodetect_port():
    """Try to automatically find the Arduino serial port."""
    ports = list(list_ports.comports())
    if not ports:
        return None

    priority = ("arduino", "ch340", "cp210", "usb serial", "ttyacm", "ttyusb")
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(k in desc or k in hwid for k in priority):
            return p.device

    return ports[0].device


def clamp(v, lo, hi):
    """Keep value v between lo and hi."""
    return max(lo, min(hi, v))


def map_to_255(num, den):
    """Map a displacement ratio to the PWM range 0..255."""
    if den <= 0:
        return 0
    return int((num * 255) / den)


def compute_brightness(x, y):
    """Convert raw joystick X/Y values into up/down/left/right brightness values."""
    up = down = left = right = 0

    if y <= CENTER_Y:
        up = map_to_255(CENTER_Y - y, CENTER_Y)
    if y >= CENTER_Y:
        down = map_to_255(y - CENTER_Y, 1023 - CENTER_Y)

    if x <= CENTER_X:
        left = map_to_255(CENTER_X - x, CENTER_X)
    if x >= CENTER_X:
        right = map_to_255(x - CENTER_X, 1023 - CENTER_X)

    vals = [clamp(up, 0, 255), clamp(down, 0, 255), clamp(left, 0, 255), clamp(right, 0, 255)]

    # Apply dead-zone so tiny movements near center are ignored
    vals = [0 if v < DEADZONE else v for v in vals]

    return vals  # up, down, left, right


class JoystickGUI:
    # Pattern for optional text-based serial format
    TEXT_RE = re.compile(r"X:\s*(\d+)\s*\|\s*Y:\s*(\d+)\s*\|\s*Button:\s*(\d+)")

    def __init__(self, root):
        self.root = root
        self.root.title("Joystick Tester - Radial Column Chart")

        self.running = False
        self.ser = None
        self.port = autodetect_port()

        self.rx_buffer = ""
        self.last_rx_time = 0.0

        # Top UI area
        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")

        self.btn = ttk.Button(top, text="Start Test", command=self.toggle)
        self.btn.pack(side="left")

        self.status = ttk.Label(top, text="OFF", foreground="red", font=("Segoe UI", 12, "bold"))
        self.status.pack(side="left", padx=12)

        self.port_label = ttk.Label(top, text=f"Port: {self.port or 'NOT FOUND'} | Baud: {BAUD}")
        self.port_label.pack(side="right")

        # Middle UI area
        mid = ttk.Frame(root, padding=10)
        mid.pack(fill="both", expand=True)

        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(mid, padding=(15, 0, 0, 0))
        right.pack(side="right", fill="y")

        # Create radial bar chart
        fig = Figure(figsize=(6, 5), dpi=100)
        self.ax = fig.add_subplot(111, polar=True)
        self.ax.set_title("Radial Column Chart (0..255)", pad=15)
        self.ax.set_ylim(0, 255)
        self.ax.set_yticks([0, 64, 128, 192, 255])

        # Bar positions: UP, RIGHT, DOWN, LEFT
        self.labels = ["UP", "RIGHT", "DOWN", "LEFT"]
        self.angles = [math.pi/2, 0, 3*math.pi/2, math.pi]
        width = math.radians(40)

        self.bars = self.ax.bar(self.angles, [0, 0, 0, 0], width=width, align="center")
        self.ax.set_xticks(self.angles)
        self.ax.set_xticklabels(self.labels)

        self.dir_text = self.ax.text(
            0.5, -0.14, "Direction: CENTER",
            transform=self.ax.transAxes, ha="center", va="center", fontsize=11
        )

        # Embed chart into Tkinter window
        self.canvas = FigureCanvasTkAgg(fig, master=left)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Direction grid display
        ttk.Label(right, text="Button Mapping", font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))

        grid = ttk.Frame(right)
        grid.pack()

        self.cells = {}
        for r in range(3):
            for c in range(3):
                lbl = tk.Label(grid, text=" ", width=10, height=4, relief="groove", bg="white")
                lbl.grid(row=r, column=c, padx=3, pady=3)
                self.cells[(r, c)] = lbl

        self.cells[(0, 1)].config(text="UP")
        self.cells[(2, 1)].config(text="DOWN")
        self.cells[(1, 0)].config(text="LEFT")
        self.cells[(1, 2)].config(text="RIGHT")
        self.cells[(1, 1)].config(text="CENTER")

        # Bottom UI area
        bottom = ttk.Frame(root, padding=10)
        bottom.pack(fill="x")

        self.data_label = ttk.Label(bottom, text="Data: UP=0 DOWN=0 LEFT=0 RIGHT=0")
        self.data_label.pack(side="left")

        self.raw_label = ttk.Label(bottom, text="Raw: (no data yet)")
        self.raw_label.pack(side="right")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(10, self.update_loop)

    def toggle(self):
        """Start or stop serial reading."""
        if not self.running:
            self.start()
        else:
            self.stop()

    def start(self):
        """Open serial port and begin visualization."""
        if not self.port:
            self.port = autodetect_port()
            self.port_label.config(text=f"Port: {self.port or 'NOT FOUND'} | Baud: {BAUD}")
            if not self.port:
                return

        try:
            self.ser = serial.Serial(self.port, BAUD, timeout=0)
            self.ser.reset_input_buffer()
            time.sleep(2.0)  # Arduino often resets when serial port opens
            self.ser.reset_input_buffer()
        except Exception as e:
            self.port_label.config(text=f"Port open failed: {e}")
            self.ser = None
            return

        self.running = True
        self.btn.config(text="Stop Test")
        self.status.config(text="ON", foreground="green")

    def stop(self):
        """Stop visualization and close serial port."""
        self.running = False
        self.btn.config(text="Start Test")
        self.status.config(text="OFF", foreground="red")

        if self.ser:
            try:
                self.ser.close()
            except:
                pass
        self.ser = None
        self.highlight("CENTER")

    def highlight(self, direction):
        """Highlight current direction in the 3x3 indicator grid."""
        for lbl in self.cells.values():
            lbl.config(bg="white")

        mapping = {
            "UP": (0, 1),
            "DOWN": (2, 1),
            "LEFT": (1, 0),
            "RIGHT": (1, 2),
            "CENTER": (1, 1)
        }
        self.cells[mapping.get(direction, (1, 1))].config(bg="#b7f7b7")

    def parse_any(self, line):
        """Parse incoming serial data in several possible formats."""
        line = line.strip()
        if not line:
            return None

        # Format 1: up,down,left,right
        parts = line.split(",")
        if len(parts) == 4 and all(p.strip().isdigit() for p in parts):
            vals = [clamp(int(p), 0, 255) for p in parts]
            return ("bright", vals)

        # Format 2: x,y,button
        if len(parts) == 3 and all(p.strip().isdigit() for p in parts):
            x, y, btn = [int(p) for p in parts]
            return ("xyb", (x, y, btn))

        # Format 3: X: ... | Y: ... | Button: ...
        m = self.TEXT_RE.search(line)
        if m:
            x = int(m.group(1))
            y = int(m.group(2))
            btn = int(m.group(3))
            return ("xyb", (x, y, btn))

        return None

    def update_loop(self):
        """Continuously read serial data and update the GUI."""
        if self.running and self.ser:
            try:
                n = self.ser.in_waiting
                if n > 0:
                    chunk = self.ser.read(n).decode(errors="ignore")
                    self.rx_buffer += chunk

                    while "\n" in self.rx_buffer:
                        line, self.rx_buffer = self.rx_buffer.split("\n", 1)

                        self.raw_label.config(text=f"Raw: {line.strip()[:45]}")
                        self.last_rx_time = time.time()

                        parsed = self.parse_any(line)
                        if not parsed:
                            continue

                        kind, data = parsed

                        if kind == "bright":
                            up, down, left, right = data
                        else:
                            x, y, btn = data
                            up, down, left, right = compute_brightness(x, y)

                        # Determine strongest direction
                        mx = max([up, down, left, right])
                        if mx == 0:
                            direction = "CENTER"
                        else:
                            idx = [up, down, left, right].index(mx)
                            direction = ["UP", "DOWN", "LEFT", "RIGHT"][idx]

                        # Visual order for radial plot: UP, RIGHT, DOWN, LEFT
                        visual = [up, right, down, left]
                        for bar, h in zip(self.bars, visual):
                            bar.set_height(h)

                        self.dir_text.set_text(f"Direction: {direction}")
                        self.data_label.config(
                            text=f"Data: UP={up} DOWN={down} LEFT={left} RIGHT={right}"
                        )
                        self.highlight(direction)

                        self.canvas.draw_idle()

                # If no recent data, show warning
                if self.running and (time.time() - self.last_rx_time) > 1.5:
                    self.raw_label.config(text="Raw: (no serial data)")

            except Exception:
                pass

        self.root.after(10, self.update_loop)

    def on_close(self):
        """Close app safely."""
        self.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = JoystickGUI(root)
    root.mainloop()
