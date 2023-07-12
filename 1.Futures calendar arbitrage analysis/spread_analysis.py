# 将以下代码单独保存一个.py文件，例如spread_analysis.py

import re 
import rqdatac
import pandas as pd
import datetime as dt
rqdatac.init()
import plotly.graph_objects as go

class SpreadCalculation:
    """
    
    """
    def __init__(self, formula, years_trace_back, trade_period_filter = False) -> None:
        self.formula = formula
        self.years_trace_back = years_trace_back
        # 可以通过访问rqdatac接口来获取期货合约基本信息，也可以通过读取保存好的文件，这里采用后者。
        # self.all_instruments = rqdatac.all_instruments(type = "Future")
        # 筛选除去连续合约、主力合约代码。
        # self.all_instruments = self.all_instruments[self.all_instruments["maturity_date"] != "0000-00-00"] 
        self.all_instruments = pd.read_csv("20230703_all_instruments.csv", index_col = 0)
        self.spread = pd.DataFrame()
        self.trade_period_filter = trade_period_filter

    def get_contract_info(
            self,
            contract_from_formula: str, # e.g. MA09
            ):
            
            underlying_symbol = re.findall(pattern = r"[A-Za-z]+", string = contract_from_formula)[0]
            all_instruments_copy = self.all_instruments.copy()
            # 创建新的列，存储合约的月份，该列的数据类型为2个字符串。
            all_instruments_copy.loc[:, "maturity_date_month"] = pd.to_datetime(all_instruments_copy["maturity_date"]).dt.month.astype(str).str.zfill(2)
            # 创建新的列，存储合约的年份，该列的数据类型为4个字符串。
            all_instruments_copy.loc[:, "maturity_date_year"] = pd.to_datetime(all_instruments_copy["maturity_date"]).dt.year.astype(str).str.zfill(4)
            # mask1，mask2为两个筛选器。
            # mask1 筛选期货品种
            mask1 = all_instruments_copy["underlying_symbol"] == underlying_symbol
            # mask2 筛选合约月份
            mask2 = all_instruments_copy["maturity_date_month"] == contract_from_formula[-2:]
            all_instruments_copy = all_instruments_copy[mask1 & mask2]
            # 筛选出过去最新N年的期货合约， N由years_trace_back决定。
            all_instruments_copy = all_instruments_copy.iloc[-self.years_trace_back:, :]

            return all_instruments_copy[["order_book_id", "listed_date", "de_listed_date","maturity_date_year"]]

    def download_hist_data(self, contract_info):
        contracts_price = rqdatac.get_price(
            order_book_ids=contract_info["order_book_id"].to_list(),
            start_date=contract_info["listed_date"].values[0],
            end_date = contract_info["de_listed_date"].values[-1],
            frequency = "1d",
        )
        # rqdatac返回的历史数据有两个index，需要删去一个多余的order_book_id
        contracts_price.reset_index(level='order_book_id', inplace = True)
        # 按照时间顺序排序
        contracts_price.sort_index(inplace = True)

        return contracts_price

    def split_by_year(self):
        # Convert the index to datetime if it is not already in datetime format
        
        # Create an empty DataFrame with the date range as the index
        splited_data = pd.DataFrame(index=pd.date_range(start='2000-01-01', end='2000-12-31', freq='D').strftime("%m-%d"))
        #print(splited_data.index)
        #print("\n")
        for year in self.spread.index.year.unique():
            year_data = self.spread[self.spread.index.year == year]
            # Remove the year from the index date
            year_data.index = year_data.index.strftime("%m-%d")
            # Add the year's data as a new column in the split_data DataFrame
            splited_data[year] = year_data
       # print(splited_data.index)

        return splited_data

    def create_figure(self, data):
        fig = go.Figure()
        x = data.index
        # 根据 列名 遍历传入的数据表
        for label, content in data.items():
            fig.add_trace(
                go.Scatter(
                    x = x, 
                    y = content, 
                    mode = "lines",
                    name = label,
                    connectgaps = True,
                    showlegend = True
                )
            )
        # 显示10个标签
        tickvals = list(range(0, len(x), int(len(x) / 10)))
        ticktext = [x[i] for i in tickvals]
        # 设置layout
        fig.update_layout(
            xaxis_title = "X轴",
            yaxis_title = "Y轴",
            yaxis = dict(
                showgrid = True,
                zeroline = True,
                showline = True,
                gridcolor = "#eee",
                linecolor = "#444"
            ),
            xaxis = dict(
                type = "category",
                categoryarray = x,
                showgrid = True,
                zeroline = True,
                gridcolor = "#eee",
                linecolor = "#444",
                tickvals = tickvals,
                ticktext = ticktext,
            ),
            legend = dict(
                orientation = "h",
                x = 0.25,
                y = 1.15,
                xanchor = "left",
                yanchor = "top",
                traceorder = "normal",
                font = dict(
                    family = "Arial",
                    size = 12,
                    color = "black"
                ),
                bgcolor = "rgba(0,0,0,0)",
                bordercolor = "rgba(0,0,0,0)"
            ),
            plot_bgcolor = "white"
        )

        return fig
    
    def find_contract_month_as_int(self, contract: str):
        """
        根据合约名称如'MA05'返回最后两位数字，
        即返回合约的月份
        """
        return int(re.findall("\d{2}$", contract)[0])
    
    def find_arbitrage_period_mask(self, month1, month2):
        """
        返回筛选套利组合可交易时间段的筛选器
        """
        min_month = min(month1, month2)
        max_month = max(month1, month2)
        delta = max_month - min_month
        if (delta <= 6):
            end = dt.date(2000, min_month, 1)
            start = dt.date(2000, max_month, 1)
            return lambda x: [y.month < end.month or y.month > start.month for y in x]
        
        else:
            start = dt.date(2000, min_month, 1)
            end = dt.date(2000, max_month, 1)
            return lambda x: [y.month > start.month and y.month < end.month for y in x]
    
    def calculate_spread(self, ):

        contracts = re.split(pattern = r'[\+\-\*\/]', string = self.formula)
        if len(contracts) == 2:
            contract1 = contracts[0].strip()
            contract2 = contracts[1].strip()
        else:
            return 0
        # 在时间序列上直接读取单个连续合约的价格，如直接读取连续N年的05合约，直接和另外一个对应的合约相减做差。

        contract1_info = self.get_contract_info(contract_from_formula=contract1)
        contract2_info = self.get_contract_info(contract_from_formula=contract2)
        contract1_price = self.download_hist_data(contract1_info)
        contract2_price = self.download_hist_data(contract2_info)
        self.spread = pd.DataFrame(columns = ["spread"])
        # pandas.DataFrame 会自动根据index时间进行运算
        self.spread["spread"] = contract1_price["close"] - contract2_price['close']
        self.spread.dropna(axis = 0, inplace = True)
        self.spread.index = pd.to_datetime(self.spread.index)
        # 获取合约月份
        contract1_month = self.find_contract_month_as_int(contract1)
        contract2_month = self.find_contract_month_as_int(contract2)
        mask_trade_period = self.find_arbitrage_period_mask(contract1_month, contract2_month)(self.spread.index)
        # trade_period_filer 是一个开关，如果是True，季节图上仅展示个人交易者可交易日期
        # 否则展示季节图上展示价差全年日期行情
        if self.trade_period_filter:
            self.spread = self.spread.loc[mask_trade_period, :]
        # self.fig = self.create_figure(data = splited_spread_data)
        
    def plot_spread_with_year(self):

        unsplited_data = self.spread.copy()
        unsplited_data.index = unsplited_data.index.date
        self.fig = self.create_figure(data = unsplited_data)

    def plot_spread_with_monthday(self):
        splited_spread_data = self.split_by_year().copy()
        # 删除没有任何数据的日期，否则画图时会出现大量的空白。
        splited_spread_data.dropna(axis = 0, thresh=1, inplace = True)
        # print(num_of_columns, splited_spread_data)
        self.fig = self.create_figure(data = splited_spread_data)


