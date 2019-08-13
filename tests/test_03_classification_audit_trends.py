# # Developing a classification Audit trend
#
# In first iteration, this will only work on datasets that already have two or more binary classification variables included.
#
# We will need additional metadata: role options of being predictions or ground truths.
#


import pytest
import numpy as np
import pandas as pd
import wiggum as wg


# First, we will need a dataset that we can work with

# In[2]:

def test_classification_trends():

    dataset = 'data/multi_decision_admisions/'
    labeled_df = wg.LabeledDataFrame(dataset)

    acc_trend = wg.Binary_Accuracy_Trend()
    tpr_trend = wg.Binary_TPR_Trend()
    ppv_trend = wg.Binary_PPV_Trend()
    tnr_trend = wg.Binary_TNR_Trend()
    fdr_trend = wg.Binary_FDR_Trend()
    f1_trend = wg.Binary_F1_Trend()
    labeled_df.get_subgroup_trends_1lev([acc_trend,tpr_trend,ppv_trend,
                                    tnr_trend,fdr_trend,f1_trend])


    # In[36]:


    labeled_df.get_SP_rows(thresh=.2)