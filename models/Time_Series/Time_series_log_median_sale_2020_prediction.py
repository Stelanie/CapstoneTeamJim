# -*- coding: utf-8 -*-
"""
Created on Wed Mar 16 09:43:45 2022

@author: melan
"""


# import secrets_melanie
import os
from datetime import datetime
import pickle

import pandas as pd
import numpy as np
from config import definitions
root_dir = definitions.root_directory()




from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.stattools import grangercausalitytests

from statsmodels.tsa.api import VAR

from  sklearn.metrics import mean_squared_error, r2_score



import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio
# render plot in default browser
pio.renderers.default = 'browser'


from urllib.request import urlopen
import json

pd.set_option('display.max_columns',None)

now = datetime.now()
now = now.strftime("%d%b%Y_%Hh%M")



#%%
def time_series_2020():
    df=pd.read_pickle(os.path.join(root_dir,"CapstoneTeamJim","data","processed","data_log_2016_2021_VARcountysubset.pkl"))
    
    county_name = df[['county_fips','region']].drop_duplicates()
    df_pivot = df.pivot(index='date',columns='county_fips',values='log_median_sale_price')
    
    # forecast 2020: need data up to 2019
    df_time = df[((df['year']>='2016')&(df['year']<'2020'))]
    df_time_log = df_time.pivot(index='date',columns='county_fips',values='log_median_sale_price')
    
    
    
    # def adfuller_func(dataframe):
    #     res = []
    #     for col in list(dataframe.columns):
    #         r = adfuller(dataframe[col], autolag='AIC')
    #         res.append(round(r[1],3))
    #     return res
    
    
    # check stationarity with ad fuller testing - no differencing
    # no_diff = adfuller_func(df_time_log)
    # adf = pd.DataFrame(data=[no_diff],columns=list(df_time_log.columns))
    # adf = adf.melt()
    # adf.columns=['county_fips','no_diff_p']
    # adf[adf['no_diff_p']<0.05].count()
    # 451/1393 are stationary
    
    # check stationarity with ad fuller testing - first differencing
    df_time_diff_log = df_time_log.diff().dropna()
    # first_diff = adfuller_func(df_time_diff_log)
    # adf['first_diff_p'] = first_diff 
    # adf[adf['first_diff_p']<0.05].count()
    # 1348/1393 are stationary
    
    df_time_2diff_log = df_time_diff_log.diff().dropna()
    # sec_diff = adfuller_func(df_time_2diff_log)
    # adf['sec_diff_p'] = sec_diff 
    # adf[adf['sec_diff_p']<0.05].count()
    # 1390/1393 are stationary
    
   
    
    #### FORECAST 2020 
    p=12
    
    num_forecasts = 12
    var_res, forecasts = None, None
    # df_time_2diff = df_time_2diff+0.000000001
    
    # using second differencing
    model = VAR(df_time_2diff_log,freq='MS')
    
    
    var_res = model.fit(maxlags=p)

    forecasts = var_res.forecast(df_time_2diff_log.values,steps=num_forecasts)
    
    #set index for new forecast df
    dfindex = pd.date_range(start=df_time_log.index[-1],periods = num_forecasts+1, freq='MS')[1:]
    
    # first undifference
    lastvals_second_diff = df_time_log.diff()[-1:]
    for_df = pd.DataFrame(data = forecasts,columns= df_time_log.columns, index = dfindex)
    for_df = pd.concat([lastvals_second_diff, for_df],axis=0,ignore_index=False).cumsum()[1:]
    # second undifference
    lastvals_first_diff = df_time_log[-1:]
    for_df = pd.concat([lastvals_first_diff, for_df],axis=0,ignore_index=False).cumsum()[1:]
    
    
    
    
    ###  TESTING USING HOLDOUT 2020 DATA
    df2020 = df[df['year']=='2020']
    
    
    pred = pd.melt(for_df.reset_index(),id_vars='index',value_name = 'Pred_log_median_sale_price')
    pred.columns=['date','county_fips','Pred_log_median_sale_price']
    pred = pred.merge(df2020, on=['county_fips','date'])
    # calculate the log_errors
    pred['log_pred_errors'] = pred['log_median_sale_price']-pred['Pred_log_median_sale_price']
    
    pred.to_csv(os.path.join(root_dir,"CapstoneTeamJim","reports","results","Time_Series","Data_hist_scatter_2020Predictions.csv"),index=False)
    
    hist = px.histogram(pred['log_pred_errors'],title='Histogram of residual error of model - appears normally distributed')
    hist.show()
    hist.write_image(os.path.join(root_dir,"CapstoneTeamJim","reports","figures","Time_Series","Hist_residual_error_model_testing_2020Pred.png"),width=1980, height=1080)
    
    
    ###  Plot residual errors  (still in log transform)
    # The residuals are uncorrelated. If there are correlations between residuals,
    #  then there is information left in the residuals which should be used in computing forecasts.
    # The residuals have zero mean. If the residuals have a mean other than zero, then the forecasts are biased.
    
    # https://www.qualtrics.com/support/stats-iq/analyses/regression-guides/interpreting-residual-plots-improve-regression/
    ## Keep - shows that errors 
    # (1) they’re pretty symmetrically distributed, tending to cluster towards the middle of the plot.
    # (2) they’re clustered around the lower single digits of the y-axis (e.g., 0.5 or 1.5, not 30 or 150).
    # (3) in general, there aren’t any clear patterns.
    pred_errors = px.scatter(pred,x='log_median_sale_price',y='log_pred_errors', title='Residual error clustered around middle of plot with tight range and no clear patterns')
    pred_errors.show()
    pred_errors.write_image(os.path.join(root_dir,"CapstoneTeamJim","reports","figures","Time_Series","Scatter_residual_error_model_testing_2020Pred.png"),width=1980, height=1080)
    
    ###   Transform log predictions to original units
    
    # https://stats.stackexchange.com/questions/55692/back-transformation-of-an-mlr-model
    
    # calculate the mean transformed error by county
    pred['pred_errors_trans'] = np.exp(pred['log_pred_errors'])
    mean_transformed_error = pred.groupby('county_fips')['pred_errors_trans'].mean().reset_index(name='Mean_pred_error_trans')
    
    # transform predicted median sale price back to dollars
    pred['pred_med_sale_trans_biased'] = np.exp(pred['Pred_log_median_sale_price'])
    pred = pred.merge(mean_transformed_error,on='county_fips')
    pred['pred_med_sale_trans']  = pred['pred_med_sale_trans_biased']*pred['Mean_pred_error_trans']
    
    
    # Prediction by county for 2020
    county_mean_pred2020 = pred.groupby('county_fips')['pred_med_sale_trans'].mean().reset_index(name='Predicted_mean_2020')
    county_mean = pred.groupby('county_fips')['median_sale_price'].mean().reset_index(name='County_mean')
    Predictions2020 = county_mean_pred2020.merge(county_mean,on='county_fips')
    # add county name for map
    Predictions2020 = Predictions2020.merge(county_name,on='county_fips')
    Predictions2020['error'] = Predictions2020['County_mean']-Predictions2020['Predicted_mean_2020']
    Predictions2020['error_pct'] = np.absolute(Predictions2020['error'])/Predictions2020['County_mean']*100
    
    # import counties only in ACS dataset for comparison to other models
    acs_counties = pd.read_csv(os.path.join(root_dir,"CapstoneTeamJim","data","processed","VAR_ACS_counties.txt"), dtype='str')
    acs_counties['county_fips'] = acs_counties['county_fips'].astype(str)
        
    # Filter for counties only in ACS
    Predictions2020 = Predictions2020[Predictions2020['county_fips'].isin(acs_counties['county_fips'])]
    
    
    
    rmse_calc = mean_squared_error(Predictions2020['County_mean'], Predictions2020['Predicted_mean_2020'],squared=False) 
    rmse_calc = ("${:,.0f}".format(rmse_calc))
    # $807
    # https://scikit-learn.org/stable/modules/generated/sklearn.metrics.r2_score.html
    r2_calc = r2_score(Predictions2020['County_mean'], Predictions2020['Predicted_mean_2020']).round(5) 
    # 0.9999723762765845
    
    rmse_df = pd.DataFrame(data = [[rmse_calc,r2_calc]], columns = ['RMSE','R^2 Score'])
    rmse_df.to_csv(os.path.join(root_dir,"CapstoneTeamJim","reports","results","Time_Series","rmse_time_2020.csv"),index=False)
    
    
    MSE_r2 = go.Figure(data=[go.Table(
        header=dict(values=['RMSE','R^2 Score'],
                line_color='darkslategray',
                fill_color='#3366CC',
                align=['center','center'],
                font=dict(color='white', size=20),
                height=40),
        cells=dict(values=[rmse_df['RMSE'], rmse_df['R^2 Score']],
                line_color='darkslategray',
                fill=dict(color=['white', 'white']),
                align=['center', 'center'],
                font_size=18,
                height=30)
                      )])
        
    MSE_r2.update_layout(title_text = "Model error for 2020 Predictions",width=500, height=300)
    MSE_r2.show()
    MSE_r2.write_image(os.path.join(root_dir,"CapstoneTeamJim","reports","figures","Time_Series","Table_Time_series_model_error_2020_predictions.png"),width=500, height=300)
    
    
    
    
    # Adding 2020 predictions back onto main dataset to compare price change from 2019
    # mean_transformed_error = mean_transformed_error.pivot_table(columns = 'county_fips')
    # mean_transformed_error = mean_transformed_error.set_index('county_fips')
    pred2020 = pd.concat([df_time_log, for_df],axis=0,ignore_index=False)
    pred_long = pd.melt(pred2020.reset_index(),id_vars='index',value_name = 'Pred_log_median_sale_price')
    pred_long.columns = ['date','county_fips','log_median_sale_price']
    pred_long['year'] = pred_long['date'].dt.year
    # merge 2021 transformed error onto df
    pred_long = pred_long.merge(mean_transformed_error,on=['county_fips'] )
    # set error for years previous to 2022 = 1
    pred_long['Mean_pred_error_trans'][pred_long['year']!=2020]=1
    # Transform log median price to orignal dollars
    pred_long['Med_price_trans_biased'] = np.exp(pred_long['log_median_sale_price'])
    # multiply median price by error term
    pred_long['Mean_pred_price_trans'] = pred_long['Med_price_trans_biased'] * pred_long['Mean_pred_error_trans']
    
    prediction_std = pred_long[pred_long['year']==2020].groupby('county_fips')['Mean_pred_price_trans'].std().reset_index(name='Predicted_med_price_std')
    
    # # group by county and year to get average median sale price 
    Predictions_by_county = pred_long.groupby(['county_fips','year'])['Mean_pred_price_trans'].mean().reset_index(name='Mean_median_sale_price')
    # # calculate the difference from 2022 to 2021
    Predictions_by_county['Mean_pred_price_diff'] = Predictions_by_county.groupby('county_fips')['Mean_median_sale_price'].transform(lambda v: v.diff()).shift(-1)
    # # add county name for map
    Predictions_by_county = Predictions_by_county.merge(county_name,on='county_fips')
    # Filter for counties only in ACS
    Predictions_by_county = Predictions_by_county[Predictions_by_county['county_fips'].isin(acs_counties['county_fips'])]
    
    # # calculation the % change from 2019
    Predictions_by_county['Mean_pred_price_pct'] = Predictions_by_county['Mean_pred_price_diff']/Predictions_by_county['Mean_median_sale_price']*100
    Top_counties = Predictions_by_county[Predictions_by_county['year']==2019].sort_values(by=['Mean_pred_price_pct'],ascending=False)
    
    Predictions2020_ = Predictions_by_county[Predictions_by_county['year']==2020][['county_fips','region','Mean_median_sale_price']]
    Predictions2020_.columns = ['county_fips','region','Pred_mean_med_sale_price_2020']
    summary2020prediction = Top_counties.merge(Predictions2020_,how='left',on=['county_fips','region']).drop(columns=['year'])
    # summary2022prediction = summary2022prediction.merge(Predictions2021,how='left',on=['county_fips','region']).drop(columns=['County_mean'])
    summary2020prediction.columns = ['county_fips','Mean_med_sale_price_2019','Mean_pred_price_yoy','county','Mean_pred_price_pct_yoy','Pred_mean_med_sale_price_2020']
    
    summary2020prediction = summary2020prediction.merge(prediction_std,how='left',on=['county_fips'])
    summary2020prediction['lower_95'] = summary2020prediction['Pred_mean_med_sale_price_2020']-(summary2020prediction['Predicted_med_price_std']*1.96)
    summary2020prediction['upper_95'] = summary2020prediction['Pred_mean_med_sale_price_2020']+(summary2020prediction['Predicted_med_price_std']*1.96)
    summary2020prediction = summary2020prediction[['county_fips','county','Mean_med_sale_price_2019','Pred_mean_med_sale_price_2020','lower_95','upper_95','Mean_pred_price_yoy','Mean_pred_price_pct_yoy']]
    summary2020prediction['Mean_med_sale_price_2019'] = summary2020prediction['Mean_med_sale_price_2019'].map("${:,.0f}".format)
    summary2020prediction['Pred_mean_med_sale_price_2020'] = summary2020prediction['Pred_mean_med_sale_price_2020'].map("${:,.0f}".format)
    summary2020prediction['lower_95'] = summary2020prediction['lower_95'].map("${:,.0f}".format)
    summary2020prediction['upper_95'] = summary2020prediction['upper_95'].map("${:,.0f}".format)
    summary2020prediction['Mean_pred_price_yoy'] = summary2020prediction['Mean_pred_price_yoy'].map("${:,.0f}".format)
    summary2020prediction['Mean_pred_price_pct_yoy'] = summary2020prediction['Mean_pred_price_pct_yoy'].round(2)
    summary2020prediction = summary2020prediction.sort_values(by='Mean_pred_price_pct_yoy',ascending=False)
    
    summary2020prediction.columns = ['FIPS','County','Median Sale Price 2019','Predicted Median Sale Price 2020','Lower 95% Prediction Inverval','Upper 95% Prediction Inverval','Median Sale Price increase','Median Sale Price % increase']
    
    summary2020prediction.to_csv(os.path.join(root_dir,"CapstoneTeamJim","reports","results","Time_Series","Summary_2020_Predictions.csv"),index=False)
    
    
    
    with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
        counties = json.load(response)
        
        
    forecasted_pct = px.choropleth(summary2020prediction, geojson=counties, locations='FIPS', color='Median Sale Price % increase',
                               color_continuous_scale="Viridis",
                                # range_color=(0, 100),
                               hover_name = 'County',
                               hover_data =['Predicted Median Sale Price 2020','Lower 95% Prediction Inverval','Upper 95% Prediction Inverval'],
                               scope="usa",
                               labels={'Mean_pred_price_pct':'% price change from 2019'},
                               title='All 613 ACS counties - 2020 average Median Sale Price % increase over 2019'
                              )
    
    forecasted_pct.show()
    forecasted_pct.write_image(os.path.join(root_dir,"CapstoneTeamJim","reports","figures","Time_Series","Choro_all_ACS_counties_pred_2020Pred.png"),width=1980, height=1080)
        
    top_cnt = px.choropleth(summary2020prediction[0:10], geojson=counties, locations='FIPS', color='Median Sale Price % increase',
                               color_continuous_scale="Viridis",
                                # range_color=(0, 100),
                               hover_name = 'County',
                               hover_data =['Predicted Median Sale Price 2020','Lower 95% Prediction Inverval','Upper 95% Prediction Inverval'],
                               scope="usa",
                               labels={'Mean_pred_price_pct':'% price change from 2019'},
                               title='Top 10 ACS counties - 2020 average Median Sale Price % increase over 2019'
                              )
    # fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    top_cnt.show()
    top_cnt.write_image(os.path.join(root_dir,"CapstoneTeamJim","reports","figures","Time_Series","Choro_top10_ACS_counties_pred_2020Pred.png"),width=1980, height=1080)
    
    
    
    # Granger Causality checks
    # from tqdm import tqdm
    # df_gran_test = df.pivot(index='date',columns='county_fips',values='median_sale_price')
    # counties = list(df_gran_test.columns)
    # test = 'ssr_chi2test'
    # granger_df = pd.DataFrame(data=None, columns = counties, index = counties)
    
    # for i in tqdm(counties):
    #     for j in counties:
    #         if i!=j:
    #             test_result = grangercausalitytests(df_gran_test[[i, j]], maxlag=p, verbose=False)
    #             p_values = [round(test_result[i+1][0][test][1],4) for i in range(p)]
    #             min_p_value = np.min(p_values)
    #             granger_df.loc[i,j] = min_p_value
                
    # granger_df.astype(float)
    
    #Takes about 4.5 hours to run.  It can be seen that there are several series that have causality to other time series.
    
    
    
    
    with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
        counties = json.load(response)
        
    Predictions2020.columns = ['FIPS','Predicted Median Sale Price 2020','Median Sale Price 2020','County','Forecast error','Forecast error %']
    Predictions2020['Predicted Median Sale Price 2020'] = Predictions2020['Predicted Median Sale Price 2020'].map("${:,.0f}".format)
    Predictions2020['Forecast error %'] = Predictions2020['Forecast error %'].round(2)
    Predictions2020.to_csv(os.path.join(root_dir,"CapstoneTeamJim","reports","results","Time_Series","Prediction_error_2020.csv"),index=False)
    
    
    Pred2020_error = px.choropleth(Predictions2020, geojson=counties, locations='FIPS', color='Forecast error %',
                                color_continuous_scale="Viridis",
                                hover_name = 'County',
                                hover_data =['Predicted Median Sale Price 2020'],
                                scope="usa",
                                labels={'Forecast error %':'2020 % Forecast error'},
                                title = 'Average forecast error by ACS county for 2020 prediction, with most counties having less error than 5%'
                              )
    
    Pred2020_error.show()
    Pred2020_error.write_image(os.path.join(root_dir,"CapstoneTeamJim","reports","figures","Time_Series","Choro_average_pred_error_2020.png"),width=1980, height=1080)
    
if __name__ == "__main__":
    time_series_2020()



























