import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
from gui_client import GuiClient
import threading


class DirtyDogGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dirty Dog - GUI Prototype")
        self.geometry("700x500")

        self.client = GuiClient()

        self._build_ui()
        self._poll()

    def _build_ui(self):
        frame = tk.Frame(self)
        frame.pack(fill=tk.X, padx=8, pady=6)

        tk.Label(frame, text="Host:").pack(side=tk.LEFT)
        self.host_var = tk.StringVar(value="localhost")
        tk.Entry(frame, textvariable=self.host_var, width=12).pack(side=tk.LEFT)

        tk.Label(frame, text="Port:").pack(side=tk.LEFT, padx=(8, 0))
        self.port_var = tk.IntVar(value=9009)
        tk.Entry(frame, textvariable=self.port_var, width=6).pack(side=tk.LEFT)

        tk.Label(frame, text="Name:").pack(side=tk.LEFT, padx=(8, 0))
        self.name_var = tk.StringVar()
        tk.Entry(frame, textvariable=self.name_var, width=12).pack(side=tk.LEFT)

        tk.Button(frame, text="Connect", command=self.connect).pack(side=tk.LEFT, padx=6)
        tk.Button(frame, text="Disconnect", command=self.disconnect).pack(side=tk.LEFT)

        # Messages area
        self.msg_area = scrolledtext.ScrolledText(self, state=tk.DISABLED)
        self.msg_area.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Controls
        ctl = tk.Frame(self)
        ctl.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.entry_var = tk.StringVar()
        tk.Entry(ctl, textvariable=self.entry_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(ctl, text="Say", command=self.on_say).pack(side=tk.LEFT, padx=4)
        tk.Button(ctl, text="Ready", command=self.on_ready).pack(side=tk.LEFT, padx=4)
        tk.Button(ctl, text="Bid", command=self.on_bid).pack(side=tk.LEFT, padx=4)
        tk.Button(ctl, text="Play", command=self.on_play).pack(side=tk.LEFT, padx=4)

    def connect(self):
        host = self.host_var.get()
        port = int(self.port_var.get())
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Name required", "Please enter a display name before connecting")
            return
        try:
            self.client.connect(host, port)
            # send join immediately
            self.client.send(f"JOIN {name}")
            self._append(f"Connected to {host}:{port} as {name}")
        except Exception as e:
            messagebox.showerror("Connection failed", str(e))

    def disconnect(self):
        try:
            self.client.close()
            self._append("Disconnected")
        except Exception:
            pass

    def on_say(self):
        text = self.entry_var.get().strip()
        if not text:
            return
        try:
            self.client.send(f"SAY {text}")
            self.entry_var.set("")
        except Exception as e:
            messagebox.showerror("Send failed", str(e))

    def on_ready(self):
        try:
            self.client.send("READY")
        except Exception as e:
            messagebox.showerror("Send failed", str(e))

    def on_bid(self):
        bid = simpledialog.askinteger("Bid", "Enter bid amount:")
        if bid is None:
            return
        try:
            self.client.send(f"BID {bid}")
        except Exception as e:
            messagebox.showerror("Send failed", str(e))

    def on_play(self):
        card = simpledialog.askstring("Play", "Enter card to play (e.g. 'AS', '10♠'):")
        if not card:
            return
        try:
            self.client.send(f"PLAY {card}")
        except Exception as e:
            messagebox.showerror("Send failed", str(e))

    def _append(self, message: str) -> None:
        self.msg_area.configure(state=tk.NORMAL)
        self.msg_area.insert(tk.END, message + "\n")
        self.msg_area.configure(state=tk.DISABLED)
        self.msg_area.see(tk.END)

    def _poll(self):
        # poll network queue and append messages
        try:
            while True:
                msg = self.client.get_message()
                if msg is None:
                    break
                self._append(msg)
        except Exception:
            pass
        self.after(100, self._poll)


if __name__ == '__main__':
    app = DirtyDogGUI()
    app.mainloop()
