New Beer In ____
================

A twitter bot that classifies tweets (to segregate the ones that are 'on the bar' tweets), then a rule-system hack to break the tweets into beers, and tweet the new ones.

To use it yourself, you'd need to train up a classifier. Then associate it with a twitter account.

Uses the friends feed as input, so you can curate the tweets via the followers.



TODO
----
- model can be more robust (this will probably be here forever):
  - better ignoring of sport
- better beer item splitting
  - awareness of what a price or abv token look like (these should be dropped/used to split)
- copy tightening
- rewrite formatting to add as many beers as will fit in broadcast tweet