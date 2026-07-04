from game import Game, DEFAULT_MAX_HANDS
import socket
import threading
from typing import Any
import argparse
import os
import sys

# Allow overriding host/port from the command line for easier local
# development and running multiple instances without killing processes.
parser = argparse.ArgumentParser(description="Dirty Dog server")
parser.add_argument("--host", default="localhost", help="Host to bind to")
parser.add_argument("--port", type=int, default=5050, help="Port to bind to")
args = parser.parse_args()

HOST = args.host
PORT = args.port

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Allow quick restart of the server on the same port
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    server.bind((HOST, PORT))
    server.listen()
    print(f"[SERVER] Listening on {HOST}:{PORT} (pid={os.getpid()})")
except OSError as e:
    print(f"[ERROR] Failed to bind to {HOST}:{PORT}: {e}")
    print(f"[HINT] Another process may be listening on that port.\n" \
          f"Run: lsof -nP -iTCP:{PORT} -sTCP:LISTEN to find the PID,\n" \
          f"then kill <PID> or choose a different port with --port.")
    sys.exit(1)

game = Game()
# Notes on cleanup:
# - The Deck instance and Player import that used to be here were removed because
#   the Game object is the authoritative owner of the deck and player objects.
#   Creating a separate Deck() or importing Player here was redundant and led
#   to duplicated state.
# - MIN_PLAYERS constant was removed since the Game instance exposes its
#   own `min_players` configuration and that single source of truth should be used.


def format_player_list() -> str:
    """Return a nicely formatted list of current players with score and READY status."""
    lines = [""]
    for i, conn in enumerate(game.players.keys(), start=1):
        p = game.players[conn]
        status = "[READY]" if conn in game.ready_players else "[NOT READY]"
        lines.append(f"{i}) {p.name} {status}")
    return "\n".join(lines)


def announce_current_turn() -> None:
    """Broadcast which player's turn it currently is (by name)."""
    try:
        current = game.get_current_player_conn()
        if current in game.players:
            name = game.players[current].name
            broadcast(f"\nTURN: {name}'s turn".encode(), None)
    except Exception:
        pass


def announce_current_speaker() -> None:
    """Broadcast whose turn it currently is to speak for chat and light actions."""
    try:
        current = game.get_current_speaker_conn()
        if current in game.players:
            name = game.players[current].name
            broadcast(f"\nSPEAKER: {name}".encode(), None)
    except Exception:
        pass


def safe_send(conn: Any, message: str) -> None:
    if conn is None:
        return
    try:
        conn.sendall(message.encode())
    except Exception as exc:
        print(f"[ERROR] Failed to send to client: {exc}")
        handle_disconnect(conn)


def handle_client(conn: Any, addr) -> None:
    print(f"[NEW CONNECTION] {addr} connected.")
    safe_send(conn, "Welcome! Please type 'JOIN <name>' to enter the game.")

    player_name = None

    while True:
        try:
            # decode converts first 1024 bytes to string
            msg = conn.recv(1024).decode().strip()
            if not msg:
                break

            normalized_msg = msg.strip()
            upper_msg = normalized_msg.upper()

            # JOIN command
            if upper_msg.startswith("JOIN ") and not game.game_started:
                player_name = normalized_msg[5:].strip()

                name_taken = False
                for p in game.players.values():
                    if p.name == player_name:
                        safe_send(conn, "That name is already taken. Choose another.")
                        name_taken = True
                        break

                if name_taken:
                    continue

                game.add_player(conn, player_name)
                print(f"[JOIN] {player_name} joined from {addr}")
                safe_send(conn, f"Hello, {player_name}! You joined the game.")
                # Send the joining player a formatted list of current players
                safe_send(conn, format_player_list())
                safe_send(conn, "\n\nGame starts when all players type <READY>")
                # Instead of a join message, broadcast the updated player list
                broadcast(format_player_list().encode(), conn)

            # Speaker turn controls for chat and light actions
            elif upper_msg.startswith("NEXT") or upper_msg.startswith("PASS"):
                if not player_name:
                    safe_send(conn, "You must JOIN before taking turns.")
                else:
                    next_conn = game.advance_speaker()
                    if next_conn is None:
                        safe_send(conn, "No players are available to speak.")
                    else:
                        next_name = game.players[next_conn].name
                        safe_send(conn, f"You passed the turn to {next_name}.")
                        announce_current_speaker()

            elif upper_msg.startswith("SAY "):
                if not player_name:
                    safe_send(conn, "You must JOIN before sending messages.")
                elif not game.is_current_speaker(conn):
                    safe_send(conn, "It is not your turn to speak. Type NEXT to pass.")
                else:
                    chat_msg = normalized_msg[4:].strip()
                    print(f"[{player_name}] says: {chat_msg}")
                    broadcast(f"{player_name}: {chat_msg}".encode(), conn)
                    game.advance_speaker()
                    announce_current_speaker()

            # READY command
            elif upper_msg.startswith("READY") and not game.game_started:
                if player_name:
                    print(f"[{player_name}] is ready to play")
                    # Mark the player as ready first so the formatted list includes them
                    all_ready = game.mark_ready(conn)
                    # Broadcast only the updated formatted player list (no separate text)
                    broadcast(format_player_list().encode(), None)
                    if all_ready:
                        # Remind players of the max before starting
                        try:
                            broadcast(f"\nMax hand size for this match: {DEFAULT_MAX_HANDS}".encode(), None)
                        except Exception:
                            pass
                        broadcast("\nGAME STARTING!".encode(), None)
                        
                        game.start_game()
                        hands = game.build_hands()

                        # Reveal trump to all players before bidding
                        if game.trump:
                            broadcast(f"\nTRUMP is {game.trump}".encode(), None)
                        else:
                            broadcast("\nNO TRUMP this hand".encode(), None)

                        broadcast("\nPlace your bid using '<BID> #'".encode(), None)
                        game.BID_PHASE = True

                        for player_conn, hand_msg in hands.items():
                            safe_send(player_conn, hand_msg)

                        current_conn = game.get_current_player_conn()
                        safe_send(current_conn, "\nIt's your turn.")
                        announce_current_turn()
            
            elif upper_msg.startswith("BID ") and game.BID_PHASE:
                if not game.game_started:
                    safe_send(conn, "The game hasn't started yet.")
                    continue

                if not game.is_player_turn(conn):
                    safe_send(conn, "It's not your turn.")
                    continue

                if not game.last_conn:
                    game.last_conn = game.get_last_player_conn()
                
                game.BID_PHASE = True
                player = game.players[conn]
                bid = msg[4:].strip()

                if not bid.isdigit():
                    safe_send(conn, "Please enter a valid digit")
                    continue
            
                elif int(bid) + game.bid_count == game.cards_per_player and conn == game.last_conn:
                    safe_send(conn, "Number of bids cannot equal number of cards in hand")
                    continue

                broadcast(f"{player.name} has bid {bid} card(s)".encode(), conn)
                safe_send(conn, f"Your bid of {bid} is accepted.")
                game.place_bid(conn, int(bid))
                

                game.advance_turn()
                if len(game.bids) < len(game.players):
                    next_conn = game.get_current_player_conn()
                    safe_send(next_conn, "\nYour turn to bid. Type: '<BID> #'")
                    announce_current_turn()
                
                else:
                    game.debug_state()

                    first_conn = game.get_current_player_conn()
                    broadcast("\nAll bids received.".encode(), None)
                    game.BID_PHASE = False
                    
                    hands = game.build_hands()

                    for player_conn, hand_msg in hands.items():
                        safe_send(player_conn, hand_msg)
                    safe_send(first_conn, "\nYour turn to play. Type: '<PLAY> card'")
                    announce_current_turn()

                    game.PLAY_PHASE = True
                    # DO NOT advance here: the first player should be able to play
                    # before the turn index moves. advance_turn() is called after
                    # they actually play.

            elif upper_msg.startswith("PLAY ") and game.PLAY_PHASE:
                if not game.game_started:
                    safe_send(conn, "The game hasn't started yet.")
                    continue

                if not game.is_player_turn(conn):
                    safe_send(conn, "It's not your turn.")
                    continue

                card_played = normalized_msg[5:].strip()
                player = game.players[conn]

                matching_card, error = game.validate_play(conn, card_played)
                if error:
                    safe_send(conn, error)
                    continue

                game.record_play(conn, matching_card)

                # Announce the play consistently to all players (including the player)
                broadcast(f"\n{player.name} played {card_played}".encode(), None)

                # Send the player their updated hand in a consistent format
                hand_str = ', '.join(str(card) for card in player.hand)
                try:
                    safe_send(conn, f"\nYour hand: {hand_str}")
                except Exception:
                    pass

                # Advance turn and notify next player
                game.advance_turn()
                if len(game.played_cards) < len(game.players):
                    next_conn = game.get_current_player_conn()
                    safe_send(next_conn, "\nYour turn to PLAY. Type: '<PLAY> card'")
                    announce_current_turn()
                else:
                    # All players have played: resolve trick
                    game.debug_state()
                    broadcast("\nEach player has played a card.".encode(), None)

                    # Determine winner of the trick
                    winner_conn, winning_card = game.resolve_trick()
                    winner_name = game.players[winner_conn].name
                    broadcast(f"\n{winner_name} won the trick with {winning_card}".encode(), None)

                    # Award trick to player
                    game.players[winner_conn].tricks += 1

                    # Clear played cards for next trick and set next turn to winner
                    game.played_cards = {}
                    game.leading_suit = None
                    if winner_conn in game.turn_order:
                        game.current_turn_index = game.turn_order.index(winner_conn)
                    # DO NOT advance here; winner should be current and lead next trick.

                    # Check end of round (all cards played)
                    remaining = any(p.hand for p in game.players.values())
                    if not remaining:
                        # End of hand — compute scoring per rules
                        game.score_round()
                        for pconn, player in game.players.items():
                            if player.tricks == player.bid:
                                safe_send(pconn, f"You made your bid! Score +{5 + player.bid}. Total: {player.score}")
                            else:
                                safe_send(pconn, f"You missed your bid. Tricks: {player.tricks}, Bid: {player.bid}. Total: {player.score}")
                        broadcast("\nRound complete.".encode(), None)
                        # reset for next round
                        game.reset()

                        if getattr(game, 'match_over', False):
                            try:
                                broadcast("\nMATCH OVER! Final Scores:".encode(), None)
                                # send each player's score
                                for pconn, player in game.players.items():
                                    try:
                                        safe_send(pconn, f"\n{player.name}: {player.score}")
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        else:
                            # Auto-start next hand: deal, reveal trump, and enter BID phase
                            try:
                                game.start_game()
                                hands = game.build_hands()

                                # Announce max hand size for this session
                                try:
                                    broadcast(f"\nMax hand size for this match: {DEFAULT_MAX_HANDS}".encode(), None)
                                except Exception:
                                    pass

                                # Reveal trump to all players before bidding
                                if game.trump:
                                    broadcast(f"\nTRUMP is {game.trump}".encode(), None)
                                else:
                                    broadcast("\nNO TRUMP this hand".encode(), None)

                                broadcast("\nPlace your bid using '<BID> #'".encode(), None)
                                game.BID_PHASE = True

                                for player_conn, hand_msg in hands.items():
                                    try:
                                        safe_send(player_conn, hand_msg)
                                    except Exception:
                                        pass

                                # Prompt first bidder and announce turn
                                first_conn = game.get_current_player_conn()
                                try:
                                    safe_send(first_conn, "\nYour turn to bid. Type: '<BID> #'")
                                except Exception:
                                    pass
                                announce_current_turn()
                            except Exception as e:
                                print(f"[ERROR] Failed to auto-start next hand: {e}")
                    else:
                        # Notify next player to play
                        next_conn = game.get_current_player_conn()
                        safe_send(next_conn, "\nYour turn to PLAY. Type: '<PLAY> card'")
                        announce_current_turn()

            else:
                safe_send(conn, "Invalid command.")

        except Exception as e:
            print(f"[ERROR] {addr} - {e}")
            break

    print(f"[DISCONNECT] {addr} disconnected.")
    if player_name:
        broadcast(f"{player_name} has left the game.".encode(), conn)
        # Broadcast updated player list after disconnect
        broadcast(format_player_list().encode(), None)
        handle_disconnect(conn)
    conn.close()

def broadcast(message: bytes, sender_conn: Any) -> None:
    # Iterate over a snapshot of current clients to allow safe removal
    for client in list(game.players.keys()):
        if client == sender_conn:
            continue
        try:
            client.sendall(message)
        except Exception as e:
            print(f"[ERROR] Failed to send message to a client: {e}")
            try:
                client.close()
            except Exception:
                pass
            # Clean up client from game state only once the socket is truly gone
            if client in game.players:
                handle_disconnect(client)
    

def handle_disconnect(conn: Any) -> None:
    # Defensive disconnect handling: ensure socket is closed and player
    # state is removed exactly once. This prevents later attempts to use
    # a closed socket which caused "Bad file descriptor" errors.
    try:
        try:
            conn.shutdown(2)
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    except Exception:
        pass

    # Remove from game state collections
    try:
        if conn in game.players:
            del game.players[conn]
    except Exception:
        pass
    try:
        if conn in game.ready_players:
            game.ready_players.discard(conn)
    except Exception:
        pass
    try:
        if conn in game.turn_order:
            game.turn_order.remove(conn)
    except Exception:
        pass
    try:
        if hasattr(game, 'speaker_order') and conn in game.speaker_order:
            game.speaker_order.remove(conn)
            # normalize current speaker index
            if getattr(game, 'current_speaker_index', 0) >= len(game.speaker_order):
                game.current_speaker_index = 0
    except Exception:
        pass

    # Optional: Reset game state or broadcast status if too few players
    if game.game_started and len(game.players) < game.min_players:
        try:
            broadcast("A player left. Game cannot continue.".encode(), None)
        except Exception:
            pass
        try:
            game.reset()
        except Exception:
            pass
    

def start():
    try:
        while True:
            conn, address = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, address), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print('\n[SERVER] Shutting down...')
    finally:
        try:
            server.close()
        except:
            pass

start()
 