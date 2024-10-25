import json
import threading
from datetime import datetime, date
from typing import List
from kiteconnect import KiteConnect, KiteTicker

from configs import kite_client_config, trading_config

# GLOBALS ----------------------------------
KITE_CONNECT_CLIENT: KiteConnect = None
NSE_INSTRUMENTS: dict = None
NFO_INSTRUMENTS: dict = None
INDEX_PRICES: List[float] = []
# ------------------------------------------

# CONSTANTS --------------------------------
nse_instrument_json_file_path = './instruments/nse.json'
nfo_instrument_json_file_path = './instruments/nfo.json'
# ------------------------------------------


def new_kite_connect_client():
    global KITE_CONNECT_CLIENT
    KITE_CONNECT_CLIENT = KiteConnect(api_key=kite_client_config.API_KEY)

    print("Please login: ", KITE_CONNECT_CLIENT.login_url())

    request_token: str = input("enter 'request_token': ")

    session_data: dict = KITE_CONNECT_CLIENT.generate_session(
        request_token=request_token,
        api_secret=kite_client_config.API_SECRETE,
    )

    kite_client_config.ACCESS_TOKEN = session_data['access_token']
    KITE_CONNECT_CLIENT.set_access_token(kite_client_config.ACCESS_TOKEN)

    print('\nkite connect client creation successful !!! ')


def fetch_and_load_NSE_and_NFO_instruments():
    if KITE_CONNECT_CLIENT is None:
        raise Exception("kite connect client is nto initialised")

    update_nse_instruments(KITE_CONNECT_CLIENT)
    update_nfo_instruments(KITE_CONNECT_CLIENT)

    global NSE_INSTRUMENTS, NFO_INSTRUMENTS

    NSE_INSTRUMENTS = load_nse_instruments_data()
    NFO_INSTRUMENTS = load_nfo_instruments_data()


def update_nse_instruments(kc: KiteConnect):
    all_nse_instruments = kc.instruments(kc.EXCHANGE_NSE)

    all_data = {}
    for data in all_nse_instruments:
        all_data[f'{data["tradingsymbol"]}'] = data

    with open(nse_instrument_json_file_path, 'w') as json_file:
        json.dump(all_data, json_file, indent=4)


def update_nfo_instruments(kc: KiteConnect):
    all_nfo_instruments = kc.instruments(kc.EXCHANGE_NFO)

    trading_symbol_to_data_map = {}
    for data in all_nfo_instruments:
        trading_symbol_to_data_map[f'{data["tradingsymbol"]}'] = data

    with open(nfo_instrument_json_file_path, 'w') as json_file:
        json.dump(trading_symbol_to_data_map, json_file, cls=CustomJSONEncoder, indent=4)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()  # Convert date and datetime to string
        return super().default(obj)


def load_nse_instruments_data() -> dict:
    with open(nse_instrument_json_file_path, 'r') as file:
        data_dict = json.load(file)

    return data_dict


def load_nfo_instruments_data() -> dict:
    with open(nfo_instrument_json_file_path, 'r') as file:
        data_dict = json.load(file)

    return data_dict


def new_kite_websocket_client() -> KiteTicker:
    if kite_client_config.ACCESS_TOKEN is None:
        err_msg = ('access_token is not initialised. Please connect to kite connect first with'
                   ' "get_kite_connect_client()" function, and then try to create websocket client')

        raise Exception(err_msg)

    kws: KiteTicker = KiteTicker(
        api_key=kite_client_config.API_KEY,
        access_token=kite_client_config.ACCESS_TOKEN,
    )

    print('\nkite websocket client creation successful !!! ')

    return kws


def async_spawn_stock_price_fetcher():
    print('[ASYNC SPAWN] - async_spawn_stock_price_fetcher ...')

    thread = threading.Thread(target=start_fetching_and_updating_stock_price)
    thread.start()


def start_fetching_and_updating_stock_price():
    kws: KiteTicker = new_kite_websocket_client()

    kws.on_connect = subscribe_to_stock_instrument
    kws.on_ticks = update_stock_ltp
    kws.on_close = close_websocket_connection

    kws.connect(threaded=True)

    while True:
        now = datetime.now()
        # Check if the current time is greater than or equal to 3:30 PM
        if now.hour > 15 or (now.hour == 15 and now.minute >= 30):
            print("It's now 3:30 PM or later.")
            break

    kws.close()


def subscribe_to_stock_instrument(ws, response):
    instruments = [get_stock_token_from_stock_symbol(trading_config.INDEX_TRADING_SYMBOL)]
    ws.subscribe(instruments)
    ws.set_mode(ws.MODE_LTP, instruments)


def close_websocket_connection(ws, code, reason):
    ws.stop()


def update_stock_ltp(ws, ticks):
    global INDEX_PRICES
    stock_data: dict = ticks[0]
    INDEX_PRICES.append(stock_data['last_price'])


def get_stock_token_from_stock_symbol(stock_symbol: str) -> int:
    instrument = NSE_INSTRUMENTS[stock_symbol]
    return instrument['instrument_token']


def get_atm_strike_for_price(price: float) -> int:
    # TODO
    return 25600


def get_weekly_pe_contract_trading_symbol(strike: int) -> str:
    """TODO: fetch from global instrument variable"""


def get_weekly_ce_contract_trading_symbol(strike: int) -> str:
    """TODO: fetch from global instrument variable"""


def place_order(
        trading_symbol: str,
        qty: int,
) -> str:
    try:
        order_id = KITE_CONNECT_CLIENT.place_order(
            variety=KITE_CONNECT_CLIENT.VARIETY_REGULAR,
            tradingsymbol=trading_symbol,
            exchange=KITE_CONNECT_CLIENT.EXCHANGE_NFO,
            transaction_type=KITE_CONNECT_CLIENT.TRANSACTION_TYPE_BUY,
            quantity=qty,
            order_type=KITE_CONNECT_CLIENT.ORDER_TYPE_MARKET,
            product=KITE_CONNECT_CLIENT.PRODUCT_MIS,
            validity=KITE_CONNECT_CLIENT.VALIDITY_DAY,  # might try VALIDITY_IOC
        )

        return order_id
    except Exception as e:
        print("[PLACE ORDER MANUALLY NOWWWW] Order placement failed: {}".format(e))


def exit_order(
        trading_symbol: str,
        qty: int,
) -> str:
    try:
        order_id = KITE_CONNECT_CLIENT.place_order(
            variety=KITE_CONNECT_CLIENT.VARIETY_REGULAR,
            tradingsymbol=trading_symbol,
            exchange=KITE_CONNECT_CLIENT.EXCHANGE_NFO,
            transaction_type=KITE_CONNECT_CLIENT.TRANSACTION_TYPE_SELL,
            quantity=qty,
            order_type=KITE_CONNECT_CLIENT.ORDER_TYPE_MARKET,
            product=KITE_CONNECT_CLIENT.PRODUCT_MIS,
            validity=KITE_CONNECT_CLIENT.VALIDITY_DAY,
        )

        return order_id
    except Exception as e:
        print("[ALEEEEEEERT !!!, Exit order manually Nowwwwwww...] Order exit failed: {}".format(e))
