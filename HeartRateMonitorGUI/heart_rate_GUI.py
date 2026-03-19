import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
from collections import deque
from threading import Thread
import time

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class HeartRateMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Arduino Heart Rate Monitor")
        self.root.geometry("1000x650")
        self.root.configure(bg="#0f172a")

        self.serial_conn = None
        self.running = False

        self.current_bpm = tk.StringVar(value="--")
        self.current_signal = tk.StringVar(value="--")
        self.current_ibi = tk.StringVar(value="--")
        self.status_text = tk.StringVar(value="Disconnected")

        self.signal_data = deque([512] * 150, maxlen=150)
        self.last_beat_flash_time = 0

        self.build_ui()
        self.refresh_ports()
        self.update_plot()

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background="#0f172a")
        style.configure("Card.TFrame", background="#1e293b")
        style.configure("TLabel", background="#0f172a", foreground="white", font=("Segoe UI", 11))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="white", background="#0f172a")
        style.configure("CardTitle.TLabel", font=("Segoe UI", 12, "bold"), foreground="#cbd5e1", background="#1e293b")
        style.configure("Value.TLabel", font=("Segoe UI", 28, "bold"), foreground="white", background="#1e293b")
        style.configure("Status.TLabel", font=("Segoe UI", 11, "bold"), foreground="#93c5fd", background="#0f172a")
        style.configure("TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TCombobox", font=("Segoe UI", 10))

        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=20, pady=(20, 10))

        title = ttk.Label(top_frame, text="Arduino Heart Rate Monitor", style="Title.TLabel")
        title.pack(side="left")

        status = ttk.Label(top_frame, textvariable=self.status_text, style="Status.TLabel")
        status.pack(side="right")

        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=20, pady=10)

        ttk.Label(control_frame, text="Serial Port:").pack(side="left", padx=(0, 8))

        self.port_combo = ttk.Combobox(control_frame, state="readonly", width=20)
        self.port_combo.pack(side="left", padx=(0, 10))

        refresh_btn = ttk.Button(control_frame, text="Refresh Ports", command=self.refresh_ports)
        refresh_btn.pack(side="left", padx=5)

        connect_btn = ttk.Button(control_frame, text="Connect", command=self.connect_serial)
        connect_btn.pack(side="left", padx=5)

        disconnect_btn = ttk.Button(control_frame, text="Disconnect", command=self.disconnect_serial)
        disconnect_btn.pack(side="left", padx=5)

        metrics_frame = ttk.Frame(self.root)
        metrics_frame.pack(fill="x", padx=20, pady=10)

        self.bpm_card = self.create_metric_card(metrics_frame, "BPM", self.current_bpm)
        self.bpm_card.pack(side="left", expand=True, fill="both", padx=8)

        self.signal_card = self.create_metric_card(metrics_frame, "Signal", self.current_signal)
        self.signal_card.pack(side="left", expand=True, fill="both", padx=8)

        self.ibi_card = self.create_metric_card(metrics_frame, "IBI (ms)", self.current_ibi)
        self.ibi_card.pack(side="left", expand=True, fill="both", padx=8)

        graph_frame = ttk.Frame(self.root, style="Card.TFrame")
        graph_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        graph_title = ttk.Label(graph_frame, text="Live Pulse Signal", style="CardTitle.TLabel")
        graph_title.pack(anchor="w", padx=15, pady=(12, 0))

        self.fig = Figure(figsize=(9, 4.5), dpi=100, facecolor="#1e293b")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#1e293b")

        self.line, = self.ax.plot(list(self.signal_data), linewidth=2)

        self.ax.set_ylim(0, 1023)
        self.ax.set_xlim(0, len(self.signal_data) - 1)
        self.ax.set_title("Pulse Sensor Signal", color="white", fontsize=12)
        self.ax.set_ylabel("ADC Value", color="white")
        self.ax.set_xlabel("Samples", color="white")

        self.ax.tick_params(axis="x", colors="white")
        self.ax.tick_params(axis="y", colors="white")

        for spine in self.ax.spines.values():
            spine.set_color("white")

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def create_metric_card(self, parent, title_text, value_var):
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)

        title = ttk.Label(card, text=title_text, style="CardTitle.TLabel")
        title.pack(anchor="w")

        value = ttk.Label(card, textvariable=value_var, style="Value.TLabel")
        value.pack(anchor="center", pady=(18, 8))

        return card

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
            self.status_text.set(f"Connected to {selected_port}")

            thread = Thread(target=self.read_serial_data, daemon=True)
            thread.start()

        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect:\n{e}")
            self.status_text.set("Disconnected")

    def disconnect_serial(self):
        self.running = False

        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

        self.serial_conn = None
        self.status_text.set("Disconnected")

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

                elif prefix == "B":
                    self.current_bpm.set(str(value))
                    self.last_beat_flash_time = time.time()

                elif prefix == "Q":
                    self.current_ibi.set(str(value))

            except Exception:
                pass

    def update_plot(self):
        self.line.set_ydata(list(self.signal_data))
        self.line.set_xdata(range(len(self.signal_data)))
        self.ax.set_xlim(0, len(self.signal_data) - 1)
        self.canvas.draw_idle()

        # beat flash effect
        if time.time() - self.last_beat_flash_time < 0.25:
            self.bpm_card.configure(style="Card.TFrame")
        else:
            self.bpm_card.configure(style="Card.TFrame")

        self.root.after(50, self.update_plot)

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