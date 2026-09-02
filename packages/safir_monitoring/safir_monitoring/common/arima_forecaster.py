"""ARIMA tabanli kapasite tahmin modulu.

pmdarima (auto_arima) kullanarak zaman serisi tahmini yapar.
Prophet'e gore daha hizli calisir.
"""

import numpy as np
import pandas as pd
from pmdarima import auto_arima

from safir_monitoring.common.base_forecaster import BaseForecaster


class ArimaForecaster(BaseForecaster):
    """Auto-ARIMA tabanli kapasite tahmin sinifi."""

    ALGORITHM_NAME = "arima"

    def _fit_and_predict(self):
        """Auto-ARIMA model fit ve predict.

        Prophet ile ayni formatta forecast DataFrame uretir:
        columns: [ds, yhat, yhat_upper, yhat_lower, trend]
        """
        y = self.df['y'].values

        # Auto-ARIMA: en iyi (p,d,q) parametrelerini otomatik bulur
        try:
            self.model = auto_arima(
                y,
                seasonal=True,
                m=7,  # Haftalik seasonality
                suppress_warnings=True,
                error_action='ignore',
                stepwise=True,
                max_p=3, max_q=3, max_d=2,
            )
        except ValueError:
            # Seasonal model basarisiz olursa non-seasonal dene
            self.model = auto_arima(
                y,
                seasonal=False,
                suppress_warnings=True,
                error_action='ignore',
                stepwise=True,
                max_p=3, max_q=3, max_d=2,
            )

        # Gelecek tahminleri
        forecast_values, conf_int = self.model.predict(
            n_periods=self.future_days, return_conf_int=True, alpha=0.2
        )

        # Fitted values (gecmis icin)
        fitted_values = self.model.predict_in_sample()

        # Trend: basit moving average ile trend cikar
        window = min(7, len(y))
        trend_hist = pd.Series(y).rolling(window=window, center=True, min_periods=1).mean().values
        trend_future = pd.Series(forecast_values).rolling(window=min(7, len(forecast_values)), center=True, min_periods=1).mean().values

        # Gecmis icin confidence interval (fitted +/- residual std)
        residuals = y - fitted_values[:len(y)]
        residual_std = float(np.std(residuals)) if len(residuals) > 1 else 0

        # Historical DataFrame
        hist_dates = self.df['ds'].values
        hist_df = pd.DataFrame({
            'ds': hist_dates,
            'yhat': fitted_values[:len(y)],
            'yhat_upper': fitted_values[:len(y)] + residual_std,
            'yhat_lower': fitted_values[:len(y)] - residual_std,
            'trend': trend_hist,
        })

        # Future DataFrame
        last_date = self.df['ds'].iloc[-1]
        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=self.future_days, freq='D'
        )
        future_df = pd.DataFrame({
            'ds': future_dates,
            'yhat': forecast_values,
            'yhat_upper': conf_int[:, 1],
            'yhat_lower': conf_int[:, 0],
            'trend': trend_future,
        })

        self.forecast = pd.concat([hist_df, future_df], ignore_index=True)
        self.historical = self.forecast.iloc[:len(self.df)]
        self.future = self.forecast.iloc[len(self.df):]
