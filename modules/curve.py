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
                self.helpers = self.get_DepositRateHelper(self.obfr)
                # gaps = self.sofr_1M_futures[~self.sofr_1M_futures['End'].isin(self.sofr_3M_futures['End'])]
                self.helpers += self.get_SofrFutureRateHelper(self.sofr_1M_futures, ql.Monthly)
                self.helpers += self.get_SofrFutureRateHelper(self.sofr_3M_futures, ql.Quarterly)
                self.helpers += self.OISRateHelper()
                self.ois_curve = ql.PiecewiseSplineCubicDiscount(self.holiday.adjust(self.today, ql.Following),
                             self.helpers, self.day_count)
                self.ois_curve.enableExtrapolation()
                if self.tenor in ['1M', '3M', '6M']:
                    self.libor = ql.USDLibor(ql.Period(self.tenor))
                    url = "https://www.global-rates.com/en/interest-rates/libor/american-dollar/american-dollar.aspx"
                    self.depo_quotes = {}
                    self.depo = self.get_depo_instruments(url)
                    self.eurodollar_futures = self.get_eurodollar_strip()
                    self.swaps = self.get_Swap_instruments()
                    self.discount_curve = ql.RelinkableYieldTermStructureHandle()
                    self.discount_curve.linkTo(self.ois_curve)
                    print(self.eurodollar_futures)
                    print(self.swaps)
                    self.forecast_helpers = self.get_libor_depo_helper()
                    self.forecast_helpers += self.FuturesRateHelper()
                    self.forecast_helpers += self.SwapRateHelper()
                    self.forecast_curve = ql.PiecewiseLogCubicDiscount(2, self.holiday, self.forecast_helpers,
                                               self.day_count)
                    self.forecast_curve.enableExtrapolation()



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

    def get_eurodollar_strip(self):


        start = self.cme_text.find("ED CME EURODOLLAR FUTURES") + len("ED CME EURODOLLAR FUTURES") + 1
        end = self.cme_text.find("EM 1-MONTH EURODOLLAR FUTURE")

        edf = self.cme_text[start:end]
        end = edf.find("TOTAL")
        edf = edf[:end]
        data = edf.splitlines()

        df = pd.DataFrame([x[:56].split() for x in data])
        df.columns = ['Expiry', 'Open', 'High', 'Low', 'Last', 'Sett']
        df.set_index('Expiry', inplace=True)
        df = df.head(28)


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

    def get_Swap_instruments(self):
        if self.currency == "USD":
            DF_INDEX = 0
        elif self.currency == "EUR":
            DF_INDEX = 2
        elif self.currency == "GBP":
            DF_INDEX = 6

        if self.tenor == "1M":
            COL_INDEX = 1
        elif self.tenor == "3M":
            COL_INDEX = 2
        elif self.tenor == "6M":
            COL_INDEX = 3

        else:
            print("Currency not supported")
            return -1

        dfs = pd.read_html("https://www.lch.com/services/swapclear/essentials/settlement-prices")
        swap_quotes = {}
        for i in range(0,5):
            swap_quotes[dfs[DF_INDEX].iloc[i,0] + ' ' + self.tenor + ' Libor'] = dfs[DF_INDEX].iloc[i,COL_INDEX]

        self.swap_rates = pd.DataFrame(list(swap_quotes.items()), columns=['Tenor', 'Rate'])
        return self.swap_rates

    def get_depo_business_day(self, start, n):

        date = start + timedelta(days=n)
        ql_date = ql.Date(date.day, date.month, date.year)
        ql_rolled = self.holiday.adjust(ql_date, ql.Following)
        ret_date = ql_to_datetime(ql_rolled)

        return ret_date

    def get_depo_business_day_months(self, start, n):

        date = start
        ql_date = ql.Date(date.day, (date.month + n) % 12,  date.year)
        ql_rolled = self.holiday.adjust(ql_date, ql.ModifiedFollowing)
        ret_date = ql_to_datetime(ql_rolled)

        return ret_date

    def get_depo_instruments(self, url):
        dfs = pd.read_html(url)
        t0 = ql_to_datetime(self.holiday.adjust(ql.Date(self.t0.day, self.t0.month, self.t0.year), ql.Following))

        today = self.get_depo_business_day(t0, 0)
        tom = self.get_depo_business_day(t0, 1)
        tom_next = self.get_depo_business_day(t0, 2)
        spot = self.get_depo_business_day(t0, 3)
        week1 = self.get_depo_business_day(t0, 9)
        month1 = self.get_depo_business_day_months(t0, 1)
        month2 = self.get_depo_business_day_months(t0, 2)
        month3 = self.get_depo_business_day_months(t0, 3)
        month6 = self.get_depo_business_day_months(t0, 6)
        month12 = self.get_depo_business_day_months(t0, 12)

        self.depo_quotes['O/N depo'] = [float(dfs[9].iloc[1,1].strip('\xa0%')), today, tom, 1, 0]
        self.depo_quotes['T/N depo'] = [float(dfs[9].iloc[1,1].strip('\xa0%')), tom, tom_next, 1, 1]
        self.depo_quotes['S/N depo'] = [float(dfs[9].iloc[1,1].strip('\xa0%')), tom_next, spot, 1, 2]
        self.depo_quotes['1 wk depo'] = [float(dfs[9].iloc[2,1].strip('\xa0%')), tom_next, week1, 7, 2]
        self.depo_quotes['1 Mth depo'] = [float(dfs[9].iloc[4, 1].strip('\xa0%')), tom_next, month1, 1, 2]
        self.depo_quotes['2 Mth depo'] = [float(dfs[9].iloc[5, 1].strip('\xa0%')), tom_next, month2, 2, 2]
        self.depo_quotes['3 Mth depo'] = [float(dfs[9].iloc[6, 1].strip('\xa0%')), tom_next, month3, 3, 2]
        self.depo_quotes['6 Mth depo'] = [float(dfs[9].iloc[9, 1].strip('\xa0%')), tom_next, month6, 6, 2]
        self.depo_quotes['12 Mth depo'] = [float(dfs[9].iloc[15, 1].strip('\xa0%')), tom_next, month12, 12, 2]

        df = pd.DataFrame.from_dict(self.depo_quotes, orient='index', columns = ['Rate', 'Start', 'End', 'Period', 'Fixing Days'])
        return df

    def get_DepositRateHelper(self, depo):
        helpers = [
            ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate / 100)),
                                 ql.Period(1, ql.Days), fixingDays,
                                 self.holiday, ql.Following,
                                 False, ql.Actual360())
            for rate, fixingDays in [(depo, 0), (depo, 1), (depo, 2)]
        ]
        return helpers
    def get_libor_depo_helper(self):
        helpers = [
            ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate/100)), ql.Period(int(period), ql.Days), int(fixing), self.holiday, ql.Following, False, self.day_count)
            # for rate, period, fixing in [
            #     (self.depo.iloc[0, 0], 1, 0),
            #     (self.depo.iloc[1, 0], 1, 1),
            #     (self.depo.iloc[2, 0], 1, 2),
            #     (self.depo.iloc[3, 0], 7, 2)
            #
            # ]
            for rate, period, fixing in self.depo[['Rate', 'Period', 'Fixing Days']].values
        ]
        helpers += [
            ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate/100)), ql.Period(int(period), ql.Months), int(fixing), self.holiday, ql.Following, False, self.day_count)
            # for rate, period, fixing in [
            #     (self.depo.iloc[4, 0], 1, 2),
            #     (self.depo.iloc[5, 0], 2, 2),
            #     (self.depo.iloc[6, 0], 3, 2),
            #     (self.depo.iloc[7, 0], 6, 2),
            #     (self.depo.iloc[7, 0], 12, 2) ]
            for rate, period, fixing in self.depo[['Rate', 'Period', 'Fixing Days']].values
        ]

        return helpers

    def FuturesRateHelper(self):
        df = self.eurodollar_futures[['Sett', 'Start']]
        helpers = [
            ql.FuturesRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate)),
                                 ql.Date(start_date.day, start_date.month, start_date.year), self.libor, ql.QuoteHandle())

            for rate, start_date in [
                (df.iloc[0, 0], df.iloc[0, 1]),
                (df.iloc[1, 0], df.iloc[1, 1]),
                (df.iloc[2, 0], df.iloc[2, 1]),
                (df.iloc[3, 0], df.iloc[3, 1]),
                (df.iloc[4, 0], df.iloc[4, 1]),
                (df.iloc[5, 0], df.iloc[5, 1]),
                (df.iloc[6, 0], df.iloc[6, 1]),
                (df.iloc[7, 0], df.iloc[7, 1]),
                (df.iloc[8, 0], df.iloc[8, 1]),
                (df.iloc[9, 0], df.iloc[9, 1]),
                (df.iloc[10, 0], df.iloc[10, 1]),
                (df.iloc[11, 0], df.iloc[11, 1]),
                (df.iloc[12, 0], df.iloc[12, 1]),
                (df.iloc[13, 0], df.iloc[13, 1]),
                (df.iloc[14, 0], df.iloc[14, 1]),
                (df.iloc[15, 0], df.iloc[15, 1]),
                (df.iloc[16, 0], df.iloc[16, 1]),
                (df.iloc[17, 0], df.iloc[17, 1]),
            ]
        ]
        # for index, row in self.eurodollar_futures.iterrows():
        #     print(index)
        #     print(row[['Start', 'Sett']])

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
                         # (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '3 month OIS', 'Rate'].values[0], (3, ql.Months)),
                         # (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '6 month OIS', 'Rate'].values[0], (6, ql.Months)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '1 year OIS', 'Rate'].values[0], (12, ql.Months)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '2 year OIS', 'Rate'].values[0], (2, ql.Years)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '3 year OIS', 'Rate'].values[0], (3, ql.Years)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '5 year OIS', 'Rate'].values[0], (5, ql.Years)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '10 year OIS', 'Rate'].values[0], (10, ql.Years)),
                         (self.oisSwaps.loc[self.oisSwaps['Tenor'] == '30 year OIS', 'Rate'].values[0], (30, ql.Years)),
            ]
        ]
        return oishelper

    def SwapRateHelper(self):
        helpers = [
            # ql.SwapRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate/100)),
            #                   ql.Period(tenor, ql.Years), self.holiday,
            #                   ql.Semiannual, ql.Unadjusted, ql.Thirty360(ql.Thirty360.BondBasis), self.libor, ql.QuoteHandle(),
            #                   ql.Period(0, ql.Days), self.discount_curve)
            ql.SwapRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate / 100)),
                              ql.Period(tenor, ql.Years), self.holiday,
                              ql.Semiannual, ql.Unadjusted,
                              self.day_count,
                              self.libor, ql.QuoteHandle(), ql.Period(0, ql.Days),
                              self.discount_curve)
            for rate, tenor in [
                (self.swaps.iloc[0, 1], 2),
                (self.swaps.iloc[1, 1], 3),
                (self.swaps.iloc[2, 1], 5),
                (self.swaps.iloc[3, 1], 10),
                (self.swaps.iloc[4, 1], 30)


            ]
        ]

        return helpers

    def build_spot_curve(self):
        spot_curve = ql.PiecewiseSplineCubicDiscount(self.holiday.adjust(self.today, ql.Following),
                             self.helpers,
                             self.day_count)

        spot_curve.enableExtrapolation()

        spots = []
        discount_factors = []
        tenors = []
        for d in spot_curve.dates():
            yrs = self.day_count.yearFraction(self.today, d)
            compounding = ql.Compounded
            freq = ql.Semiannual
            zero_rate = spot_curve.zeroRate(yrs, compounding, freq)
            discount_fs = spot_curve.discount(d)
            tenors.append(yrs)
            eq_rate = zero_rate.equivalentRate(self.day_count,
                                               compounding,
                                               freq,
                                               self.today,
                                               d).rate()
            spots.append(100 * eq_rate)
            discount_factors.append(discount_fs)


        datec = spot_curve.dates()
        curve_dates = []
        for c in datec:
            curve_dates.append(ql_to_datetime(c))

        chart = pd.DataFrame(list(zip(tenors, curve_dates, spots, discount_factors)), columns=['YearFrac', 'Date', 'Zero', 'Discount Factor'])
        print(chart)
        return chart

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


# a = Curve()
# b = Curve("GBP")
# c = Curve("EUR", "LIBOR", "3M")
# d = Curve("EUR", "LIBOR",)
#
# print(a.contents(), b.contents(), c.contents(), d.contents())
# a.OISRateHelper()
# a.build_from_ois()

# chart = a.build_spot_curve()
# print(chart)
# print(chart.info())

e = Curve("USD", "LIBOR", "6M")
e.build_spot_curve()

