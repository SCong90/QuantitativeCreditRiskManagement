import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
import json
from scipy import stats

from dateutil.parser import parse
from pandas.tseries.offsets import MonthBegin, Day, MonthEnd
import statsmodels.api as sm
import tqdm

import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_validation
from sklearn.tree import DecisionTreeClassifier
from sklearn import metrics
from sklearn.model_selection import GridSearchCV
from sklearn.externals import joblib
from sklearn import preprocesssing


def mis_check(df):
    ft_name = df.columns.values[0]

    mis = len(df.dropna())/np.float(len(df))
    df['type'] = df[ft_name].apply(lambda x: isinstance(eval(x), int))

    if df['type'].mean() == 1.0:
        v1 = len(df[df[ft_name].apply(eval)==1])/np.float(len(df))
        v2 = len(df[df[ft_name].apply(eval)==1])/np.float(len(df))
        return {'missing':mis, 'value1_pct':v1, 'value2_pct':v2}
    else:
        return {'missing':mis, 'value1_pct':np.nan, 'value2_pct':np.nan}

def psi_cal_func(df1, df2, grps = 10):
    ft_name = df1.columns.values[0]

    min_v = min(df1[ft_name].min(), df2[ft_name].min())
    max_v = max(df1[ft_name].max(), df2[ft_name].max())


    step = (max_v - min_v)/grps
    cuts = [min_v + step * a for a in range(grps)]+[max_v+1]

    df1['cuts'] = pd.cut(df1[ft_name], bins = cuts, right = True)
    df2['cuts'] = pd.cut(df2[ft_name], bins = cuts, right = True)
    df1_s = df1.groupby('cuts', as_index = True).count()/np.float(len(df1))
    df1_s.columns = ['b_stat']
    df2_s = df2.groupby('cuts', as_index = True).count()/np.float(len(df2))
    df2_s.columns = ['a_stat']

    df = pd.merge(left = df1_s, right = df2_s, right_index = True, left_index = True, how = 'outer')
    df['psi'] = (df['b_stat']-df['a_stat'])*np.log((df['b_stat']/df['a_stat']))

    return df['psi'].sum()

def tvalue_cal_func(df, ifconst = True):
    ft_name, _ = df.columns.value
    #但因子检验的时候不考虑空值
    df = df.dropna()

    y = df['label']
    x = df[[ft_name]]
    if ifconst:
        x = sm.add_constant(x)

    model = sm.Logit(y, x).fit()
    return model.tvalues[ft_name]

def ks_cal_func(df, grps=10, ascd = False):
    ft_name, _ = df.columns.values
    #单因子统计的时候不需要考虑缺失情况
    df = df.dropna()

    df.sort_values(by = ft_name, ascending = ascd, inplace = True)
    df['grps'] = pd.qcut(df[ft_name], q = grps, labels = list(range(grps)))

    stat = df.groupby('grps', as_index = False).agg({ft_name:['min', 'max'], 'label':{'count', 'sum'}})
    stat.columns = ['grps', 'min_ft', 'max_ft', 'size', 'bad_cnt']
    stat.sort_values('grps', ascending = False, inplace = True)

    stat['good_cnt'] = stat['size'] - stat['bad_cnt']
    stat['good_cumsum'] = stat['good_cnt'].cumsum()
    stat['bad_cumsum'] = stat['bad'].cumsum()

    stat['bad_pct'] = stat['bad_cnt']/stat['size']
    stat['good_cumsum_pct'] = stat['good_cumsum']/df['label'].sum()
    stat['bad_cumsum_pct'] = stat['bad_cumsum']/(len(df)-df['label'].sum())

    stat['ks'] = stat['bad_cumsum_pct'] - stat['good_cumsum_pct']
    return stat

def ks_cal_func():
    