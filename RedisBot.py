import cacher
from cacher import Tabar
from const import *
import const
import time
from binance import Client
import base64
from solana.publickey import PublicKey
from solana.keypair import Keypair
from telegram import Bot, ParseMode
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.rpc.api import Client as SolClient
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer


balance = cacher.Tabar(host=REDIS_HOST, port=REDIS_PORT, db=15)
binance_price_cacher = cacher.Tabar(host=REDIS_HOST, port=REDIS_PORT, db=12)
binance_client = Client(api_key="API", api_secret="SECRET")

account = {"SOLANA_ACCOUNT"}

owner = Keypair.from_secret_key(account['secret_key']['machine_readable'].encode("latin-1"))
sender = owner

solana_client = SolClient("https://arbprotocol.genesysgo.net/")


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


def get_balances():
    while True:
        time.sleep(1)
        try:
            solana_balances_dict = {}
            binance_balances_dict = {}
            sol_balance = dict(solana_client.get_balance(pubkey=account['public_key']))
            sol_value = wei_to_coin(int(sol_balance["result"]["value"]), "SOL")
            solana_balances_dict["SOL"] = sol_value - 0.1
            for token in const.SOLANA_TOKEN_CACHE:
                token_balance = dict(solana_client.get_token_account_balance(pubkey=SOLANA_TOKEN_ACCOUNT[token]))
                solana_balances_dict[token] = token_balance["result"]["value"]["uiAmount"]
            binance_balances = binance_client.get_account()
            for symbol in const.BINANCE_BALANCE_CACHE:
                for bal in binance_balances['balances']:
                    if bal['asset'].lower() == symbol.lower():
                        symbol_balance = bal["free"]
                        binance_balances_dict[symbol.upper()] = symbol_balance
            balance_dic = {"SOLANA": solana_balances_dict, "BINANCE": binance_balances_dict}
            balance.cache_price(symbol="BALANCE", data=balance_dic)
            print(balance_dic)
        except Exception as e:
            print(f"Exception At Balance Cacher : {e}")


get_balances()