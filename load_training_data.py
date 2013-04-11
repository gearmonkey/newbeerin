#!/usr/bin/env python
# encoding: utf-8
"""
load_training_data.py

pull in the training data and do 10 fold 70-30 cross validation to see how accurate the model is with this data.

Created by Benjamin Fields on 2013-03-27.
Copyright (c) 2013 . Some rights reserved.
"""

import sys
import os
import re
import codecs
import random
import cPickle

from classifier import *


infile = 'training_data.csv'

def load_labeled_examples(fileHandle):
    regex = re.compile(r'^(.*?)\t(.*?)\t(.*?)\t(.*?)\n', flags=re.MULTILINE|re.DOTALL) # to deal with multiline tweets
    data = fileHandle.read()
    res = regex.findall(data)
    return filter(lambda x:x[3] in (u'0',u'1'), res)

def clean_and_tokenize(labeled_data, min_len=3):
    dataset = []
    for (text, label) in labeled_data:
        words_filtered = [e.lower() for e in text.split() if len(e) >= min_len]
        dataset.append((words_filtered, label))
    return dataset

def get_words(dataset):
    all_words = []
    for (words, label) in dataset:
      all_words.extend(words)
    return all_words

def get_word_features(wordlist):
    wordlist = nltk.FreqDist(wordlist)
    word_features = wordlist.keys()
    return word_features



def main():
    folds = 10
    train_prop = 0.8
    with codecs.open(infile, encoding='utf-8') as rh:
        full_training = map(lambda x:(x[2],int(x[3])), load_labeled_examples(rh))
    print "found", len(full_training), "labeled examples in the file", infile
    
    print "running", folds, "cross validation with a", int(train_prop*100), '% training percentage...'
    training_size = int(len(full_training)*train_prop)
    per_fold_results = []
    for _ in xrange(folds):
        shuffled = random.sample(full_training, len(full_training))
        training, testing = shuffled[:training_size], shuffled[training_size:]
        classifier = Classifier(training)
        classifier.run()
        correct_pos = 0
        correct_neg = 0
        false_pos = 0
        false_neg = 0
        for test in testing:
            inferred_label = classifier.classify(test[0])
            if inferred_label == test[1]:
                if inferred_label == 1:
                    correct_pos += 1
                elif inferred_label == 0:
                    correct_neg += 1
            elif inferred_label == 0:
                false_neg += 1
            elif inferred_label == 1:
                false_pos += 1
            else:
                print "something went wrong"
                raise ValueError
        per_fold_results.append({'correct_pos':correct_pos, 'correct_neg':correct_neg, 
                                 'false_neg':false_neg, 'false_pos':false_pos})
    print 'tabulating results...'
    total_correct_pos = sum(map(lambda x:x['correct_pos'], per_fold_results))
    total_correct_neg = sum(map(lambda x:x['correct_neg'], per_fold_results))
    total_false_pos = sum(map(lambda x:x['false_pos'], per_fold_results))
    total_false_neg = sum(map(lambda x:x['false_neg'], per_fold_results))
    
    print "total correct positive:", total_correct_pos
    print "total correct negative:", total_correct_neg
    print "total false positive:", total_false_pos
    print "total fase negative:", total_false_neg
    print "accuracy over", folds, "folds with a", "{0}:{1}".format(int(train_prop*100), 100-int(train_prop*100)),
    print "train:test split is", float(total_correct_pos+total_correct_neg)/\
            sum([total_correct_pos, total_correct_neg, total_false_pos, total_false_neg])
    print "positive accuracy:", float(total_correct_pos)/(total_correct_pos+total_false_neg)
    print "negative accuracy:", float(total_correct_neg)/(total_correct_neg+total_false_pos)
    print "full results:", per_fold_results
    
    print "model trained on all data stored in model.pickle"
    classifier = Classifier(full_training)
    classifier.run()
    with open('model.pickle', 'w') as wh:
        cPickle.dump(classifier, wh)
    
    
    



if __name__ == '__main__':
    main()

