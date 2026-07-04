import socket
import threading
import queue
from typing import Optional, Callable


class GuiClient:
    def __init__(self) -> None:
        self.sock: Optional[socket.socket] = None
        self._recv_thread: Optional[threading.Thread] = None
        self._queue: queue.Queue[str] = queue.Queue()
        self._running = False

    def connect(self, host: str, port: int) -> None:
        self.sock = socket.create_connection((host, port))
        self._running = True
        self._recv_thread = threading.Thread(target=self._receiver, daemon=True)
        self._recv_thread.start()

    def send(self, message: str) -> None:
        if not self.sock:
            raise RuntimeError("Not connected")
        # normalize newline for server
        data = (message + "\n").encode()
        self.sock.sendall(data)

    def _receiver(self) -> None:
        assert self.sock is not None
        try:
            while self._running:
                data = self.sock.recv(4096)
                if not data:
                    break
                # split incoming by lines in case multiple messages arrive
                for line in data.decode(errors="ignore").splitlines():
                    self._queue.put(line)
        except Exception:
            pass
        finally:
            self._running = False

    def get_message(self) -> Optional[str]:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
