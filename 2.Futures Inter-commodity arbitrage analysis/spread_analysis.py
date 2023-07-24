# 将本格代码另存到一个.py文件，并命名成spread_analysis.py

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
        self.all_instruments = pd.read_csv("20230722_all_instruments.csv", index_col = 0)
        self.spread = pd.DataFrame()
        self.trade_period_filter = trade_period_filter
        self.get_contract_instruments()
        self.get_index_instruments()
    def get_contract_instruments(self):
        """
        返回合约信息，不包括指数类信息
        """
        all_instruments = self.all_instruments
        contract_instruments = all_instruments[all_instruments["listed_date"] != "0000-00-00"].copy()
        self.contract_instruments = contract_instruments
        
    
    def get_index_instruments(self):
        """ 
        返回指数类信息，不包括合约信息
        """
        all_instruments = self.all_instruments
        index_instruments = all_instruments[all_instruments["listed_date"] == "0000-00-00"].copy()
        self.index_instruments = index_instruments
    
    def get_contract_info(
        self,
        contract_from_formula: str, # e.g. MA09
        ):
        """ 
        从交易代码和rqdata获取的all_instruments信息表中，
        获取相应的历史合约代码。
        例如已知MA09，要求获取过去N年的09合约代码，包括上市日期，退市日期。
        """
        underlying_symbol = re.findall(pattern = r"[A-Za-z]+", string = contract_from_formula)[0]
        contract_instruments = self.contract_instruments
        # 创建新的列，存储合约的月份，该列的数据类型为2个字符串。
        contract_instruments.loc[:, "maturity_date_month"] = pd.to_datetime(contract_instruments["maturity_date"]).dt.month.astype(str).str.zfill(2)
        # 创建新的列，存储合约的年份，该列的数据类型为4个字符串。
        contract_instruments.loc[:, "maturity_date_year"] = pd.to_datetime(contract_instruments["maturity_date"]).dt.year.astype(str).str.zfill(4)
        # mask1，mask2为两个筛选器。
        # mask1 筛选期货品种
        mask1 = contract_instruments["underlying_symbol"] == underlying_symbol
        # mask2 筛选合约月份
        # 注意不能有空格
        mask2 = contract_instruments["maturity_date_month"] == contract_from_formula[-2:]
        contract_instruments = contract_instruments[mask1 & mask2]
        # 筛选出过去最新N年的期货合约， N由years_trace_back决定。
        contract_instruments = contract_instruments.iloc[-self.years_trace_back:, :]
        print(f"{len(contract_instruments)} years of symbol {contract_from_formula} historical contracts are found.")
        return (contract_instruments[["order_book_id", "listed_date", "de_listed_date","maturity_date_year"]], len(contract_instruments))

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
        for year in self.spread.index.year.unique():
            year_data = self.spread[self.spread.index.year == year]
            # Remove the year from the index date
            year_data.index = year_data.index.strftime("%m-%d")
            # Add the year's data as a new column in the split_data DataFrame
            splited_data[year] = year_data

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
    
    def get_contract_month_list(self, contract_symbol_list):
        """
        遍历合约名称列表
        根据合约名称如'MA05'返回最后两位数字，
        即返回合约的月份
        """
        contract_month_list = []
        for i in contract_symbol_list:
            month = int(re.findall("\d{2}$", i)[0])
            contract_month_list.append(month)
        return contract_month_list
    
    def find_arbitrage_period_mask(self, contract_month_list: list):
        """
        返回筛选套利组合可交易时间段的筛选器
        """
        min_month = min(contract_month_list)
        max_month = max(contract_month_list)
        delta = max_month - min_month
        if (delta <= 6):
            end = dt.date(2000, min_month, 1)
            start = dt.date(2000, max_month, 1)
            return lambda x: [y.month < end.month or y.month > start.month for y in x]
        
        else:
            start = dt.date(2000, min_month, 1)
            end = dt.date(2000, max_month, 1)
            return lambda x: [y.month > start.month and y.month < end.month for y in x]
        
    def get_contract_info_list_and_available_lookback_window_list(self, contract_symbol_list):
        contract_info_list = []
        available_lookback_window_list = []
        for i in contract_symbol_list:
            contract_info, available_lookback_window = self.get_contract_info(i)
            contract_info_list.append(contract_info)
            available_lookback_window_list.append(available_lookback_window)
    
        return contract_info_list, available_lookback_window_list

    def lookback_window_alignment(self, contract_info_list, available_lookback_window_list):
        """ 
        对获得的各品种年限进行矫正。
        价差计算经常会遇到不同品种合约，上市时间不一样的情形。
        例如（在rqdata上）螺纹钢最长能查询到15年的历史，铁矿最长只能查询到10年的历史，
        当用到这两者做价差计算时，螺纹钢和铁矿必须在时间戳上进行对齐。
        这也就意味着，螺纹钢比铁矿早五年的历史行情需要舍去的。
        """
        lookback_window_for_spread = min(available_lookback_window_list)
        if lookback_window_for_spread < self.years_trace_back:
            print(f"only {lookback_window_for_spread} years data is available for spread calculation.")
            for num in range(len(contract_info_list)):
                contract_info_list[num] = contract_info_list[num].tail(lookback_window_for_spread)       
        
        return contract_info_list
    
    def clean_symbol_list(self, contract_symbol_list):
        new_list = []
        for i in contract_symbol_list:
            new_list.append(i.strip())
        return new_list
    
    def calculate_spread(self, ):

        #contract_symbol_list = re.split(pattern = r'[\+\-\*\/]', string = self.formula)
        contract_symbol_list = re.findall(r"[A-Za-z]+\d+", self.formula)
        # 情理合约符号，不能带空格
        #contract_symbol_list = self.clean_symbol_list(contract_symbol_list)
        contract_info_list, available_lookback_window_list = self.get_contract_info_list_and_available_lookback_window_list(contract_symbol_list)
        # 对获得的各品种信息进行矫正。
        # 价差计算经常会遇到不同品种合约，上市时间不一样的情形。
        # 例如（在rqdata上）螺纹钢最长能查询到15年的历史，铁矿最长只能查询到10年的历史，
        # 当用到这两者做价差计算时，螺纹钢和铁矿必须在时间戳上进行对齐。
        # 这也就意味着，螺纹钢比铁矿早期的五年历史行情是需要舍去的。
        contract_info_list = self.lookback_window_alignment(contract_info_list, available_lookback_window_list)
        spread = pd.DataFrame(columns = ["spread"])
        for i, j in zip(contract_symbol_list, contract_info_list):
            print("downloading historical data for ", i)
            exec(f"{i} = self.download_hist_data(j)['close']")
        exec(f"spread['spread'] = {self.formula}")
        spread.dropna(axis = 0, inplace = True)
        spread.index = pd.to_datetime(spread.index)
        contract_month_list = self.get_contract_month_list(contract_symbol_list)
        mask_for_trade_period = self.find_arbitrage_period_mask(contract_month_list)(spread.index)
        # trade_period_filer 是一个开关，如果是True，季节图上仅展示个人交易者可交易日期
        # 否则展示季节图上展示价差全年日期行情
        if self.trade_period_filter:
            self.spread = spread.loc[mask_for_trade_period, :].copy()
        else:
            self.spread = spread.copy()
        # self.fig = self.create_figure(data = splited_spread_data)
        
    def plot_spread_with_year(self):

        unsplited_data = self.spread.copy()
        unsplited_data.index = unsplited_data.index.date
        self.fig = self.create_figure(data = unsplited_data)
        self.fig.show()

    def plot_spread_with_monthday(self):
        splited_spread_data = self.split_by_year().copy()
        # 删除没有任何数据的日期，否则画图时会出现大量的空白。
        splited_spread_data.dropna(axis = 0, thresh=1, inplace = True)
        # print(num_of_columns, splited_spread_data)
        self.fig = self.create_figure(data = splited_spread_data)
        self.fig.show()


