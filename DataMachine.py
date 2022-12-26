from abc import *
import pandas as pd
from fredapi import Fred
from datetime import datetime, timedelta
from tqdm import tqdm
from pykrx import stock
import re
import FinanceDataReader as fdr
import pandas_datareader.data as web

class DataMachine(metaclass=ABCMeta):
    def __init__(self):
        self._contents = dict()
        self._startDate = "2000-01-01"
        self._endDate = datetime.now().strftime('%Y-%m-%d')
        self._apiKey = None
        self._dataFrame = None

    @abstractmethod
    def parser(self):
        pass

    @property
    def contents(self):
        return self._contents

    @contents.setter
    def contents(self, value):
        self._contents = value

    @property
    def startDate(self):
        return self._startDate

    @startDate.setter
    def startDate(self, value):
        self._startDate = value

# Macro Index
class FRED(DataMachine):
    """
    ------------------------------------
    FRED 메크로 데이터 크롤링 클래스

                 T10Y    T2Y
    2020-01-01    2.5    1.5
    2020-01-02    2.4    1.3
    2020-01-03    2.3    1.5
    
    Variables:
        apiKey: str, Fred api 사용을 위한 Personal Api Key
        contents: dict, {'사용자 지정 이름': 'FRED 코드'}
        dataFrame: Pandas DataFrame, 데이터 저장 객체
    ------------------------------------
    """
    def __init__(self, apiKey, contents, dataFrame=None):
        super().__init__()
        self._apiKey = apiKey
        self._frd = Fred(api_key=apiKey)
        self.contents(contents)

        if dataFrame != None:
            self._dataFrame = dataFrame

        self.parser() #객체 생성 후 바로 파싱

    def parser(self):
        key = [key for key in self._contents.keys()]
        value = [value for value in self._contents.values()]

        # update
        if self._dataFrame != None:
            tmpFrame = pd.DataFrame()
            lastUpdate = datetime.strftime(self._dataFrame.index[-1]+timedelta(days=1),'%Y-%m-%d')
            for i in tqdm(range(len(value)), desc='Update'):
                tmpFrame[key[i]] = self._frd.get_series(value[i], lastUpdate, self._endDate)
            self._dataFrame = pd.concat([self._dataFrame, tmpFrame])

        #parsing
        else:
            for i in tqdm(range(len(value)), desc='Crawling'):
                self._dataFrame[key[i]] = self._frd.get_series(value[i], self._startDate, self._endDate)

        self._dataFrame.index = [datetime.strptime(idx,'%Y-%m-%d') for idx in self._dataFrame.index]

    @property
    def dataFrame(self):
        return self._dataFrame

# KRX Sector Index
class KRX(DataMachine):
    """
    ------------------------------------
    KRX 섹터 지수 데이터 크롤링 클래스
    국내 상장 주식, ETF OHLCV 크롤링 StaticMethod 포함

               Chemical Health
    2020-01-01    2.5    1.5
    2020-01-02    2.4    1.3
    2020-01-03    2.3    1.5

                  Open   High   Low  Close   Volume
    2020-01-01      1     2      3     4       5
    2020-01-02      1     2      3     4       5
    2020-01-03      1     2      3     4       5
    
    Variables:
        contents: dict, {'사용자 지정 이름': '지수 코드'}
        dataFrame: Pandas DataFrame, 데이터 저장 객체
    ------------------------------------
    """
    def __init__(self, contents, dataFrame=None):
        super().__init__()
        self.contents(contents)

        if dataFrame != None:
            self._dataFrame = dataFrame

        self.parser() #객체 생성 후 바로 파싱

    def parser(self):
        key = [key for key in self._contents.keys()]
        value = [value for value in self._contents.values()]

        startDate, endDate = re.sub(r'[^0-9]',"",self._startDate), re.sub(r'[^0-9]',"",self._endDate)

        # update
        if self._dataFrame != None:
            tmpFrame = pd.DataFrame()
            lastUpdate = datetime.strftime(self._dataFrame.index[-1]+timedelta(days=1),'%Y%m%d')
            for i in tqdm(range(len(value)), desc='Update'):
                tmpFrame[key[i]] = stock.get_index_ohlcv_by_date(lastUpdate, endDate, value[i])['종가']
            self._dataFrame = pd.concat([self._dataFrame, tmpFrame])

        #parsing
        else:
            for i in tqdm(range(len(value)), desc='Crawling'):
                self._dataFrame[key[i]] = stock.get_index_ohlcv_by_date(startDate, endDate, value[i])['종가']

        self._dataFrame.index = [datetime.strptime(idx,'%Y-%m-%d') for idx in self._dataFrame.index]

    @property
    def dataFrame(self):
        return self._dataFrame

    @staticmethod
    def getStockData(ticker, startDate, endDate):
        tmpFrame = stock.get_market_ohlcv(startDate, endDate, ticker)
        tmpFrame = tmpFrame.drop(labels=['거래대금', '등락률'], axis=1)
        tmpFrame.columns = ['Open', 'High', 'Low', 'Close', 'volume']
        tmpFrame.index = [datetime.strptime(idx,'%Y-%m-%d') for idx in tmpFrame.index]
        return tmpFrame
        
    @staticmethod
    def getETFData(ticker, startDate, endDate):
        tmpFrame = stock.get_index_ohlcv_by_date(startDate, endDate, ticker)
        tmpFrame = tmpFrame.drop(labels=['거래대금', '상장시가총액'], axis=1)
        tmpFrame.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        tmpFrame.index = [datetime.strptime(idx,'%Y-%m-%d') for idx in tmpFrame.index]
        return tmpFrame

# Commodities, Currency, World Indices
class Yahoo(DataMachine):
    """
    ------------------------------------
    Yahoo 메크로 데이터 크롤링 클래스
    FinanceDataReader/yfinance channel 선택

                 Gold    Oil
    2020-01-01    2.5    1.5
    2020-01-02    2.4    1.3
    2020-01-03    2.3    1.5
    
    Variables:
        contents: dict, {'사용자 지정 이름': 'Yahoo 종목 코드'}
        dataFrame: Pandas DataFrame, 데이터 저장 객체

    Methods:
        getStockData: yahoo에 존재하는 종목 OHLCV 크롤링 StaticMethod
    ------------------------------------
    """
    def __init__(self, contents, channel='FinanceDataReader', dataFrame=None):
        super().__init__()
        self.contents(contents)
        self._channel = channel

        if dataFrame != None:
            self._dataFrame = dataFrame

        self.parser() #객체 생성 후 바로 파싱

    def parser(self):
        key = [key for key in self._contents.keys()]
        value = [value for value in self._contents.values()]

        # update
        if self._dataFrame != None:
            tmpFrame = pd.DataFrame()
            lastUpdate = datetime.strftime(self._dataFrame.index[-1]+timedelta(days=1),'%Y-%m-%d')
            for i in tqdm(range(len(value)), desc='Update'):
                tmpFrame[key[i]] = fdr.DataReader(value[i], lastUpdate, self._endDate)['Adj Close']
            self._dataFrame = pd.concat([self._dataFrame, tmpFrame])

        #parsing
        else:
            for i in tqdm(range(len(value)), desc='Crawling'):
                self._dataFrame[key[i]] = fdr.DataReader(value[i], self._startDate, self._endDate)['Adj Close']

        self._dataFrame.index = [datetime.strptime(idx,'%Y-%m-%d') for idx in self._dataFrame.index]

    @property
    def dataFrame(self):
        return self._dataFrame

    @staticmethod
    def getStockData(ticker, startDate, endDate):
        tmpFrame = stock.get_market_ohlcv(startDate, endDate, ticker)
        tmpFrame = tmpFrame.drop(labels=['Change'], axis=1)
        tmpFrame.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        tmpFrame.index = [datetime.strptime(idx,'%Y-%m-%d') for idx in tmpFrame.index]
        return tmpFrame

# SDMX: Statistical Macro Data
class SDMX(DataMachine):
    """
    ------------------------------------
    Yahoo 메크로 데이터 크롤링 클래스
    FinanceDataReader/yfinance channel 선택

                 Gold    Oil
    2020-01-01    2.5    1.5
    2020-01-02    2.4    1.3
    2020-01-03    2.3    1.5
    
    Variables:
        contents: dict, {'사용자 지정 이름': 'Yahoo 종목 코드'}
        dataFrame: Pandas DataFrame, 데이터 저장 객체

    Methods:
        getStockData: yahoo에 존재하는 종목 OHLCV 크롤링 StaticMethod
    ------------------------------------
    """
    def __init__(self):
        super().__init__()
        pass

    def parser(self):
        pass

# KRX Fundamental Data
class DART(DataMachine):
    """
    ------------------------------------
    Yahoo 메크로 데이터 크롤링 클래스
    FinanceDataReader/yfinance channel 선택

                 Gold    Oil
    2020-01-01    2.5    1.5
    2020-01-02    2.4    1.3
    2020-01-03    2.3    1.5
    
    Variables:
        contents: dict, {'사용자 지정 이름': 'Yahoo 종목 코드'}
        dataFrame: Pandas DataFrame, 데이터 저장 객체

    Methods:
        getStockData: yahoo에 존재하는 종목 OHLCV 크롤링 StaticMethod
    ------------------------------------
    """
    def __init__(self):
        super().__init__()
        pass

    def parser(self):
        pass