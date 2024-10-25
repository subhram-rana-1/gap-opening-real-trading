import time
from datetime import datetime, time

from configs import trading_config
from configs.trading_config import LOT_QTY, QTY
from kite import new_kite_connect_client, fetch_and_load_NSE_and_NFO_instruments, \
    async_spawn_stock_price_fetcher, INDEX_PRICES, get_weekly_pe_atm_strike_for_price, \
    get_weekly_ce_atm_strike_for_price
from utils import get_prev_market_day_closing_price


def start_gap_opening_trading_strategy():
    """
    1. connect to KITE
    2. fetch NSE instruments
    3. connect to websocket server and start fetching tick price
    4. start the strategy
    """

    prev_market_day_closing_price = get_prev_market_day_closing_price()
    new_kite_connect_client()
    fetch_and_load_NSE_and_NFO_instruments()
    async_spawn_stock_price_fetcher()
    start_strategy(prev_market_day_closing_price)


def start_strategy(prev_market_day_closing_price: float):
    """
    1. Wait for 1st tick price to come
    2. Enter in direction opposite to gap opening at ATM strike
    3. keep track of SL and target and exit accordingly
    """
    while len(INDEX_PRICES) == 0:
        time.sleep(0.1)  # sleep 100 ms

    # 1st tick has come
    opening_price: float = INDEX_PRICES[0]
    gap = opening_price - prev_market_day_closing_price

    print(f"checking opening price at: {datetime.now().time()}, "
          f"opening price: {opening_price},"
          f"prev day closing price: {prev_market_day_closing_price}, "
          f"gap: {gap}")

    # check for ENTRY

    entry_type = None
    target = None
    stoploss = None

    if gap > abs(trading_config.THRESHOLD_GAP):
        weekly_pe_atm_strike: str = get_weekly_pe_atm_strike_for_price(opening_price)
        print(f'I will take short entry for {weekly_pe_atm_strike} for {QTY} quantity')
        # TODO: call order api

        entry_type = 'short'
        stoploss = opening_price + trading_config.FIXED_STOPLOSS
        target = opening_price - trading_config.FIXED_TARGET
    elif gap > -1 * abs(trading_config.THRESHOLD_GAP):
        weekly_ce_atm_strike: str = get_weekly_ce_atm_strike_for_price(opening_price)
        print(f'I will take long entry for {weekly_ce_atm_strike} for {QTY} quantity')
        # TODO: call order api

        entry_type = 'long'
        stoploss = opening_price - trading_config.FIXED_STOPLOSS
        target = opening_price + trading_config.FIXED_TARGET
    else:
        print(f"No trade today as today's gap {abs(gap)} is <= {trading_config.THRESHOLD_GAP}")
        return

    # wait for EXIT
    while True:
        ltp: float = INDEX_PRICES[len(INDEX_PRICES)-1]

        if entry_type == 'long':
            if ltp <= stoploss:
                print(f"exit long entry order due to STOPLOSS  hit. SL: {stoploss}, ltp: {ltp}")
                # todo: call exit order
            elif ltp >= target:
                print(f"exit long entry order due to TARGET hit. target: {target}, ltp: {ltp}")
                # todo: call exit order
            elif datetime.now().time() >= time(12, 0):
                print(f"exit long entry order due to time >= 12 pm. ltp: {ltp}")
                # todo: call exit order
        elif entry_type == 'short':
            if ltp >= stoploss:
                print(f"exit short entry order due to STOPLOSS  hit. SL: {stoploss}, ltp: {ltp}")
                # todo: call exit order
            elif ltp <= target:
                print(f"exit short entry order due to TARGET hit. target: {target}, ltp: {ltp}")
                # todo: call exit order
            elif datetime.now().time() >= time(12, 0):
                print(f"exit short entry order due to time >= 12 pm. ltp: {ltp}")
                # todo: call exit order
        else:
            raise Exception(f"for entry type {entry_type} you should exit code before")

        time.sleep(0.2)  # 200 ms


if __name__ == '__main__':
    start_gap_opening_trading_strategy()
