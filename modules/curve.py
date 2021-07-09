from selenium import webdriver
import pandas as pd
from datetime import datetime, timedelta, date
import bs4 as bs
import lxml
import requests
import QuantLib as ql


def ql_to_datetime(d):
    return datetime(d.year(), d.month(), d.dayOfMonth())

class Curve:
    def __init__(self, currency="USD", type="OIS", *args):
        self.currency = currency    #Currency of underlying rate.; E.g. USD, GBP, EUR
        self.type = type            #Type of curve: E.g. OIS (Discount) or LIBOR (Forecast)
        self.holiday = ql.TARGET()
        self.t0 = date.today()
        self.today = ql.Date(self.t0.day, self.t0.month, self.t0.year)
        ql.Settings.instance().evaluationDate = self.today
        if type=="OIS":
            self.tenor = "O/N"
        elif len(args) != 0:
            self.tenor = args[0]
        else:
            self.tenor = "6M"

        if self.currency in ["USD", "GBP"]:
            self.get_cme_settlement_data()
            if self.currency == "USD":
                self.effr = self.get_effr()
                self.obfr = self.get_obfr()
                self.day_count = ql.Thirty360()
                self.fed_funds_futures = self.get_30_day_fed_funds_strip()
                self.sofr_1M_futures = self.get_1M_sofr_strip()
                self.sofr_3M_futures = self.get_3M_sofr_strip()
                self.oisSwaps = self.get_OIS_instruments()



                self.helpers = self.get_DepositRateHelper()
                gaps = self.sofr_1M_futures[~self.sofr_1M_futures['End'].isin(self.sofr_3M_futures['End'])]

                self.helpers += self.get_SofrFutureRateHelper(gaps, ql.Monthly)
                self.helpers += self.get_SofrFutureRateHelper(self.sofr_3M_futures, ql.Quarterly)
                self.helpers += self.OISRateHelper()



        else:
            print("Must be EUR")

    def contents(self):
        print("Currency is: ", self.currency, "Type is: ", self.type, "Tenor is: ", self.tenor)
        # if self.currency in ["USD", "GBP"]:
        #     print(self.cme_text)



    def get_cme_settlement_data(self):
        driver = webdriver.Chrome()
        driver.get('http://www.cmegroup.com/ftp/pub/settle/stlint')

        self.cme_text = driver.page_source
        driver.quit()

    def get_effr(self):
        url = "https://markets.newyorkfed.org/read?productCode=50&eventCodes=500&limit=25&startPosition=0&sort=postDt:-1&format=xml"

        url_link = requests.get(url)
        file = bs.BeautifulSoup(url_link.text, "lxml")
        find_table = file.find("percentrate")

        return float(find_table.text)

    def get_obfr(self):
        url = "https://markets.newyorkfed.org/read?productCode=50&eventCodes=505&limit=25&startPosition=0&sort=postDt:-1&format=xml"

        url_link = requests.get(url)
        file = bs.BeautifulSoup(url_link.text, "lxml")
        find_table = file.find("percentrate")

        return float(find_table.text)

    def get_one_month_futures_dates(self, futures_code):
        month_dict = {
            'JAN': 1,
            'FEB': 2,
            'MAR': 3,
            'APR': 4,
            'MAY': 5,
            'JUN': 6,
            'JLY': 7,
            'AUG': 8,
            'SEP': 9,
            'OCT': 10,
            'NOV': 11,
            'DEC': 12,

        }
        year_prefix = str(datetime.now().year)[:2]
        year = int(year_prefix + futures_code[3:])
        first_day_of_month = ql.Date(1, month_dict[futures_code[0:3]], year)
        fbd = self.holiday.adjust(first_day_of_month, ql.Following)
        first_business_day_of_month = ql_to_datetime(fbd)
        lbd = self.holiday.endOfMonth(first_day_of_month)
        last_business_day_of_month = ql_to_datetime(lbd)

        return first_business_day_of_month, last_business_day_of_month

        # return datetime.strftime(first_business_day_of_month, "%m/%d/%Y"), datetime.strftime(last_business_day_of_month, "%m/%d/%Y")


    def getIMMDate(self, IMMcode, month):
        '''Takes 5 character IMM code (e.g. SEP23) and returns effective date as datetime object'''
        if month == 1:
            offset = 31
        else:
            offset = 93

        from datetime import datetime, timedelta
        month_dict = {
            'JAN': 1,
            'FEB': 2,
            'MAR': 3,
            'APR': 4,
            'MAY': 5,
            'JUN': 6,
            'JLY': 7,
            'AUG': 8,
            'SEP': 9,
            'OCT': 10,
            'NOV': 11,
            'DEC': 12,

        }

        month = month_dict[IMMcode[0:3]]

        year_prefix = str(datetime.now().year)[:2]

        year = int(year_prefix + IMMcode[3:])

        the_date = datetime(year, month, 1)
        end_date = the_date + timedelta(days=offset)
        temp = the_date.replace(day=1)
        temp_end = end_date.replace(day=1)
        nth_week = 3
        week_day = 2
        adj = (week_day - temp.weekday()) % 7
        adj_end = (week_day - temp_end.weekday()) % 7
        temp += timedelta(days=adj)
        temp += timedelta(weeks=nth_week - 1)
        temp_end += timedelta(days=adj_end)
        temp_end += timedelta(weeks=nth_week - 1)


        return temp, temp_end
        # return datetime.strftime(temp, "%m/%d/%Y"), datetime.strftime(temp_end, "%m/%d/%Y")

    def get_30_day_fed_funds_strip(self):
        start = self.cme_text.find("FF 30 DAY FED FUNDS FUTURES") + len("FF 30 DAY FED FUNDS FUTURES") + 1
        end = self.cme_text.find("FV 5 YEAR US TREASURY NOTE FUTURES")

        edf = self.cme_text[start:end]
        end = edf.find("TOTAL")
        edf = edf[:end]
        data = edf.splitlines()


        df = pd.DataFrame([x[:56].split() for x in data])
        df.columns = ['Expiry', 'Open', 'High', 'Low', 'Last', 'Sett']
        df.set_index('Expiry', inplace=True)
        df = df.head(21)


        df = df.apply(pd.to_numeric, errors='ignore')
        expiry = df.index.tolist()

        start = []
        end = []
        month = []
        year = []
        for d in expiry:
            s, e = self.get_one_month_futures_dates(d)
            start.append(s)
            end.append(e)
            month.append(s.month)
            year.append(s.year)

        df2 = pd.DataFrame(list(zip(expiry, start, end, month, year)), columns=['Expiry', 'Start', 'End', 'Month', 'Year'])

        df = df.merge(df2, left_on='Expiry', right_on='Expiry')

        return df

    def get_1M_sofr_strip(self):
        start = self.cme_text.find("SR1 1-MONTH SOFR FUTURE") + len("SR1 1-MONTH SOFR FUTURE") + 1
        end = self.cme_text.find("SR3 3-MONTH SOFR FUTURE")

        edf = self.cme_text[start:end]
        end = edf.find("TOTAL")
        edf = edf[:end]
        data = edf.splitlines()


        df = pd.DataFrame([x[:56].split() for x in data])
        df.columns = ['Expiry', 'Open', 'High', 'Low', 'Last', 'Sett']
        df.set_index('Expiry', inplace=True)
        df = df.head(11)


        df = df.apply(pd.to_numeric, errors='ignore')
        expiry = df.index.tolist()

        start = []
        end = []
        month = []
        year = []
        for d in expiry:
            s, e = self.get_one_month_futures_dates(d)
            start.append(s)
            end.append(e)
            month.append(s.month)
            year.append(s.year)

        df2 = pd.DataFrame(list(zip(expiry, start, end, month, year)), columns=['Expiry', 'Start', 'End', 'Month', 'Year'])

        df = df.merge(df2, left_on='Expiry', right_on='Expiry')
        prior = df[df['Start'] <= pd.Timestamp(self.t0)].index
        df.drop(prior, inplace=True)




        return df

    def get_3M_sofr_strip(self):
        start = self.cme_text.find("SR3 3-MONTH SOFR FUTURE") + len("SR3 3-MONTH SOFR FUTURE") + 1
        end = self.cme_text.find("T1S 2-Year MAC SOFR Swap Futures")

        edf = self.cme_text[start:end]
        end = edf.find("TOTAL")
        edf = edf[:end]
        data = edf.splitlines()


        df = pd.DataFrame([x[:56].split() for x in data])
        df.columns = ['Expiry', 'Open', 'High', 'Low', 'Last', 'Sett']
        df.set_index('Expiry', inplace=True)
        df = df.head(15)


        df = df.apply(pd.to_numeric, errors='ignore')
        expiry = df.index.tolist()

        start = []
        end = []
        month = []
        year = []
        for d in expiry:
            s, e = self.getIMMDate(d, 3)

            start.append(s)
            end.append(e)
            month.append(s.month)
            year.append(s.year)

        df2 = pd.DataFrame(list(zip(expiry, start, end, month, year)), columns=['Expiry', 'Start', 'End', 'Month', 'Year'])

        df = df.merge(df2, left_on='Expiry', right_on='Expiry')

        prior = df[df['Start'] <= pd.Timestamp(self.t0)].index

        df.drop(prior, inplace=True)


        return df

    def get_OIS_instruments(self):
        if self.currency == "USD":
            DF_INDEX = 1
        elif self.currency == "EUR":
            DF_INDEX = 3
        elif self.currency == "GBP":
            DF_INDEX = 7

        else:
            print("Currency not supported")
            return -1

        dfs = pd.read_html("https://www.lch.com/services/swapclear/essentials/settlement-prices")
        ois_quotes = {}
        for i in range(0,8):
            ois_quotes[dfs[DF_INDEX].iloc[i,0] + ' OIS'] = dfs[DF_INDEX].iloc[i,1]


        self.ois_rates = pd.DataFrame(list(ois_quotes.items()), columns=['Tenor', 'Rate'])
        return self.ois_rates

    def get_DepositRateHelper(self):
        helpers = [
            ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate / 100)),
                                 ql.Period(1, ql.Days), fixingDays,
                                 self.holiday, ql.Following,
                                 False, ql.Actual360())
            for rate, fixingDays in [(self.obfr, 0), (self.obfr, 1), (self.obfr, 2)]
        ]
        return helpers

    def get_SofrFutureRateHelper(self, gaps, tenor):
        rate_month_year_list = []

        for i in range(len(gaps)):
            rate = gaps['Sett'].to_list()[i]
            month = gaps['Month'].to_list()[i]
            year = gaps['Year'].to_list()[i]

            rate_month_year_list.append((rate, month, year))


        helpers = [
            ql.SofrFutureRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate)), month, year, tenor, ql.Sofr())
            for rate, month, year in rate_month_year_list

        ]
        return helpers

    def OISRateHelper(self):

        forward6mLevel = self.oisSwaps.loc[self.oisSwaps['Tenor'] == '6 month OIS', 'Rate'].values[0]/100

        forward6mQuote = ql.QuoteHandle(ql.SimpleQuote(forward6mLevel))
        yts6m = ql.FlatForward(0, ql.TARGET(), forward6mQuote, ql.Actual365Fixed())
        yts6mh = ql.YieldTermStructureHandle(yts6m)
        oishelper = [ql.OISRateHelper(2, ql.Period(*tenor), ql.QuoteHandle(ql.SimpleQuote(rate/100)), ql.FedFunds(yts6mh), yts6mh,
                                     True)
            for rate, tenor in [
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '3 month OIS', 'Rate'].values[0], (3, ql.Months)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '6 month OIS', 'Rate'].values[0], (6, ql.Months)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '1 year OIS', 'Rate'].values[0], (12, ql.Months)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '2 year OIS', 'Rate'].values[0], (2, ql.Years)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '3 year OIS', 'Rate'].values[0], (3, ql.Years)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '5 year OIS', 'Rate'].values[0], (5, ql.Years)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '10 year OIS', 'Rate'].values[0], (10, ql.Years)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '30 year OIS', 'Rate'].values[0], (30, ql.Years)),
            ]
        ]
        return oishelper

    def build_spot_curve(self):
        spot_curve = ql.PiecewiseLogCubicDiscount(self.today,
                             self.helpers,
                             self.day_count)

        spots = []
        tenors = []
        for d in spot_curve.dates():
            yrs = self.day_count.yearFraction(self.today, d)
            compounding = ql.Compounded
            freq = ql.Semiannual
            zero_rate = spot_curve.zeroRate(yrs, compounding, freq)
            tenors.append(yrs)
            eq_rate = zero_rate.equivalentRate(self.day_count,
                                               compounding,
                                               freq,
                                               self.today,
                                               d).rate()
            spots.append(100 * eq_rate)

        chart = dict(zip(tenors, spots))

        print(chart)

    def build_from_ois(self):
        spot_curve = ql.PiecewiseLogCubicDiscount(self.today,
                             self.helpers,
                             self.day_count)
        df_curve = ql.PiecewiseFlatForward(self.today, self.helpers,
                                            ql.Actual360())

        spots = []
        tenors = []
        dfs = []
        dfs2 = []
        for d in spot_curve.dates():
            yrs = self.day_count.yearFraction(self.today, d)
            compounding = ql.Compounded
            freq = ql.Semiannual
            zero_rate = spot_curve.zeroRate(yrs, compounding, freq)
            discount_factor = df_curve.discount(d)
            discount_factor2 = spot_curve.discount(d)
            tenors.append(yrs)
            eq_rate = zero_rate.equivalentRate(self.day_count,
                                               compounding,
                                               freq,
                                               self.today,
                                               d).rate()
            spots.append(100 * eq_rate)
            dfs.append(discount_factor)
            dfs2.append(discount_factor2)

        chart_df = dict(zip(tenors, dfs))
        chart_spot = dict(zip(tenors, spots))
        chart_df2 = dict(zip(tenors, dfs2))

        print(chart_df)
        print(chart_df2)
        print(chart_spot)
        return


a = Curve()
b = Curve("GBP")
c = Curve("EUR", "LIBOR", "3M")
d = Curve("EUR", "LIBOR",)

print(a.contents(), b.contents(), c.contents(), d.contents())
a.OISRateHelper()
a.build_from_ois()

a.build_spot_curve()

