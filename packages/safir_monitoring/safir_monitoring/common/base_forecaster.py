"""Forecaster base sinifi.

Tum forecasting algoritmalari bu siniftan turetilir.
Ortak response format ve kapasite hesaplama mantigi burada.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import pandas as pd
from oslo_log import log

LOG = log.getLogger(__name__)


class BaseForecaster(ABC):
    """Forecasting algoritmalari icin abstract base sinif.

    Subclass'lar sadece _fit_and_predict() metodunu implement eder.
    Ortak response formatlama ve kapasite hesaplama burada yapilir.
    """

    ALGORITHM_NAME = "base"

    def __init__(self, daily_usages, total_capacity, future_days=90):
        """
        Args:
            daily_usages: [[timestamp_str, value], ...] listesi
            total_capacity: float, maksimum kapasite degeri
            future_days: int, kac gun ilerisi tahmin edilecek
        """
        self.total_capacity = float(total_capacity)
        self.future_days = future_days

        self.df = pd.DataFrame({
            'ds': pd.to_datetime(
                [item[0] for item in daily_usages], utc=True
            ).tz_localize(None),
            'y': [float(item[1]) for item in daily_usages]
        })

        # Subclass'in fit & predict sonuclari
        # Her subclass _fit_and_predict() icinde bunlari doldurmali:
        #   self.forecast: DataFrame (ds, yhat, yhat_upper, yhat_lower, trend)
        #   self.historical: forecast'un ilk history_len satiri
        #   self.future: forecast'un geri kalan satirlari
        self._fit_and_predict()

    @abstractmethod
    def _fit_and_predict(self):
        """Model fit ve predict islemini yapar.

        Bu metod su alanlari doldurmalidilr:
            self.forecast: DataFrame with columns [ds, yhat, yhat_upper, yhat_lower, trend]
            self.historical: forecast[:history_len]
            self.future: forecast[history_len:]
        """
        pass

    def get_capacity_full_date(self):
        """Trend'in kapasiteye ulastigi tarihi bulur."""
        future_trend = self.forecast[
            self.forecast['ds'] > self.df['ds'].iloc[-1]]

        exceeds = future_trend[
            future_trend['trend'] >= self.total_capacity]

        if not exceeds.empty:
            full_date = exceeds.iloc[0]['ds'].to_pydatetime()
            days_remaining = (full_date - datetime.now()).days
            if days_remaining > 0:
                return full_date, days_remaining

        trend_vals = self.forecast['trend'].values
        if len(trend_vals) >= 2:
            daily_slope = float(trend_vals[-1] - trend_vals[-2])
            if daily_slope > 0:
                current_trend = float(trend_vals[len(self.df) - 1])
                remaining = self.total_capacity - current_trend
                if remaining > 0:
                    days_remaining = int(remaining / daily_slope)
                    if days_remaining > 3650:
                        return None, None
                    full_date = datetime.now() + timedelta(days=days_remaining)
                    return full_date, days_remaining

        return None, None

    def get_capacity_full_date_upper(self):
        """yhat_upper (worst case) uzerinden kapasite doluluk tarihi."""
        future_data = self.forecast[
            self.forecast['ds'] > self.df['ds'].iloc[-1]]

        exceeds = future_data[
            future_data['yhat_upper'] >= self.total_capacity]

        if not exceeds.empty:
            full_date = exceeds.iloc[0]['ds'].to_pydatetime()
            days_remaining = (full_date - datetime.now()).days
            if days_remaining > 0:
                return full_date, days_remaining

        return None, None

    def get_daily_growth(self):
        """Trend component'inden gunluk buyume oranini hesaplar."""
        hist_len = len(self.df)
        if hist_len >= 2:
            trend_vals = self.forecast['trend'].values
            total_change = float(trend_vals[hist_len - 1] - trend_vals[0])
            return total_change / (hist_len - 1)
        return 0.0

    def get_prediction_result(self, resource_type, extra_fields=None):
        """Prediction API response dict'i olusturur."""
        current_usage = float(self.df['y'].iloc[-1])
        capacity_full_date, days_remaining = self.get_capacity_full_date()
        capacity_full_date_upper, days_remaining_upper = (
            self.get_capacity_full_date_upper())
        daily_growth = self.get_daily_growth()

        if capacity_full_date is None:
            status = "stable"
        elif days_remaining < 90:
            status = "warning"
        else:
            status = "healthy"

        not_applicable = "Trend is stable or decreasing"

        result = {
            "status": status,
            "capacity_full_date": (capacity_full_date.isoformat()
                                   if capacity_full_date else not_applicable),
            "days_remaining": (int(days_remaining)
                               if days_remaining else not_applicable),
            "current_usage": round(current_usage, 2),
            "total_capacity": self.total_capacity,
            "usage_percentage": round(
                (current_usage / self.total_capacity) * 100, 2),
            "daily_growth": round(daily_growth, 4),
            "resource_type": resource_type,
            "prediction_method": self.ALGORITHM_NAME if capacity_full_date else "none",
            "worst_case": {
                "capacity_full_date": (
                    capacity_full_date_upper.isoformat()
                    if capacity_full_date_upper else not_applicable),
                "days_remaining": (int(days_remaining_upper)
                                   if days_remaining_upper else not_applicable),
            },
            "confidence": {
                "upper": round(
                    float(self.historical['yhat_upper'].iloc[-1]), 2),
                "lower": round(
                    float(self.historical['yhat_lower'].iloc[-1]), 2),
            }
        }

        if status == "stable":
            result["message"] = (
                f"{resource_type} usage is stable or decreasing")

        if extra_fields:
            result.update(extra_fields)

        return result

    def get_trend_graph_result(self, resource_type, dimension=None,
                               unit=None, extra_fields=None):
        """TrendGraph API response dict'i olusturur."""
        current_usage = float(self.df['y'].iloc[-1])
        daily_growth = self.get_daily_growth()
        capacity_full_date, days_remaining = self.get_capacity_full_date()

        data_points = []
        for i in range(len(self.df)):
            row = self.historical.iloc[i]
            data_points.append({
                'date': self.df['ds'].iloc[i].strftime('%Y-%m-%dT00:00:00Z'),
                'actual_value': round(float(self.df['y'].iloc[i]), 4),
                'trend_value': round(float(row['trend']), 4),
                'yhat': round(float(row['yhat']), 4),
                'yhat_upper': round(float(row['yhat_upper']), 4),
                'yhat_lower': round(float(row['yhat_lower']), 4),
            })

        future_predictions = []
        for i in range(len(self.future)):
            row = self.future.iloc[i]
            future_predictions.append({
                'date': row['ds'].strftime('%Y-%m-%dT00:00:00Z'),
                'predicted_value': round(float(row['yhat']), 4),
                'trend_value': round(float(row['trend']), 4),
                'upper_bound': round(float(row['yhat_upper']), 4),
                'lower_bound': round(float(row['yhat_lower']), 4),
            })

        not_applicable = "Trend is stable or decreasing"

        result = {
            'resource_type': resource_type,
            'unit': unit,
            'data_points': data_points,
            'future_predictions': future_predictions,
            'statistics': {
                'current_usage': round(current_usage, 4),
                'total_capacity': self.total_capacity,
                'usage_percentage': round(
                    (current_usage / self.total_capacity) * 100, 2),
                'daily_growth': round(daily_growth, 4),
                'prediction_method': self.ALGORITHM_NAME,
                'capacity_full_date': (
                    capacity_full_date.isoformat()
                    if capacity_full_date else not_applicable),
                'days_remaining': (
                    int(days_remaining)
                    if days_remaining else not_applicable),
            },
            'capacity_line': {
                'value': self.total_capacity,
                'label': f'Total {resource_type} Capacity'
            }
        }

        if dimension:
            result['dimension'] = dimension

        if extra_fields:
            result.update(extra_fields)

        return result
