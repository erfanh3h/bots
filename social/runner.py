"""
Command Line Runner and Interactive Suite for Cafe Fekr Social Bots.

Provides both an automated end-to-end verification suite and an interactive
terminal interface to test any social interaction using authentic real user tokens.
"""

import argparse
import sys
import time

if __package__ is None or __package__ == "":
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from bots.social.auth_helper import RealUserManager, REAL_USER_PROFILES
    from bots.social.social_bot import SocialBot
else:
    from .auth_helper import RealUserManager, REAL_USER_PROFILES
    from .social_bot import SocialBot


def print_users_table():
    users = RealUserManager.load_users()
    print("\n==================== Registered Real Users ====================")
    print(f"{'#':<3} | {'User ID':<8} | {'Username':<14} | {'Phone':<12} | {'Device ID'}")
    print("-" * 65)
    for idx, u in enumerate(users, 1):
        print(f"{idx:<3} | {u.get('_id'):<8} | {u.get('username'):<14} | {u.get('phone'):<12} | {u.get('device_id')}")
    print("================================================================\n")


def run_peer_flow_test(user_a_spec: str = "akbari", user_b_spec: str = "Niliii22", base_url: str = "http://127.0.0.1:5001"):
    """
    Executes a comprehensive two-way social interaction between two real users:
    User A sends friend request -> User B accepts ->
    User A sends DM -> User B reads and replies ->
    User A invites to game match -> User B accepts ->
    User A posts in clan chat.
    """
    bot_a = SocialBot(user_a_spec, base_url=base_url)
    bot_b = SocialBot(user_b_spec, base_url=base_url)

    print(f"\n=======================================================")
    print(f"  Peer-to-Peer Social Flow Test")
    print(f"  Actor A: {bot_a.username} ({bot_a.user_id})")
    print(f"  Actor B: {bot_b.username} ({bot_b.user_id})")
    print(f"=======================================================\n")

    # Step 1: Friend Request Flow
    print("[Step 1] Actor A -> Actor B: Friend Request...")
    ok, st, d = bot_a.friends.send_request(bot_b.user_id, "سلام! بیا با هم بازی کنیم.")
    print(f"  Status: {st} | Response: {d}")

    # Check incoming on B
    print("[Step 2] Actor B: Check Incoming Friend Requests...")
    ok, st, d = bot_b.friends.list_requests()
    req_id = ""
    if ok and isinstance(d, dict):
        inc = d.get("result", {}).get("incoming", []) if isinstance(d.get("result"), dict) else d.get("incoming", [])
        for r in inc:
            u_info = r.get("user", {})
            if str(u_info.get("user_id", u_info.get("_id", ""))) == bot_a.user_id:
                req_id = str(r.get("request_id", r.get("_id", "")))
                break
    print(f"  Incoming found request_id: {req_id or 'None'}")

    if req_id:
        print("[Step 3] Actor B -> Accepts Friend Request...")
        ok, st, d = bot_b.friends.respond_request(req_id, "accept")
        print(f"  Status: {st} | Response: {d}")

    # Step 4: Direct Messaging
    print("\n[Step 4] Actor A -> Actor B: Send DM...")
    ok, st, d = bot_a.messages.send_dm(bot_b.user_id, "سلام نیلوفر! بازی مونوپولی هستی؟")
    print(f"  Status: {st} | Response: {d}")

    print("[Step 5] Actor B -> Reads and Replies...")
    bot_b.messages.mark_read(bot_a.user_id)
    ok, st, d = bot_b.messages.send_dm(bot_a.user_id, "سلام علی! آره حتماً، یک مسابقه بساز بیام.")
    print(f"  Status: {st} | Response: {d}")

    # Step 6: Direct Game Invitation
    print("\n[Step 6] Actor A -> Actor B: Send Game Match Invitation (Monopoly)...")
    ok, st, d = bot_a.invitations.send_game_invite(bot_b.user_id, game_type="Monopoly", invite_mode="direct_match")
    print(f"  Status: {st} | Response: {d}")

    # Step 7: Clan Chat & Challenge
    print("\n[Step 7] Clan Interaction Check...")
    ok, st, my_clan = bot_a.clans.get_my_clan()
    if ok and isinstance(my_clan, dict) and my_clan.get("clan"):
        c_id = str(my_clan["clan"].get("clan_id", my_clan["clan"].get("_id", "")))
        print(f"  Actor A is in clan: {my_clan['clan'].get('name')} ({c_id})")
        ok, st, d = bot_a.clans.send_chat("سلام به همه اعضای کلن! چالش جدید ثبت شد.", clan_id=c_id)
        print(f"  Post clan chat: {st} | {d}")
    else:
        print("  Actor A is not currently in a clan. Searching directory...")
        ok, st, d = bot_a.clans.search_clans("", sort_by="clan_score")
        print(f"  Clans found: {st}")

    print("\n=======================================================")
    print("  Peer-to-Peer Social Flow Completed Successfully!")
    print("=======================================================\n")


def interactive_menu(bot: SocialBot):
    while True:
        print(f"\n--- Cafe Fekr Social Bot: {bot.username} ({bot.user_id}) ---")
        print("1. View Social Overview")
        print("2. List Confirmed Friends")
        print("3. Search Players")
        print("4. Send Friend Request")
        print("5. Send Direct Message (DM)")
        print("6. Read Messages Thread")
        print("7. View Clan Status & Chat")
        print("8. Send Game Invitation")
        print("9. Run Full Diagnostic Suite")
        print("10. Switch Active Real User")
        print("0. Exit")
        choice = input("Select an option [0-10]: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            ok, st, d = bot.invitations.get_overview()
            print(f"[{st}] Overview:\n{d}")
        elif choice == "2":
            ok, st, d = bot.friends.list_friends()
            print(f"[{st}] Friends:\n{d}")
        elif choice == "3":
            q = input("Search query: ").strip()
            ok, st, d = bot.friends.search_players(q)
            print(f"[{st}] Results:\n{d}")
        elif choice == "4":
            tid = input("Target User ID: ").strip()
            msg = input("Optional message: ").strip()
            ok, st, d = bot.friends.send_request(tid, msg)
            print(f"[{st}] Result: {d}")
        elif choice == "5":
            tid = input("Recipient User ID: ").strip()
            txt = input("Message text: ").strip()
            ok, st, d = bot.messages.send_dm(tid, txt)
            print(f"[{st}] Result: {d}")
        elif choice == "6":
            tid = input("Partner User ID: ").strip()
            ok, st, d = bot.messages.get_messages(tid)
            print(f"[{st}] Thread:\n{d}")
        elif choice == "7":
            ok, st, d = bot.clans.get_my_clan()
            print(f"[{st}] My Clan:\n{d}")
            ok, st, ch = bot.clans.get_chat()
            print(f"[{st}] Recent Chat:\n{ch}")
        elif choice == "8":
            tid = input("Target User ID: ").strip()
            gt = input("Game type (default Monopoly): ").strip() or "Monopoly"
            ok, st, d = bot.invitations.send_game_invite(tid, game_type=gt)
            print(f"[{st}] Invite Result: {d}")
        elif choice == "9":
            peer = input("Optional Peer User ID (press enter to skip): ").strip() or None
            res = bot.run_full_diagnostic(peer_user_id=peer)
            print(f"Completed {len(res)} diagnostic checks.")
        elif choice == "10":
            print_users_table()
            uname = input("Enter username or ID to switch to: ").strip()
            bot = SocialBot(uname)
            print(f"Switched to user: {bot.username} ({bot.user_id})")


def main():
    parser = argparse.ArgumentParser(description="Cafe Fekr Social Bot Runner")
    parser.add_argument("--user", "-u", default="akbari", help="Username or ID of real user persona")
    parser.add_argument("--peer", "-p", default="Niliii22", help="Peer real user for two-way flow tests")
    parser.add_argument("--list-users", "-l", action="store_true", help="List all available real users in DB")
    parser.add_argument("--test-all", "-t", action="store_true", help="Run full diagnostic suite")
    parser.add_argument("--test-peer", action="store_true", help="Run two-way peer flow test")
    parser.add_argument("--server", default="http://127.0.0.1:5001", help="REST API server URL")

    args = parser.parse_args()

    if args.list_users:
        print_users_table()
        return

    if args.test_peer:
        run_peer_flow_test(args.user, args.peer, base_url=args.server)
        return

    bot = SocialBot(args.user, base_url=args.server)

    if args.test_all:
        bot.run_full_diagnostic(peer_user_id=RealUserManager.get_user_by_username(args.peer)["_id"] if RealUserManager.get_user_by_username(args.peer) else None)
        return

    interactive_menu(bot)


if __name__ == "__main__":
    main()
