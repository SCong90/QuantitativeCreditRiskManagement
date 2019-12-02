import os

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

import warning

from tools import *

def smp_valid_check(path, output, size_c = 1000):
    """
    check the validality of samples based on feature coverage
    """
    rlts = []
    with open(path, 'r') as f:
        rlts = [re.sub(r'[_ \t,| ]', ' ', a).split(' ').count('') for a in f.readlines()[1:]]
        f.close()

    df = pd.DataFrame([list(range(len(rlts))), rlts], index = ['line', 'mis_cnt']).T
    df.to_csv(output+'/smp_valid_check.csv')

    return df

def badSmpRm(path, output, alist):
    """
    delete invalid bad samples
    """
    line_cnt = -1
    with open(path, 'r') as f:
        with open(output, 'w') as w:
            for i in f.readlines():
                line_cnt += 1
                if line_cnt in alist:
                    continue
                else:
                    w.write(i)
            w.close()
        f.close()

def ft_type_check(path, output, header = True, size_c = 1000):
    """
    检查样本特征种类
    """
    fsize = os.path.getsize(pth)/1024**2
    if fsize > size_c:
        warnings.warn('sample data is used to assess data type')
        rlts = []
        with open(path, 'r') as f:
            txt = [re.sub(r'[_ \t,| ]', ' ', a).split(' ') for a in f.readlines()[:2000+np.int(header)]]
            f.close()

        hds = txt[0]
        vls = txt[1:]
        all_data = pd.DataFrame(vls, columns = hds)
    else:
        if header:
            all_data = pd.read_csv(path, sep = r'[_ \t,| ]', header = 0, dtype = 'str')
        else:
            all_data = pd.read_csv(path, sep = r'[_ \t,| ]', dtype = 'str')

    if len(all_data.shape[2]) == 1:
        warnings.warn("invalid parser probably"))
    hds = list(all_data.columns.values)

    rlts = {}
    for i in hds:
        try:
            tmp = all_data[i].apply(np.int)
            rlts[i] = {'type':'int', 'dist':len(all_data[i].unique())}
        except:
            try:
                tmp = all_data[i].apply(np.float)
                rlts[i] = {'type':'float', 'dist':len(all_data)}
            except:
                rlts[i] = {'type':'str', 'dist':len(all_data[i].unique())}

    if fsize > size_c:
        nm = 'type_info_sample.json'
    else:
        nm = 'typ_info.json'

    putFile(output, nm, rlts)

    return rlts

#缺失及分布情况初步统计
def ft_mis_check(df, tp):
    """
    计算缺失值及简单的分布情况
    """
    def sml_func(s, i):
        try:
            return s.index[i]
        except:
            return None
    ft_name = df.columns.values[0]

    if len(df[ft_name].dropna())

    if tp == 'int':
        vl_check[i] = {'type': 'int', 'mis_rate':1-df[ft_name].isna().mean(), '0': (df[ft_name]==0).mean(), '1': (df[i]==1).mean()}
    elif tp == 'str':
        tmp = df[ft_name].value_counts()
        vl_check[i] = {'type': 'str', 'mis_rate':1-df[i].isna().mean(), sml_func(tmp, 0):sml_func(tmp, 0)/len(df[i]), sml_func(tmp, 1):sml_func(tmp, 1)/len(df[i])}
    else:
        #tgt = df[ft_name].dropna()
        bins = [df[ft_name].min() + i * np.float((df[ft_name].max()-df[ft_name].min()))/grps] + [df[ft_name].max()+1]
        tgt = pd.cut(df[ft_name], bins = bins).value_counts()
        vl_check[i] = {'type': 'float', 'mis_rate':1-df[i].isna().mean(), sml_func(tmp, 0):sml_func(tmp, 0)/len(df[i]), sml_func(tmp, 1):sml_func(tmp, 1)/len(df[i])}

    return vl_check

def ft_corr(df):
    """
    计算相关性
    """
    return df.corr()

def psi_cal_func(df1, df2, grps = 10):
    """
    计算PSI
    """
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
    """
    计算单因子T值：
    ifconst:控制是否添加常数项
    """
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
    """
    计算KS值
    """
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
    stat['bad_cumsum_pct'] = stat['bad_cumsum']/df['label'].sum()
    stat['good_cumsum_pct'] = stat['good_cumsum']/(len(df)-df['label'].sum())

    stat['ks'] = stat['bad_cumsum_pct'] - stat['good_cumsum_pct']
    return stat
