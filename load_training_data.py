#!/usr/bin/env python
# encoding: utf-8
"""
load_training_data.py

Created by Benjamin Fields on 2013-03-27.
Copyright (c) 2013 . All rights reserved.
"""

import sys
import os
import re
import codecs

infile = 'training_data.csv'

def load_labeled_examples(fileHandle):
    regex = re.compile(r'^(.*?)\t(.*?)\t(.*?)\t(.*?)\n', flags=re.MULTILINE|re.DOTALL) # to deal with multiline tweets
    data = fileHandle.read()
    res = regex.findall(data)
    return filter(lambda x:x[3] in (u'0',u'1'), res)


def main():
    with codecs.open(infile, encoding='utf-8') as rh:
        training = load_labeled_examples(rh)
    print "found", len(training), "labeled examples in the file", infile
    



if __name__ == '__main__':
    main()

