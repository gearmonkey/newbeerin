#!/usr/bin/env python
# encoding: utf-8
"""
newbeerin.py

main daemeon, pulls in tweets, ignores ones that aren't OTB tweets, then

Created by Benjamin Fields on 2013-04-11.
Copyright (c) 2013 . All rights reserved.
"""

import sys
import os
import unittest
from datetime import datetime

import twitter
import redis
r = redis.StrictRedis(host='localhost', port=6379, db=0)

from credentials import *

def fetch_new_tweets(api, cursor = 0):
    """grab new tweets from followers, since cursor, if given
    returns sequence of tuples of the form
    (username, tweetid, tweet text)"""
    raise NotImplementedError
    
def is_otb(model, tweet, bypass_words = ['#otb', '#nowpouring']):
    """run tweet on model to determine if it a probably OTB tweet returning true if it is
    if the tweet contains any bybass_words, does not run against model and returns true"""
    raise NotImplementedError
    
def split_beers(tweet):
    """break tweet into composite list of strings representing beers on offer
    currently uses """
    raise NotImplementedError
    
def is_fresh(beer, days_old=90):
    """looks for the beer string in the redis store
        if it's there, check to see if the date string is more then days_old.
        In the case that it either isn't in the store or the date is older than days_old
        return True, otherwise return False
        in all cases create or update value in the redis store for the beer string to be the current datetime"""
        raise NotImplementedError

def tweet_these(api, beers, username, twid, dryrun=False):
    """generate tweet about the appearance of beers, 
       citing the name and id they came from if dryrun, 
       just print the tweet, else push it via api
       """
       raise NotImplementedError

def main(argv=None):
    if argv==None:
        argv = sys.argv
    dry_run=False
    if '-d' in argv:
        dry_run = True
    api = twitter.Api(consumer_key=CONSUMER_KEY,
                      consumer_secret=CONSUMER_SECRET,
                      access_token_key=ACCESS_KEY,
                      access_token_secret=ACCESS_SECRET)
    with open(argv[0]) as rh:
        model = cPickle.load(rh)
    cursor = 0
    while True:
        for username, twid, tweet in fetch_new_tweets(api, cursor):
            if is_otb(model, tweet):
                beers = split_beers(tweet)
                new_beers = [beer for beer in beers if beer not is_fresh(beer)]
            if len(new_beers) > 0:
                tweet_these(api, beers, username, twid)
        time.sleep(900)

if __name__ == '__main__':
    main()