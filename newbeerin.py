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
import cPickle
import time
import re

from datetime import datetime
from random import sample

import twitter
import bitly_api
import redis
r = redis.StrictRedis(host='localhost', port=6379, db=0)

from credentials import *

TEMPLATES = [unicode("New beer @{username}! Head there to find {beer}", 'utf8'),
             unicode("Looking for {beer}? Just put on @{username}", 'utf8'),
             unicode("So @{username} just put on {beer}, so you know", 'utf8'),
             unicode("Thirsty? Grab some {beer} @{username}!", 'utf8')
             ]

SHORT_TMPLS = [u"New beers on klaxon, @{username}, can't fit in 140 chars, check: {link}",
               u"Some new beer on @{username}, {link}",
               u".@{username} has new beer on: {link}",
               u"Looks like @{username} just put on a bunch of new beer {link}",
               u"Tasty new beer @{username}: {link}"
               ]

BYPASS_WORDS = ['otb', 'on the bar', 'new on', 'on cask today', 'on keg today']
STOP_WORDS = ['football', 'rugby', 'cricket', 'champions league']

def fetch_new_tweets(api, cursor = 0): 
    """grab new tweets from followers, since cursor, if given
    returns sequence of tuples of the form
    (username, tweetid, tweet text)
    fetches until at least cursor, unless cursor is 0, in which case only the most recent page is grabbed
    (just grabs a page for now)"""
    kwargs = {'count':100}
    if cursor > 0:
        kwargs["since_id"] = cursor
    try:
        tweets = api.GetFriendsTimeline(**kwargs)
    except twitter.TwitterError, err:
        print 'twitter error', err, 'trying again in a minute'
        time.sleep(60)
        tweets = api.GetFriendsTimeline(**kwargs)
    for tweet in tweets:
        yield tweet.user.screen_name, tweet.id, tweet.text
    
    
def is_otb(model, tweet, bypass_words=BYPASS_WORDS, stop_words=STOP_WORDS):
    """run tweet on model to determine if it a probably OTB tweet returning true if it is
    if the tweet contains any stop_words, does not run against the model, returns false
    if the tweet contains any bypass_words, does not run against model and returns true
    stop_words take precendant over bypass words, except the hardcoded '#otb' and '#nowpouring'"""
    tweet = tweet.lower()
    for word in ('#nowpouring','#otb'):
        if word in tweet:
            print word
            return True
    for word in stop_words:
        if word in tweet:
            print 'explict STOP on tweet'
            return False
    for word in bypass_words:
        if word in tweet:
            print 'bypass catch'
            return True
    if int(model.classify(tweet)) == 1:
        return True
    return False

    
def split_beers(tweet, max_intro_prop=0.33, stops=BYPASS_WORDS):
    """break tweet into composite list of strings representing beers on offer
    currently uses"""
    tweet = tweet.lower()
    #remove any urls
    for url in re.finditer(r'(http://t.co/[\w]*)', tweet):
        print 'pruning', url.group()
        tweet = tweet.replace(url.group(), '').replace('  ', ' ')
    
    #first pruning
    pruned = tweet.rsplit(':',1)[-1]
    #if it pulls off more than max_intro_prop ignore
    if len(pruned)/float(len(tweet))>(1-max_intro_prop):
        tweet = pruned
        
    pruned = tweet.rsplit(':',1)[-1]
    #if it pulls off more than max_intro_prop ignore
    if len(pruned)/float(len(tweet))>(1-max_intro_prop):
        tweet = pruned
        
    pruned = tweet.rsplit(' - ',1)[-1]
    #if it pulls off more than 33% ignore
    if len(pruned)/float(len(tweet))>(1-max_intro_prop):
        tweet = pruned
        
    #the (intro) cask (beer) keg (beer) pattern
    pruned = tweet.rsplit('cask',1)[-1]
    #if it pulls off more than 33% ignore
    if len(pruned)/float(len(tweet))>(1-max_intro_prop):
        tweet = pruned
        tweet = tweet.replace('keg', ' ')
    
    #split on newlines, then ',', then '.' use first that results in at least 3 tokens
    if len(tweet.split('\n'))>2:
        beers = tweet.split('\n')
        if '.' in beers[-1]:
            beers[-1] = beers[-1].split('.',1)[0]
        if ',' in beers[-1]:
            beers[-1] = beers[-1].split(',',1)[0]
    elif len(tweet.split(','))>2:
        beers = tweet.split(',')
        if '.' in beers[-1]:
            beers[-1] = beers[-1].split('.',1)[0]
    elif len(tweet.split('.'))>2:
        beers = tweet.split('.')
        if ',' in beers[-1]:
            beers[-1] = beers[-1].split(',',1)[0]
    #last ditch effort, use the '@' to split (but need to put it back for the render)
    elif len(tweet.split('@'))>2:
        beers = ['@'+b for b in tweet.split('@')]
        if tweet[0] != '@':
            #special case, first beer might be weird
            beers[0] = beers[0][1:]
    else:
        beers = [tweet]
    
    #if there's an 'and' in the last beer, split on it
    if ' and ' in beers[-1]:
        last_beer = beers.pop(-1)
        beers += last_beer.split(' and ')
    elif '&' in beers[-1]:
        last_beer = beers.pop(-1)
        beers += [b.strip() for b in last_beer.split('&')]
    
    beers = [b.strip().strip('.,?!:;').strip() for b in beers if len(b)>9 and not b.lower() in stops]
    
    for stop_phrase in stops:
        #clean out the hard stops
        for idx, beer in enumerate(beers):
            if stop_phrase in beer:
                beers[idx] = beer.split(stop_phrase, 1)[0]
                
    return beers
    
def is_fresh(beer, days_old=90):
    """looks for the beer string in the redis store
        if it's there, check to see if the date string is more then days_old.
        In the case that it either isn't in the store or the date is older than days_old
        return True, otherwise return False
        in all cases create or update value in the redis store for the beer string to be the current datetime"""
    try:
        last_seen = datetime.strptime(r.get('beer_'+beer), '%Y-%m-%d %H:%M:%S.%f')
    except (ValueError, TypeError):
        last_seen = None
    now = datetime.now()
    if last_seen != None:
        print 'beer_'+beer, 'was last seen ', (now-last_seen).days, 'ago'
    r.set('beer_'+beer, now)
    if last_seen and  (now-last_seen).days < days_old:
        return False
    print 'beer_'+beer, 'is fresh, last seen on', last_seen
    return True
            
        

def tweet_these(api, beers, username, twid, dryrun=False, templates=TEMPLATES, short_tmpls=SHORT_TMPLS):
    """generate tweet about the appearance of beers, 
       citing the name and id they came from if dryrun, 
       just print the tweet, else push it via api
       """
    username = username.decode('utf8')
    bitly = bitly_api.Connection(access_token=BITLY_ACCESS_TOKEN)
    short = bitly.shorten(u'https://twitter.com/{user}/status/{twid}'.format(user=username, twid=twid))
    template = sample(templates, 1)[0]
    
    if len(beers) > 0:
        beers.sort(key=len)
        this_beer = beers.pop(0).decode('utf8').strip()
        text = template.format(username=username, beer=this_beer+u"{beer}")
        
        while len(beers) > 0 and len(text.format(beer=", "+beers[0])) < 110:
            this_beer = beers.pop(0).decode('utf8')
            if len(beers) > 0:
                text = text.format(beer=", "+this_beer+u"{beer}")
            else:
                text = text.format(beer="& "+this_beer)
        if len(beers) > 0:
            text = text.format(beer=u' & more')
        text += u' '+ short[u'url']
    else:
        print "No Beers, but tweeting a link for", twid
        text = sample(short_tmpls,1)[0].format(username=username, link=short[u'url'])
    if len(text) > 140:
        #give up, just tweet the link
        text = sample(short_tmpls,1)[0].format(username=username, link=short[u'url'])
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
    the_tweeter = api.VerifyCredentials().screen_name
    with open(argv[1]) as rh:
        model = cPickle.load(rh)
    cursor = 0
    while True:
        print time.asctime(), "fetching new tweets…"
        for username, twid, tweet in fetch_new_tweets(api, cursor):
            if username == the_tweeter:
                #skip tweets from yourself.
                continue
            if is_otb(model, tweet):
                beers = split_beers(tweet)
                if len(beers) == 0:
                    #if we're here it means flagged as OTB but couldn't get any beer names out ot the tweet
                     tweet_these(api, beers, username, twid, dryrun=dry_run)
                new_beers = [beer for beer in beers if is_fresh(beer)]
                if len(new_beers) > 0:
                    tweet_these(api, beers, username, twid, dryrun=dry_run)
            else:
                if dry_run:
                    print "this is not otb:"
                    print '@'+username+': '+tweet
                    print ''
            if cursor < twid:
                cursor = twid
                    
        time.sleep(900)

if __name__ == '__main__':
    main()