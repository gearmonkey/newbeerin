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
import HTMLParser

from datetime import datetime
from random import sample

import twitter
import bitly_api
import redis

from titlecase import titlecase

r = redis.StrictRedis(host='localhost', port=6379, db=0)

from credentials import *

TEMPLATES = [u"New beer @{username}! Head there to find {beer}",
             u"Looking for {beer}? Just put on @{username}",
             u"So @{username} just put on {beer}, so you know",
             u"Thirsty? Grab some {beer} @{username}!"
             ]

SHORT_TMPLS = [u"New beers on klaxon, @{username}, can't fit in 140 chars, check: {link}",
               u"Some new beer on @{username}, {link}",
               u".@{username} has new beer on: {link}",
               u"Looks like @{username} just put on a bunch of new beer {link}",
               u"Tasty new beer @{username}: {link}"
               ]

BYPASS_WORDS = ['otb', 'on the bar', 'new on', 'on cask today', 'on keg today']
STOP_WORDS = ['football', 'rugby', 'cricket', 'champions league']

TOKEN_REGEX = r'\W{token}\W'
MIN_BEER_LENGTH = 9

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
        tweets = api.GetHomeTimeline(**kwargs)
    except (twitter.TwitterError, twitter.httplib.BadStatusLine), err:
        print 'twitter error', err, 'trying again in a minute'
        time.sleep(60)
        tweets = api.GetHomeTimeline(**kwargs)
    for tweet in tweets:
        if tweet.GetRetweeted_status() != None:
          #no RTs!
          continue
        yield tweet.user.screen_name, tweet.id, tweet.text
    
    
def is_otb(model, tweet, bypass_words=BYPASS_WORDS, stop_words=STOP_WORDS):
    """run tweet on model to determine if it a probably OTB tweet returning true if it is
    if the tweet contains any stop_words, does not run against the model, returns false
    if the tweet contains any bypass_words, does not run against model and returns true
    stop_words take precendant over bypass words, except the hardcoded '#otb' and '#nowpouring'"""
    tweet = tweet.lower()
    for word in ('#nowpouring','#otb'):
        if re.findall(TOKEN_REGEX.format(token=word), tweet):
            print word
            return True
    for word in stop_words:
        if re.findall(TOKEN_REGEX.format(token=word), tweet):
            print 'explict STOP on tweet'
            return False
    for word in bypass_words:
        if re.findall(TOKEN_REGEX.format(token=word), tweet):
            print 'bypass catch'
            return True
    if int(model.classify(tweet)) == 1:
        print "Model says it's OTB"
        return True
    return False

    
def split_beers(tweet, max_intro_prop=0.49, stops=BYPASS_WORDS):
    """break tweet into composite list of strings representing beers on offer
    currently uses"""
    # print 'incoming:',tweet
    h = HTMLParser.HTMLParser()
    tweet = h.unescape(tweet.lower())
    #remove any urls
    for url in re.finditer(r'(http://t.co/[\w]*)', tweet):
        # print 'pruning', url.group()
        tweet = tweet.replace(url.group(), '').replace('  ', ' ')
    tweet = tweet.replace('...', '') #scrub manual elipse
    # print 'cleaned:',tweet
    #first pruning
    pruned = tweet.split(':',1)[-1]
    # print "proposed to prune to", pruned,
    #if it pulls off more than max_intro_prop ignore
    if len(pruned)/float(len(tweet))>(1-max_intro_prop):
        tweet = pruned
        print "using it"
    print 
        
    pruned = tweet.split(';',1)[-1]
    print "proposed to prune to", pruned,
    #if it pulls off more than max_intro_prop ignore
    if len(pruned)/float(len(tweet))>(1-max_intro_prop):
        tweet = pruned
        print "using it"
    print
        
    pruned = tweet.split(' - ',1)[-1]
    print "proposed to prune to", pruned,
    #if it pulls off more than max_intro_prop ignore
    if len(pruned)/float(len(tweet))>(1-max_intro_prop):
        tweet = pruned
        print "using it"
    print
        
    #the (intro) cask (beer) keg (beer) pattern
    pruned = tweet.split('cask',1)[-1]
    print "proposed to prune to", pruned,
    #if it pulls off more than max_intro_prop ignore
    if len(pruned)/float(len(tweet))>(1-max_intro_prop):
        tweet = pruned
        tweet = tweet.replace('keg', ' ')
        print "using it"
    print
    
    #split on newlines, then ',', then '.' use first that results in at least 2 tokens
    if len(tweet.split('\n'))>2:
        print 'spliting on newline', len(tweet.split('\n')), 'beers'
        beers = tweet.split('\n')
        if '.' in beers[-1]:
            beers[-1] = beers[-1].split('.',1)[0]
        if ',' in beers[-1]:
            beers[-1] = beers[-1].split(',',1)[0]
    elif len(tweet.split(','))>2:
        print 'spliting on ,', len(tweet.split(',')), 'beers'
        beers = tweet.split(',')
        if '.' in beers[-1]:
            beers[-1] = beers[-1].split('.',1)[0]
    
    elif len(tweet.split('.'))>2:
        print 'spliting on .', len(tweet.split('.')), 'beers'
        beers = tweet.split('.')
        if ',' in beers[-1]:
            beers[-1] = beers[-1].split(',',1)[0]
    #last ditch effort, use the '@' to split (but need to put it back for the render)
    elif len(tweet.split('@'))>2:
        print 'spliting on @', len(tweet.split('@')), 'beers'
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
    
    beers = [b.strip().strip('.,?!:;').strip() for b in beers if len(b)>MIN_BEER_LENGTH and not b.lower() in stops]
    
    for stop_phrase in stops:
        #clean out the hard stops
        token_test = re.compile(TOKEN_REGEX.format(token=stop_phrase))
        for idx, beer in enumerate(beers):
            for seperated_token in token_test.findall(beer):
                #take the largest side, if it's larger than MIN_BEER_LENGTH
                this_beer = max(beer.split(seperated_token))
                if len(this_beer) > MIN_BEER_LENGTH:
                    beers[idx] = this_beer
                else:
                    beers.pop(idx)
                
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
    username = username.encode('utf-8').decode('utf-8')
    bitly = bitly_api.Connection(access_token=BITLY_ACCESS_TOKEN)
    short = bitly.shorten(u'https://twitter.com/{user}/status/{twid}'.format(user=username, twid=twid))
    template = sample(templates, 1)[0]
    
    if len(beers) > 0:
        beers.sort(key=len)
        this_beer = titlecase(beers.pop(0).encode('utf-8').decode('utf-8').strip())
        text = template.format(username=username, beer=this_beer+u"{beer}")
        
        while len(beers) > 0 and len(text.format(beer=", "+beers[0])) < 110:
            this_beer = titlecase(beers.pop(0).encode('utf-8').decode('utf-8').strip())
            if len(beers) > 0:
                text = text.format(beer=", "+this_beer+u"{beer}")
            else:
                text = text.format(beer=" & "+this_beer)
        if len(beers) > 0:
            text = text.format(beer=u' & more')
        text = text.replace('{beer}', '')
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
                if the_tweeter.lower() in tweet.lower():
                  tweet = tweet.lower().replace(the_tweeter.lower(), '')
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