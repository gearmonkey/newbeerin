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
from random import sample

import twitter
import redis
r = redis.StrictRedis(host='localhost', port=6379, db=0)

from credentials import *

TEMPLATES = ["New beer @{username}! Head there to find {beer}",
             "Looking for {beer}? They just put it on @{username}",
             ]

def fetch_new_tweets(api, cursor = 0, page=0): 
    """grab new tweets from followers, since cursor, if given
    returns sequence of tuples of the form
    (username, tweetid, tweet text)
    fetches until at least cursor, unless cursor is 0, in which case only the most recent page is grabbed
    (just grabs a page for now)"""
    tweets = api.GetFriendsTimeline(count=100)
    for tweet in tweets:
        yield tweet.user.screen_name, tweet.id, tweet.text
    
    
def is_otb(model, tweet, bypass_words = ['#otb', '#nowpouring']):
    """run tweet on model to determine if it a probably OTB tweet returning true if it is
    if the tweet contains any bybass_words, does not run against model and returns true"""
    for word in bypass_words:
        if word in tweet.split():
            return True
    if model.classify(tweet) == 1:
        return True
    return False

    
def split_beers(tweet, max_intro_prop=0.33):
    """break tweet into composite list of strings representing beers on offer
    currently uses"""
    tweet = tweet.lower()
    #first pruning
    pruned = tweet.rsplit(':',1)[-1]
    #if it pulls off more than max_intro_prop ignore
    if len(pruned)/float(len(tweet))<max_intro_prop:
        tweet = pruned
        
    pruned = tweet.rsplit(':',1)[-1]
    #if it pulls off more than max_intro_prop ignore
    if len(pruned)/float(len(tweet))<max_intro_prop:
        tweet = pruned
        
    pruned = tweet.rsplit(' - ',1)[-1]
    #if it pulls off more than 33% ignore
    if len(pruned)/float(len(tweet))<max_intro_prop:
        tweet = pruned
        
    #the (intro) cask (beer) keg (beer) pattern
    pruned = tweet.rsplit('cask',1)[-1]
    #if it pulls off more than 33% ignore
    if len(pruned)/float(len(tweet))<max_intro_prop:
        tweet = pruned
    
    #split on newlines, then ',', then '.' use first that results in at least 3 tokens
    if len(tweet.split(','))>2:
        beers = tweet.split(',')
        if '.' in beers[-1]:
            beers[-1] = beers[-1].split('.',1)[0]
    elif len(tweet.split('.'))>2:
        beers = tweet.split('.')
        if ',' in beers[-1]:
            beers[-1] = beers[-1].split(',',1)[0]
    elif len(tweet.split('\n'))>2:
        if '.' in beers[-1]:
            beers[-1] = beers[-1].split('.',1)[0]
        if ',' in beers[-1]:
            beers[-1] = beers[-1].split(',',1)[0]
    else:
        beers = []
    
    if len(beers)>0 and 'http' in beers[-1]:
        beers[-1] = beers[-1].split('http',1)[0]
    
    return beers
    
    
def is_fresh(beer, days_old=90):
    """looks for the beer string in the redis store
        if it's there, check to see if the date string is more then days_old.
        In the case that it either isn't in the store or the date is older than days_old
        return True, otherwise return False
        in all cases create or update value in the redis store for the beer string to be the current datetime"""
        last_seen = r.get('beer_'+beer)
        now = datetime.now()
        r.set('beer_'+beer, now)
        if last_seen != None and  (now-last_seen).days < days_old:
            return False
        return True
            
        

def tweet_these(api, beers, username, twid, dryrun=False, templates=TEMPLATES ):
    """generate tweet about the appearance of beers, 
       citing the name and id they came from if dryrun, 
       just print the tweet, else push it via api
       """
    pretty_beer = reduce(lambda x,y:x+', '+y, beers)
    text = sample(templates, 1)[0].format(beer=pretty_beer, username=username)
    if len(text)<111:
        text += ' https://twitter.com/{user}/status/{twid}'.format(user=username, twid=twid)
    if dryrun:
        print 'would have tweeted:'
        print text
    else:
        status = api.PostUpdate(text)
        

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
        for username, twurl, tweet in fetch_new_tweets(api, cursor):
            if is_otb(model, tweet):
                beers = split_beers(tweet)
                new_beers = [beer for beer in beers if beer not is_fresh(beer)]
            if len(new_beers) > 0:
                tweet_these(api, beers, username, twid)
        time.sleep(900)

if __name__ == '__main__':
    main()