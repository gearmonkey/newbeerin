"""A simple text classifier, 
based on http://web2dot5.wordpress.com/2012/03/21/text-classification-in-python/
"""
import nltk
import itertools
import sys
import random
 
class Classifier(object):
    """classify by looking at a site"""
    def __init__(self, training_set):
        self.training_set = training_set
        self.stopwords = nltk.corpus.stopwords.words("english")
        self.stemmer = nltk.PorterStemmer()
        self.minlength = 2
        self.maxlength = 25
 
    def text_process_entry(self, example):
        site_text = nltk.clean_html(example[0]).lower()
        original_tokens = itertools.chain.from_iterable(nltk.word_tokenize(w) for w in nltk.sent_tokenize(site_text))
        tokens = original_tokens #+ [' '.join(w) for w in nltk.util.ngrams(original_tokens, 2)]
        tokens = [w for w in tokens if not w in self.stopwords]
        tokens = [w for w in tokens if self.minlength < len(w) < self.maxlength]
        #tokens = [self.stemmer.stem(w) for w in tokens]
        return (tokens, example[1])
 
    def text_process_all(self, exampleset):
        processed_training_set = [self.text_process_entry(i) for i in self.training_set]
        processed_training_set = filter(lambda x: len(x[0]) > 0, processed_training_set) # remove empty crawls
        processed_texts = [i[0] for i in processed_training_set]
         
        all_words = nltk.FreqDist(itertools.chain.from_iterable(processed_texts))
        features_to_test = all_words.keys()[:5000]
        self.features_to_test = features_to_test
 
        featuresets = [(self.document_features(d), c) for (d,c) in processed_training_set]
        return featuresets
 
    def document_features(self, document):
        #document_words = set(document)
        features = {}
        for word in self.features_to_test:
            #features['contains(%s)' % word] = (word in document_words)
            features['contains(%s)' % word] = (word in document)
            #features['occurrencies(%s)' % word] = document.count(word) 
            #features['atleast3(%s)' % word] = document.count(word) > 3
        return features
 
    def build_classifier(self, featuresets):
        random.shuffle(featuresets)
        cut_point = len(featuresets) / 5
        train_set, test_set = featuresets[cut_point:], featuresets[:cut_point]
        classifier = nltk.NaiveBayesClassifier.train(train_set)
        return (classifier, test_set)
 
    def run(self):
        featuresets = self.text_process_all(self.training_set)
        classifier, test_set = self.build_classifier(featuresets)
        self.classifier = classifier
        self.test_classifier(classifier, test_set)
 
    def classify(self, text):
        return self.classifier.classify(self.document_features(text))
 
    def test_classifier(self, classifier, test_set):
        print nltk.classify.accuracy(classifier, test_set)
        classifier.show_most_informative_features(45)
 
classes = ('a la carte', 'advertising', 'commission', 'investment', 'pay as you go')
 
training_set = [
    ('we are a bank specialized in dealing with IT companies', classes[3]),
    ('we sell our product at a fixed cost of 10 pounds', classes[0]),
    ('the cost per click is 0.01 dollars but if you get more than 10000 impression the cost will be 0.12', classes[1]),
    ('we take a 1% commission on all sales, overseas sales have an additional charge of 12%', classes[2]),
    ('we charge a 1% on top of your final price.', classes[2]),
    ('we sell our product at 5 pounds, excluding with the variant A which costs an extra of 55 pounds', classes[0]),
    ('we sell our product at 6 pounds, excluding with the variant B which costs 45 pounds', classes[0]),
    ('our commission is normally between 1% and 2%', classes[2]),
    ('impressions on the homepage on sundays are worth 0.01 pounds', classes[1]),
    ('we will show impressions only to users that correspond to certain criteria.', classes[1]),
    ('we manage an hedge fund and we take care of placing investments on behalf of our clients', classes[3]),
    ('we bill only for the amount of api you use. 0.10 per 1000 calls', classes[4]),
    ('running a virtual machine will cost you 0.12 pounds per hour', classes[4]),
    ('we invest in major hedge funds', classes[3]),
    ('we are an international bank, based in all countries of europe', classes[3]),
]
 
test_text = "we are a hedge fund collaborating with many banks in europe"
test_text2 = "we charge a fixed fee on top of our client's sales"
 
if __name__ == '__main__':
    classifier = Classifier(training_set)
    classifier.run()
    print "%s -> classified as: %s" % (test_text, classifier.classify(test_text))
    print "%s -> classified as: %s" % (test_text2, classifier.classify(test_text2))
