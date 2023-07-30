import numpy as np
import pandas as pd
from bs4 import BeautifulSoup as bs
import requests as rq
import json as js
import re
from difflib import SequenceMatcher
import datetime

def lambda_handler(event, context):
    global output

    jobs = protocolit('https://theprotocol.it/filtry/1;s?', 50)
    output = output(jobs)

    return output

def protocolit(url, pages):
    add_divs = []
    for i in range(pages):
        request = rq.get(url + 'pageNumber={}'.format(i+1))
        soup = bs(request.content, 'html.parser')

        divs = soup.find_all('a', {'class': 'anchorClass_a6of9et'})
        add_divs.append(divs)
    
    jobs = []

    for i in range(pages):
        for d in add_divs[i]:
            title = d.find_all('h2', {'data-test': 'text-jobTitle'})
            t_list = []
            for t in title:
                t = t.text
                t_list.append(t)
            salary = d.find_all('span', {'class': 'boldText_b1wsb650'})
            s_list = []
            for s in salary:
                s = s.text
                s_list.append(s)
            contract_type = d.find_all('span', {'class': 'mainText_m15w0023'})
            c_list = []
            for c in contract_type:
                c = c.text
                c_list.append(c)
            jobs.append([t_list, s_list, c_list])

    jobs = pd.DataFrame(jobs, columns=['title', 'salary', 'contract'])

    jobs['title'] = jobs['title'].astype(str).str[2:-2]
    jobs['title'] = jobs['title'].replace('', np.nan)
    jobs = jobs.dropna(subset=['title'])

    jobs[['salary_1', 'salary_2']] = jobs['salary'].astype(str).str[2:-2].str.split(',', expand=True)
    jobs['salary_1'] = jobs['salary_1'].astype(str).str.replace("'", "")
    jobs['salary_2'] = jobs['salary_2'].astype(str).str.replace("'", "")
    jobs['salary_2'] = jobs['salary_2'].replace('None', np.nan)

    jobs[['contract_1', 'contract_2']] = jobs['contract'].astype(str).str[2:-2].str.split(',', expand=True)[[0, 3]]
    for i in ['contract_1', 'contract_2']:
        jobs[i] = jobs[i].astype(str).str.extract(r'\((.*?)\)').replace('UoP', 'CoE')
    jobs['salary_coe'] = np.where(jobs['contract_1'] == 'CoE', jobs['salary_1'], np.where(jobs['contract_2'] == 'CoE', jobs['salary_2'], np.nan))

    jobs[['salary_coe_min', 'salary_coe_max']] = jobs['salary_coe'].astype(str).str.split('–', expand=True)[[0, 1]]
    for i in ['salary_coe_min', 'salary_coe_max']:
        jobs[i] = jobs[i].replace('None', np.nan)
        jobs[i] = jobs[i].astype(str).str.replace('k', '')
        jobs[i] = jobs[i].replace('None', np.nan)
        jobs[i] = jobs[i].astype(float)*1000

    jobs = jobs.drop(columns=['salary', 'contract', 'salary_1', 'salary_2', 'contract_1', 'contract_2', 'salary_coe']).dropna()
    return jobs

def similar(a, b):
    a = a.lower()
    b = b.lower()

    a = re.sub(r'\b(senior|junior|mid|remote|młodszy|młodsza)\b', '', a)
    b = re.sub(r'\b(senior|junior|mid|remote|młodszy|młodsza)\b', '', b)
    
    return SequenceMatcher(None, a, b).ratio()

def output(df):
    df['title'] = df['title'].str.lower()
    df['title'] = np.where(df['title'] == 'programista .net', '.net developer', df['title'])
    df['title'] = np.where(df['title'] == 'front-end developer', 'frontend developer', df['title'])
    df['title'] = np.where(df['title'] == 'analityk biznesowy', 'business analyst', df['title'])
    df['title'] = np.where(df['title'] == 'analityk danych', 'data analyst', df['title'])
    df['title'] = np.where(df['title'] == 'analityk', 'analyst', df['title'])
    df['title'] = np.where(df['title'].str.contains('analityk danych'), 'data analyst', df['title'])
    df['title'] = np.where(df['title'].str.contains('analityk biznesowy'), 'business analyst', df['title'])
    df['title'] = np.where(df['title'].str.contains('analityk it'), 'it analyst', df['title'])
    df['title'] = df['title'].str.replace('back-end', 'backend')
    df['title'] = df['title'].str.replace('front-end', 'backend')
    df['title'] = df['title'].str.replace('user interface', 'ui')
    df['title'] = df['title'].str.replace('user interface', 'ux')

    titles = [re.sub(r'\b(senior|junior|mid|remote|młodszy|młodsza)\b', '', title) for title in df['title'].tolist()]
    titles = [title.strip() for title in titles]
    titles = pd.Series(titles).value_counts()

    for i in titles[:10].index:
        df[i] = df['title'].apply(lambda x: 1 if similar(x, i) > 0.9 else 0)

    salaries = []
    for n in titles[:10].index:
        s = pd.concat([df['salary_coe_min'].loc[df[n]==1], df['salary_coe_max'].loc[df[n]==1]])
        d = s.describe()
        min, mid, max = d['25%'], d['50%'], d['75%']
        salaries.append([n, min, mid, max])

    salaries = pd.DataFrame(salaries, columns=['title', 'min', 'mid', 'max']).sort_values(by='title', ascending=True).reset_index(drop=True)
    salaries['id'] = salaries.index + 1
    salaries['date'] = datetime.datetime.now().strftime("%Y.%m.%d")
    salaries = salaries.to_dict(orient='records')

    return salaries