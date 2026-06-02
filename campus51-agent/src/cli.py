# ============================================================
# src/cli.py
# ------------------------------------------------------------
# تجربة البوت من التيرمنال — من غير WhatsApp.
# ده أحسن مكان تبدأ منه عشان تفهم سلوك الـ agent
# وتشوف بنفسك امتى بينادي الأدوات.
#
# التشغيل:
#   python -m src.cli
# ============================================================

import logging

from src.agent import build_agent, chat_once

# نشغّل logging عشان نشوف tool calls وأي رسائل مهمة
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    print("=" * 50)
    print("  مرشد — Campus 51 (تجربة تيرمنال)")
    print("  اكتب 'خروج' أو 'exit' للإنهاء")
    print("=" * 50)

    agent = build_agent()

    # في التجربة بنستخدم thread واحد ثابت (مستخدم واحد)
    thread_id = "cli-test-user"

    print("\nاكتب رسالتك:\n")

    while True:
        try:
            user_text = input("أنت: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nمع السلامة 👋")
            break

        if user_text.lower() in {"خروج", "exit", "quit"}:
            print("مع السلامة 👋")
            break
        if not user_text:
            continue

        reply = chat_once(agent, user_text, thread_id)
        print(f"\nمرشد: {reply}\n")


if __name__ == "__main__":
    main()
