from collections import deque
import uuid
import time

class PaperBroker:
    """
    PaperBroker simulates a brokerage interface for demo trading.
    It connects to real market data via an EventBus, listens to market events,
    and executes orders virtually without real trades.
    """

    def __init__(self, bus, starting_balance=10000.0, margin_mode="isolated"):
        """
        Initialize the PaperBroker.

        :param bus: EventBus instance for subscribing and publishing events.
        :param starting_balance: Initial demo account balance.
        :param margin_mode: Margin mode, e.g. "isolated" or "cross".
        """
        self.bus = bus
        self.balance = starting_balance
        self.margin_mode = margin_mode
        self.positions = {}  # symbol -> position dict: {'qty': float, 'avg_price': float}
        self.open_orders = {}  # order_id -> order dict
        self.trade_history = deque(maxlen=1000)  # store last 1000 trades
        self.running = False

        # Subscribe to market tick events to simulate order execution
        self.bus.subscribe('market.tick', self.on_tick)

    def start(self):
        """
        Start demo trading.
        """
        self.running = True
        # Publish status update for UI
        self.update_ui_state()

    def stop(self):
        """
        Stop demo trading.
        """
        self.running = False
        # Publish status update for UI
        self.update_ui_state()

    def reset_balance(self, amount):
        """
        Reset demo account balance.

        :param amount: New balance amount.
        """
        self.balance = amount
        self.positions.clear()
        self.open_orders.clear()
        self.trade_history.clear()
        # Publish status update for UI
        self.update_ui_state()

    def place_order(self, symbol, side, qty, price, order_type="limit", reduce_only=False):
        """
        Place a new order in the paper trading system.

        :param symbol: Trading symbol.
        :param side: 'buy' or 'sell'.
        :param qty: Quantity to trade.
        :param price: Limit price.
        :param order_type: 'limit' or 'market' (market orders will be executed immediately).
        :param reduce_only: If True, only reduce existing position.
        :return: order_id string.
        """
        if not self.running:
            return None

        order_id = str(uuid.uuid4())
        order = {
            'id': order_id,
            'symbol': symbol,
            'side': side,
            'qty': qty,
            'price': price,
            'type': order_type,
            'reduce_only': reduce_only,
            'timestamp': time.time(),
            'status': 'open'
        }

        if order_type == "market":
            # Execute immediately at current market price (simulate)
            # We do not have current price here, so we rely on last tick or price param
            self._execute_order(order, price)
            order['status'] = 'filled'
        else:
            # Store limit order for future execution on ticks
            self.open_orders[order_id] = order

        # Publish status update for UI
        self.update_ui_state()
        return order_id

    def cancel_order(self, order_id):
        """
        Cancel an existing order.

        :param order_id: ID of the order to cancel.
        """
        if order_id in self.open_orders:
            self.open_orders[order_id]['status'] = 'canceled'
            del self.open_orders[order_id]
            # Publish status update for UI
            self.update_ui_state()

    def on_tick(self, tick):
        """
        Handle new market tick to simulate order execution.

        :param tick: dict with keys including 'symbol', 'price'.
        """
        if not self.running:
            return

        symbol = tick.get('symbol')
        price = tick.get('price')
        if symbol is None or price is None:
            return

        # Iterate over a copy of open_orders to allow removal during iteration
        for order_id, order in list(self.open_orders.items()):
            if order['symbol'] != symbol or order['status'] != 'open':
                continue

            # Check if limit order price conditions are met to execute
            if order['side'] == 'buy' and price <= order['price']:
                self._execute_order(order, price)
                order['status'] = 'filled'
                del self.open_orders[order_id]
            elif order['side'] == 'sell' and price >= order['price']:
                self._execute_order(order, price)
                order['status'] = 'filled'
                del self.open_orders[order_id]

        # Publish status update for UI
        self.update_ui_state()

    def _execute_order(self, order, execution_price):
        """
        Simulate execution of an order and update positions and balance.

        :param order: order dict.
        :param execution_price: price at which order is executed.
        """
        symbol = order['symbol']
        side = order['side']
        qty = order['qty']
        reduce_only = order['reduce_only']

        # Calculate cost and update balance and positions
        cost = execution_price * qty

        # Initialize position if needed
        pos = self.positions.get(symbol, {'qty': 0.0, 'avg_price': 0.0})

        if side == 'buy':
            if reduce_only:
                # reduce position qty if possible
                if pos['qty'] <= 0:
                    # no position to reduce, ignore order execution
                    return
                reduce_qty = min(qty, pos['qty'])
                pos['qty'] -= reduce_qty
                # Realized PnL calculation
                pnl = reduce_qty * (pos['avg_price'] - execution_price)
                self.balance += pnl
            else:
                # Increase position
                total_qty = pos['qty'] + qty
                if total_qty == 0:
                    avg_price = 0.0
                else:
                    avg_price = (pos['avg_price'] * pos['qty'] + execution_price * qty) / total_qty
                pos['qty'] = total_qty
                pos['avg_price'] = avg_price
                self.balance -= cost

        elif side == 'sell':
            if reduce_only:
                if pos['qty'] >= 0:
                    # no short position to reduce
                    return
                reduce_qty = min(qty, abs(pos['qty']))
                pos['qty'] += reduce_qty
                pnl = reduce_qty * (execution_price - pos['avg_price'])
                self.balance += pnl
            else:
                # Increase short position
                total_qty = pos['qty'] - qty
                if total_qty == 0:
                    avg_price = 0.0
                else:
                    avg_price = (pos['avg_price'] * abs(pos['qty']) + execution_price * qty) / abs(total_qty)
                pos['qty'] = total_qty
                pos['avg_price'] = avg_price
                self.balance += cost

        self.positions[symbol] = pos

        # Record trade in history
        trade = {
            'timestamp': time.time(),
            'symbol': symbol,
            'side': side,
            'qty': qty,
            'price': execution_price,
            'order_id': order['id']
        }
        self.trade_history.append(trade)

    def update_ui_state(self):
        """
        Publish current demo trading state to EventBus for UI.

        The UI can subscribe to 'paper_broker.state' to update the demo trading tab.
        """
        state = {
            'balance': self.balance,
            'positions': self.positions,
            'open_orders': list(self.open_orders.values()),
            'trade_history': list(self.trade_history)
        }
        self.bus.publish('paper_broker.state', state)

# Note:
# To integrate PaperBroker state into the UI,
# subscribe to 'paper_broker.state' events and update the "Демоторговля" tab accordingly.
# This allows real-time monitoring of demo balance, positions, open orders, and trade history.
