import asyncio
from day2.barista_agent import BaristaAgent

class DummySession:
    async def say(self, text):
        print('[Agent says] ' + text)

async def test():
    sess = DummySession()
    bar = BaristaAgent(sess)
    await bar.start()
    await bar.on_user_message('Hi, I want a medium oat latte with whipped cream. Name is Sahil')
    await bar.on_user_message('That\'s all')
    print('--- Done. Check the orders/ folder for a JSON file ---')

if __name__ == "__main__":
    asyncio.run(test())
