import numpy as np
import pandas as pd
from sklearn import mixture
from sklearn import metrics
import itertools
from .labeled_dataframe import META_COLUMNS

clustering_techniques = {'dpgmm': lambda df,var_list : mixture.BayesianGaussianMixture(n_components=20,
                                covariance_type='full').fit(df[var_list]).predict(df[var_list])}

class _AugmentedData():

    def add_acc(self,true_col,pred_col):
        """
        add a column to data_df that labels the confusion matrix role of each
        row given the two columns to compare

        new column name is truthVar_predictionName_acc
        """
        col_name = '_'.join([true_col,pred_col,'acc'])
        label_mat = [['TN','FP'],['FN','TP']]
        add_acc_cur = lambda row: label_mat[row[true_col]][row[pred_col]]

        self.df[col_name] = self.df.apply(add_acc_cur,axis=1)

        return self.df

    def update_meta_df_cluster(self):
        """
        update meta_df after clustering or adding other additional groupby vars
        """
        # get all vars in data
        data_vars = self.df.columns
        # get previous vars with meta information
        meta_vars = self.meta_df.index
        # check which are new
        new_vars = [var for var in data_vars if not(var in meta_vars)]
        # create a new DataFrame withthe right index and columns
        new_vars_df = pd.DataFrame(index = new_vars, columns = META_COLUMNS)

        # set all meta info, all will be the same because they're cluster assignments
        new_vars_df['dtype'] = self.df[new_vars].dtypes
        new_vars_df['var_type'] = 'categorical'
        new_vars_df['role'] = 'groupby'
        new_vars_df['isCount'] = False

        # append new rows
        self.meta_df = self.meta_df.append(new_vars_df)
        return self.meta_df

    def add_intersectional(self,var_list=None,tuple_lens=2):
        """
        add categorical variables that are intersectional combinatitons of other
        categorical variables of lengs 2:tuple_len if integer

        Parameters
        -----------
        var_list : None or list of strings
            variables from data_df to use for creating intersectional groupby
        variables or None to use all categorical variables
        tuple_lens : integer (2)
            length of variables to combine, default is 2 for pairwise groups
        """
        # comput var list if not passed
        if not var_list:
            var_list = list(self.get_vars_per_type('categorical'))

        # make tuple len a list for looping
        if not(type(tuple_lens)==list):
            tuple_lens = list(range(2,tuple_lens+1))

        # loop over lengths
        for k in tuple_lens:
            # generate tuples of cat variables
            vl_tuples = itertools.combinations(var_list,k)
            for cur_var_list in vl_tuples:
                # create column name
                new_name = '_'.join(cur_var_list)

                # lambda to merge the valuse fo the current columns
                mergerow =  lambda row: '_'.join([str(v) for v in
                                            row[list(cur_var_list)].values])
                # apply and save to df
                self.df[new_name] = self.df.apply(mergerow,axis=1)


        self.update_meta_df_cluster()

        return self.df




    def add_cluster(self,view,name,qual_thresh=.2):
        """
        add a column to a DataFrame generated by a clustering solution

        Parameters
        -----------
        data_df : DataFrame
            tidy data to cluster and augment
        view : list of strings
            list of column names that defines a view of the data to perform
        clustering in
        name : string
            name of clustering method to apply
        """

        #cluster the data_df
        try: #some will fail, just dont add them for now

            clust_assignments = clustering_techniques[name](self.df,view)

            # squash values, if empty assignments
            clust_ids = np.unique(clust_assignments)
            num_clusters = len(clust_ids)

            span_clust = np.max(clust_assignments)

            if span_clust > num_clusters:
                # map them down
                cleaned = {learned_id: clean_id for clean_id,learned_id in
                                                    enumerate(clust_ids)}
                clust_assignments = [cleaned[c] for c in clust_assignments]

            # compute cluster qualty metric

            clust_qual = metrics.silhouette_score(self.df[view],
                            clust_assignments, metric='euclidean')

            #create column_name
            col_name = '_'.join(['_'.join(view),name])

            # only assign if quality is high enough
            if clust_qual > qual_thresh and num_clusters >1:
                self.df[col_name] = clust_assignments
        except Exception as e:
            pass

        return self.df

    def generate_continuous_views(self,n_dim=2):
        """
        generate all views of a given size

        Parameters
        -----------
        data_df : DataFrame
            tidy data to cluster and augment
        """
        view_vars = list(self.get_vars_per_type('continuous'))

        # select all groups of the desired length, convert to list
        view_list = [list(v) for v in itertools.combinations(view_vars,n_dim)]

        return view_list

    def add_all_dpgmm(self,n_dim=2,qual_thresh= .2):
        """
        add dpgmm clusters for all ndimviews of continuous variables

        Parameters
        -----------
        data_df : DataFrame
            tidy data to cluster and augment
        """
        view_list =  self.generate_continuous_views(n_dim)

        for view in view_list:
            self.add_cluster(view,'dpgmm',qual_thresh)

        self.update_meta_df_cluster()

        return self.df


    def add_interval(self,vars_in,q,q_names=None):
        """
        add a column to a DataFrame generated from quantiles specified by `q` of
        variable `var`


        Parameters
        -----------
        data_df : DataFrame
            must be tidy
        vars_in : string or list of strings
            column name(s) to compute quantile values of
        q : float or list
            if scalar then the new column will be {top, bottom, middle} using the
            bottom [0,q) [q,1-q), [1-q,1]. If q is a list it specifies the splits.
            Should be compatible with pandas.quantile
        q_names : list
            list of names for quantiles assumed to be in order otherwise numerical
            names will be assigned unles there q is a float or len(q) ==2
        """

        # make sure var is a list
        if type(vars_in) == list:
            var_list = vars_in
        else:
            var_list = [vars_in]

        # transform q and generate names if necessary
        if type(q) == float:
            q_str = str(q)
            q_m_str = str(1-2*q)
            q_names = ['bottom'+q_str,'middle'+q_m_str,'top'+q_str]
            q = [q,1-q]

        # get quantile cutoffs for the columns of interest
        quantile_df = data_df[var_list].quantile(q)


        # transform to labels for merging
        q_l = q.copy()
        q_u = q.copy()
        q_l.insert(0,0) #prepend a 0
        q_u.append(1)

        # create names
        min_names = {col:col+'_min' for col in var_list}
        max_names = {col:col+'_max' for col in var_list}


        # TODO: for large data, this should be done with copy instead of recompute

        # get quantile bottoms and rename to _min
        ql_df = data_df[var_list].quantile(q_l).rename(columns=min_names)
        # get quantile tops and rename to _max
        qu_df = data_df[var_list].quantile(q_u).rename(columns= max_names)
        # round up the last interval's upper limit for <=, < ranges
        qu_df.iloc[-1] = np.ceil(qu_df.iloc[-1])
        # rename index of uppers for concat to work properly
        qu_df = qu_df.rename(index={u:l for l,u in zip(q_l,q_u)})



        # concatenate uppers and lwoers
        q_intervals = pd.concat([ql_df,qu_df],axis=1)

        if q_names is None:
            q_intervals['quantile_name'] = [' - '.join([str(l),str(u)]) for l,u in zip(q_l,q_u)]
        else:
            q_intervals['quantile_name'] = q_names

        # iterate over vars
        for var in var_list:
            interval_column_key = {'start':var+'_min',
                                    'end': var + '_max',
                                    'label': 'quantile_name',
                                    'source':var}
            self.df = interval_merge(data_df,q_intervals,interval_column_key)

        return self.df

    def add_quantile(self,var_list, quantiles=None,quantile_name='quantiles'):
        """
        add quantiles labeled according to quantiles dictionary provided to
        self.df with column(s) named var+quantile_name . also updates meta_df to
        make the quantiles used only as groupby

        Parameters
        -----------
        var_list : list
            variable(s) to compute for
        q : dict
            {'name':upper_limit}, pairs to name the quantiles.  1 must be one of the
            values

        Returns
        --------
        self.df : DataFrame
            with new added colmns
        """

        if quantiles ==None:
            quantiles = {'low':.25,'mid':.75,'high':1}

        if type(var_list) is str:
            var_list = [var_list]

        N = len(self.df)

        cutoffs,label_list = zip(*[(int(np.round(N*q_val)),label) for
                                            label,q_val in quantiles.items()])
        # make a list
        cutoffs = list(cutoffs)
        # prepend a 0
        cutoffs.insert(0,0)
        # diffs are now the lenths of the intervals can be used with repeat
        label_reps = np.diff(cutoffs)

        # create list of labels of the size fo the df with the quantile labels,
        # assuming a sorted list
        q_labels = np.repeat(label_list,label_reps)

        for var in var_list:
            # sort and append a column of the labels
            self.df.sort_values(var,inplace = True)
            colname = var + quantile_name
            self.df[colname] = q_labels

        # return to oringnal order
        self.df.sort_index(inplace=True)

        # update meta infor
        self.update_meta_df_cluster()

        return self.df



def interval_merge(data_df, interval_df,interval_column_key):
    """
    add a column to an dataframes according to intervals specified in another
    DataFrame

    Parameters
    ----------
    data_df : DataFrame
        tidy df of data, will be augmented and returned
    interval_df : DataFrame
        df with columns to be used as start, stop, and label must be non
    overlapping and include a region for all values of data_df's source column
    interval_column_key : dict
        dictionary with keys: `start` `end` `label` with values as column names
        in interval_df and `source` with a value of a column name in data_df

    Returns
    --------
    data_df : DataFrame
        original DataFrame with new column named `interval_column_key['label']`
        that has valued from interval_df[interval_column_key['label']] assigned
        basedon the value in data_df[interval_column_key['source']] and the
        intervals defined in interval_df
    """

    # parse column names for easier usage
    source_col = interval_column_key['source']
    start_col = interval_column_key['start']
    end_col = interval_column_key['end']
    label_col = interval_column_key['label']

    # create piecewise function
    input_domain = np.linspace(np.min(interval_df[start_col]),np.max(interval_df[start_col]))
    assign_interval_label = np.piecewise()

    # evaluate a row and return true if val in [start,end)
    row_eval = lambda row,val: (val >=row[start_col])&(val<row[end_col])
    # evalutea all rows of a table, return true or false for each
    table_eval = lambda val: interval_df.apply(row_eval,args=(val,),axis=1)
    # return the label value for the true one
    get_label = lambda val: interval_df[label_col][table_eval(val)].item()

    # add the column
    data_df[label_col] = data_df[source_col].apply(get_label)

    return data_df
