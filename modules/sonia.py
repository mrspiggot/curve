import requests
import QuantLib as ql
import datetime as dt
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd

SONIA_OBSERVATION_SHIFT = 5

def ql_to_datetime(d):
    return dt.date(d.year(), d.month(), d.dayOfMonth())

def datetime_to_ql(d):
    return ql.Date(d.day, d.month, d.year)

class Sonia:
    def __init__(self):
        self.today = dt.date.today()
        self.term_start = self.today - timedelta(days=(366+SONIA_OBSERVATION_SHIFT))
        self.calendar = ql.UnitedKingdom()

        self.sonia_on = self.get_boe_overnight_sonia_quotes()
        self.sonia_1m = self.get_term_sonia(1)
        self.sonia_3m = self.get_term_sonia(3)
        self.sonia_6m = self.get_term_sonia(6)


    def get_boe_overnight_sonia_quotes(self):
        quote_start = self.today - timedelta(days=730)
        web_string = f'https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?Travel=NIxSUx&FromSeries=1&ToSeries=50&DAT=RNG&FD={quote_start.day}&FM={quote_start.strftime("%b")}&FY={quote_start.year}&TD={self.today.day}&TM={self.today.strftime("%b")}&TY={self.today.year}&FNY=&CSVF=TT&html.x=262&html.y=37&C=5JK&Filter=N'
        url = requests.get(web_string)
        tabs = pd.read_html(url.text)
        sonia = tabs[0]
        sonia['Date'] = pd.to_datetime(sonia['Date'], format='%d %b %y')
        sonia.rename(columns={'Date': 'Date', 'Daily Sterling overnight index average (SONIA) rate  IUDSOIA': 'Rate'},
                     inplace=True)
        return sonia

    def get_term_sonia(self, months):
        startDate = ql.Date(self.term_start.day, self.term_start.month, self.term_start.year)
        terminationDate = ql.Date(self.today.day, self.today.month, self.today.year)
        frequency = ql.Period('1D')
        convention = ql.Following
        terminationDateConvention = ql.ModifiedFollowing
        rule = ql.DateGeneration.Backward
        endOfMonth = False
        schedule = ql.Schedule(startDate, terminationDate, frequency, self.calendar, convention, terminationDateConvention,
                               rule, endOfMonth)

        list_start = []
        list_end = []
        for d_end in schedule:
            e_date = ql_to_datetime(d_end)
            s_date = e_date - relativedelta(months=months)
            d_start = self.calendar.adjust(datetime_to_ql(s_date), ql.Preceding)

            list_start.append(s_date)
            list_end.append(e_date)

        term_dict = dict(zip(list_start, list_end))

        sonia_term = {}
        for start, end in term_dict.items():
            sonia_schedule = ql.Schedule(datetime_to_ql(start), datetime_to_ql(end), frequency, self.calendar, convention,
                                         terminationDateConvention, ql.DateGeneration.Backward, endOfMonth)
            sonia_term[end] = [sonia_schedule, (end - start).days]

        date_list = []
        rate_list = []
        for d, schedule in sonia_term.items():
            i = 0
            index_total = 1.0
            for period in schedule[0]:
                if i == 0:
                    son_start = period
                    i = 1
                else:
                    term = period - son_start
                    fixing_date = ql_to_datetime(self.calendar.adjust(
                        datetime_to_ql(ql_to_datetime(son_start) - timedelta(days=SONIA_OBSERVATION_SHIFT)),
                        ql.Preceding))
                    sonia_on = self.sonia_on['Rate'][self.sonia_on['Date'].dt.date == fixing_date].to_numpy()[0] / 100
                    fi = 1 + (sonia_on * term) / 365
                    index_total = index_total * (fi)

                    son_start = period
            r = (365 / schedule[1]) * (index_total - 1) * 100

            date_list.append(d)
            rate_list.append(r)

        quotes = list(zip(date_list, rate_list))
        df = pd.DataFrame(quotes, columns=['Date', 'Rate'])
        df['Date'] = df['Date'].astype('datetime64')
        return df

    def get_sonia_1m(self, quote_date):
        try:
            quote =  self.sonia_1m['Rate'][self.sonia_1m['Date'].dt.date == quote_date].to_numpy()[0] / 100
        except Exception as e:
            d = ql_to_datetime(self.calendar.adjust(datetime_to_ql(quote_date), ql.Preceding))
            quote = self.sonia_1m['Rate'][self.sonia_1m['Date'].dt.date == d].to_numpy()[0] / 100
            print(f"No overnight rate published on {quote_date}, supplying quote from {d}. {e}")
        return quote

    def get_sonia_3m(self, quote_date):
        try:
            quote =  self.sonia_3m['Rate'][self.sonia_3m['Date'].dt.date == quote_date].to_numpy()[0] / 100
        except Exception as e:
            d = ql_to_datetime(self.calendar.adjust(datetime_to_ql(quote_date), ql.Preceding))
            quote = self.sonia_3m['Rate'][self.sonia_3m['Date'].dt.date == d].to_numpy()[0] / 100
            print(f"No overnight rate published on {quote_date}, supplying quote from {d}. {e}")
        return quote

    def get_sonia_6m(self, quote_date):
        try:
            quote =  self.sonia_6m['Rate'][self.sonia_6m['Date'].dt.date == quote_date].to_numpy()[0] / 100
        except Exception as e:
            d = ql_to_datetime(self.calendar.adjust(datetime_to_ql(quote_date), ql.Preceding))
            quote = self.sonia_6m['Rate'][self.sonia_6m['Date'].dt.date == d].to_numpy()[0] / 100
            print(f"No overnight rate published on {quote_date}, supplying quote from {d}. {e}")
        return quote

son = Sonia()
print(son.sonia_1m)
quote_date = dt.date(2021,7,11)
print(son.get_sonia_1m(quote_date))
print(son.get_sonia_3m(quote_date))
print(son.get_sonia_6m(quote_date))

