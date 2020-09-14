import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

from lightwood.constants.lightwood import COLUMN_DATA_TYPES
from lightwood.mixers import BaseMixer


class BoostMixer(BaseMixer):
    def __init__(self):
        super().__init__()
        self.targets = None

    def fit(self, train_ds, test_ds):
        output_features = train_ds.configuration['output_features']

        self.targets = {}
        
        for output_feature in output_features:
            self.targets[output_feature['name']] = {
                'type': output_feature['type']
            }
            if 'weights' in output_feature:
                self.targets[output_feature['name']]['weights'] = output_feature['weights']
            else:
                self.targets[output_feature['name']]['weights'] = None

        X = []
        for x in train_ds:
            X.append([])
            for feature in x:
                X[-1].extend(list(float(val) for val in feature))

        for target_col_name in self.targets:
            Y = train_ds.get_column_original_data(target_col_name)

            if self.targets[target_col_name]['type'] == COLUMN_DATA_TYPES.CATEGORICAL:
                weight_map = self.targets[target_col_name]['weights']
                sample_weight = [1] * len(Y)
                # if weight_map is None:
                #     sample_weight = [1] * len(Y)
                # else:
                #     sample_weight = [weight_map[val] for val in Y]

                self.targets[target_col_name]['model'] = GradientBoostingClassifier(n_estimators=600)
                self.targets[target_col_name]['model'].fit(X, Y, sample_weight=sample_weight)

            elif self.targets[target_col_name]['type'] == COLUMN_DATA_TYPES.NUMERIC:
                self.targets[target_col_name]['model'] = GradientBoostingRegressor(n_estimators=600)
                self.targets[target_col_name]['model'].fit(X, Y)
                if self.quantiles is not None:
                    self.targets[target_col_name]['quantile_models'] = {}
                    for i, quantile in enumerate(self.quantiles):
                        self.targets[target_col_name]['quantile_models'][i] = GradientBoostingRegressor(n_estimators=600, loss='quantile', alpha=quantile)
                        self.targets[target_col_name]['quantile_models'][i].fit(X, Y)

            else:
                self.targets[target_col_name]['model'] = None

    def predict(self, when_data_source, include_extra_data=False):
        when_data_source.transformer = self.transformer
        when_data_source.encoders = self.encoders
        _, _ = when_data_source[0]

        X = []
        for x in when_data_source:
            X.append([])
            for feature in x:
                X[-1].extend(list(float(val) for val in feature))
        
        predictions = {}

        for target_col_name in self.targets:

            if self.targets[target_col_name]['model'] is None:
                predictions[target_col_name] = None
            else:
                predictions[target_col_name] = {}
                predictions[target_col_name]['predictions'] = [x for x in self.targets[target_col_name]['model'].predict(X)]

                try:
                    predictions[target_col_name]['selfaware_confidences'] = [max(x) for x in self.targets[target_col_name]['model'].predict_proba(X)]
                except Exception as e:
                    pass

                if 'quantile_models' in self.targets[target_col_name]:
                    lower_quantiles = self.targets[target_col_name]['quantile_models'][0].predict(X)
                    upper_quantiles = self.targets[target_col_name]['quantile_models'][1].predict(X)

                    predictions[target_col_name]['confidence_range'] = [[lower_quantiles[i],upper_quantiles[i]] for i in range(len(lower_quantiles))]
                    predictions[target_col_name]['quantile_confidences'] = [self.quantiles[1] - self.quantiles[0] for i in range(len(lower_quantiles))]

        return predictions
