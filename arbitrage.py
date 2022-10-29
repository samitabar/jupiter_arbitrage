import time
import base64
from solana.publickey import PublicKey
from solana.keypair import Keypair
from telegram import Bot, ParseMode
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.rpc.api import Client as SolClient
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
from binance import Client
import json
import requests
import const
from threading import Thread
import cacher
from cacher import Tabar
from const import *
import const

binance_client = Client(api_key="KEY",
                        api_secret="SECRET")
account = "YOUR SOLANA ACCOUNT"

owner = Keypair.from_secret_key(account['secret_key']['machine_readable'].encode("latin-1"))
sender = owner

solana_client = SolClient("https://arbprotocol.genesysgo.net/")
ADMIN = ["YOUR TELEGRAM ID"]
bot = Bot('TELEGRAM TOKEN')

binance_price_cacher = cacher.Tabar(host=REDIS_HOST, port=REDIS_PORT, db=12)
balance = cacher.Tabar(host=REDIS_HOST, port=REDIS_PORT, db=15)


def bot_logger(text: str):
    text = str(text)
    try:
        for x in ADMIN:
            bot.send_message(chat_id=x, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(e)


def truncate(f, n):
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return float('.'.join([i, (d + '0' * n)[:n]]))


def coin_to_wei(amount, coin):
    return int(amount * const.COIN_DECIMALS[coin])


def wei_to_coin(amount, coin):
    return float(truncate(float(amount / const.COIN_DECIMALS[coin]), const.COIN_DECIMAL_AMOUNT[coin]))


def get_binance_price(symbol):
    return float(binance_client.get_ticker(symbol=f"{symbol}USDT")["lastPrice"])


def validate_transaction(txid):
    while True:
        try:
            tx_info = dict(solana_client.get_transaction(tx_sig=txid))
            print(tx_info)
            tx_error_msg = tx_info["result"]["meta"]["err"]
            if not tx_error_msg:
                print("Transaction Successful")
                bot_logger(f"Transaction Valid : {txid}")
                return True
            print("Transaction Failed")
            bot_logger(f"Transaction Invalid : {txid}")
            return False
        except Exception as e:
            bot_logger(f"Exception At Function validate_transaction : {e}")
            time.sleep(1)


def solscan_response(txid):
    attempts = 0
    while True:
        try:
            time.sleep(2)
            headers = {
                'authority': 'api.solscan.io',
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'if-none-match': 'W/"1a28-TZjJkkzsJw8I1oRKSmkimnZXdGs"',
                'origin': 'https://solscan.io',
                'referer': 'https://solscan.io/',
                'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
            }

            params = {
                'tx': txid,
            }
            response = requests.get('https://api.solscan.io/transaction', params=params, headers=headers)
            response_text = response.text
            if "tx not found" in response_text:
                if attempts >= 5:
                    print(f"Unknown Status For TX : {txid} , Solscan Response : {response_text}")
                    return False
                print("TX not found")
                attempts = attempts + 1
                time.sleep(2)
                continue
            response_json = response.json()
            if response_json["status"] == "Success":
                print("Good TX")
                return True
            elif response_json["status"] == "Fail":
                print("Bad TX")
                return False
            else:
                print(f"Unknown Status For TX : {txid} , Solscan Response : {response_text}")
                return False
        except Exception as e:
            bot_logger(f"Exception At Function solscan_response : {e}, Request Response : {response}")
            pass


def send_transaction_jup(payer: Keypair, swap_transaction: str):
    """ Send a serialized transaction to the RPC node """
    try:
        trans = Transaction.deserialize(base64.b64decode(swap_transaction))
        result = solana_client.send_transaction(trans, payer)
        print(result)
        transaction_id = result['result']
        if transaction_id is not None:
            time.sleep(1)
            transaction_state = solscan_response(txid=transaction_id)  # Returns True Or False
            if transaction_state is True:
                print(f"here1 , {transaction_state}")
                return transaction_id
            else:
                print(f"here2, {transaction_state}")
                return None
        else:
            print(f"Failed Transaction : {result}")
            return None
    except Exception as e:
        print(f"Error in send_transaction_jup: {e}")


def get_swap_transactions(route):
    try:
        payload = {"route": route, "userPublicKey": account['public_key']}
        swaps_request = requests.post("https://quote-api.jup.ag/v1/swap", json=payload)
        transactions_list = swaps_request.json()
        transactions = []
        for transaction in transactions_list:
            transactions.append(transactions_list[transaction])
        return transactions
    except Exception as e:
        print(f"Exception At Function get_swap_transactions : {e}")


def coin_received_for_usdt(amount, coin):
    try:
        params = {
            'inputMint': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
            'outputMint': 'So11111111111111111111111111111111111111112',
            'amount': coin_to_wei(amount, "USDT"),
            'slippage': f'{SLIPPAGE}',
        }
        response = requests.get('https://quote-api.jup.ag/v1/quote', params=params).json()
        routes = response['data']
        amount_gained = wei_to_coin(float(routes[0]["outAmount"]), coin)
        data = {'amount_gained': amount_gained, 'route': routes[0]}
        return data
    except Exception as e:
        print(f"Exception At Function coin_received_for_usdt : {e}")


def usdt_received_for_coin(amount, coin):
    try:
        params = {
            'inputMint': 'So11111111111111111111111111111111111111112',
            'outputMint': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
            'amount': coin_to_wei(amount, coin),
            'slippage': f'{SLIPPAGE}',
        }
        response = requests.get('https://quote-api.jup.ag/v1/quote', params=params).json()
        routes = response['data']
        amount_gained = wei_to_coin(float(routes[0]["outAmount"]), "USDT")
        data = {'amount_gained': amount_gained, 'route': routes[0]}
        return data
    except Exception as e:
        print(f"Exception At Function usdt_received_for_coin : {e}")


def buy_from_jup(profit_limit, coin, initial_usd_amount):
    while True:  # inputs USDT
        time.sleep(0.5)
        try:
            binance_buyer_price = float(binance_price_cacher.read_price(coin)["BUY"])
            binance_coin_balance = float(balance.read_price("BALANCE")["BINANCE"][coin]) - 0.1
            solana_usdt_balance = float(balance.read_price("BALANCE")["SOLANA"]["USDT"]) - 10
            if solana_usdt_balance > initial_usd_amount and binance_coin_balance > initial_usd_amount / binance_buyer_price:
                initial_amount = initial_usd_amount
            elif solana_usdt_balance < initial_usd_amount and binance_coin_balance > initial_usd_amount / binance_buyer_price:
                initial_amount = solana_usdt_balance
            elif binance_coin_balance < initial_usd_amount / binance_buyer_price and solana_usdt_balance > initial_usd_amount:
                initial_amount = binance_coin_balance * binance_buyer_price
            elif solana_usdt_balance < initial_usd_amount and binance_coin_balance < initial_usd_amount / binance_buyer_price:
                if solana_usdt_balance < binance_coin_balance * binance_buyer_price:
                    initial_amount = solana_usdt_balance
                else:
                    initial_amount = binance_coin_balance * binance_buyer_price
            else:
                bot_logger("Undefined Logic 1")
                time.sleep(10)
                continue
            if initial_amount < 20:
                print("Insufficient Balance, Amount")
                time.sleep(10)
                continue
            else:
                pass
            coin_output = coin_received_for_usdt(amount=initial_amount, coin=coin)
            amount_gained_by_selling_on_binance = coin_output["amount_gained"] * binance_buyer_price
            profit = round(float(amount_gained_by_selling_on_binance - initial_amount), 2)
            profit_percent = round(profit / initial_amount * 100, 2)
            text = \
                f"Buying {coin.upper()} From Jupiter\n\n" \
                f"Buying {coin_output['amount_gained']} {coin.upper()} For {initial_amount} USDT\n\n" \
                f"Selling {coin.upper()} On Binance With Rate : {binance_buyer_price}\n\n" \
                f"Profit : {profit} USDT\n\n" \
                f"Profit Percent : {profit_percent}%\n\n" \
                f"======================"
            print(text)
            try:
                if profit_percent > profit_limit:
                    print("Arbitrage Opportunity Found")
                    failed = False
                    successful_transactions = []
                    try:
                        transactions = get_swap_transactions(route=coin_output["route"])
                        for transaction in transactions:
                            solana_transaction = send_transaction_jup(sender, transaction)
                            if solana_transaction is not None:
                                print("Transaction Sent")
                                successful_transactions.append(f"https://solscan.io/tx/{solana_transaction}")
                            else:
                                print(f"Solana Transaction Failed, Discontinuing Arbitrage , {solana_transaction}")
                                failed = True
                                break
                        if failed:
                            continue
                        else:
                            try:
                                binance_sell_order = binance_client.order_market_sell(
                                    symbol=f"{coin.upper()}USDT",
                                    quoteOrderQty=initial_amount)
                                bot_logger(f"Binance Sell Order : {binance_sell_order}")
                                bot_logger(text)
                            except Exception as e:
                                bot_logger(f"Exception At Function buy_from_jup // Binance Transaction : {e} // Binance Coin Balance : {binance_coin_balance} // Amount To Be Executed : {coin_output['amount_gained']}")
                    except Exception as e:
                        bot_logger(f"Exception At Function buy_from_jup // Solana Transactions : {e}")
                else:
                    print("No Arbitrage Opportunity Found")
                    print(text)
            except Exception as e:
                bot_logger(f"Exception At Function buy_from_jup Second Try // Exception : {e}")
        except Exception as e:
            print(f"Error in Calculating Parameters In Buy From Jupiter : {e}")


def sell_on_jup(profit_limit, coin, initial_coin):
    while True:
        time.sleep(0.5)
        try:
            binance_seller_price = float(binance_price_cacher.read_price(coin)["SELL"])
            binance_usdt_balance = float(balance.read_price("BALANCE")["BINANCE"]["USDT"]) - 10
            solana_coin_balance = float(balance.read_price("BALANCE")["SOLANA"][coin]) - 0.1
            if solana_coin_balance > initial_coin and binance_usdt_balance > initial_coin * binance_seller_price:
                initial_coin_amount = initial_coin
            elif solana_coin_balance < initial_coin and binance_usdt_balance > initial_coin * binance_seller_price:
                initial_coin_amount = solana_coin_balance
            elif binance_usdt_balance < initial_coin * binance_seller_price and solana_coin_balance > initial_coin:
                initial_coin_amount = (binance_usdt_balance - 10) / binance_seller_price
            elif solana_coin_balance < initial_coin and binance_usdt_balance < initial_coin * binance_seller_price:
                if solana_coin_balance < (binance_usdt_balance - 10) / binance_seller_price:
                    initial_coin_amount = solana_coin_balance
                else:
                    initial_coin_amount = (binance_usdt_balance - 10) / binance_seller_price
            else:
                bot_logger("Undefined Logic 2")
                time.sleep(10)
                continue
            if initial_coin_amount * binance_seller_price < 20:
                print("Insufficient Balance, Amount")
                time.sleep(10)
                continue
            else:
                pass
            usdt_output = usdt_received_for_coin(amount=initial_coin_amount, coin=coin)
            amount_spent_for_buying_on_binance = initial_coin_amount * binance_seller_price
            profit = round(float(usdt_output["amount_gained"] - amount_spent_for_buying_on_binance), 2)
            profit_percent = round(profit / usdt_output["amount_gained"] * 100, 2)
            text = \
                f"Selling {coin.upper()} On Jupiter\n\n" \
                f"Selling {initial_coin_amount} {coin.upper()} For {usdt_output['amount_gained']} USDT\n\n" \
                f"Buying {coin.upper()} On Binance With Rate : {binance_seller_price}\n\n" \
                f"Profit : {profit} USDT\n\n" \
                f"Profit Percent : {profit_percent} %\n\n" \
                f"======================"
            print(text)
            try:
                if profit_percent > profit_limit:
                    print("Arbitrage Opportunity Found")
                    failed = False
                    successful_transactions = []
                    try:
                        transactions = get_swap_transactions(route=usdt_output["route"])
                        for transaction in transactions:
                            solana_transaction = send_transaction_jup(sender, transaction)
                            if solana_transaction is not None:
                                print("Transaction Sent")
                                successful_transactions.append(f"https://solscan.io/tx/{solana_transaction}")
                            else:
                                print(f"Solana Transaction Failed, Discontinuing Arbitrage, {solana_transaction}")
                                failed = True
                                break
                        if failed:
                            continue
                        else:
                            try:
                                binance_buy_order = binance_client.order_market_buy(
                                    symbol=f"{coin.upper()}USDT",
                                    quantity=truncate(initial_coin_amount, const.COIN_DECIMAL_AMOUNT[coin]))
                                bot_logger(f"Binance Buy Order : {binance_buy_order}")
                                bot_logger(text)
                            except Exception as e:
                                bot_logger(f"Exception At Function sell_on_jup // Binance Transaction : {e} // Binance USDT Balance : {binance_usdt_balance} // Amount To Be Executed : {initial_coin_amount} // Binance Seller Price : {binance_seller_price}")
                    except Exception as e:
                        bot_logger(f"Exception At Function sell_on_jup // Solana Transactions : {e}")
                else:
                    print("No Arbitrage Opportunity Found")
                    print(text)
            except Exception as e:
                bot_logger(f"Exception At Second Try in Function sell_on_jup : {e}")
        except Exception as e:
            bot_logger(f"Error Calculating Parameters On Sell On Jupiter : {e}")


Thread(target=buy_from_jup, args=(PROFIT_PERCENT, "SOL", 200)).start()
Thread(target=sell_on_jup, args=(PROFIT_PERCENT, "SOL", 6)).start()
