import socket
import threading

HOST = 'localhost'
PORT = 5050

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

def receive() -> None:
    while True:
        try:
            # Read a larger buffer and normalize whitespace so server-leading newlines
            # don't produce double blank lines on the client terminal.
            msg = client.recv(4096).decode()
            if msg:
                # Strip only outer whitespace; keep internal newlines so multi-line
                # server blocks (like the player roster) render correctly.
                normalized = msg.strip()
                if not normalized:
                    continue

                # Simple labeled parsing so the prototype client renders the
                # server's canonical messages in a consistent, readable way.
                try:
                    # Roster / multi-line blocks
                    if "Players in this game:" in normalized:
                        print("\n--- Players ---")
                        print(normalized)

                    # Turn announcements
                    elif "TURN:" in normalized:
                        for line in normalized.splitlines():
                            print(f"\n>>> {line}")

                    # Trump announcements
                    elif "TRUMP" in normalized or "NO TRUMP" in normalized:
                        print(f"\n== {normalized} ==")

                    # Player hand (showed only to acting player)
                    elif normalized.startswith("Your hand:"):
                        print(f"\n[HAND] {normalized[len('Your hand:'):].strip()}")

                    # Prompts and action reminders
                    elif "Your turn" in normalized or "Place your bid" in normalized or "Type: '<BID>'" in normalized or "Type: '<PLAY>'" in normalized:
                        print(f"\n>>> {normalized}")

                    # Generic fallback
                    else:
                        print(f"\n{normalized}")
                except Exception:
                    # On any parsing error, fall back to raw print so we don't hide
                    # server output during the prototype.
                    print(f"\n{normalized}")
            else:
                break
        except:
            print("[ERROR] Disconnected from server.")
            client.close()
            break

def send() -> None:
    name = input("Enter your name: ")

    # Send JOIN command on connection to match server's expected protocol
    try:
        client.send(f"JOIN {name}".encode())
    except Exception:
        print("[ERROR] Failed to send JOIN to server.")
        return

    while True:
        try:
            msg = input("")
            if msg.lower() == "quit":
                break
            client.send(f"{msg}".encode())  
        except:
            break
    client.close()

# Start threads
threading.Thread(target=receive, daemon=True).start()
send()
