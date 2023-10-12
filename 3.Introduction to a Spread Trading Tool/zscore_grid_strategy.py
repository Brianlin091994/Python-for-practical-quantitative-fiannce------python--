from math import floor, ceil

from vnpy.trader.utility import BarGenerator, ArrayManager
from vnpy_spreadtrading import (
    SpreadStrategyTemplate,
    SpreadAlgoTemplate,
    SpreadData,
    OrderData,
    TradeData,
    TickData,
    BarData
)


class ZscoreGridStrategy(SpreadStrategyTemplate):
    """"""

    author = "BrianL"

    ma_window = 20
    volume_multiplier = 5 # 每一格开仓手数
    max_pos = 25
    payup = 10
    interval = 5

    ma_value = 0.0
    z_score = 0.0
    spread_pos = 0.0

    parameters = [
        "ma_window",
        "volume_multiplier",
        "max_pos",
        "payup",
        "interval",
    ]
    variables = [
        "ma_value",
        "z_score",
        "spread_pos",
    ]

    def __init__(
        self,
        strategy_engine,
        strategy_name: str,
        spread: SpreadData,
        setting: dict
    ):
        """"""
        super().__init__(strategy_engine, strategy_name, spread, setting)

        self.bg = BarGenerator(self.on_spread_bar)
        self.am = ArrayManager(self.ma_window + 10)

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        self.load_bar(10)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")
    def on_spread_data(self):
        """
        Callback when spread price is updated.
        """
        tick = self.get_spread_tick()
        self.on_spread_tick(tick)

    def on_spread_tick(self, tick: TickData):
        """
        Callback when new spread tick data is generated.
        """
        self.bg.update_tick(tick)

    def on_spread_bar(self, bar: BarData):
        """"""
        self.am.update_bar(bar)
        if not self.am.inited or not self.trading:
            return
        
        # 撤销之前的挂单
        self.stop_all_algos()

        # 计算当前 z_score
        self.ma_value = self.am.sma(self.ma_window)
        self.price_change = bar.close_price - self.ma_value
        self.std = self.am.std(self.ma_window)
        self.z_score = self.price_change / self.std

        # 超价委托
        long_price = bar.close_price * 1.01
        short_price = bar.close_price * 0.99

        # 如果价格穿越均线全部平仓
        if self.spread_pos > 0 and self.price_change >= 0:
            self.start_short_algo(
                short_price,
                abs(self.spread_pos),
                payup=self.payup,
                interval=self.interval
            )
        elif self.spread_pos < 0 and self.price_change <= 0:
            self.start_long_algo(
                long_price,
                abs(self.spread_pos),
                payup=self.payup,
                interval=self.interval
            )
        # 若无持仓则判断条件是否开仓
        else:
            if self.price_change > (0 + self.std):
                target_pos = -floor(self.z_score - 1) * self.volume_multiplier
                target_pos = max(-self.max_pos, target_pos)

                if target_pos < self.spread_pos:
                    self.start_short_algo(
                        short_price,
                        abs(target_pos - self.spread_pos),
                        payup=self.payup,
                        interval=self.interval
                    )
            
            elif self.price_change < (0 - self.std):
                target_pos = -ceil(self.z_score + 1) * self.volume_multiplier
                target_pos = min(self.max_pos, target_pos)
                if target_pos > self.spread_pos:
                    self.start_long_algo(
                        long_price,
                        abs(target_pos - self.spread_pos),
                        payup=self.payup,
                        interval=self.interval
                    )
        
        # 更新图形界面
        self.put_event()

    def on_spread_pos(self):
        """
        Callback when spread position is updated.
        """
        self.spread_pos = self.get_spread_pos()
        self.put_event()

    def on_spread_algo(self, algo: SpreadAlgoTemplate):
        """
        Callback when algo status is updated.
        """
        pass

    def on_order(self, order: OrderData):
        """
        Callback when order status is updated.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback when new trade data is received.
        """
        pass
