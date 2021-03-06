import numpy as np
import pandas as pd
from sklearn import preprocessing
import statistics
from sklearn.model_selection import train_test_split, KFold
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.feature_selection import f_regression
from scipy.stats import pearsonr
from plotting import *
import os

from scipy.stats import PearsonRConstantInputWarning


# Preprocesses data and keeps any metadata we may need later
class DataPreprocessor(object):
    def __init__(self, input_path=None, label='price', drop_features=['date'], save_dir=None, test_size=0.2,\
    normalize_features=True, omit_norm_features=['zipcode'], normalize_labels=False, save_plots=False, plotDir='./figures',
    xtrain=None, xtest=None, ytrain=None, ytest=None, input_split=False):
        self.input_path = input_path
        self.label = label
        self.drop_features = drop_features
        self.save_dir = save_dir
        self.test_size = 0.2
        self.normalize_features = normalize_features
        self.normalize_labels = normalize_labels
        self.omit_norm_features = omit_norm_features

        # Splitting data into features/labels
        if input_path:
            self.X = pd.read_csv(self.input_path)
            self.Y = pd.DataFrame(self.X[self.label])

        os.makedirs(plotDir, exist_ok=True)
        os.makedirs(save_dir, exist_ok=True)

        self.input_split = input_split
        if input_split:
            self.X_train = xtrain.copy()
            self.X_test  = xtest.copy()
            self.Y_train = ytrain.copy()
            self.Y_test  = ytest.copy()

        self.__preprocess_data()

        if (save_plots):
            plot_train_test_split(self.X_train['long'], self.X_test['long'], 
                self.X_train['lat'], self.X_test['lat'])

        self.get_feature_stats()
        self.get_correlations()

        # Plots histograms
        if (save_plots):
            os.makedirs(plotDir+'/histograms', exist_ok=True)
            os.makedirs(plotDir+'/correlation', exist_ok=True)
            
            plot_feature_histograms(self.X_train, save_dir=plotDir+'/histograms')
            plot_feature_histograms(self.Y_train, save_dir=plotDir+'/histograms')
            plot_feature_correlation(self.X_train, self.Y_train, save_dir=plotDir+"/correlation")
            plot_price_heatmap(self.X_train['long'], self.X_train['lat'], self.Y_train['price'], save_dir=plotDir)


    # Normalizes data columns between 0 and 1
    def normalize_data(self, normalize_labels=False, omit=['zipcode']):
        # Normalizing features between 0 and 1 (except for those in omit)
        norm_features = list(self.X_train.columns)
        self.norm_features = norm_features
        for feature in omit:
            norm_features.remove(feature)
        omit_features_train = self.X_train[omit]
        omit_features_test  = self.X_test[omit]

        # Normalizing features
        mmScaler = preprocessing.MinMaxScaler()
        mmScaler.fit(self.X_train[norm_features])
        self.X_train = pd.DataFrame(mmScaler.transform(self.X_train[norm_features]), index=self.X_train.index, columns=norm_features)
        self.X_train[omit] = omit_features_train
        self.X_test  = pd.DataFrame(mmScaler.transform(self.X_test[norm_features]), index=self.X_test.index, columns=norm_features)
        self.X_test[omit] = omit_features_test

        # Normalizing labels as well
        if (normalize_labels):
            mmScaler.fit(self.Y_train)
            self.Y_train = pd.DataFrame(mmScaler.transform(self.Y_train), index=self.X_train.index, columns=[self.Y_train.columns[0]])
            self.Y_test  = pd.DataFrame(mmScaler.transform(self.Y_test), index=self.X_test.index, columns=[self.Y_test.columns[0]])


        return self.X_train, self.X_test, self.Y_train, self.Y_test


    # Preprocesses data by normalizing, dropping specified features, and splitting into train/test sets
    # TODO: Incorporate splitting from decision tree (GINI/Entropy) to bin data as well (if needed)
    def __preprocess_data(self):
        if (not self.input_split):

            # Dropping label and irrelevant features from X
            self.X.drop(self.label, inplace=True, axis=1)
            self.X.drop(self.drop_features, inplace=True, axis=1)

            self.X_train, self.X_test, self.Y_train, self.Y_test =\
            train_test_split(self.X, self.Y, test_size=self.test_size, shuffle=True, random_state=None)
            self.min_norm = np.min(self.Y_train)
            self.max_norm = np.max(self.Y_train)
        else:
            #self.X_train.drop(self.label, inplace=True, axis=1)
            self.X_train = self.X_train.drop(self.drop_features, axis=1)
            #self.X_test.drop(self.label, inplace=True, axis=1)
            self.X_test  = self.X_test.drop(self.drop_features, axis=1)


        # Doing normalization
        if self.normalize_features:
            self.normalize_data(self.normalize_labels, self.omit_norm_features)

        self.X_train.reset_index(inplace=True, drop=True)
        self.X_test.reset_index(inplace=True, drop=True)
        self.Y_train.reset_index(inplace=True, drop=True)
        self.Y_test.reset_index(inplace=True, drop=True) 

        
        # Exporting normalized data to CSV
        if (self.save_dir != None):    
            self.X_train.to_csv('%s/X_train.csv' % (self.save_dir))
            self.Y_train.to_csv('%s/Y_train.csv' % (self.save_dir))

            self.X_test.to_csv('%s/X_test.csv' % (self.save_dir))
            self.Y_test.to_csv('%s/Y_test.csv' % (self.save_dir))


        return self.X_train, self.X_test, self.Y_train, self.Y_test


    # Gets list of correlations, sorted in reverse order by magnitude of correlation for each feature within a dataframe
    # TODO: Handle case for constant value arrays (i.e. cluster of houses in mainland all have waterfront == 0)
    def get_correlations(self, disp=False):
        correlations = []
        for i, column in enumerate(self.X_train.columns):
            corr = 0
            if len(list(set(self.X_train[column]))) <= 1:
                corr = 1e-10
            else:
                try:
                    corr = pearsonr(self.X_train[column], self.Y_train[self.label])[0]
                except RuntimeWarning:
                    print('Runtime warning')

            correlations.append((column, corr))

        correlations = sorted(correlations, key=lambda tup: abs(tup[1]), reverse=True)

        if (disp):
            print('Correlations of Features reverse sorted by magnitude:')
            for i in range(len(correlations)):
                print(correlations[i])

        self.feature_label_correlations = correlations

        return correlations

    # Gets stats for each feature like mean, stddev, etc...
    def get_feature_stats(self):
        stats = {}
        for column in self.X_train.columns:
            stats[column] = {}
            stats[column]['mean'] = np.mean(self.X_train[column])
            stats[column]['median'] = np.median(self.X_train[column])
            stats[column]['std']  = np.std(self.X_train[column])
            stats[column]['var']  = np.var(self.X_train[column])

            # Gets mode (or None in case of continuous / equally probable values)
            try:
                stats[column]['mode'] = statistics.mode(self.X_train[column])
            except statistics.StatisticsError:
                mode = -1

        self.feature_stats = stats

        return stats

    # Ranks the input features using a random forest algorithm (MSE)
    def rf_rank(self, n_estimators=25, max_depth=None, disp=False, threshold=None):
        rf = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth)
        rf.fit(self.X_train, self.Y_train['price'])
        feature_importances = zip(self.X_train.columns, rf.feature_importances_)
        feature_importances = sorted(feature_importances, key=lambda tup: abs(tup[1]), reverse=True)

        if threshold:
            cutoff = len(feature_importances)
            for i, importance in enumerate(feature_importances):
                if importance[1] < threshold:
                    cutoff = i
                    break
            feature_importances = feature_importances[:cutoff]
            feature_strs = []
            for i in range(len(feature_importances)):
                feature_strs.append(feature_importances[i][0])
            return feature_strs

        if (disp):
            print('\nTop 10 Features reverse sorted by importance from random forest')
            for feature in feature_importances:
                print(feature)

        self.feature_importances = feature_importances 
        return feature_importances


    # MRMR
    ##################################################
    def compute_correlation(self, X, Y):
        correlations = []
        for i, column in enumerate(X.columns):
            correlations.append(abs(get_correlation(X[column], Y[Y.columns[0]])))

        return correlations

    def compute_self_correlation(self, X):
        correlations = []
        for i, i_column in enumerate(X.columns):
            for j, j_column in enumerate(X.columns):
                if (len(list(set(X[i_column]))) <= 1 or len(list(set(X[j_column]))) <= 1):
                    correlations.append(1e-10)
                else:
                    try:
                        correlations.append(abs(pearsonr(X[i_column], X[j_column])[0]))
                    except RuntimeWarning:
                        print('rt warning')

        return correlations

    def compute_f_statistic(self, X, Y):
        f_scores = []

        var_y = np.var(Y[Y.columns[0]])
        for i, column in enumerate(X.columns):
            var_x = np.var(X[column])
            f_scores.append(abs(var_x / var_y))
        
        return f_scores

    def compute_relevance_redundancy(self, x, y):
        try:
            f_scores = f_regression(x, y[y.columns[0]])[0]
            f_scores /= np.max(f_scores)
            cor = self.compute_self_correlation(x)
        except RuntimeWarning:
            print('rt warning')

        s = len(f_scores)
        rel = 0
        for x in f_scores:
            rel += x
        rel *= (1 / s)

        s = len(cor)
        red = 0
        for x in cor:
            red += x
        red *= (1 / s)

        return rel, red


    # Perform mRMR to greedily select the top k features which minimize redundancy and maximize relevance
    # When additive is true, we perform FCD mRMR, when false we perform FCQ mRMR
    # Returns: List of selected feature names
    def mRMR(self, k=10, additive=True, verbose=1):
        if k < 1:
            return []

        # Compute F-Test (used for relevance)
        f_scores = f_regression(self.X_train, self.Y_train[self.Y_train.columns[0]])[0]
        f_scores /= np.max(f_scores)

        # Select first feature based on maximum relevance
        best = None
        best_col = None
        for i, column in enumerate(self.X_train.columns):
            if (best == None or f_scores[i] > best):
                best = f_scores[i]
                best_col = column

        selected_features = [best_col]
        remaining_features = self.X_train.columns.tolist()
        remaining_features.remove(best_col)
        overall = 0
        rel, red = self.compute_relevance_redundancy(self.X_train[selected_features], self.Y_train)
        if (additive):
            overall = rel - red
        else:
            overall = rel / red

        # Add up to k addition features, so long as overall objective function is improving
        for i in range(k-1):
            best = None
            best_col = None

            if (len(remaining_features) < 1):
                break

            if (verbose == 2):
                print (" ---  Start iter ", i+1, " --- ")

            # Try adding each feature and select one that maximizes the objective function
            for j, col in enumerate(remaining_features):
                features = selected_features.copy()
                features.append(col)
                try:
                    rel, red = self.compute_relevance_redundancy(self.X_train[features], self.Y_train)

                    value = 0
                    if (additive):
                        value = rel - red
                    else:
                        value = rel / red

                    if (best == None or value > best):
                        best = value
                        best_col = col

                    if (verbose == 2):
                        print ("   Feature ", col, ":")
                        print ("     rel = ", rel)
                        print ("     red = ", red)
                        print ("     value = ", value, "\n")
                except RuntimeWarning:
                    print('Runtime Warning')

            # Add the feature to selected features and continue
            selected_features.append(best_col)
            remaining_features.remove(best_col)
            overall = best

            if (verbose):
                print("Iter ", i+1, " added feature ", best_col, " for an overall value of ", overall)

        if (verbose):
            print ("mRMR selected features:\n", selected_features)

        self.mRMR_features = selected_features
        return selected_features


    # Feature selection with mRMR for full dataset, using varying number of features
    # Seems to vary noticably between runs, probably want to do some kind of averaging
    def mRMR_KNN_test(self):
        feature_order = self.mRMR(k=len(self.X_train.columns), additive=True, verbose=0)
        best = 0
        best_features = []
        print(" --- Using FCD mRMR --- ")
        for k in range(1, len(self.X_train.columns)):
            features = feature_order[:k]
            KNN = KNeighborsRegressor(n_neighbors=5, weights='distance')
            KNN.fit(self.X_train[features], self.Y_train[self.label])
            score = KNN.score(self.X_train[features], self.Y_train[self.label])
            print("KNN using", k, "mRMR selected features. Score = ", score)

            if score > best:
                best = score
                best_features = features
        
        print ("\b Best number of features for additive mRMR and KNN is ", len(best_features), " with score of", best, " and using features:\n", best_features)

        self.mrmr_add_knn_best_features = best_features

        feature_order = self.mRMR(k=len(self.X_train.columns), additive=False, verbose=0)
        best = 0
        best_features = []
        print("\n --- Using FCDQ mRMR --- ")
        for k in range(1, len(self.X_train.columns)):
            features = feature_order[:k]
            KNN = KNeighborsRegressor(n_neighbors=5, weights='distance')
            KNN.fit(self.X_train[features], self.Y_train)
            score = KNN.score(self.X_train[features], self.Y_train[self.label])
            print("KNN using", k, "mRMR selected features. Score = ", score)

            if score > best:
                best = score
                best_features = features
        
        print ("\b Best number of features for multiplicative mRMR and KNN is ", len(best_features), " with score of", best, " and using features:\n", best_features)

        self.mrmr_mult_knn_best_features = best_features




# Gets stats for each feature like mean, stddev, etc...
def get_feature_stats(X):
    stats = {}
    for column in X.columns:
        stats[column] = {}
        stats[column]['mean'] = np.mean(X[column])
        stats[column]['median'] = np.median(X[column])
        stats[column]['std']  = np.std(X[column])
        stats[column]['var']  = np.var(X[column])

        # Gets mode (or None in case of continuous / equally probable values)
        try:
            stats[column]['mode'] = statistics.mode(X[column])
        except statistics.StatisticsError:
            mode = -1

    return stats