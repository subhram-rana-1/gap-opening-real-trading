import time as tm
from datetime import datetime, time
from configs import trading_config
from configs.trading_config import QTY
from kite import new_kite_connect_client, fetch_and_load_NSE_and_NFO_instruments, \
    async_spawn_stock_price_fetcher, INDEX_PRICES, \
    get_atm_strike_for_price, place_order, get_weekly_pe_contract_trading_symbol, get_weekly_ce_contract_trading_symbol, \
    exit_order
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
        tm.sleep(0.1)  # sleep 100 ms

    # 1st tick has come
    opening_price: float = INDEX_PRICES[0]
    gap = opening_price - prev_market_day_closing_price

    print(f"checking opening price at: {datetime.now().time()}, "
          f"opening price: {opening_price},"
          f"prev day closing price: {prev_market_day_closing_price}, "
          f"gap: {gap}")

    # check for ENTRY

    entry_type: str = None
    target: float = None
    stoploss: float = None
    option_contract_trading_symbol: str = None
    atm_strike: int = None

    if gap > abs(trading_config.THRESHOLD_GAP):
        print(f'I will take short entry for {atm_strike} for {QTY} quantity')

        atm_strike = get_atm_strike_for_price(opening_price, 'pe')
        option_contract_trading_symbol = get_weekly_pe_contract_trading_symbol(atm_strike)
        entry_type = 'short'
        stoploss = opening_price + trading_config.FIXED_STOPLOSS
        target = opening_price - trading_config.FIXED_TARGET
    elif gap > -1 * abs(trading_config.THRESHOLD_GAP):
        print(f'I will take long entry for {atm_strike} for {QTY} quantity')

        atm_strike = get_atm_strike_for_price(opening_price, 'ce')
        option_contract_trading_symbol = get_weekly_ce_contract_trading_symbol(atm_strike)
        entry_type = 'long'
        stoploss = opening_price - trading_config.FIXED_STOPLOSS
        target = opening_price + trading_config.FIXED_TARGET
    else:
        print(f"No trade today as today's gap {abs(gap)} is <= {trading_config.THRESHOLD_GAP}")
        return

    print(f"placing {trading_config.QTY} qty order for {option_contract_trading_symbol}")
    entry_order_id = place_order(
        trading_symbol=option_contract_trading_symbol,
        qty=trading_config.QTY,
    )
    print(f"Placed order. order id: {entry_order_id}")

    # wait for EXIT
    while True:
        ltp: float = INDEX_PRICES[len(INDEX_PRICES)-1]
        should_exit = False

        if entry_type == 'long':
            if ltp <= stoploss:
                print(f"exit long entry order due to STOPLOSS  hit. SL: {stoploss}, ltp: {ltp}")
                should_exit = True
            elif ltp >= target:
                print(f"exit long entry order due to TARGET hit. target: {target}, ltp: {ltp}")
                should_exit = True
            elif datetime.now().time() >= time(12, 0):
                print(f"exit long entry order due to time >= 12 pm. ltp: {ltp}")
                should_exit = True
        elif entry_type == 'short':
            if ltp >= stoploss:
                print(f"exit short entry order due to STOPLOSS  hit. SL: {stoploss}, ltp: {ltp}")
                should_exit = True
            elif ltp <= target:
                print(f"exit short entry order due to TARGET hit. target: {target}, ltp: {ltp}")
                should_exit = True
            elif datetime.now().time() >= time(12, 0):
                print(f"exit short entry order due to time >= 12 pm. ltp: {ltp}")
                should_exit = True
        else:
            raise Exception(f"for entry type {entry_type} you should exit code before")

        if should_exit:
            print(f"Exiting {trading_config.QTY} qty order for {option_contract_trading_symbol}")
            exit_order(order_id=entry_order_id)
            break

        tm.sleep(0.2)  # 200 ms


if __name__ == '__main__':
    start_gap_opening_trading_strategy()
