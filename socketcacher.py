import websockets
import asyncio
import json
from telegram import Bot, ParseMode
from binance import AsyncClient, BinanceSocketManager
import cacher
from const import *
import const

bot = Bot('TELGRAM_TOKEN')
ADMIN = ['TELEGRAM_ID']
symbols = ["SOLUSDT"]

binance_price_cacher = cacher.Tabar(host=REDIS_HOST, port=REDIS_PORT, db=12)


def truncate(f, n):
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return '.'.join([i, (d + '0' * n)[:n]])


def bot_logger(text: str):
    text = str(text)
    try:
        for x in ADMIN:
            bot.send_message(chat_id=x, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(e)


def analyzer(msg):
    bot_logger(msg)
    print(msg)


async def callback(data: list):
    for ticker in data:
        event = ticker.get('e')
        if event == '24hrTicker':
            symbol = ticker.get('s')
            if symbols is not None and len(symbols) > 0:
                if symbol.upper() not in symbols:
                    continue
            symbol_splitted = symbol.split('USDT')[0]
            price = float(truncate(float(ticker.get('c')), const.SYMBOL_PRICE_ROUND_POINT[symbol_splitted]))
            binance_dictionary = {"BUY": price, "SELL": price}
            binance_price_cacher.cache_price(symbol_splitted, data=binance_dictionary)
            print(f"Symbol : {symbol_splitted} // Price : {price}")


async def main():
    client = await AsyncClient.create()
    socket_manager = BinanceSocketManager(client)
    ticker_socket = socket_manager.ticker_socket()
    async with ticker_socket as ts:
        while True:
            try:
                res = await ts.recv()
                await callback(res)
            except Exception as e:
                print(e)
                await asyncio.sleep(1)
                await ts.close()
                await client.close_connection()
                await asyncio.sleep(1)
                await main()

    await client.close_connection()

    await asyncio.sleep(1)

    await main()


def main_main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())


main_main()
