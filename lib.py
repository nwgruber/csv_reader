import pandas as pd
import numpy as np
import time
# datalogfile = 'G:/Cobb/Logs/datalog4.csv'

def read_datalog(filepath: str):
    """Opens a datalog csv file and returns a list of the datalog as a DataFrame followed by a string of the accessport info
    """
    f = open(filepath, 'r', encoding='Windows-1252')
    df = pd.read_csv(f)
    cols = list(df.columns)
    df = df.iloc[:, 0:(len(cols) - 1)]
    ap_info = cols[len(cols) - 1]
    f.close()
    return [df, ap_info]

def get_pulls(df: pd.DataFrame, min_throttle: float, time_filter: float):
    """Takes a DataFrame of a datalog and returns a list of DataFrames for each pull in the log

    Arguments:\n
    df : pd.DataFrame -- DataFrame of the datalog\n
    min_throttle : float -- identify pulls when throttle pos >= this value\n
    time_filter : float -- omit pulls whose duration <= than this number
    """
    # Aggregate by throttle pos and split by groups into list
    df['is pull'] = df['Throttle Pos (%)'] >= min_throttle
    df['g'] = df['is pull'].ne(df['is pull'].shift()).cumsum()
    df = df.loc[df['is pull'], :]
    pulls = df.groupby('g')
    pulls = [pulls.get_group(x) for x in pulls.groups]
    pulls = [x.reset_index(drop=True) for x in pulls]
    # Omit pulls whose length is less than time filter
    result = []
    for pull in pulls:
        startrow = pull.iloc[0]
        endrow = pull.iloc[-1]
        if (endrow['Time (sec)'] - startrow['Time (sec)']) > time_filter:
            result.append(pull)
    # Remove helper cols
    result = [x.drop(['is pull', 'g'], axis=1) for x in result]
    return result

def get_pull_info(pulls: list[pd.DataFrame]) -> dict:
    """Accepts a list of pull DataFrames and returns a dict
    """
    result = {}
    for i in range(len(pulls)):
        pull = pulls[i]
        startrow = pull.iloc[0]
        endrow = pull.iloc[-1]
        result[i + 1] = {
            'start': startrow['Time (sec)'],
            'duration': endrow['Time (sec)'] - startrow['Time (sec)']
        }
    return result

def time_test(df):
    start = time.time()
    pull_rows = np.where(df['Throttle Pos (%)'] >= 50, True, False)
    end = time.time()
    print(f'np.where: {end - start}')
    start = time.time()
    pull_rows2 = df['Throttle Pos (%)'] >= 50
    end = time.time()
    print(f'row operation: {end - start}')