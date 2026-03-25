import tkinter as tk
from tkinter import ttk, messagebox
from collections import deque
from threading import Thread
import time

import serial
import serial.tools.list_ports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class HeartRateMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Heart Rate Monitor Dashboard")
        self.root.geometry("1180x760")
        self.root.configure(bg="#0b1220")

        self.serial_conn = None
        self.running = False

        self.current_bpm = tk.StringVar(value="--")
        self.current_signal = tk.StringVar(value="--")
        self.hr_status = tk.StringVar(value="Waiting for pulse")
        self.connection_status = tk.StringVar(value="Disconnected")
        self.monitor_text = tk.StringVar(value="Idle")

        self.signal_data = deque(maxlen=300)
        self.has_signal = False

        self.last_beat_flash_time = 0
        self.last_status_color = "#22c55e"
        self.heart_big = False

        self.build_ui()
        self.refresh_ports()
        self.animate_ui()
        self.update_plot()

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background="#0b1220")
        style.configure("Panel.TFrame", background="#111827")
        style.configure("Card.TFrame", background="#182235")
        style.configure(
            "Header.TLabel",
            background="#0b1220",
            foreground="white",
            font=("Segoe UI", 28, "bold")
        )
        style.configure(
            "Sub.TLabel",
            background="#0b1220",
            foreground="#93c5fd",
            font=("Segoe UI", 11, "bold")
        )
        style.configure(
            "CardTitle.TLabel",
            background="#182235",
            foreground="#cbd5e1",
            font=("Segoe UI", 12, "bold")
        )
        style.configure(
            "CardValue.TLabel",
            background="#182235",
            foreground="white",
            font=("Segoe UI", 30, "bold")
        )
        style.configure(
            "Muted.TLabel",
            background="#0b1220",
            foreground="#94a3b8",
            font=("Segoe UI", 10)
        )
        style.configure("TLabel", background="#0b1220", foreground="white", font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TCombobox", font=("Segoe UI", 10))

        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=22, pady=(18, 8))

        left_header = ttk.Frame(header)
        left_header.pack(side="left")

        ttk.Label(left_header, text="Heart Rate Monitor", style="Header.TLabel").pack(anchor="w")
        ttk.Label(left_header, textvariable=self.monitor_text, style="Sub.TLabel").pack(anchor="w", pady=(4, 0))

        right_header = ttk.Frame(header)
        right_header.pack(side="right")

        self.connection_dot = tk.Label(
            right_header, text="●", font=("Segoe UI", 20, "bold"),
            bg="#0b1220", fg="#ef4444"
        )
        self.connection_dot.pack(side="left", padx=(0, 8))

        ttk.Label(right_header, textvariable=self.connection_status, style="Sub.TLabel").pack(side="left")

        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=22, pady=(0, 10))

        ttk.Label(controls, text="Serial Port:").pack(side="left", padx=(0, 8))

        self.port_combo = ttk.Combobox(controls, state="readonly", width=18)
        self.port_combo.pack(side="left", padx=(0, 10))

        ttk.Button(controls, text="Refresh", command=self.refresh_ports).pack(side="left", padx=4)
        ttk.Button(controls, text="Connect", command=self.connect_serial).pack(side="left", padx=4)
        ttk.Button(controls, text="Disconnect", command=self.disconnect_serial).pack(side="left", padx=4)

        hero = ttk.Frame(self.root, style="Panel.TFrame")
        hero.pack(fill="x", padx=22, pady=(6, 12))

        self.heart_label = tk.Label(
            hero,
            text="♥",
            font=("Segoe UI", 42, "bold"),
            bg="#111827",
            fg="#ef4444"
        )
        self.heart_label.pack(side="left", padx=(18, 12), pady=14)

        hero_text = tk.Frame(hero, bg="#111827")
        hero_text.pack(side="left", fill="both", expand=True)

        tk.Label(
            hero_text,
            text="Live biometric monitoring",
            font=("Segoe UI", 18, "bold"),
            bg="#111827",
            fg="white"
        ).pack(anchor="w", pady=(16, 2))

        tk.Label(
            hero_text,
            text="Displaying real-time pulse sensor data from Arduino.",
            font=("Segoe UI", 11),
            bg="#111827",
            fg="#9ca3af"
        ).pack(anchor="w", pady=(0, 16))

        cards = ttk.Frame(self.root)
        cards.pack(fill="x", padx=22, pady=8)

        self.bpm_card, self.bpm_value_label = self.create_metric_card(cards, "BPM", self.current_bpm)
        self.bpm_card.pack(side="left", expand=True, fill="both", padx=8)

        self.signal_card, self.signal_value_label = self.create_metric_card(cards, "Live Signal", self.current_signal)
        self.signal_card.pack(side="left", expand=True, fill="both", padx=8)

        self.status_card, self.status_value_label = self.create_metric_card(cards, "Heart Rate Status", self.hr_status)
        self.status_card.pack(side="left", expand=True, fill="both", padx=8)

        chart_card = ttk.Frame(self.root, style="Panel.TFrame")
        chart_card.pack(fill="both", expand=True, padx=22, pady=(10, 18))

        chart_top = tk.Frame(chart_card, bg="#111827")
        chart_top.pack(fill="x", padx=14, pady=(12, 0))

        tk.Label(
            chart_top,
            text="Live Pulse Sensor Waveform",
            font=("Segoe UI", 13, "bold"),
            bg="#111827",
            fg="#e5e7eb"
        ).pack(side="left")

        self.scan_label = tk.Label(
            chart_top,
            text="Monitoring...",
            font=("Segoe UI", 10, "bold"),
            bg="#111827",
            fg="#22c55e"
        )
        self.scan_label.pack(side="right")

        self.fig = Figure(figsize=(10, 4.9), dpi=100, facecolor="#111827")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#111827")

        self.line, = self.ax.plot([], [], linewidth=2)

        self.ax.set_ylim(0, 1023)
        self.ax.set_xlim(0, 299)
        self.ax.set_title("Real-Time Pulse Wave", color="white", fontsize=12)
        self.ax.set_ylabel("Sensor Value", color="white")
        self.ax.set_xlabel("Samples", color="white")
        self.ax.grid(True, alpha=0.2)

        self.ax.tick_params(axis="x", colors="white")
        self.ax.tick_params(axis="y", colors="white")

        for spine in self.ax.spines.values():
            spine.set_color("white")

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_card)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(
            self.root,
            text="Waveform shows the real pulse sensor signal. BPM and status update from live Arduino serial data.",
            style="Muted.TLabel"
        ).pack(pady=(0, 10))

    def create_metric_card(self, parent, title_text, value_var):
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)

        title = ttk.Label(card, text=title_text, style="CardTitle.TLabel")
        title.pack(anchor="w")

        value = tk.Label(
            card,
            textvariable=value_var,
            font=("Segoe UI", 30, "bold"),
            bg="#182235",
            fg="white"
        )
        value.pack(anchor="center", pady=(20, 8))

        return card, value

    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.current(0)
        else:
            self.port_combo.set("")

    def connect_serial(self):
        selected_port = self.port_combo.get().strip()
        if not selected_port:
            messagebox.showwarning("No Port", "Please select a COM port.")
            return

        try:
            self.serial_conn = serial.Serial(selected_port, 115200, timeout=1)
            time.sleep(2)
            self.running = True
            self.connection_status.set(f"Connected to {selected_port}")
            self.monitor_text.set("Live stream active")
            self.connection_dot.config(fg="#22c55e")

            reader_thread = Thread(target=self.read_serial_data, daemon=True)
            reader_thread.start()

        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect:\n{e}")
            self.connection_status.set("Disconnected")
            self.monitor_text.set("Idle")
            self.connection_dot.config(fg="#ef4444")

    def disconnect_serial(self):
        self.running = False

        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

        self.serial_conn = None
        self.connection_status.set("Disconnected")
        self.monitor_text.set("Idle")
        self.connection_dot.config(fg="#ef4444")

    def get_hr_status(self, bpm):
        if bpm < 60:
            return "Slow", "#60a5fa"
        elif bpm <= 100:
            return "Normal", "#22c55e"
        return "Fast", "#f97316"

    def read_serial_data(self):
        while self.running and self.serial_conn and self.serial_conn.is_open:
            try:
                line = self.serial_conn.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                prefix = line[0]
                value_part = line[1:].strip()

                if not value_part.isdigit():
                    continue

                value = int(value_part)

                if prefix == "S":
                    self.signal_data.append(value)
                    self.current_signal.set(str(value))
                    self.has_signal = True

                elif prefix == "B":
                    self.current_bpm.set(str(value))
                    label, color = self.get_hr_status(value)
                    self.hr_status.set(label)
                    self.last_status_color = color
                    self.last_beat_flash_time = time.time()

                elif prefix == "Q":
                    pass

            except Exception:
                pass

    def animate_ui(self):
        now = time.time()
        beat_active = (now - self.last_beat_flash_time) < 0.18

        if beat_active:
            self.heart_label.config(font=("Segoe UI", 50, "bold"), fg="#ff4d6d")
            self.bpm_value_label.config(fg="#ff4d6d")
        else:
            self.heart_label.config(font=("Segoe UI", 42, "bold"), fg="#ef4444")
            self.bpm_value_label.config(fg="white")

        self.status_value_label.config(fg=self.last_status_color)

        if self.running:
            if int(now * 2) % 2 == 0:
                self.scan_label.config(text="Monitoring...")
            else:
                self.scan_label.config(text="Monitoring")
        else:
            self.scan_label.config(text="Disconnected", fg="#ef4444")

        if self.running:
            self.scan_label.config(fg="#22c55e")

        self.root.after(60, self.animate_ui)

    def update_plot(self):
        if self.has_signal and len(self.signal_data) > 1:
            y_values = list(self.signal_data)
            x_values = list(range(len(y_values)))
            self.line.set_data(x_values, y_values)
            self.ax.set_xlim(0, max(299, len(y_values) - 1))
        else:
            self.line.set_data([], [])
            self.ax.set_xlim(0, 299)

        self.canvas.draw_idle()
        self.root.after(40, self.update_plot)

    def on_close(self):
        self.disconnect_serial()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = HeartRateMonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()