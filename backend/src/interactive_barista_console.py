import sys
import pathlib
import asyncio

# ensure repo root is importable (agent file is backend/src/..., repo root is parents[2])
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from day2.barista_agent import BaristaAgent

EXIT_COMMANDS = {"quit", "exit", "q"}

class ConsoleSession:
    async def say(self, text):
        print('[Agent says] ' + text)

async def run_console():
    print("Interactive Barista Console — type a sentence to the agent.")
    print("To exit at any time: type 'quit', 'exit', 'q' or press Enter on an empty line.")
    while True:
        # create a fresh session/agent for each new order cycle
        sess = ConsoleSession()
        bar = BaristaAgent(sess)
        await bar.start()

        # prompt user for the starting utterance(s)
        while True:
            try:
                user = input('You: ').strip()
            except (EOFError, KeyboardInterrupt):
                print('\nExiting interactive console.')
                return

            # global exits
            if user.lower() in EXIT_COMMANDS or user == '':
                print('Exiting interactive console.')
                return

            # forward to the barista
            await bar.on_user_message(user)

            # check if order complete (no missing fields)
            missing = [k for k, v in bar.order.items() if not v]
            if not missing:
                # order finished; prompt whether to continue or exit
                print('Order completed. Start new order? Type "yes" to continue or press Enter to quit.')
                try:
                    cont = input('Continue? (yes/Enter to quit): ').strip()
                except (EOFError, KeyboardInterrupt):
                    print('\nExiting interactive console.')
                    return

                if cont.lower() in ('yes', 'y'):
                    # start a fresh order loop (outer while will recreate agent)
                    break
                else:
                    print('Exiting interactive console.')
                    return
        # outer while continues, creating a fresh agent for next order

if __name__ == '__main__':
    asyncio.run(run_console())
