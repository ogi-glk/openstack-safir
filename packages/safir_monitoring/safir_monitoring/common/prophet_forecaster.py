"""Prophet tabanli kapasite tahmin modulu.

monasca-api ProphetForecaster sinifinin Thanos uyumlu adaptasyonu.
"""

import logging

from prophet import Prophet

from safir_monitoring.common.base_forecaster import BaseForecaster

# Prophet, cmdstanpy ve plotly verbose loglarini sustur
logging.getLogger('prophet').setLevel(logging.WARNING)
logging.getLogger('prophet.plot').setLevel(logging.CRITICAL)
logging.getLogger('cmdstanpy').setLevel(logging.WARNING)


class ProphetForecaster(BaseForecaster):
    """Prophet tabanli kapasite tahmin sinifi."""

    ALGORITHM_NAME = "prophet"

    def __init__(self, daily_usages, total_capacity,
                 future_days=90, changepoint_prior_scale=0.05):
        self.changepoint_prior_scale = changepoint_prior_scale
        super().__init__(daily_usages, total_capacity, future_days)

    def _fit_and_predict(self):
        """Prophet model fit ve predict."""
        self.model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=self.changepoint_prior_scale
        )
        self.model.fit(self.df)

        future_df = self.model.make_future_dataframe(
            periods=self.future_days, freq='D')
        self.forecast = self.model.predict(future_df)

        history_len = len(self.df)
        self.historical = self.forecast.iloc[:history_len]
        self.future = self.forecast.iloc[history_len:]
